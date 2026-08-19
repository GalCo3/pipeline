#!/bin/bash
set -euo pipefail

# Exports images from the pipeline registry into a single .tar.zst, loadable with:
#   zstd -dc --long=31 <bundle>.tar.zst | docker load
#
# Usage: ./save-bundle.sh <bundle-name> <image>:<tag> [<image>:<tag> ...]
#
# Env: PLATFORM (linux/amd64), OUT_DIR (.), WORK_DIR (mktemp -d),
#      ZSTD_OPTS (-19 --long=31 -T0)
#
# Layers are exported uncompressed, so the bundle does not carry the registry's
# manifest digest. Merging into one OCI layout dedups shared base blobs, and
# zstd's 2GB match window collapses the near-identical per-service .venv layers.

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
META="$WORK_DIR/meta"
trap 'rm -rf "$WORK_DIR"' EXIT

mkdir -p "$MERGED/blobs/sha256" "$META" "$OUT_DIR"

for FULL_IMAGE in "$@"; do
  IMAGE_TAG_PAIR="${FULL_IMAGE##*/}"
  IMAGE_NAME="${IMAGE_TAG_PAIR%:*}"
  TAG="${IMAGE_TAG_PAIR#*:}"
  IMAGE_REF="$REGISTRY_PREFIX/$IMAGE_NAME:$TAG"
  NAME="$IMAGE_NAME-$TAG"

  echo "=== Exporting $IMAGE_NAME:$TAG ($PLATFORM) ==="

  EXTRACTED="$WORK_DIR/extracted"
  rm -rf "$EXTRACTED"
  mkdir -p "$EXTRACTED"
  TMP_TAR="$WORK_DIR/image.tar"

  # buildx, not `docker save`: with the containerd image store `docker save`
  # can emit a metadata-only tar. $EXTRACTED doubles as an empty build context.
  printf 'FROM %s\n' "$IMAGE_REF" | docker buildx build \
    --platform "$PLATFORM" \
    --provenance=false \
    -t "$IMAGE_REF" \
    --output "type=docker,dest=$TMP_TAR,compression=uncompressed,force-compression=true" \
    -f - "$EXTRACTED"

  tar -xf "$TMP_TAR" -C "$EXTRACTED"
  rm -f "$TMP_TAR"

  # -n keeps the first copy; identical digest means identical bytes.
  cp -n "$EXTRACTED"/blobs/sha256/* "$MERGED/blobs/sha256/" 2>/dev/null || true
  cp "$EXTRACTED/index.json" "$META/$NAME.index.json"
  cp "$EXTRACTED/manifest.json" "$META/$NAME.manifest.json"
  rm -rf "$EXTRACTED"
done

jq -s '{schemaVersion: 2,
        mediaType: "application/vnd.oci.image.index.v1+json",
        manifests: (map(.manifests) | add)}' \
  "$META"/*.index.json > "$MERGED/index.json"
jq -s 'add' "$META"/*.manifest.json > "$MERGED/manifest.json"
printf '{"imageLayoutVersion":"1.0.0"}' > "$MERGED/oci-layout"

BUNDLE="$OUT_DIR/$BUNDLE_NAME.tar.zst"
rm -f "$BUNDLE"
# shellcheck disable=SC2086
tar -cf - -C "$MERGED" . | zstd $ZSTD_OPTS -q -o "$BUNDLE"

echo "=== Wrote $BUNDLE ($(du -h "$BUNDLE" | cut -f1)) ==="
jq -r '.manifests[].annotations["io.containerd.image.name"] | "      " + .' "$MERGED/index.json"
echo "=== Load with: zstd -dc --long=31 $(basename "$BUNDLE") | docker load ==="
