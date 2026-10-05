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

# Explicit workspace-wide shutdown. Managed per-client detach uses live drain,
# stdio EOF and the separate session-status/reap-session native adapter instead.
containers=$(docker ps -aq --no-trunc \
  --filter "label=io.context.mcp-factory=unaltraweb" \
  --filter "label=io.context.mcp-project=$project_id")
networks=$(docker network ls -q --no-trunc \
  --filter "label=io.context.mcp-factory=unaltraweb" \
  --filter "label=io.context.mcp-project=$project_id")

valid_id() {
  [ "${#1}" -eq 64 ] || return 1
  case "$1" in *[!0-9a-f]*) return 1 ;; esac
}
count=0
for cid in $containers; do
  count=$((count + 1))
  [ "$count" -le 64 ] && valid_id "$cid" || { printf '%s\n' 'Container inventory is invalid or exceeds bounds' >&2; exit 2; }
  labels=$(docker container inspect --format '{{index .Config.Labels "io.context.mcp-factory"}}|{{index .Config.Labels "io.context.mcp-role"}}|{{index .Config.Labels "io.context.mcp-project"}}' "$cid")
  case "$labels" in
    "unaltraweb|stdio|$project_id"|"unaltraweb|preview|$project_id"|"unaltraweb|computation|$project_id"|"unaltraweb|manual-pdf|$project_id"|"unaltraweb|web-capture|$project_id"|"unaltraweb|web-capture-site|$project_id") ;;
    *) printf '%s\n' 'Refusing unknown container ownership' >&2; exit 2 ;;
  esac
done
for nid in $networks; do
  count=$((count + 1))
  [ "$count" -le 64 ] && valid_id "$nid" || { printf '%s\n' 'Network inventory is invalid or exceeds bounds' >&2; exit 2; }
  labels=$(docker network inspect --format '{{index .Labels "io.context.mcp-factory"}}|{{index .Labels "io.context.mcp-role"}}|{{index .Labels "io.context.mcp-project"}}' "$nid")
  [ "$labels" = "unaltraweb|web-capture|$project_id" ] || { printf '%s\n' 'Refusing unknown network ownership' >&2; exit 2; }
done
if [ -n "$containers" ]; then docker rm -f $containers >/dev/null; fi
if [ -n "$networks" ]; then docker network rm $networks >/dev/null; fi
for cid in $containers; do
  if observed=$(docker container inspect --format '{{.Id}}' "$cid" 2>&1); then
    printf '%s\n' 'Container termination is not confirmed' >&2; exit 1
  else
    case "$observed" in *"No such container"*|*"no such container"*|*"No such object"*) ;; *) printf '%s\n' 'Container absence is unknown' >&2; exit 1 ;; esac
  fi
done
for nid in $networks; do
  if observed=$(docker network inspect --format '{{.Id}}' "$nid" 2>&1); then
    printf '%s\n' 'Network removal is not confirmed' >&2; exit 1
  else
    case "$observed" in *"No such network"*|*"no such network"*|*"No such object"*) ;; *) printf '%s\n' 'Network absence is unknown' >&2; exit 1 ;; esac
  fi
done
