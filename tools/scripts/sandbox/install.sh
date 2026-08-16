#!/usr/bin/env bash
# Installs the whole local stack into the `hermes` namespace, in dependency order.
# Image tags come from .image-tags beside this script, written by build-images.sh —
# run that script first (or pass --build here) whenever image code changes.
# Rebuilding on every install is unnecessary: build_image already tags by
# content ID, so nothing downstream needs re-running just to install again.
#
# --light leaves out the releases in LIGHT_SKIP below, for a smaller stack on a
# machine that cannot hold the full one.
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

# name:tag lines kept as a flat array, not an associative one: macOS ships
# bash 3.2, where `declare -A` is a syntax error. A handful of images makes a
# linear lookup free.
IMAGE_TAGS=()
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -n "$line" ]] && IMAGE_TAGS+=("$line")
done < "$TAGS_FILE"

# Prints the recorded tag for an image name, and fails loudly rather than
# expanding to an empty --set when the tags file has no line for it.
tag_of() {
    local pair
    # `${a[@]}` on an empty array is an unbound-variable error under bash 3.2's
    # `set -u`, hence the count guard.
    [[ ${#IMAGE_TAGS[@]} -gt 0 ]] || { echo "$TAGS_FILE is empty — run build-images.sh" >&2; return 1; }
    for pair in "${IMAGE_TAGS[@]}"; do
        [[ "$pair" == "$1:"* ]] && { echo "${pair#*:}"; return 0; }
    done
    echo "no image tag recorded for '$1' — run build-images.sh" >&2
    return 1
}

DEMO_PRODUCER_TAG="$(tag_of demo-producer)"
INDEX_DEFINITIONS_TAG="$(tag_of index-definitions)"
MOCK_TRITON_TAG="$(tag_of mock-triton)"

# Every release under services/, as `release[:image]`. The image defaults to the
# release name; the cargo pair spell theirs out because they are the same
# cargo-lexical consumer deployed twice under different topics and indices, so
# neither has an image of its own. dls-console is in here too: it serves its UI
# and its API from one image, which makes it a release like any other.
APPS=(
    candy-lexical
    chat-messages-lexical
    chat-rooms-lexical
    chat-users-lexical
    chief-lexical
    cargo-operational-lexical:cargo-lexical
    cargo-my-storage-lexical:cargo-lexical
    dls-console
)

# --light drops these releases. All four are read-only views onto something
# else in the stack, except keycloak, which is dls-console's OIDC issuer: a
# --light stack still serves the console UI, but signing in fails.
LIGHT_SKIP=(grafana keycloak kibana mongo-express)

skipped() {
    local release
    [[ "$LIGHT" == 1 ]] || return 1
    for release in "${LIGHT_SKIP[@]}"; do
        [[ "$release" == "$1" ]] && return 0
    done
    return 1
}

echo "==> Resolving chart dependencies"

# `helm dependency update` re-resolves and re-downloads every subchart on
# every run. Chart.lock already pins them, so skip the fetch when each locked
# dependency is present under charts/. Timestamps are useless for this: a
# fresh clone stamps Chart.yaml and Chart.lock identically, so compare content.

# Number of entries under a `dependencies:` block.
count_deps() {
    awk '/^dependencies:/ { inblock = 1; next }
         /^[^ -]/         { inblock = 0 }
         inblock && /^[[:space:]]*-?[[:space:]]*name:/ { n++ }
         END              { print n + 0 }' "$1"
}

# True when every dependency in Chart.lock has its tarball on disk, and the
# lock still covers everything Chart.yaml declares.
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

resolve_deps() {
    local dir="$1"

    grep -q '^dependencies:' "$dir/Chart.yaml" || return 0
    deps_satisfied "$dir" && return 0

    # A lock exists but is unsatisfied: honour its pins rather than re-resolving.
    if [[ -f "$dir/Chart.lock" ]]; then
        helm dependency build "$dir" >/dev/null
    else
        helm dependency update "$dir" >/dev/null
    fi
}

while IFS= read -r chart; do
    resolve_deps "$(dirname "$chart")"
done < <(find "$CHARTS_DIR" -name Chart.yaml)

kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

install() {
    local release="$1" chart="$2"
    shift 2
    if skipped "$release"; then
        echo "==> $release (skipped, --light)"
        return 0
    fi
    echo "==> $release"
    helm upgrade --install "$release" "$CHARTS_DIR/$chart" -n "$NAMESPACE" --timeout 15m "$@"
}

install kafka         local-infra/backing/kafka/kafka                --wait
install minio         local-infra/backing/minio                      --wait
install elasticsearch local-infra/backing/elastic/elasticsearch      --wait
install mongodb       local-infra/backing/mongodb/mongodb            --wait
install tika          local-infra/backing/tika                       --wait
# OIDC issuer for dls-console; nothing else in the stack provides one.
install keycloak      local-infra/backing/keycloak                   --wait
install kafka-ui      local-infra/backing/kafka/kafka-ui             --wait
install kibana        local-infra/backing/elastic/kibana             --wait
install mongo-express local-infra/backing/mongodb/mongo-express      --wait
# chief-lexical enriches from this; see local-infra/backing/chief-api for what it stands in for.
install chief-api     local-infra/backing/chief-api                  --wait
# The semantic path embeds against this; see local-infra/backing/triton for what
# it stands in for. Release and Service are named `triton`, the image is not.
install triton        local-infra/backing/triton                     --wait --set "image.tag=$MOCK_TRITON_TAG"
install headlamp      local-infra/tooling/headlamp                   --wait
# Telemetry backends before the collector, which starts pushing as soon as it is up.
install mimir         local-infra/observability/mimir                --wait
install loki          local-infra/observability/loki                 --wait
install tempo         local-infra/observability/tempo                --wait
install grafana       local-infra/observability/grafana              --wait
install otel-operator local-infra/observability/otel-operator        --wait

# The operator's webhook serving cert is regenerated by helm on every upgrade,
# but nothing on the Deployment changes, so the running pod keeps serving the
# previous cert while the webhook configs already carry the new CA. Creating an
# OpenTelemetryCollector then fails the admission webhook with
# "x509: certificate signed by unknown authority". Restarting the operator makes
# it load the cert helm just wrote.
echo "==> Restarting otel-operator (reload regenerated webhook cert)"
kubectl -n "$NAMESPACE" rollout restart deploy/otel-operator
kubectl -n "$NAMESPACE" rollout status deploy/otel-operator --timeout=180s

# The webhook Service's endpoint can lag the pod's readiness by a few
# seconds — kube-proxy hasn't synced yet even though rollout status just
# reported Ready — so the very next admission call here occasionally times
# out with "context deadline exceeded". That failure is transient, but
# `helm upgrade --install` leaves the release stuck in state "failed" and
# set -e would otherwise abort before the jobs and consumers install at all.
for attempt in 1 2 3 4 5; do
    if install otel-collector local-infra/observability/otel-collector; then
        break
    fi
    [[ "$attempt" == 5 ]] && { echo "otel-collector install failed after 5 attempts" >&2; exit 1; }
    echo "    webhook not ready yet, retrying ($attempt/5)..."
    sleep 5
done

# Both jobs run before the consumers, which is also the order populate.sh keeps:
# the consumers' memory requests leave the single dev node with no room for a
# job pod to schedule into, and a consumer subscribed to a topic that does not
# exist yet dies on UNKNOWN_TOPIC_OR_PART — the topics are auto-created by the
# producer. Every service reads with auto.offset.reset=earliest, so starting
# after the produce still consumes the whole backlog.
install index-definitions local-infra/tooling/index-definitions --set "image.tag=$INDEX_DEFINITIONS_TAG"
install demo-producer     local-infra/tooling/demo-producer     --set "image.tag=$DEMO_PRODUCER_TAG"
for entry in "${APPS[@]}"; do
    release="${entry%%:*}"
    # Assigned before the install so a missing tag aborts here: tag_of's failure
    # inside an argument would only expand to an empty --set.
    tag="$(tag_of "${entry##*:}")"
    install "$release" "services/$release" --set "image.tag=$tag"
done

echo
echo "Done. UI access: tools/scripts/sandbox/port-forward.sh"
