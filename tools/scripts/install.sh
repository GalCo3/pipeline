#!/usr/bin/env bash
# Installs the whole local stack into the `hermes` namespace, in dependency order.
set -euo pipefail

NAMESPACE="${NAMESPACE:-hermes}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHARTS_DIR="$REPO_ROOT/helm-charts"

# Docker Desktop's "kind" Kubernetes mode runs its own containerd, isolated
# from the Docker Engine `docker build` uses — a locally built image is
# invisible to the cluster (ImagePullBackOff, kubelet tries Docker Hub)
# until it is explicitly imported. This throwaway, privileged pod chroots
# into the node's filesystem so images can be piped straight into its
# containerd via `ctr images import`, no registry involved. Best-effort: on
# a setup where the cluster already shares the Docker image store (or this
# isn't a single accessible local node), the pod just never comes up and we
# fall back to the old behaviour instead of failing the whole install.
LOADER_POD="kind-image-loader"
LOAD_IMAGES=1

ensure_image_loader() {
    kubectl get pod "$LOADER_POD" >/dev/null 2>&1 && return 0

    kubectl apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $LOADER_POD
spec:
  restartPolicy: Never
  hostPID: true
  tolerations:
    - operator: Exists
  containers:
    - name: loader
      image: alpine:3.20
      command: ["sleep", "infinity"]
      securityContext:
        privileged: true
      volumeMounts:
        - name: host-root
          mountPath: /host
  volumes:
    - name: host-root
      hostPath:
        path: /
EOF
    kubectl wait --for=condition=Ready "pod/$LOADER_POD" --timeout=60s >/dev/null
}

# Streams "$name:$tag" straight from the Docker Engine into the cluster
# node's containerd. No-op (and non-fatal) once the loader can't be set up.
load_image() {
    [[ "$LOAD_IMAGES" == 1 ]] || return 0

    if ! ensure_image_loader; then
        echo "    (skipping cluster image load: could not set up loader pod)" >&2
        LOAD_IMAGES=0
        return 0
    fi
    docker save "$1:$2" | kubectl exec -i "$LOADER_POD" -- \
        chroot /host ctr -n k8s.io images import - >/dev/null
}

# Builds "$name" (remaining args passed straight to `docker build`) into a
# stable ":local" tag, then re-tags it by its own content-addressed image ID
# and prints that ID. Docker's build cache already makes an unchanged build
# a no-op; re-tagging by ID means the *tag* we hand to Helm also only changes
# when the image's content actually does. A fresh timestamp tag every run
# would force Kubernetes to restart every pod regardless of whether anything
# changed — this way only the pods whose image actually changed get bounced.
build_image() {
    local name="$1"
    shift
    docker build -t "$name:local" "$@" >/dev/null
    local id
    id="$(docker image inspect --format '{{.Id}}' "$name:local")"
    id="${id#sha256:}"
    id="${id:0:12}"
    docker tag "$name:local" "$name:$id"
    load_image "$name" "$id"
    echo "$id"
}

# Every service that has both a chart under services/ and a consumer image.
SERVICES=(candy-reports-lexical cargo-lexical chat-lexical chat-rooms-lexical chat-users-lexical chief-lexical)

echo "==> Building images"
SERVICE_TAGS=()
for service in "${SERVICES[@]}"; do
    tag="$(build_image "$service" -f "$REPO_ROOT/apps/Dockerfile" --build-arg GROUP=services \
        --build-arg "NAME=$service" "$REPO_ROOT")"
    echo "    $service -> $tag"
    SERVICE_TAGS+=("$tag")
done
DEMO_PRODUCER_TAG="$(build_image demo-producer "$REPO_ROOT/tools/demo-producer")"
echo "    demo-producer -> $DEMO_PRODUCER_TAG"
INDEX_DEFINITIONS_TAG="$(build_image index-definitions -f "$REPO_ROOT/apps/Dockerfile" --build-arg GROUP=jobs \
    --build-arg NAME=index-definitions "$REPO_ROOT")"
echo "    index-definitions -> $INDEX_DEFINITIONS_TAG"

kubectl delete pod "$LOADER_POD" --ignore-not-found >/dev/null

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

install kafka         local-infra/backing/kafka/kafka                --wait
install minio         local-infra/backing/minio                      --wait
install elasticsearch local-infra/backing/elastic/elasticsearch      --wait
install mongodb       local-infra/backing/mongodb/mongodb            --wait
install tika          local-infra/backing/tika                       --wait
install kafka-ui      local-infra/backing/kafka/kafka-ui             --wait
install kibana        local-infra/backing/elastic/kibana             --wait
install mongo-express local-infra/backing/mongodb/mongo-express      --wait
# chief-lexical enriches from this; see local-infra/backing/chief-api for what it stands in for.
install chief-api     local-infra/backing/chief-api                  --wait
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
for i in "${!SERVICES[@]}"; do
    install "${SERVICES[$i]}" "services/${SERVICES[$i]}" --set "image.tag=${SERVICE_TAGS[$i]}"
done

echo
echo "Done. UI access: tools/scripts/port-forward.sh"
