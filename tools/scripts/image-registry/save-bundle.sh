#!/usr/bin/env bash
set -euo pipefail

# Exports images from the pipeline registry into a single .tar.zst, loadable with:
#   zstd -dc --long=31 <bundle>.tar.zst | docker load
#
# Usage: ./save-bundle.sh                            # interactive picker
#        ./save-bundle.sh <image>:<tag> [...]        # explicit images
#
# With no arguments it lists every repository in the pipeline registry with its
# current build -- the immutable commit-SHA tag `latest` points at, never
# `latest` itself -- and asks which ones to bundle.
#
# Env: BUNDLE_NAME (bundle), PLATFORM (linux/amd64), OUT_DIR (.),
#      WORK_DIR (mktemp -d), ZSTD_OPTS (-19 --long=31 -T0),
#      GITLAB_TOKEN (only needed when `glab` is not installed)
#
# Layers are exported uncompressed, so the bundle does not carry the registry's
# manifest digest. Merging into one OCI layout dedups shared base blobs, and
# zstd's 2GB match window collapses the near-identical per-service .venv layers.

REGISTRY_PREFIX="registry.gitlab.com/textfactory/hermes/pipeline"
PROJECT_PATH="textfactory/hermes/pipeline"
PLATFORM="${PLATFORM:-linux/amd64}"
OUT_DIR="${OUT_DIR:-.}"
ZSTD_OPTS="${ZSTD_OPTS:--19 --long=31 -T0}"
BUNDLE_NAME="${BUNDLE_NAME:-bundle}"

GITLAB_API="https://gitlab.com/api/v4"

# `glab` carries its own credentials; without it fall back to GITLAB_TOKEN.
api_get() {
  if command -v glab >/dev/null 2>&1; then
    glab api "$1"
  else
    curl -fsSL --header "PRIVATE-TOKEN: $GITLAB_TOKEN" "$GITLAB_API/$1"
  fi
}

api_graphql() {
  if command -v glab >/dev/null 2>&1; then
    glab api graphql -f query="$1"
  else
    jq -n --arg q "$1" '{query: $q}' |
      curl -fsSL --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        --header "Content-Type: application/json" \
        --data @- "$GITLAB_API/graphql"
  fi
}

require_api_auth() {
  command -v glab >/dev/null 2>&1 && return 0
  if [ -z "${GITLAB_TOKEN:-}" ]; then
    echo "interactive mode needs \`glab\` on PATH or GITLAB_TOKEN set" >&2
    exit 1
  fi
}

# The tag to bundle is the commit-SHA tag sharing `latest`'s digest: the same
# image, but pinned. Repositories CI has not tagged `latest` fall back to the
# most recently pushed tag.
resolve_repo_tag() {
  jq -r '
    .data.containerRepository.tags.nodes as $tags
    | ($tags | map(select(.name == "latest")) | first) as $latest
    | ($tags | map(select(.name != "latest"))) as $pinned
    | (if $latest then ($pinned | map(select(.digest == $latest.digest)) | first) else null end)
      // ($pinned | sort_by(.createdAt) | last)
    | if . == null then empty else [.name, .createdAt, (.totalSize // 0)] | @tsv end
  '
}

# Lists every repository as "name<TAB>tag<TAB>createdAt<TAB>size", one repo per
# background job so the per-repo tag queries do not run end to end.
list_repo_builds() {
  local list_dir="$1" repos id name
  repos="$(api_get "projects/${PROJECT_PATH//\//%2F}/registry/repositories?per_page=100")"

  while IFS=$'\t' read -r id name; do
    {
      local row
      row="$(api_graphql "query {
        containerRepository(id: \"gid://gitlab/ContainerRepository/$id\") {
          tags(first: 100) { nodes { name digest createdAt totalSize } }
        }
      }" | resolve_repo_tag)" || row=""
      [ -n "$row" ] && printf '%s\t%s\n' "$name" "$row" > "$list_dir/$name"
    } &
  done < <(jq -r '.[] | [(.id|tostring), .name] | @tsv' <<<"$repos")

  wait
  cat "$list_dir"/* 2>/dev/null | sort
}

human_size() {
  awk -v b="$1" 'BEGIN {
    split("B KiB MiB GiB TiB", u, " ")
    i = 1
    while (b >= 1024 && i < 5) { b /= 1024; i++ }
    printf (i == 1 ? "%d %s" : "%.1f %s"), b, u[i]
  }'
}

# Expands "1 3-5 7" / "all" into the chosen "<image>:<tag>" refs.
select_images() {
  local -n out=$1
  local -a names=() tags=()
  local line name tag created size i token start end reply

  while IFS=$'\t' read -r name tag created size; do
    names+=("$name")
    tags+=("$tag")
    printf '  %2d) %-26s %-10s %10s  %s\n' \
      "${#names[@]}" "$name" "$tag" "$(human_size "$size")" "${created%T*}" >&2
  done < <(list_repo_builds "$2")

  [ "${#names[@]}" -gt 0 ] || { echo "no images found in $PROJECT_PATH" >&2; exit 1; }

  echo >&2
  read -rp "images to bundle (numbers, ranges, or 'all'): " -a reply
  [ "${#reply[@]}" -gt 0 ] || { echo "nothing selected" >&2; exit 1; }

  for token in "${reply[@]}"; do
    case "$token" in
      all|a|ALL) for i in "${!names[@]}"; do out+=("${names[i]}:${tags[i]}"); done ;;
      *-*)
        start="${token%%-*}"; end="${token##*-}"
        for ((i = start; i <= end; i++)); do
          [ "$i" -ge 1 ] && [ "$i" -le "${#names[@]}" ] || { echo "out of range: $i" >&2; exit 1; }
          out+=("${names[i-1]}:${tags[i-1]}")
        done ;;
      *[!0-9]*|"") echo "not a selection: $token" >&2; exit 1 ;;
      *)
        [ "$token" -ge 1 ] && [ "$token" -le "${#names[@]}" ] || { echo "out of range: $token" >&2; exit 1; }
        out+=("${names[token-1]}:${tags[token-1]}") ;;
    esac
  done
}

WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
MERGED="$WORK_DIR/merged"
META="$WORK_DIR/meta"
trap 'rm -rf "$WORK_DIR"' EXIT

IMAGES=("$@")
if [ "${#IMAGES[@]}" -eq 0 ]; then
  require_api_auth
  mkdir -p "$WORK_DIR/repos"
  echo "=== Images in $PROJECT_PATH ===" >&2
  select_images IMAGES "$WORK_DIR/repos"
fi

echo "=== Bundling ${#IMAGES[@]} image(s) ==="
docker login registry.gitlab.com

mkdir -p "$MERGED/blobs/sha256" "$META" "$OUT_DIR"

for FULL_IMAGE in "${IMAGES[@]}"; do
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
