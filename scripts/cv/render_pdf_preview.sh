#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  printf 'Usage: %s path/to/cv.pdf path/to/cv-preview.jpg\n' "$0" >&2
  exit 2
fi

pdf=$1
out=$2
density=${DENSITY:-180}

if [ ! -f "$pdf" ]; then
  printf 'PDF not found: %s\n' "$pdf" >&2
  exit 1
fi

mkdir -p "$(dirname "$out")"

if command -v pdftoppm >/dev/null 2>&1; then
  tmp_dir=$(mktemp -d)
  trap 'rm -rf "$tmp_dir"' EXIT
  pdftoppm -f 1 -singlefile -jpeg -r "$density" "$pdf" "$tmp_dir/page"
  mv "$tmp_dir/page.jpg" "$out"
elif command -v mutool >/dev/null 2>&1; then
  mutool draw -r "$density" -o "$out" "$pdf" 1
elif command -v magick >/dev/null 2>&1 && command -v gs >/dev/null 2>&1; then
  magick -density "$density" "${pdf}[0]" -background white -alpha remove -alpha off -quality 90 "$out"
elif command -v convert >/dev/null 2>&1 && command -v gs >/dev/null 2>&1; then
  convert -density "$density" "${pdf}[0]" -background white -alpha remove -alpha off -quality 90 "$out"
else
  printf 'No supported PDF renderer found. Install poppler-utils, mupdf-tools, or Ghostscript for ImageMagick.\n' >&2
  exit 1
fi

printf 'Wrote %s\n' "$out"
