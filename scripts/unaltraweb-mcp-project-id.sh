#!/bin/sh
set -eu

project="${1:-${UNALTRAWEB_PROJECT:-${PROJECT:-$PWD}}}"

if [ "$#" -gt 1 ]; then
  printf '%s\n' 'Usage: unaltraweb-mcp-project-id [PROJECT]' >&2
  exit 2
fi
if [ ! -d "$project" ]; then
  printf 'Project directory not found: %s\n' "$project" >&2
  exit 1
fi

project="$(CDPATH= cd -- "$project" && pwd -P)"
if command -v sha256sum >/dev/null 2>&1; then
  checksum="$(printf '%s' "$project" | sha256sum)"
elif command -v shasum >/dev/null 2>&1; then
  checksum="$(printf '%s' "$project" | shasum -a 256)"
else
  printf '%s\n' 'sha256sum or shasum is required to identify the project.' >&2
  exit 1
fi
checksum="${checksum%% *}"
printf '%.16s\n' "$checksum"
