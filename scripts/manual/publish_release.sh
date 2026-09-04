#!/usr/bin/env bash
set -euo pipefail

if (($# != 0)); then
  echo "publish_release.sh does not accept caller-controlled arguments." >&2
  exit 2
fi

required_environment=(
  CANDIDATE_MANIFEST_SHA256
  CORE_SHA
  GH_TOKEN
  GITHUB_REPOSITORY
  MANUAL_PDF_IMAGE
  PYTHON_VERSION
  REVIEWED_SHA
  RUBY_VERSION
  RUNNER_TEMP
  SELECTOR
  SITE_BUILD_IMAGE
  WORKFLOW_FILE_PATH
  WORKFLOW_REF
  WORKFLOW_REPOSITORY
  WORKFLOW_SHA
)
for variable in "${required_environment[@]}"; do
  if [[ -z "${!variable:-}" ]]; then
    echo "Required release environment is missing: $variable" >&2
    exit 1
  fi
done

if [[ "$WORKFLOW_REPOSITORY" != "dosquartsdedocs/unaltraweb" ]] || [[ "$WORKFLOW_FILE_PATH" != ".github/workflows/site-release.yml" ]]; then
  echo "Stable publication must run from the canonical reusable workflow." >&2
  exit 1
fi
if [[ ! "$WORKFLOW_SHA" =~ ^[0-9a-f]{40}$ ]] || [[ "$CORE_SHA" != "$WORKFLOW_SHA" ]]; then
  echo "The release tooling revision does not match the defining workflow revision." >&2
  exit 1
fi
if [[ "$WORKFLOW_REF" != "$WORKFLOW_REPOSITORY/$WORKFLOW_FILE_PATH@$CORE_SHA" ]]; then
  echo "The reusable stable workflow was not invoked by its immutable commit SHA." >&2
  exit 1
fi
if [[ ! "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "GITHUB_REPOSITORY is not a canonical owner/repository name." >&2
  exit 1
fi
if [[ "$(git -C .unaltraweb-release-core rev-parse HEAD)" != "$WORKFLOW_SHA" ]] || \
   [[ -n "$(git -C .unaltraweb-release-core status --porcelain=v1 --untracked-files=all)" ]]; then
  echo "The privileged release tooling checkout is not the exact reviewed revision." >&2
  exit 1
fi
actual_python="$(python3 -c 'import platform; print(platform.python_version())')"
if [[ "$actual_python" != "$PYTHON_VERSION" ]]; then
  echo "The privileged verifier Python version does not match python_version." >&2
  exit 1
fi

verify_assets=(
  python3 .unaltraweb-release-core/scripts/manual/verify_release_assets.py
  --selector "$SELECTOR"
  --reviewed-sha "$REVIEWED_SHA"
  --core-sha "$CORE_SHA"
  --manual-pdf-image "$MANUAL_PDF_IMAGE"
  --python-version "$PYTHON_VERSION"
  --ruby-version "$RUBY_VERSION"
  --site-build-image "$SITE_BUILD_IMAGE"
  --vegavisuals-sha "${VEGAVISUALS_SHA:-}"
  --repository "$GITHUB_REPOSITORY"
  --candidate-manifest-sha256 "$CANDIDATE_MANIFEST_SHA256"
)
"${verify_assets[@]}" --assets release-assets

notes="$RUNNER_TEMP/release-notes.md"
printf 'Stable manual %s\n\nSource commit: `%s`\nCore commit: `%s`\n' \
  "$SELECTOR" "$REVIEWED_SHA" "$CORE_SHA" > "$notes"

shopt -s nullglob
pdf_assets=(release-assets/*.pdf)
if ((${#pdf_assets[@]} == 0)); then
  echo "The verified release has no standalone PDF assets." >&2
  exit 1
fi
release_assets=(
  release-assets/SHA256SUMS
  release-assets/publication.json
  release-assets/release-manifest.json
  "release-assets/manual-site-$SELECTOR.tar.gz"
  "${pdf_assets[@]}"
)
python3 - "$RUNNER_TEMP/expected-release-assets.json" "${release_assets[@]}" <<'PY'
import json
import os
import sys

names = []
for raw in sys.argv[2:]:
    if not os.path.isfile(raw) or os.path.islink(raw):
        raise SystemExit(f"Release asset is not a regular file: {raw}")
    names.append(os.path.basename(raw))
if len(names) != len(set(names)):
    raise SystemExit("Release asset names are not unique.")
with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
    json.dump(sorted(names), handle)
    handle.write("\n")
PY

gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases?per_page=100" > "$RUNNER_TEMP/releases.json"
releases="$(jq -c --arg selector "$SELECTOR" '[.[][] | select(.tag_name == $selector)]' "$RUNNER_TEMP/releases.json")"
release_count="$(jq 'length' <<<"$releases")"
if [[ "$release_count" -gt 1 ]]; then
  echo "More than one release uses tag $SELECTOR; refusing an ambiguous resume." >&2
  exit 1
fi
release_id=""
if [[ "$release_count" == 1 ]]; then
  release_draft="$(jq -r '.[0].draft' <<<"$releases")"
  release_tag="$(jq -r '.[0].tag_name' <<<"$releases")"
  release_id="$(jq -r '.[0].id' <<<"$releases")"
  if [[ "$release_draft" != "true" ]] || [[ "$release_tag" != "$SELECTOR" ]] || [[ ! "$release_id" =~ ^[0-9]+$ ]]; then
    echo "An existing release is published or does not match the reviewed tag." >&2
    exit 1
  fi
fi

gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/git/matching-refs/tags/$SELECTOR?per_page=100" \
  > "$RUNNER_TEMP/tags.json"
tags="$(jq -c --arg ref "refs/tags/$SELECTOR" '[.[][] | select(.ref == $ref)]' "$RUNNER_TEMP/tags.json")"
tag_count="$(jq 'length' <<<"$tags")"
if [[ "$tag_count" -gt 1 ]]; then
  echo "More than one exact Git ref matches $SELECTOR." >&2
  exit 1
fi
if [[ "$tag_count" == 1 ]]; then
  tag_sha="$(jq -r '.[0].object.sha' <<<"$tags")"
  tag_type="$(jq -r '.[0].object.type' <<<"$tags")"
  if [[ "$tag_type" != "commit" ]] || [[ "$tag_sha" != "$REVIEWED_SHA" ]]; then
    echo "Tag $SELECTOR is not a lightweight tag at the reviewed commit." >&2
    exit 1
  fi
else
  gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs" \
    -f ref="refs/tags/$SELECTOR" -f sha="$REVIEWED_SHA" >/dev/null
fi

tag_json="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$SELECTOR")"
if [[ "$(jq -r .object.type <<<"$tag_json")" != "commit" ]] || \
   [[ "$(jq -r .object.sha <<<"$tag_json")" != "$REVIEWED_SHA" ]]; then
  echo "The release tag changed after it was bound to the reviewed commit." >&2
  exit 1
fi

draft_payload() {
  jq -n \
    --arg tag "$SELECTOR" \
    --arg title "$SELECTOR" \
    --rawfile body "$notes" \
    '{tag_name: $tag, name: $title, body: $body, draft: true, prerelease: false, make_latest: "false"}'
}

if [[ -z "$release_id" ]]; then
  release_json="$(draft_payload | gh api --method POST "repos/$GITHUB_REPOSITORY/releases" --input -)"
  release_id="$(jq -r .id <<<"$release_json")"
  if [[ ! "$release_id" =~ ^[0-9]+$ ]]; then
    echo "GitHub did not return a numeric release ID." >&2
    exit 1
  fi
fi

release_json="$(draft_payload | gh api --method PATCH "repos/$GITHUB_REPOSITORY/releases/$release_id" --input -)"
jq -e \
  --arg tag "$SELECTOR" \
  --arg title "$SELECTOR" \
  --rawfile body "$notes" \
  '.draft == true and .prerelease == false and .tag_name == $tag and .name == $title and .body == $body' \
  <<<"$release_json" >/dev/null

gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases/$release_id/assets?per_page=100" \
  > "$RUNNER_TEMP/existing-release-assets.json"
jq -e 'all(.[][]; (.id | type) == "number")' "$RUNNER_TEMP/existing-release-assets.json" >/dev/null
jq -r '.[][] | .id' "$RUNNER_TEMP/existing-release-assets.json" > "$RUNNER_TEMP/existing-release-asset-ids"
while IFS= read -r asset_id; do
  [[ -z "$asset_id" ]] && continue
  gh api --method DELETE "repos/$GITHUB_REPOSITORY/releases/assets/$asset_id"
done < "$RUNNER_TEMP/existing-release-asset-ids"

for asset in "${release_assets[@]}"; do
  name="${asset##*/}"
  encoded_name="$(jq -rn --arg value "$name" '$value | @uri')"
  response="$(curl --fail-with-body --silent --show-error \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    -H 'Content-Type: application/octet-stream' \
    --data-binary "@$asset" \
    "https://uploads.github.com/repos/$GITHUB_REPOSITORY/releases/$release_id/assets?name=$encoded_name")"
  asset_size="$(stat -c %s -- "$asset")"
  jq -e --arg name "$name" --argjson size "$asset_size" \
    '.name == $name and .state == "uploaded" and .size == $size and (.id | type) == "number"' \
    <<<"$response" >/dev/null
done

downloaded_assets="$(mktemp -d "$RUNNER_TEMP/uploaded-release-assets.XXXXXX")"
cleanup() {
  rm -rf -- "$downloaded_assets"
}
trap cleanup EXIT

release_json="$(gh api "repos/$GITHUB_REPOSITORY/releases/$release_id")"
jq -e \
  --arg tag "$SELECTOR" \
  --arg title "$SELECTOR" \
  --rawfile body "$notes" \
  '.draft == true and .prerelease == false and .tag_name == $tag and .name == $title and .body == $body' \
  <<<"$release_json" >/dev/null
gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases/$release_id/assets?per_page=100" \
  > "$RUNNER_TEMP/uploaded-release-assets-api.json"
jq -e --slurpfile expected "$RUNNER_TEMP/expected-release-assets.json" '
  [.[][]] as $assets |
  ($assets | length) == ($expected[0] | length) and
  ([$assets[].name] | sort) == ($expected[0] | sort) and
  all($assets[]; (.id | type) == "number" and (.name | type) == "string" and .state == "uploaded")
' "$RUNNER_TEMP/uploaded-release-assets-api.json" >/dev/null
jq -S '[.[][] | {digest, id, name, size, state, updated_at}] | sort_by(.name)' \
  "$RUNNER_TEMP/uploaded-release-assets-api.json" > "$RUNNER_TEMP/uploaded-release-assets-inventory.json"
jq -r '.[][] | [.id, .name] | @tsv' "$RUNNER_TEMP/uploaded-release-assets-api.json" \
  > "$RUNNER_TEMP/uploaded-release-assets.tsv"
while IFS=$'\t' read -r asset_id asset_name; do
  [[ "$asset_id" =~ ^[0-9]+$ ]]
  gh api -H 'Accept: application/octet-stream' \
    "repos/$GITHUB_REPOSITORY/releases/assets/$asset_id" > "$downloaded_assets/$asset_name"
done < "$RUNNER_TEMP/uploaded-release-assets.tsv"

"${verify_assets[@]}" --assets "$downloaded_assets" --reference-assets release-assets

tag_json="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$SELECTOR")"
if [[ "$(jq -r .object.type <<<"$tag_json")" != "commit" ]] || \
   [[ "$(jq -r .object.sha <<<"$tag_json")" != "$REVIEWED_SHA" ]]; then
  echo "The release tag changed before publication." >&2
  exit 1
fi
release_json="$(gh api "repos/$GITHUB_REPOSITORY/releases/$release_id")"
jq -e \
  --arg tag "$SELECTOR" \
  --arg title "$SELECTOR" \
  --rawfile body "$notes" \
  '.draft == true and .prerelease == false and .tag_name == $tag and .name == $title and .body == $body' \
  <<<"$release_json" >/dev/null
gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases/$release_id/assets?per_page=100" \
  > "$RUNNER_TEMP/current-release-assets-api.json"
jq -S '[.[][] | {digest, id, name, size, state, updated_at}] | sort_by(.name)' \
  "$RUNNER_TEMP/current-release-assets-api.json" > "$RUNNER_TEMP/current-release-assets-inventory.json"
cmp -- "$RUNNER_TEMP/uploaded-release-assets-inventory.json" "$RUNNER_TEMP/current-release-assets-inventory.json"

published_payload="$(jq -n \
  --arg tag "$SELECTOR" \
  --arg title "$SELECTOR" \
  --rawfile body "$notes" \
  '{tag_name: $tag, name: $title, body: $body, draft: false, prerelease: false, make_latest: "false"}')"
published="$(gh api --method PATCH "repos/$GITHUB_REPOSITORY/releases/$release_id" --input - <<<"$published_payload")"
jq -e \
  --arg tag "$SELECTOR" \
  --arg title "$SELECTOR" \
  --rawfile body "$notes" \
  '.draft == false and .prerelease == false and .tag_name == $tag and .name == $title and .body == $body' \
  <<<"$published" >/dev/null

tag_json="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$SELECTOR")"
if [[ "$(jq -r .object.type <<<"$tag_json")" != "commit" ]] || \
   [[ "$(jq -r .object.sha <<<"$tag_json")" != "$REVIEWED_SHA" ]]; then
  echo "The release tag changed during publication." >&2
  exit 1
fi
published="$(gh api "repos/$GITHUB_REPOSITORY/releases/$release_id")"
jq -e \
  --arg tag "$SELECTOR" \
  --arg title "$SELECTOR" \
  --rawfile body "$notes" \
  '.draft == false and .prerelease == false and .tag_name == $tag and .name == $title and .body == $body' \
  <<<"$published" >/dev/null
