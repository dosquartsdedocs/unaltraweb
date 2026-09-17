Read `.github/CONTRIBUTING.md` before editing.

## Task And Reservation

Closes #

Work type: <!-- content | reference | figure/<provider> | integration/<provider> | fix -->

Exact reserved paths:

<!-- Add one repository-relative file path per line. Do not use directories or globs. -->

## Generated Figure Bundle

<!-- When applicable, list source, data/inputs, output, content reference, and receipt/lock/manifest paths. -->

Provider repository and pull request:

Immutable provider release, SHA, or digest:

## Editor Checklist

- [ ] I was assigned to the issue or a maintainer accepted my explicit file reservation.
- [ ] This is one task on a correctly named short-lived branch; I did not edit `main` directly.
- [ ] I confirmed this was the repository's only active editing session; the reservation limited scope rather than permitting concurrent edits.
- [ ] If working locally, I used the primary mutable checkout, ran the read-only checkout preflight, and did not create or manipulate a linked worktree.
- [ ] If the session required a process-held cooperative lease, I launched it through the control plane's `exec` wrapper.
- [ ] For MCP-backed work, I passed the consumer root through `MCP_CONSUMER_WORKSPACE` and requested one top-level MCP with its declared dependency closure.
- [ ] This pull request contains only the exact reserved paths.
- [ ] I opened this as a Draft pull request and reviewed the **Files changed** tab.
- [ ] Images use approved content paths, safe unique filenames, publishable material, and meaningful alternative text.
- [ ] Renderer-owned outputs and receipts were regenerated from their authoritative sources rather than hand-edited.
- [ ] Provider changes were completed upstream and this consumer uses only an immutable integration revision.
- [ ] I did not add credentials or unrelated technical controls.
- [ ] If I encountered a conflict, I stopped and asked the maintainer instead of resolving it by overwriting work.

## Maintainer Review

- [ ] The issue, assignment or reservation, branch, and changed-file scope agree.
- [ ] Required local checks and renders pass.
- [ ] Rendered web output and any generated manual PDF/cover were reviewed.
- [ ] The pull request is ready to leave Draft and merge into `main`.
- [ ] If publication is intended, deployment will be started manually only after merge.
- [ ] After merge or closure, the reservation, cooperative lease, and local/remote task branch will be released or removed; the primary checkout will be retained.
