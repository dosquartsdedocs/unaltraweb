#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
project_id="${MCP_PROJECT_ID:-}"
workspace="${MCP_CONSUMER_WORKSPACE:-}"
project=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      [ "$#" -ge 2 ] || { printf '%s\n' '--project requires a path' >&2; exit 2; }
      project=$2
      shift 2
      ;;
    --project-id)
      [ "$#" -ge 2 ] || { printf '%s\n' '--project-id requires an ID' >&2; exit 2; }
      project_id=$2
      shift 2
      ;;
    *)
      printf 'Unknown cleanup argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$project" ]; then
  project=$workspace
fi

if [ -n "$project" ]; then
  if [ -d "$project" ]; then
    computed_id=$(/bin/sh "$script_dir/unaltraweb-mcp-project-id.sh" "$project")
    if [ -n "$project_id" ] && [ "$project_id" != "$computed_id" ]; then
      printf 'Project ID %s does not match canonical live workspace %s\n' "$project_id" "$project" >&2
      exit 2
    fi
    project_id=$computed_id
  elif [ -e "$project" ]; then
    printf 'Workspace path is not a directory: %s\n' "$project" >&2
    exit 2
  elif [ -z "$project_id" ]; then
    printf 'Workspace is absent: %s. Set MCP_PROJECT_ID to the retained 16-hex project ID explicitly.\n' "$project" >&2
    exit 2
  fi
fi

case "$project_id" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  '')
    printf '%s\n' 'Set MCP_CONSUMER_WORKSPACE or pass --project-id with the retained project ID.' >&2
    exit 2
    ;;
  *)
    printf 'Invalid unaltraweb project ID: %s\n' "$project_id" >&2
    exit 2
    ;;
esac

containers=$(docker ps -aq \
  --filter "label=io.context.mcp-factory=unaltraweb" \
  --filter "label=io.context.mcp-project=$project_id")
if [ -n "$containers" ]; then
  docker rm -f $containers >/dev/null
fi

networks=$(docker network ls -q \
  --filter "label=io.context.mcp-factory=unaltraweb" \
  --filter "label=io.context.mcp-project=$project_id")
if [ -n "$networks" ]; then
  docker network rm $networks >/dev/null
fi
