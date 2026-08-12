#!/usr/bin/env bash
# Builds every image the local stack needs and records their content-addressed
# tags in tools/scripts/.image-tags for install.sh to consume without having
# to rebuild. Run this on its own whenever code changes; install.sh only
# rebuilds when asked (see its --build flag).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TAGS_FILE="$REPO_ROOT/tools/scripts/.image-tags"
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

# Every service with a consumer image. cargo-lexical no longer has a chart of
# its own — cargo-operational-lexical and cargo-my-storage-lexical are the
# deployed consumers, both running this same image under their own topic/index.
IMAGE_SOURCES=(candy-reports-lexical cargo-lexical chat-messages-lexical chat-rooms-lexical chat-users-lexical chief-lexical)

echo "==> Building images"
> "$TAGS_FILE_TMP"
for service in "${IMAGE_SOURCES[@]}"; do
    tag="$(build_image "$service" -f "$REPO_ROOT/apps/Dockerfile" --build-arg GROUP=services \
        --build-arg "NAME=$service" "$REPO_ROOT")"
    echo "    $service -> $tag"
    echo "$service:$tag" >> "$TAGS_FILE_TMP"
done
DEMO_PRODUCER_TAG="$(build_image demo-producer "$REPO_ROOT/tools/demo-producer")"
echo "    demo-producer -> $DEMO_PRODUCER_TAG"
echo "demo-producer:$DEMO_PRODUCER_TAG" >> "$TAGS_FILE_TMP"
INDEX_DEFINITIONS_TAG="$(build_image index-definitions -f "$REPO_ROOT/apps/Dockerfile" --build-arg GROUP=jobs \
    --build-arg NAME=index-definitions "$REPO_ROOT")"
echo "    index-definitions -> $INDEX_DEFINITIONS_TAG"
echo "index-definitions:$INDEX_DEFINITIONS_TAG" >> "$TAGS_FILE_TMP"

# Only replace the real tags file once every build above has succeeded, so a
# failure partway through never leaves install.sh reading a stale/empty file.
mv "$TAGS_FILE_TMP" "$TAGS_FILE"

kubectl delete pod "$LOADER_POD" --ignore-not-found >/dev/null

echo "Done. Tags recorded in $TAGS_FILE"
