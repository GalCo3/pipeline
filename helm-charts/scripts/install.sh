#!/usr/bin/env bash
# Installs the whole local stack into the `hermes` namespace, in dependency order.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
CHARTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$CHARTS_DIR/.." && pwd)"

# A fresh tag per build: Kubernetes caches images by tag, so rebuilding
# :local would leave the old bits running.
IMAGE_TAG="${IMAGE_TAG:-dev-$(date +%Y%m%d%H%M%S)}"

echo "==> Building images ($IMAGE_TAG)"
docker build -f "$REPO_ROOT/Dockerfile" --build-arg SERVICE=cargo-lexical -t "cargo-lexical:$IMAGE_TAG" "$REPO_ROOT"
docker build -t "demo-producer:$IMAGE_TAG" "$REPO_ROOT/demo-producer"

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
    echo "==> $release"
    helm upgrade --install "$release" "$CHARTS_DIR/$chart" -n "$NAMESPACE" --timeout 15m "$@"
}

install kafka         utils/infra/kafka/kafka                --wait
install minio         utils/infra/minio                      --wait
install elasticsearch utils/infra/elastic/elasticsearch      --wait
install mongodb       utils/infra/mongodb/mongodb            --wait
install tika          utils/infra/tika                       --wait
install kafka-ui      utils/infra/kafka/kafka-ui             --wait
install kibana        utils/infra/elastic/kibana             --wait
install mongo-express utils/infra/mongodb/mongo-express      --wait
install headlamp      utils/dev/headlamp                     --wait
# Telemetry backends before the collector, which starts pushing as soon as it is up.
install mimir         utils/observability/mimir              --wait
install loki          utils/observability/loki               --wait
install tempo         utils/observability/tempo              --wait
install grafana       utils/observability/grafana            --wait
install otel-operator utils/observability/otel-operator      --wait
install otel-collector utils/observability/otel-collector
install es-index      utils/dev/es-index
install cargo-lexical         services/cargo-lexical        --set "image.tag=$IMAGE_TAG"
install demo-producer utils/dev/demo-producer --set "image.tag=$IMAGE_TAG"

echo
echo "Done. UI access: helm-charts/scripts/port-forward.sh"
