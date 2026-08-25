#!/bin/sh
set -eu

usage() {
  cat <<'USAGE'
Usage: unaltraweb-mcp-bootstrap [--project PATH] [--image IMAGE]

Start one Dockerized unaltraweb MCP stdio server for the selected workspace.
If --project is omitted, UNALTRAWEB_PROJECT is used, then the current directory.
USAGE
}

image="${UNALTRAWEB_MCP_IMAGE:-ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.2.0}"
project="${UNALTRAWEB_PROJECT:-${PROJECT:-}}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      [ "$#" -ge 2 ] || { printf '%s\n' 'Missing value for --project' >&2; exit 2; }
      project="$2"
      shift 2
      ;;
    --image)
      [ "$#" -ge 2 ] || { printf '%s\n' 'Missing value for --image' >&2; exit 2; }
      image="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$project" ]; then
  project="$PWD"
fi
if [ ! -d "$project" ]; then
  printf 'Project directory not found: %s\n' "$project" >&2
  exit 1
fi

project="$(CDPATH= cd -- "$project" && pwd -P)"
owner="${UNALTRAWEB_PROJECT_USER:-$(id -u):$(id -g)}"
docker_socket="${UNALTRAWEB_DOCKER_SOCKET:-/var/run/docker.sock}"
checksum="$(printf '%s' "$project" | cksum)"
project_id="${checksum%% *}"
container_name="unaltraweb-mcp-$project_id"

if ! resolved_image="$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null)"; then
  docker pull "$image" >/dev/null
  resolved_image="$(docker image inspect --format '{{.Id}}' "$image")"
fi

set -- docker run --rm -i \
  --name "$container_name" \
  --label io.context.mcp-factory=unaltraweb \
  --label io.context.mcp-role=stdio \
  --label "io.context.mcp-project=$project_id" \
  --user "$owner" \
  -e HOME=/tmp \
  -e COMPUTE_CORE=/opt/unaltraweb \
  -e LOCAL_CORE=/opt/unaltraweb \
  -e "PROJECT=$project" \
  -e "UNALTRAWEB_DOCKER_ROOT=$project" \
  -e UNALTRAWEB_FACTORY_DIR=/opt/unaltraweb \
  -e "UNALTRAWEB_MCP_IMAGE=$resolved_image" \
  -e "UNALTRAWEB_PROJECT_USER=$owner" \
  -v "$project:/workspace" \
  -v "$project:$project" \
  -w "$project"

if [ -S "$docker_socket" ]; then
  socket_group="$(stat -c '%g' "$docker_socket")"
  set -- "$@" --group-add "$socket_group" -v "$docker_socket:/var/run/docker.sock"
fi

exec "$@" "$resolved_image" --project "$project" mcp serve
