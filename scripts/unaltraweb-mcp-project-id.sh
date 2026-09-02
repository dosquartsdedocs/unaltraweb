#!/bin/sh
set -eu

project="${1:-${MCP_CONSUMER_WORKSPACE:-${UNALTRAWEB_PROJECT:-$PWD}}}"

if [ "$#" -gt 1 ]; then
  printf '%s\n' 'Usage: unaltraweb-mcp-project-id [PROJECT]' >&2
  exit 2
fi
newline='
'
carriage_return=$(printf '\r')
case "$project" in
  *"$newline"*|*"$carriage_return"*)
    printf '%s\n' 'Project paths must not contain carriage returns or newlines.' >&2
    exit 2
    ;;
esac
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
