#!/usr/bin/env bash

set -euo pipefail

OUT_PATH=".cache/scimago/scimagojr.csv"
URL="https://raw.githubusercontent.com/ikashnitsky/sjrdata/master/data/sjr_journals.rda"
INPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      OUT_PATH="$2"
      shift 2
      ;;
    --url)
      URL="$2"
      shift 2
      ;;
    --input)
      INPUT_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--input local.(csv|rda)] [--url SOURCE_URL] [--out .cache/scimago/scimagojr.csv]" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$(dirname "$OUT_PATH")"

convert_rda_to_csv() {
  local src_rda="$1"
  local dst_csv="$2"

  python3 - "$src_rda" "$dst_csv" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

try:
    import rdata
except ImportError as exc:
    print("Missing Python dependency 'rdata'. Install dependencies first:", file=sys.stderr)
    print("  python3 -m pip install --break-system-packages -r requirements.txt", file=sys.stderr)
    print(f"Details: {exc}", file=sys.stderr)
    raise SystemExit(1)

obj = rdata.read_rda(str(src))
if not obj:
    print(f"No objects found in RDA file: {src}", file=sys.stderr)
    raise SystemExit(1)

_, payload = next(iter(obj.items()))

if not hasattr(payload, "columns"):
    print("Unsupported RDA payload: expected a data.frame/tibble", file=sys.stderr)
    raise SystemExit(1)

required = ["year", "issn", "sjr", "sjr_best_quartile", "categories"]
missing = [c for c in required if c not in payload.columns]
if missing:
    print(f"RDA dataset missing expected columns: {missing}", file=sys.stderr)
    raise SystemExit(1)

df = payload.loc[:, required].copy()
df.to_csv(dst, index=False)
print(f"Converted RDA -> CSV ({len(df)} rows): {dst}")
PY
}

if [[ -n "$INPUT_PATH" ]]; then
  if [[ ! -f "$INPUT_PATH" ]]; then
    echo "Input file not found: $INPUT_PATH" >&2
    exit 1
  fi
  case "${INPUT_PATH,,}" in
    *.rda)
      convert_rda_to_csv "$INPUT_PATH" "$OUT_PATH"
      ;;
    *.csv)
      cp "$INPUT_PATH" "$OUT_PATH"
      echo "Copied local Scimago CSV to $OUT_PATH"
      ;;
    *)
      echo "Unsupported input format: $INPUT_PATH" >&2
      echo "Expected .csv or .rda" >&2
      exit 1
      ;;
  esac
else
  TMP_FILE="${OUT_PATH}.download"
  TMP_EXT="${URL##*.}"
  echo "Downloading Scimago source from: $URL"
  if ! curl -fsSL "$URL" -A "Mozilla/5.0" -o "$TMP_FILE"; then
    echo "Download failed. Use --input path/to/local.(csv|rda)" >&2
    rm -f "$TMP_FILE"
    exit 1
  fi

  case "${TMP_EXT,,}" in
    rda)
      convert_rda_to_csv "$TMP_FILE" "$OUT_PATH"
      rm -f "$TMP_FILE"
      ;;
    csv)
      mv "$TMP_FILE" "$OUT_PATH"
      echo "Downloaded CSV to $OUT_PATH"
      ;;
    *)
      echo "Unknown source extension from URL: .$TMP_EXT" >&2
      echo "Use --url ending in .csv or .rda, or pass --input." >&2
      rm -f "$TMP_FILE"
      exit 1
      ;;
  esac
fi

python3 scripts/biblio/metrics_update.py --validate-scimago "$OUT_PATH"
echo "Scimago CSV ready: $OUT_PATH"
