#!/usr/bin/env bash
# Installs the local stack into the `hermes` namespace, in dependency order.
# usage: install.sh [--build] [--light]   (--light drops the releases in LIGHT_SKIP,
#                                          uninstalling them if they are already up)
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CHARTS_DIR="$REPO_ROOT/helm-charts"
TAGS_FILE="$SCRIPT_DIR/.image-tags"

BUILD=0
LIGHT=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build) BUILD=1 ;;
        --light) LIGHT=1 ;;
        *) echo "usage: $(basename "$0") [--build] [--light]" >&2; exit 2 ;;
    esac
    shift
done

if [[ "$BUILD" == 1 || ! -s "$TAGS_FILE" ]]; then
    "$SCRIPT_DIR/build-images.sh"
fi

tag_of() {
    local tag
    tag="$(sed -n "s/^$1://p" "$TAGS_FILE")"
    [[ -n "$tag" ]] || { echo "no image tag recorded for '$1' — run build-images.sh" >&2; return 1; }
    echo "$tag"
}

# release[:image] under services/; image defaults to the release name.
# The *-semantic releases embed through the `triton` release below and tokenize
# with the tokenizer in MinIO's `tokenizers` bucket — see
# tools/scripts/tokenizers to put it there.
APPS=(
    candy-lexical
    chat-messages-lexical
    chat-rooms-lexical
    chat-users-lexical
    chief-lexical
    chief-semantic
    cargo-operational-lexical:cargo-lexical
    cargo-my-storage-lexical:cargo-lexical
    cargo-operational-semantic:cargo-semantic
    cargo-my-storage-semantic:cargo-semantic
    dls-console
    labels-api
)

# Dropped by --light — skipped when absent, uninstalled when already installed;
# space-padded so `*" $release "*` matches whole names only.
# keycloak is dls-console's OIDC issuer, so a --light console cannot log in.
LIGHT_SKIP=" grafana keycloak kibana mongo-express "

# `helm dependency update` re-downloads every subchart on every run, so skip the
# fetch when Chart.lock's pins are all present under charts/.
count_deps() {
    awk '/^dependencies:/ { inblock = 1; next }
         /^[^ -]/         { inblock = 0 }
         inblock && /^[[:space:]]*-?[[:space:]]*name:/ { n++ }
         END              { print n + 0 }' "$1"
}

deps_satisfied() {
    local dir="$1" line name="" version=""

    [[ -f "$dir/Chart.lock" ]] || return 1
    [[ "$(count_deps "$dir/Chart.yaml")" == "$(count_deps "$dir/Chart.lock")" ]] || return 1

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        case "$line" in
            *name:*)    name="${line#*name: }" ;;
            *version:*) version="${line#*version: }"
                        [[ -f "$dir/charts/$name-$version.tgz" ]] || return 1
                        name="" ;;
        esac
    done < "$dir/Chart.lock"
}

echo "==> Resolving chart dependencies"
while IFS= read -r chart; do
    dir="$(dirname "$chart")"
    grep -q '^dependencies:' "$chart" || continue
    deps_satisfied "$dir" && continue
    if [[ -f "$dir/Chart.lock" ]]; then
        helm dependency build "$dir" >/dev/null
    else
        helm dependency update "$dir" >/dev/null
    fi
done < <(find "$CHARTS_DIR" -name Chart.yaml)

kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

install() {
    local release="$1" chart="$2"
    shift 2
    if [[ "$LIGHT" == 1 && "$LIGHT_SKIP" == *" $release "* ]]; then
        # Skipping the install is not enough on a cluster that already had a
        # full run: the release stays up holding its memory requests, which is
        # the one thing --light exists to avoid. Uninstalling makes the flag
        # mean the same on a fresh cluster and on a used one.
        if helm status "$release" -n "$NAMESPACE" >/dev/null 2>&1; then
            echo "==> $release (uninstalled, --light)"
            helm uninstall "$release" -n "$NAMESPACE" >/dev/null
        else
            echo "==> $release (skipped, --light)"
        fi
        return 0
    fi
    echo "==> $release"
    helm upgrade --install "$release" "$CHARTS_DIR/$chart" -n "$NAMESPACE" --timeout 15m "$@"
}

# install, with the recorded tag for $3 wired into image.tag.
install_tagged() {
    local release="$1" chart="$2" tag
    tag="$(tag_of "$3")"
    shift 3
    install "$release" "$chart" --set "image.tag=$tag" "$@"
}

# These releases don't depend on each other, so installing them one at a time
# means the run costs the *sum* of their readiness waits instead of the longest
# one. install_bg starts a release in the background with its output buffered
# (parallel helm logs would otherwise interleave into nonsense); wait_batch
# collects them in launch order, replays each log, and fails if any failed.
LOG_DIR="$(mktemp -d)"
trap 'rm -rf "$LOG_DIR"' EXIT

BG_PIDS=()
BG_NAMES=()

install_bg() {
    local release="$1"
    install "$@" >"$LOG_DIR/$release.log" 2>&1 &
    BG_PIDS+=("$!")
    BG_NAMES+=("$release")
}

install_tagged_bg() {
    local release="$1"
    install_tagged "$@" >"$LOG_DIR/$release.log" 2>&1 &
    BG_PIDS+=("$!")
    BG_NAMES+=("$release")
}

wait_batch() {
    local i failed=()
    [[ ${#BG_PIDS[@]} -gt 0 ]] || return 0
    for i in "${!BG_PIDS[@]}"; do
        if ! wait "${BG_PIDS[$i]}"; then
            failed+=("${BG_NAMES[$i]}")
        fi
        cat "$LOG_DIR/${BG_NAMES[$i]}.log"
    done
    BG_PIDS=()
    BG_NAMES=()
    [[ ${#failed[@]} -eq 0 ]] || { echo "failed: ${failed[*]}" >&2; return 1; }
}

# Everything the pipeline itself talks to. --wait here, since the jobs, the
# consumers and the collector below all need these actually serving.
echo "==> Backing services (parallel)"
install_bg kafka         local-infra/backing/kafka/kafka           --wait
install_bg minio         local-infra/backing/minio                 --wait
install_bg elasticsearch local-infra/backing/elastic/elasticsearch --wait
install_bg mongodb       local-infra/backing/mongodb/mongodb       --wait
install_bg tika          local-infra/backing/tika                  --wait
install_bg keycloak      local-infra/backing/keycloak              --wait
install_bg chief-api     local-infra/backing/chief-api             --wait
install_tagged_bg triton local-infra/backing/triton mock-triton    --wait
install_bg mimir         local-infra/observability/mimir           --wait
install_bg loki          local-infra/observability/loki            --wait
install_bg tempo         local-infra/observability/tempo           --wait
install_bg otel-operator local-infra/observability/otel-operator   --wait
wait_batch

# Consoles: nothing in the stack blocks on them, and each retries its own
# backend on its own, so no --wait — the install returns as soon as Kubernetes
# has accepted the manifests and the pods come up in the background.
echo "==> Consoles (parallel, no readiness wait)"
install_bg kafka-ui      local-infra/backing/kafka/kafka-ui
install_bg kibana        local-infra/backing/elastic/kibana
install_bg mongo-express local-infra/backing/mongodb/mongo-express
install_bg headlamp      local-infra/tooling/headlamp
install_bg grafana       local-infra/observability/grafana
wait_batch

# Helm regenerates the webhook cert without changing the Deployment, so the
# running pod keeps serving the old one and collector creation fails on x509.
echo "==> Restarting otel-operator (reload regenerated webhook cert)"
kubectl -n "$NAMESPACE" rollout restart deploy/otel-operator
kubectl -n "$NAMESPACE" rollout status deploy/otel-operator --timeout=180s

# The webhook endpoint can lag the pod's readiness by a few seconds.
for attempt in 1 2 3 4 5; do
    install otel-collector local-infra/observability/otel-collector && break
    [[ "$attempt" == 5 ]] && { echo "otel-collector install failed after 5 attempts" >&2; exit 1; }
    echo "    webhook not ready yet, retrying ($attempt/5)..."
    sleep 5
done

# Jobs before consumers: no node room for a job pod once the consumers are up,
# and a consumer whose topic does not exist yet dies on UNKNOWN_TOPIC_OR_PART.
install_tagged index-definitions local-infra/tooling/index-definitions index-definitions
install_tagged demo-producer     local-infra/tooling/demo-producer     demo-producer
for entry in "${APPS[@]}"; do
    install_tagged "${entry%%:*}" "services/${entry%%:*}" "${entry##*:}"
done

echo
echo "Done. UI access: tools/scripts/sandbox/port-forward.sh"
