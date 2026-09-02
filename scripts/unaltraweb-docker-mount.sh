#!/bin/sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  printf '%s\n' 'Usage: unaltraweb-docker-mount SOURCE TARGET [readonly]' >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) printf '%s\n' 'Docker bind source must be an absolute path.' >&2; exit 2 ;;
esac
case "$2" in
  /*) ;;
  *) printf '%s\n' 'Docker bind target must be an absolute path.' >&2; exit 2 ;;
esac
if [ "$#" -eq 3 ] && [ "$3" != "readonly" ]; then
  printf '%s\n' 'The optional Docker bind mode must be readonly.' >&2
  exit 2
fi
newline='
'
carriage_return=$(printf '\r')
case "$1$2" in
  *"$newline"*|*"$carriage_return"*)
    printf '%s\n' 'Docker bind source and target must not contain carriage returns or newlines.' >&2
    exit 2
    ;;
esac

source_field=$(printf 'source=%s' "$1" | sed 's/"/""/g')
target_field=$(printf 'target=%s' "$2" | sed 's/"/""/g')
printf 'type=bind,"%s","%s"' "$source_field" "$target_field"
if [ "$#" -eq 3 ]; then
  printf ',readonly'
fi
printf '\n'
