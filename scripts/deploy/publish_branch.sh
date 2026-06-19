#!/usr/bin/env bash
set -euo pipefail

PUBLISH_REMOTE="${PUBLISH_REMOTE:-origin}"
PUBLISH_BRANCH="${PUBLISH_BRANCH:-gh-pages}"
PUBLISH_SOURCE="${PUBLISH_SOURCE:-_site}"
PUBLISH_WORKTREE="${PUBLISH_WORKTREE:-tmp/publish-${PUBLISH_BRANCH}}"
PUBLISH_DRY_RUN="${PUBLISH_DRY_RUN:-0}"
PUBLISH_PREPARE_ONLY="${PUBLISH_PREPARE_ONLY:-0}"
PUBLISH_ALLOW_PROTECTED_BRANCH="${PUBLISH_ALLOW_PROTECTED_BRANCH:-0}"

die() {
  printf 'publish_branch: %s\n' "$*" >&2
  exit 1
}

is_true() {
  case "${1:-0}" in
    1|true|TRUE|yes|YES|y|Y) return 0 ;;
    *) return 1 ;;
  esac
}

case "$PUBLISH_BRANCH" in
  main|master)
    is_true "$PUBLISH_ALLOW_PROTECTED_BRANCH" || die "refusing to publish to protected branch '$PUBLISH_BRANCH'"
    ;;
esac

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || die "run from inside a git repository"
cd "$repo_root"

git diff-index --quiet HEAD -- || die "working tree has uncommitted tracked changes"

untracked="$(git ls-files --exclude-standard --others)"
if test -n "$untracked"; then
  printf '%s\n' "$untracked" >&2
  die "working tree has untracked files"
fi

test -d "$PUBLISH_SOURCE" || die "publish source '$PUBLISH_SOURCE' does not exist; run the build first"

source_abs="$(cd "$PUBLISH_SOURCE" && pwd)"
worktree_abs="$repo_root/$PUBLISH_WORKTREE"
source_rev="$(git rev-parse --short HEAD)"
message="${PUBLISH_MESSAGE:-Publish site from ${source_rev}}"

git worktree remove --force "$worktree_abs" >/dev/null 2>&1 || true
mkdir -p "$(dirname "$worktree_abs")"
git worktree add --detach "$worktree_abs" HEAD >/dev/null

(
  cd "$worktree_abs"
  git rm -r --ignore-unmatch . >/dev/null
  cp -a "$source_abs"/. .
  if test -f "$repo_root/CNAME" && ! test -f CNAME; then
    cp "$repo_root/CNAME" CNAME
  fi
  touch .nojekyll

  if ! git config user.name >/dev/null; then
    git config user.name "unaltraweb local publish"
  fi
  if ! git config user.email >/dev/null; then
    git config user.email "unaltraweb-local-publish@example.invalid"
  fi

  git add -A
  git commit --allow-empty -m "$message" >/dev/null
)

printf 'Prepared %s from %s in %s\n' "$PUBLISH_BRANCH" "$PUBLISH_SOURCE" "$PUBLISH_WORKTREE"

if is_true "$PUBLISH_DRY_RUN" || is_true "$PUBLISH_PREPARE_ONLY"; then
  printf 'Dry run or prepare-only mode: not pushing. Inspect with:\n'
  printf '  git -C %s log --oneline -1\n' "$PUBLISH_WORKTREE"
  exit 0
fi

git -C "$worktree_abs" push --force "$PUBLISH_REMOTE" "HEAD:refs/heads/$PUBLISH_BRANCH"
