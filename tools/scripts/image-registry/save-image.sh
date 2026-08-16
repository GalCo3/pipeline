#!/bin/bash
set -euo pipefail

# Saves images from the pipeline registry as .tar.xz archives loadable with:
#   xz -dc <file>.tar.xz | docker load
#
# Usage: ./save-image.sh dls-console:394f705e [more-image:tag ...]
#        (a full registry reference is accepted too; only name:tag is used)
#
# Env:
#   PLATFORM   image platform to export      (default: linux/amd64)
#   OUT_DIR    where archives are written    (default: current directory)
#   XZ_OPTS    xz flags                      (default: -T0 -9e)
#
# Note: layers are exported uncompressed so xz compresses the raw bytes
# (~44MB vs ~69MB for a gzip-layer archive). The archive therefore does not
# carry the registry's manifest digest — the filesystem and config are
# identical, but a digest/signature check against the registry will not match.
#
# The export goes through `docker buildx build` rather than `docker save`:
# with Docker Desktop's containerd image store, `docker save` can emit a
# metadata-only tar with no layer blobs.

REGISTRY_PREFIX="registry.gitlab.com/textfactory/hermes/pipeline"
PLATFORM="${PLATFORM:-linux/amd64}"
OUT_DIR="${OUT_DIR:-.}"
XZ_OPTS="${XZ_OPTS:--T0 -9e}"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <image>:<tag> [<image>:<tag> ...]" >&2
  exit 1
fi

docker login registry.gitlab.com

mkdir -p "$OUT_DIR"

for FULL_IMAGE in "$@"; do
  IMAGE_TAG_PAIR="${FULL_IMAGE##*/}"
  IMAGE_NAME="${IMAGE_TAG_PAIR%:*}"
  TAG="${IMAGE_TAG_PAIR#*:}"
  IMAGE_REF="$REGISTRY_PREFIX/$IMAGE_NAME:$TAG"
  ARCHIVE="$OUT_DIR/$IMAGE_NAME-$TAG.tar.xz"

  echo "=== Processing $IMAGE_NAME:$TAG ($PLATFORM) ==="

  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  TMP_TAR="$TMP_DIR/image.tar"

  # $TMP_DIR doubles as an empty build context — nothing is copied in.
  printf 'FROM %s\n' "$IMAGE_REF" | docker buildx build \
    --platform "$PLATFORM" \
    --provenance=false \
    -t "$IMAGE_REF" \
    --output "type=docker,dest=$TMP_TAR,compression=uncompressed,force-compression=true" \
    -f - "$TMP_DIR"

  rm -f "$ARCHIVE"
  # shellcheck disable=SC2086
  xz $XZ_OPTS -c "$TMP_TAR" > "$ARCHIVE"
  rm -rf "$TMP_DIR"

  echo "=== Wrote $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1)) ==="
done
