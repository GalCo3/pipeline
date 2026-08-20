#!/bin/bash
set -euo pipefail

REGISTRY_PREFIX="registry.gitlab.com/textfactory/hermes/pipeline"
PLATFORM="${PLATFORM:-linux/amd64}"
OUT_DIR="${OUT_DIR:-.}"
ZSTD_OPTS="${ZSTD_OPTS:--19 --long=31 -T0}"

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <bundle-name> <image>:<tag> [<image>:<tag> ...]" >&2
  exit 1
fi

BUNDLE_NAME="$1"
shift

docker login registry.gitlab.com

WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
MERGED="$WORK_DIR/merged"
trap 'rm -rf "$WORK_DIR"' EXIT
mkdir -p "$OUT_DIR"

for FULL_IMAGE in "$@"; do
  IMAGE_TAG_PAIR="${FULL_IMAGE##*/}"
  IMAGE_NAME="${IMAGE_TAG_PAIR%:*}"
  TAG="${IMAGE_TAG_PAIR#*:}"
  IMAGE_REF="$REGISTRY_PREFIX/$IMAGE_NAME:$TAG"

  echo "=== Exporting $IMAGE_NAME:$TAG ($PLATFORM) ==="
  skopeo copy \
    --override-os "${PLATFORM%%/*}" --override-arch "${PLATFORM##*/}" \
    "docker://$IMAGE_REF" "oci:$MERGED:$IMAGE_NAME-$TAG"
done

BUNDLE="$OUT_DIR/$BUNDLE_NAME.tar.zst"
rm -f "$BUNDLE"
# shellcheck disable=SC2086
tar -cf - -C "$MERGED" . | zstd $ZSTD_OPTS -q -o "$BUNDLE"

echo "=== Wrote $BUNDLE ($(du -h "$BUNDLE" | cut -f1)) ==="
jq -r '.manifests[].annotations["org.opencontainers.image.ref.name"] | "      " + .' "$MERGED/index.json"
echo "=== Load with: zstd -dc --long=31 $(basename "$BUNDLE") | docker load ==="
