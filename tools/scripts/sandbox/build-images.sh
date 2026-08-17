#!/usr/bin/env bash
# Builds every image the local stack needs and records their content-addressed
# tags in tools/scripts/.image-tags for install.sh to consume without having
# to rebuild. Run this on its own whenever code changes; install.sh only
# rebuilds when asked (see its --build flag).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TAGS_FILE="$SCRIPT_DIR/.image-tags"
TAGS_FILE_TMP="$TAGS_FILE.tmp"
trap 'rm -f "$TAGS_FILE_TMP"' EXIT

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

# Every service with a consumer image. cargo-lexical/cargo-semantic no longer
# have a chart of their own — cargo-{operational,my-storage}-{lexical,semantic}
# are the deployed consumers, each running one of these images under its own
# topic/index.
IMAGE_SOURCES=(candy-reports-lexical cargo-lexical cargo-semantic chat-messages-lexical chat-rooms-lexical chat-users-lexical chief-lexical chief-semantic)

# Node apps: one image, one chart named after the directory. dls-console serves
# both its UI and its API, so it is a single image like any consumer.
NODE_APPS=(dls-console)

echo "==> Building images"
> "$TAGS_FILE_TMP"
for service in "${IMAGE_SOURCES[@]}"; do
    # Same rule as CI (tools/ci/find_build.py): an app that ships its own
    # Dockerfile overrides the shared one, and the context is the repo root
    # either way so the build can reach libs/ and uv.lock.
    dockerfile="$REPO_ROOT/apps/services/$service/Dockerfile"
    [[ -f "$dockerfile" ]] || dockerfile="$REPO_ROOT/apps/Dockerfile"

    tag="$(build_image "$service" -f "$dockerfile" --build-arg GROUP=services \
        --build-arg "NAME=$service" "$REPO_ROOT")"
    echo "    $service -> $tag"
    echo "$service:$tag" >> "$TAGS_FILE_TMP"
done
# Repo root context again — the Dockerfile spells out its own subpath, and it
# takes no GROUP/NAME build args.
for app in "${NODE_APPS[@]}"; do
    tag="$(build_image "$app" -f "$REPO_ROOT/apps/services/$app/Dockerfile" "$REPO_ROOT")"
    echo "    $app -> $tag"
    echo "$app:$tag" >> "$TAGS_FILE_TMP"
done
DEMO_PRODUCER_TAG="$(build_image demo-producer "$REPO_ROOT/tools/demo-producer")"
echo "    demo-producer -> $DEMO_PRODUCER_TAG"
echo "demo-producer:$DEMO_PRODUCER_TAG" >> "$TAGS_FILE_TMP"
# Stands in for the real Triton the semantic path embeds against. Its chart is
# local-infra/backing/triton, and the image is named for what it is rather than
# what it impersonates — only the Service carries the name `triton`.
MOCK_TRITON_TAG="$(build_image mock-triton "$REPO_ROOT/tools/mock-triton")"
echo "    mock-triton -> $MOCK_TRITON_TAG"
echo "mock-triton:$MOCK_TRITON_TAG" >> "$TAGS_FILE_TMP"
INDEX_DEFINITIONS_TAG="$(build_image index-definitions -f "$REPO_ROOT/apps/Dockerfile" --build-arg GROUP=jobs \
    --build-arg NAME=index-definitions "$REPO_ROOT")"
echo "    index-definitions -> $INDEX_DEFINITIONS_TAG"
echo "index-definitions:$INDEX_DEFINITIONS_TAG" >> "$TAGS_FILE_TMP"

# Only replace the real tags file once every build above has succeeded, so a
# failure partway through never leaves install.sh reading a stale/empty file.
mv "$TAGS_FILE_TMP" "$TAGS_FILE"

kubectl delete pod "$LOADER_POD" --ignore-not-found >/dev/null

echo "Done. Tags recorded in $TAGS_FILE"
