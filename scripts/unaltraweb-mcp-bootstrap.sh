#!/bin/sh
set -eu

usage() {
  cat <<'USAGE'
Usage: unaltraweb-mcp-bootstrap [--project PATH] [--host-project PATH] [--image IMAGE]
       [--expected-image-id ID] [--managed] [--offline] [--session-id ID] [--worker-images JSON]
       [--storage-state PATH] [--host-storage-state PATH]
       [--prepare|--check|--smoke]

Start one Dockerized unaltraweb MCP stdio server for the selected workspace.
If --project is omitted, MCP_CONSUMER_WORKSPACE is used, then the current directory.
--prepare inspects or pulls the selected image without mounting a consumer.
Launch, --check and --smoke require that exact image locally; none builds or pulls.
Managed mode requires an immutable reference or an expected full image ID.
USAGE
}

image="${UNALTRAWEB_MCP_IMAGE:-ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6}"
project="${MCP_CONSUMER_WORKSPACE:-${UNALTRAWEB_PROJECT:-}}"
operation=serve
expected_image="${UNALTRAWEB_EXPECTED_IMAGE_ID:-}"
managed="${UNALTRAWEB_MANAGED_RUNTIME:-0}"
session_id=""
host_project=""
network=bridge
worker_images="${UNALTRAWEB_WORKER_IMAGES:-}"
storage_state="${UNALTRAWEB_JOB_STORAGE_STATE:-}"
host_storage_state="${UNALTRAWEB_JOB_STORAGE_HOST_STATE:-}"
[ -n "$worker_images" ] || worker_images='{}'

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
    --host-project|--expected-image-id|--session-id|--worker-images|--storage-state|--host-storage-state)
      [ "$#" -ge 2 ] || { printf 'Missing value for %s\n' "$1" >&2; exit 2; }
      case "$1" in
        --host-project) host_project=$2 ;;
        --expected-image-id) expected_image=$2 ;;
        --session-id) session_id=$2 ;;
        --worker-images) worker_images=$2 ;;
        --storage-state) storage_state=$2 ;;
        --host-storage-state) host_storage_state=$2 ;;
      esac
      shift 2
      ;;
    --managed) managed=1; shift ;;
    --offline) network=none; shift ;;
    --prepare|--check|--smoke)
      [ "$operation" = serve ] || { printf '%s\n' 'Select only one operation.' >&2; exit 2; }
      operation="${1#--}"
      shift
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

valid_image_id() {
  case "$1" in sha256:*) hex=${1#sha256:} ;; *) return 1 ;; esac
  [ "${#hex}" -eq 64 ] || return 1
  case "$hex" in *[!0-9a-f]*) return 1 ;; esac
}
case "$image" in ''|*[!A-Za-z0-9._/:@-]*) printf '%s\n' 'Invalid image reference' >&2; exit 2 ;; esac
case "$image" in *://*) printf '%s\n' 'Docker references are not URLs' >&2; exit 2 ;; esac
case "$image" in
  *@*)
    valid_image_id "${image##*@}" || { printf '%s\n' 'Invalid digest reference' >&2; exit 2; }
    case "${image%@*}" in *@*) printf '%s\n' 'Invalid digest reference' >&2; exit 2 ;; esac
    ;;
esac
if [ -n "$expected_image" ]; then
  valid_image_id "$expected_image" || { printf '%s\n' 'Expected image ID must be a full lowercase sha256' >&2; exit 2; }
  managed=1
fi
case "$image" in
  sha256:*) valid_image_id "$image" || exit 2; managed=1 ;;
  *@sha256:*) valid_image_id "sha256:${image##*@sha256:}" || exit 2; managed=1 ;;
  *) if [ "$managed" = 1 ] && [ -z "$expected_image" ]; then printf '%s\n' 'Managed mutable references require --expected-image-id' >&2; exit 2; fi ;;
esac

resolve_image() {
  if ! resolved_image="$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null)"; then
    case "$operation" in
      serve|check|smoke)
        printf 'Image is not prepared: %s. Run --prepare first.\n' "$image" >&2
        exit 1
        ;;
    esac
    docker pull "$image" >&2
    resolved_image="$(docker image inspect --format '{{.Id}}' "$image")"
  fi
  valid_image_id "$resolved_image" || { printf '%s\n' 'Docker returned an invalid image identity' >&2; exit 2; }
  case "$image" in sha256:*) [ "$image" = "$resolved_image" ] || { printf '%s\n' 'Selected image ID mismatch' >&2; exit 1; } ;; esac
  if [ -n "$expected_image" ] && [ "$expected_image" != "$resolved_image" ]; then
    printf '%s\n' 'Prepared image does not match the expected image ID; no fallback was attempted' >&2; exit 1
  fi
}

if [ "$operation" != serve ]; then
  resolve_image
  case "$operation" in
    prepare) printf '%s\n' "$resolved_image"; exit 0 ;;
    check) exec docker run --rm --pull never --network none --user "$(id -u):$(id -g)" -e HOME=/tmp --entrypoint unaltraweb-mcp "$resolved_image" version ;;
    smoke) exec docker run --rm --pull never --network none --user "$(id -u):$(id -g)" -e HOME=/tmp --entrypoint python3 "$resolved_image" /opt/unaltraweb/test/mcp_smoke.py ;;
  esac
fi

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
launcher_project="$project"
if [ -z "$host_project" ]; then
  host_project="${UNALTRAWEB_DOCKER_ROOT:-}"
  if [ -n "$host_project" ]; then
    inherited_workspace="${MCP_CONSUMER_WORKSPACE:-}"
    if [ -z "$inherited_workspace" ] || [ ! -d "$inherited_workspace" ] || [ "$(CDPATH= cd -- "$inherited_workspace" && pwd -P)" != "$launcher_project" ]; then
      printf '%s\n' 'Inherited daemon mapping belongs to another or unknown workspace; pass --host-project explicitly' >&2; exit 2
    fi
  fi
fi
if [ -z "$host_project" ] && [ -f /.dockerenv ]; then
  printf '%s\n' 'A containerized launcher needs --host-project with the explicit daemon-host mapping' >&2; exit 2
fi
host_project="${host_project:-$project}"
case "$host_project" in /*) ;; *) printf '%s\n' 'Host project must be absolute' >&2; exit 2 ;; esac
case "$host_project" in *"$newline"*|*"$carriage_return"*) exit 2 ;; esac
[ "$host_project" != / ] && [ "$(realpath -ms -- "$host_project")" = "$host_project" ] || { printf '%s\n' 'Host project must be normalized' >&2; exit 2; }
project="$host_project"
owner="${UNALTRAWEB_PROJECT_USER:-$(id -u):$(id -g)}"
docker_socket="${UNALTRAWEB_DOCKER_SOCKET:-/var/run/docker.sock}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
project_id="$(printf '%s' "$project" | sha256sum | cut -c 1-16)"
workspace_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$project" /workspace)"
mirror_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$project" "$project")"

if [ -S "$docker_socket" ]; then
  unresolved_socket="$docker_socket"
  if ! docker_socket="$(realpath -e -- "$unresolved_socket")"; then
    printf '%s\n' "Cannot resolve Docker socket: $unresolved_socket" >&2
    exit 1
  fi
  if [ "$(stat -c '%h' "$docker_socket")" != 1 ]; then
    printf '%s\n' 'UNALTRAWEB_DOCKER_SOCKET must not have hard-link aliases that could enter the consumer project.' >&2
    exit 1
  fi
  case "$docker_socket" in
    "$project"|"$project"/*|"$launcher_project"|"$launcher_project"/*)
      printf '%s\n' 'UNALTRAWEB_DOCKER_SOCKET must be outside the consumer project so the persistent preview cannot inherit it.' >&2
      exit 1
      ;;
  esac
fi

resolve_image
if [ -z "$session_id" ]; then session_id=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n'); fi
[ "${#session_id}" -eq 32 ] || { printf '%s\n' 'Session ID must contain 32 lowercase hex characters' >&2; exit 2; }
case "$session_id" in *[!0-9a-f]*) exit 2 ;; esac
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

# Persistent control metadata is separate from both the consumer and job volumes.
# Containerized launchers need an explicit daemon mapping; do not guess one from
# HOME or a factory checkout. Old/non-storage operations can still connect.
storage_mount=""
storage_identity=""
if [ ! -f /.dockerenv ] || [ -n "$host_storage_state" ] || [ -n "$storage_state" ]; then
  storage_state="${storage_state:-${XDG_STATE_HOME:-$HOME/.local/state}/unaltraweb/job-storage-v1}"
  case "$storage_state" in /*) ;; *) printf '%s\n' 'Storage state path must be absolute' >&2; exit 2 ;; esac
  case "$storage_state" in *"$newline"*|*"$carriage_return"*) exit 2 ;; esac
  [ "$storage_state" != / ] && [ "$(realpath -m -- "$storage_state")" = "$storage_state" ] || { printf '%s\n' 'Storage state path must be normalized and contain no symlinks' >&2; exit 2; }
  case "$storage_state" in "$launcher_project"|"$launcher_project"/*) printf '%s\n' 'Storage registry must be outside the consumer' >&2; exit 2 ;; esac
  if [ -f /.dockerenv ] && [ -z "$host_storage_state" ]; then
    printf '%s\n' 'A containerized storage launcher needs --host-storage-state' >&2; exit 2
  fi
  host_storage_state="${host_storage_state:-$storage_state}"
  case "$host_storage_state" in /*) ;; *) exit 2 ;; esac
  case "$host_storage_state" in *"$newline"*|*"$carriage_return"*|"$project"|"$project"/*) exit 2 ;; esac
  [ "$host_storage_state" != / ] && [ "$(realpath -ms -- "$host_storage_state")" = "$host_storage_state" ] || exit 2
  (umask 077; mkdir -p -- "$storage_state")
  [ ! -L "$storage_state" ] && [ "$(realpath -e -- "$storage_state")" = "$storage_state" ] || exit 2
  [ "$(stat -c '%u:%a' -- "$storage_state")" = "${owner%%:*}:700" ] || { printf '%s\n' 'Storage registry must be private (0700) and owned by the controller user' >&2; exit 2; }
  storage_identity="$(stat -c '%d:%i' -- "$storage_state")"
  storage_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$host_storage_state" /var/lib/unaltraweb-job-storage)"
fi

set -- docker run --rm --pull never --init -i \
  --network "$network" \
  --name "unaltraweb-stdio-$session_id" --cpus 2 --memory 4g --pids-limit 512 \
  --label io.context.mcp-factory=unaltraweb \
  --label io.context.mcp-role=stdio \
  --label "io.context.mcp-project=$project_id" \
  --label "io.context.mcp-session=$session_id" \
  --user "$owner" \
  -e HOME=/tmp \
  -e COMPUTE_CORE=/opt/unaltraweb \
  -e LOCAL_CORE=/opt/unaltraweb \
  -e "MCP_CONSUMER_WORKSPACE=$project" \
  -e "UNALTRAWEB_DOCKER_ROOT=$project" \
  -e UNALTRAWEB_FACTORY_DIR=/opt/unaltraweb \
  -e "UNALTRAWEB_MCP_IMAGE=$resolved_image" \
  -e "UNALTRAWEB_MCP_IMAGE_REFERENCE=$image_reference" \
  -e "UNALTRAWEB_MCP_REQUESTED_IMAGE=$image" \
  -e "UNALTRAWEB_EXPECTED_IMAGE_ID=$resolved_image" \
  -e "UNALTRAWEB_RUNTIME_SESSION=$session_id" \
  -e "UNALTRAWEB_MANAGED_RUNTIME=$managed" \
  -e "UNALTRAWEB_RUNTIME_NETWORK=$network" \
  -e "UNALTRAWEB_LAUNCHER_PROJECT=$launcher_project" \
  -e "UNALTRAWEB_WORKER_IMAGES=$worker_images" \
  -e "UNALTRAWEB_PROJECT_USER=$owner" \
  --mount "$workspace_mount" \
  --mount "$mirror_mount" \
  -w "$project"

if [ -n "$storage_mount" ]; then
  set -- "$@" --mount "$storage_mount" \
    -e UNALTRAWEB_JOB_STORAGE_STATE=/var/lib/unaltraweb-job-storage \
    -e "UNALTRAWEB_JOB_STORAGE_HOST_STATE=$host_storage_state" \
    -e "UNALTRAWEB_JOB_STORAGE_ROOT_IDENTITY=$storage_identity"
fi

if [ -S "$docker_socket" ]; then
  socket_group="$(stat -c '%g' "$docker_socket")"
  socket_mount="$(/bin/sh "$script_dir/unaltraweb-docker-mount.sh" "$docker_socket" /var/run/docker.sock)"
  set -- "$@" --group-add "$socket_group" --mount "$socket_mount"
fi

exec "$@" "$resolved_image" --project "$project" mcp serve
