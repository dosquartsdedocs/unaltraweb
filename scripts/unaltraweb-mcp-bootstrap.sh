#!/bin/sh
set -eu

usage() {
  cat <<'USAGE'
Usage: unaltraweb-mcp-bootstrap [--project PATH] [--image IMAGE]

Start one Dockerized unaltraweb MCP stdio server for the selected workspace.
If --project is omitted, MCP_CONSUMER_WORKSPACE is used, then the current directory.
USAGE
}

image="${UNALTRAWEB_MCP_IMAGE:-ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0}"
project="${MCP_CONSUMER_WORKSPACE:-${UNALTRAWEB_PROJECT:-}}"

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
owner="${UNALTRAWEB_PROJECT_USER:-$(id -u):$(id -g)}"
docker_socket="${UNALTRAWEB_DOCKER_SOCKET:-/var/run/docker.sock}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
project_id="$(/bin/sh "$script_dir/unaltraweb-mcp-project-id.sh" "$project")"
workspace_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$project" /workspace)"
mirror_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$project" "$project")"

if ! resolved_image="$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null)"; then
  docker pull "$image" >/dev/null
  resolved_image="$(docker image inspect --format '{{.Id}}' "$image")"
fi
image_reference="$image"
case "$image_reference" in
  ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:*) ;;
  *)
    for repository_digest in $(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$image"); do
      case "$repository_digest" in
        ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:*) image_reference="$repository_digest"; break ;;
      esac
    done
    ;;
esac

set -- docker run --rm -i \
  --label io.context.mcp-factory=unaltraweb \
  --label io.context.mcp-role=stdio \
  --label "io.context.mcp-project=$project_id" \
  --user "$owner" \
  -e HOME=/tmp \
  -e COMPUTE_CORE=/opt/unaltraweb \
  -e LOCAL_CORE=/opt/unaltraweb \
  -e "MCP_CONSUMER_WORKSPACE=$project" \
  -e "UNALTRAWEB_DOCKER_ROOT=$project" \
  -e UNALTRAWEB_FACTORY_DIR=/opt/unaltraweb \
  -e "UNALTRAWEB_MCP_IMAGE=$resolved_image" \
  -e "UNALTRAWEB_MCP_IMAGE_REFERENCE=$image_reference" \
  -e "UNALTRAWEB_PROJECT_USER=$owner" \
  --mount "$workspace_mount" \
  --mount "$mirror_mount" \
  -w "$project"

if [ -S "$docker_socket" ]; then
  socket_group="$(stat -c '%g' "$docker_socket")"
  socket_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$docker_socket" /var/run/docker.sock)"
  set -- "$@" --group-add "$socket_group" --mount "$socket_mount"
fi

exec "$@" "$resolved_image" --project "$project" mcp serve
