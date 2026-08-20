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
# Requires: skopeo, authenticated with `skopeo login registry.gitlab.com`
# (separate from `docker login` -- skopeo keeps its own credential store).
#
# Images are pulled straight from the registry via skopeo, not the Docker
# daemon, so this needs no local Docker/buildx driver support. Each image
# lands in the classic docker-save layout; merging them by content-addressed
# layer/config filename dedups shared base layers before zstd (whose 2GB
# match window then collapses the near-identical per-service .venv layers).

REGISTRY_PREFIX="registry.gitlab.com/textfactory/hermes/pipeline"
PROJECT_PATH="textfactory/hermes/pipeline"
PLATFORM="${PLATFORM:-linux/amd64}"
OUT_DIR="${OUT_DIR:-.}"
ZSTD_OPTS="${ZSTD_OPTS:--19 --long=31 -T0}"
BUNDLE_NAME="${BUNDLE_NAME:-bundle}"

for dep in skopeo jq zstd tar; do
  command -v "$dep" >/dev/null 2>&1 ||
    { echo "missing dependency: $dep (brew install $dep)" >&2; exit 1; }
done

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
  local list_dir="$1" repos id name row
  repos="$(api_get "projects/${PROJECT_PATH//\//%2F}/registry/repositories?per_page=100")"

  while IFS=$'\t' read -r id name; do
    {
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

# GitLab's createdAt is UTC ("2024-01-15T10:30:00.123Z"); render it in the
# local timezone, human-readable.
human_datetime() {
  # First 19 chars are always "YYYY-MM-DDTHH:MM:SS"; GitLab appends either a
  # "Z" or a "+00:00" offset (both UTC), so drop whatever trails and re-add Z.
  local iso="${1:0:19}Z"
  if date --version >/dev/null 2>&1; then
    date -d "$iso" '+%d/%m/%y %H:%M'
  else
    date -r "$(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$iso" '+%s')" '+%d/%m/%y %H:%M'
  fi
}

# Menu state, shared by both pickers: parallel arrays plus a 0/1 mark per row.
MENU_NAMES=()
MENU_TAGS=()
MENU_LABELS=()
MENU_MARKS=()

load_menu() {
  local name tag created size
  MENU_NAMES=(); MENU_TAGS=(); MENU_LABELS=(); MENU_MARKS=()

  while IFS=$'\t' read -r name tag created size; do
    MENU_NAMES+=("$name")
    MENU_TAGS+=("$tag")
    MENU_LABELS+=("$(printf '%-26s %-10s %10s  %s' \
      "$name" "$tag" "$(human_size "$size")" "$(human_datetime "$created")")")
    MENU_MARKS+=(0)
  done < <(list_repo_builds "$1")

  [ "${#MENU_NAMES[@]}" -gt 0 ] || { echo "no images found in $PROJECT_PATH" >&2; return 1; }
}

emit_marked() {
  local i any=0
  for ((i = 0; i < ${#MENU_NAMES[@]}; i++)); do
    if [ "${MENU_MARKS[i]}" = 1 ]; then
      printf '%s:%s\n' "${MENU_NAMES[i]}" "${MENU_TAGS[i]}"
      any=1
    fi
  done
  [ "$any" = 1 ] || { echo "nothing selected" >&2; return 1; }
}

# Full-list redraw: every frame reprints in place, so the cursor is parked at
# the top of the block before drawing and the previous frame's line is cleared
# rather than scrolled away.
draw_menu() {
  local cursor="$1" i box pointer
  for ((i = 0; i < ${#MENU_NAMES[@]}; i++)); do
    [ "${MENU_MARKS[i]}" = 1 ] && box="[x]" || box="[ ]"
    if [ "$i" = "$cursor" ]; then
      pointer=" >"
      printf '\033[2K%s \033[7m%s %s\033[0m\n' "$pointer" "$box" "${MENU_LABELS[i]}"
    else
      printf '\033[2K   %s %s\n' "$box" "${MENU_LABELS[i]}"
    fi
  done
  printf '\033[2K\n\033[2K  \033[2m^/v move  space toggle  a all  enter confirm  q quit\033[0m\n'
}

# Arrow-key checkbox picker. Draws on /dev/tty and reads keys from it, leaving
# stdout free for the selected refs.
pick_interactive() {
  # draw_menu emits one line per entry plus a blank and the key hint.
  local rows=$((${#MENU_NAMES[@]} + 2))
  local cursor=0 aborted=0 key rest i

  # Between reads the tty would drop back to cooked mode and echo whatever is
  # typed into the frame, so hold it raw for the whole loop. A RETURN trap
  # would fire for the nested calls too; the loop restores state explicitly.
  local saved_stty
  saved_stty="$(stty -g < /dev/tty)"
  stty -echo -icanon min 1 time 0 < /dev/tty
  exec 3>/dev/tty
  printf '\033[?25l' >&3

  draw_menu "$cursor" >&3
  while true; do
    IFS= read -rsn1 key < /dev/tty || { aborted=1; break; }
    case "$key" in
      $'\e')
        # bash 3.2 takes whole-second timeouts only; a lone Esc waits it out.
        read -rsn2 -t 1 rest < /dev/tty || rest=""
        case "$rest" in
          '[A') ((cursor > 0)) && ((cursor--)) || true ;;
          '[B') ((cursor < ${#MENU_NAMES[@]} - 1)) && ((cursor++)) || true ;;
          '') aborted=1; break ;;
        esac ;;
      k) ((cursor > 0)) && ((cursor--)) || true ;;
      j) ((cursor < ${#MENU_NAMES[@]} - 1)) && ((cursor++)) || true ;;
      ' ') [ "${MENU_MARKS[cursor]}" = 1 ] && MENU_MARKS[cursor]=0 || MENU_MARKS[cursor]=1 ;;
      a)
        # All-or-nothing: if anything is marked, `a` clears; otherwise marks all.
        local target=1
        for ((i = 0; i < ${#MENU_MARKS[@]}; i++)); do
          [ "${MENU_MARKS[i]}" = 1 ] && target=0 && break
        done
        for ((i = 0; i < ${#MENU_MARKS[@]}; i++)); do MENU_MARKS[i]=$target; done ;;
      q) aborted=1; break ;;
      '') break ;;
    esac
    printf '\033[%dA' "$rows" >&3
    draw_menu "$cursor" >&3
  done

  printf '\033[?25h' >&3
  exec 3>&-
  stty "$saved_stty" < /dev/tty
  [ "$aborted" = 0 ] || return 1
  emit_marked
}

# Typed fallback for pipes and dumb terminals: "1 3-5 7" or "all".
pick_typed() {
  local reply=() token i start end

  for ((i = 0; i < ${#MENU_NAMES[@]}; i++)); do
    printf '  %2d) %s\n' "$((i + 1))" "${MENU_LABELS[i]}" >&2
  done
  echo >&2
  read -rp "images to bundle (numbers, ranges, or 'all'): " -a reply

  for token in "${reply[@]}"; do
    case "$token" in
      all|a|ALL) for ((i = 0; i < ${#MENU_MARKS[@]}; i++)); do MENU_MARKS[i]=1; done ;;
      *-*)
        start="${token%%-*}"; end="${token##*-}"
        for ((i = start; i <= end; i++)); do
          [ "$i" -ge 1 ] && [ "$i" -le "${#MENU_NAMES[@]}" ] || { echo "out of range: $i" >&2; return 1; }
          MENU_MARKS[i-1]=1
        done ;;
      *[!0-9]*|"") echo "not a selection: $token" >&2; return 1 ;;
      *)
        [ "$token" -ge 1 ] && [ "$token" -le "${#MENU_NAMES[@]}" ] || { echo "out of range: $token" >&2; return 1; }
        MENU_MARKS[token-1]=1 ;;
    esac
  done

  emit_marked
}

select_images() {
  load_menu "$1" || return 1
  if [ -t 0 ] && [ -r /dev/tty ] && [ "${TERM:-dumb}" != dumb ]; then
    pick_interactive
  else
    pick_typed
  fi
}

WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
MERGED="$WORK_DIR/merged"
META="$WORK_DIR/meta"
trap 'rm -rf "$WORK_DIR"' EXIT

IMAGES=("$@")
if [ "$#" -eq 0 ]; then
  require_api_auth
  mkdir -p "$WORK_DIR/repos"
  echo "=== Images in $PROJECT_PATH ===" >&2
  IMAGES=()
  while IFS= read -r line; do IMAGES+=("$line"); done < <(select_images "$WORK_DIR/repos")
  [ "${#IMAGES[@]}" -gt 0 ] || exit 1
fi

echo "=== Bundling ${#IMAGES[@]} image(s) ==="
skopeo login registry.gitlab.com

mkdir -p "$MERGED" "$META" "$OUT_DIR"

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

  skopeo copy --override-os "${PLATFORM%%/*}" --override-arch "${PLATFORM##*/}" \
    "docker://$IMAGE_REF" "docker-archive:$TMP_TAR:$IMAGE_REF"

  tar -xf "$TMP_TAR" -C "$EXTRACTED"
  rm -f "$TMP_TAR"

  # Layer blobs and config files are named by content digest, so -n across
  # images naturally dedups shared base layers; only manifest.json needs merging.
  cp -n "$EXTRACTED"/*.tar "$MERGED/" 2>/dev/null || true
  find "$EXTRACTED" -maxdepth 1 -name '*.json' ! -name manifest.json \
    -exec cp -n {} "$MERGED/" \;
  cp "$EXTRACTED/manifest.json" "$META/$NAME.manifest.json"
  rm -rf "$EXTRACTED"
done

jq -s 'add' "$META"/*.manifest.json > "$MERGED/manifest.json"

BUNDLE="$OUT_DIR/$BUNDLE_NAME.tar.zst"
rm -f "$BUNDLE"
# shellcheck disable=SC2086
tar --no-xattrs -cf - -C "$MERGED" . | zstd $ZSTD_OPTS -q -o "$BUNDLE"

echo "=== Wrote $BUNDLE ($(du -h "$BUNDLE" | cut -f1)) ==="
jq -r '.[].RepoTags[] | "      " + .' "$MERGED/manifest.json"
echo "=== Load with: zstd -dc --long=31 $(basename "$BUNDLE") | docker load ==="
