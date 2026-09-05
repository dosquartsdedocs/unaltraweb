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
- [ ] If working locally, I used a dedicated worktree and did not share a mutable checkout.
- [ ] I confirmed that no other active editor is working on these files.
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
- [ ] After merge or closure, the reservation, worktree, and local/remote task branch will be removed.
