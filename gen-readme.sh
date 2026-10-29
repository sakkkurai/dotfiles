#!/usr/bin/env bash

set -euo pipefail

ROOT="${1:-wallpapers}"
OUT="${2:-README.md}"
TITLE="dotfiles"

ROOT="${ROOT%/}"
if [[ ! -d "$ROOT" ]]; then
  printf 'Directory not found: %s\n' "$ROOT" >&2
  exit 1
fi

get_size() {
  local file=$1 output=""
  if command -v magick >/dev/null 2>&1; then
    output=$(magick identify -format '%w %h' "${file}[0]" 2>/dev/null || true)
  elif command -v identify >/dev/null 2>&1; then
    output=$(identify -format '%w %h' "${file}[0]" 2>/dev/null || true)
  elif command -v file >/dev/null 2>&1; then
    output=$(file -b "$file" | grep -oE '[0-9]+[[:space:]]*x[[:space:]]*[0-9]+' | tail -n 1 | tr -d ' ' | tr 'x' ' ' || true)
  fi

  if [[ "$output" =~ ^[0-9]+[[:space:]]+[0-9]+$ ]]; then
    printf '%s' "$output"
  fi
}

make_tags() {
  local width=$1 height=$2 tags=""
  if (( width >= 3840 || height >= 2160 )); then
    tags="4K+"
  elif (( width >= 1920 || height >= 1080 )); then
    tags="FHD"
  fi

  if (( width * 100 >= height * 210 )); then
    tags="${tags:+$tags · }UW"
  fi

  printf '%s' "$tags"
}

make_name() {
  local stem="${1%.*}" name

  name=$(printf '%s' "$stem" |
    sed -E 's/[-_ ]*[0-9]{3,5}x[0-9]{3,5}$//; s/[-_]+/ /g' |
    awk '{
      for (i = 1; i <= NF; i++) {
        $i = toupper(substr($i, 1, 1)) substr($i, 2)
      }
      print
    }')

  printf '%s' "${name:-$stem}"
}

url_escape() {
  local value=$1
  value=${value//%/%25}
  value=${value// /%20}
  value=${value//(/%28}
  value=${value//)/%29}
  value=${value//#/%23}
  printf '%s' "$value"
}

format_category() {
  local value=$1
  value=${value//[-_]/ }
  printf '%s' "$value" | awk '{
    for (i = 1; i <= NF; i++) {
      $i = tolower($i)
      $i = toupper(substr($i, 1, 1)) substr($i, 2)
    }
    print
  }'
}

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

mapfile -d '' -t paths < <(
  find "$ROOT" -type f \
    \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \) \
    -print0 | LC_ALL=C sort -z
)

count=${#paths[@]}
declare -a categories=()

for path in "${paths[@]}"; do
  rel=${path#"$ROOT"/}
  dir=$(dirname "$rel")
  [[ "$dir" == "." ]] && dir="other"

  found=0
  for existing in "${categories[@]}"; do
    if [[ "$existing" == "$dir" ]]; then
      found=1
      break
    fi
  done

  if (( found == 0 )); then
    categories+=("$dir")
  fi
done

{
  printf '# %s\n\n' "$TITLE"
  printf '## Contents\n\n'
  printf -- '- [Wallpapers](#wallpapers)\n'

  for dir in "${categories[@]}"; do
    category=$(format_category "$dir")
    anchor=$(printf '%s' "$category" |
      tr '[:upper:]' '[:lower:]' |
      sed -E 's/[[:space:]]+/-/g')

    printf '  - [%s](#%s)\n' "$category" "$anchor"
  done

  printf '\n## Wallpapers\n\n'

  current_dir=""
  column=0

  for path in "${paths[@]}"; do
    rel=${path#"$ROOT"/}
    dir=$(dirname "$rel")
    file=${rel##*/}
    [[ "$dir" == "." ]] && dir="other"

    if [[ "$dir" != "$current_dir" ]]; then
      if [[ -n "$current_dir" ]]; then
        if (( column == 1 )); then
          printf '<td width="50%%"></td></tr>\n'
        else
          printf '</tr>\n'
        fi
        printf '</tbody></table>\n\n'
      fi

      category=$(format_category "$dir")
      printf '### %s\n\n' "$category"
      printf '<table><tbody>\n<tr>\n'
      current_dir="$dir"
      column=0
    fi

    name=$(make_name "$file")
    image_path=$(url_escape "$ROOT/$rel")
    dimensions=$(get_size "$path")
    w=""
    h=""
    read -r w h <<< "$dimensions" || true

    if [[ -n "$w" && -n "$h" ]]; then
      resolution="${w} × ${h}"
      tags=$(make_tags "$w" "$h")
    else
      resolution="Resolution unknown"
      tags=""
    fi

    printf '<td width="50%%" valign="top">\n'
    printf '<img src="%s" alt="%s" width="100%%">\n\n' "$image_path" "$name"
    printf '<strong>%s</strong><br>\n' "$name"
    printf '<sub>%s' "$resolution"
    if [[ -n "$tags" ]]; then
      printf ' · %s' "$tags"
    fi
    printf '</sub>\n'
    printf '</td>\n'

    column=$((column + 1))
    if (( column == 2 )); then
      printf '</tr>\n<tr>\n'
      column=0
    fi
  done

  if (( count > 0 )); then
    if (( column == 1 )); then
      printf '<td width="50%%"></td></tr>\n'
    fi
    printf '</tbody></table>\n\n'
  fi

  printf -- '---\n\n'
  printf '<sub>%s wallpapers · Automatically generated</sub>\n' "$count"
} > "$tmp"

chmod 644 "$tmp"
mv "$tmp" "$OUT"
trap - EXIT

printf 'Done: %s (%s wallpapers)\n' "$OUT" "$count"
