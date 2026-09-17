# Consumer Collaboration Contract

This package-managed file is the shared collaboration contract for an `unaltraweb` consumer. Update it through `scaffold_sync`; keep project-specific editorial rules in the repository's root `AGENTS.md`.

## Repository Model

- `main` is the only long-lived human-maintained branch. Never commit to it directly.
- Use one focused issue, one short-lived task branch, one editor or agent, and one pull request.
- Allow only one active editing session per repository, whether the editor works locally or in GitHub Web.
- A maintainer must accept an exact reservation before editing starts. Reserve repository-relative file paths, not broad directories or globs.
- A reservation limits the task and review scope; it does not authorize concurrent editing sessions. Add newly needed paths before touching them, and stop when another task already owns a path.

## Branch Names

Consumer branches use one of these forms:

- `content/<issue>-<slug>` for prose, teaching material, translations, and content metadata.
- `reference/<issue>-<slug>` for verified bibliography or reference data.
- `figure/<provider>/<issue>-<slug>` for a figure and its complete generated bundle.
- `integration/<provider>/<issue>-<slug>` for immutable provider or scaffold updates.
- `fix/<issue>-<slug>` for a site-specific defect that does not belong in the shared provider.

Reusable provider repositories use short-lived `format/<issue>-<slug>`, `feat/<issue>-<slug>`, `fix/<issue>-<slug>`, `docs/<issue>-<slug>`, or `chore/<issue>-<slug>` branches. Format and renderer implementation must not be copied into a consumer branch.

Use lowercase ASCII slugs. Do not create personal, agent-specific, permanent content, or permanent format branches.

## Checkout, Session, And Reservation

- Keep one primary mutable checkout for the repository and use its current task branch. Do not create a linked worktree for an editor or agent.
- Before local editing, run the MCP control plane's read-only checkout preflight. If the session requires a process-held cooperative lease, launch the editing command through the control plane's `exec` wrapper and hold the lease for the session.
- Never create, switch to, move, prune, repair, or remove Git worktrees implicitly. Report a stale or unexpected registration instead of altering it.
- For MCP-backed work, request one top-level MCP and let the control plane select its declared dependency closure. Existing unrelated registrations remain until explicitly removed and clients reconnect.
- Pass the consumer root only through `MCP_CONSUMER_WORKSPACE`; keep factory `build`, `check`, and `smoke` operations in the factory checkout.
- GitHub Web editors use the task branch created for their issue and never edit another task branch.
- Push the branch after reservation and open a Draft pull request after the first coherent change.
- Repeat the exact reserved paths in the Draft pull request so the reservation is visible without reading chat history.
- Do not stack branches unless the maintainer records the dependency in both issues and pull requests.

## Figures And Providers

- Reserve a generated figure as one atomic bundle: source, every local data/input file, output, caption-bearing content reference, and receipt, lock, or manifest entry.
- Edit authoritative computation, capture, diagram, or visualization sources. Never hand-edit renderer-owned outputs or receipts.
- Change reusable renderer, capture, web, or PDF behavior in its provider repository first.
- Merge and release the provider change before opening a separate consumer `integration/<provider>/...` pull request.
- Consumer integration must use an immutable release, full commit SHA, or image digest. Never integrate a provider branch, mutable tag, or sibling checkout.
- Record the provider repository and pull request, immutable revision, and affected consumer bundle in the integration issue and pull request.

## Pull Requests And Cleanup

- Keep the pull request in Draft while files or generated artefacts are incomplete.
- Change only reserved paths and review the complete diff before requesting review.
- Run every applicable source, render, web, PDF, and site check. Human review of visible output remains required.
- Resolve conflicts by coordination; never overwrite another reservation or unreviewed work.
- After merge or closure, release the reservation and any cooperative lease, delete the local and remote task branch, and retain the primary checkout. Never reuse the branch for another task.

Repository rulesets must block direct changes to `main`. A branch or merge does not publish the site; deployment remains an explicit maintainer action.
