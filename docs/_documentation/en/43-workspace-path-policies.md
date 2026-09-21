---
title: Workspace Path Policies And Consumer Updates
description: File ownership, Git expectations, PDF recovery and safe consumer migration.
lang: en
ref: workspace_path_policies
profiles:
- unaltredocs
documentation_profiles:
- core-developers
section: Core Development
weight: 625
permalink: "/workspace-path-policies/"
nav_title: Workspace Path Policies
---

The discovery manifest `mcp-factory.yml` declares literal consumer-relative
`workspace_rule.path_policies`, under schema version 1, `binding: consumer` and
`consumer_root: .`. The central `my-scripts-factory` manager checks these policies
without launching a provider. `MCP_CONSUMER_WORKSPACE` still carries the absolute
consumer workspace through the `make -C` stdio launcher; the factory checkout
does not become the consumer.

## Policy Meaning

- `git: ignored` requires actual Git ignore coverage, including inherited parent
  rules, and rejects indexed files anywhere under that path. Merely adding an
  ignore rule does not untrack files.
- `git: versioned` permits an absent path. An existing path must be indexed and
  not ignored. Stage reviewed source files before checking a freshly created site.
- `git: consumer` reports the observed Git state without imposing a decision.
- `cleanup: disposable`, `explicit` and `never` are descriptive metadata, not
  deletion authority. `workspace-check` never performs cleanup. `down` manages
  labelled runtime resources, not the consumer filesystem.

Missing optional paths do not enable a feature or create files. An absent ignored
directory still needs an ignore rule; a trailing-slash rule works before that
directory exists. In a non-Git directory the manager reports `not_applicable`,
which is not evidence that a future Git repository is compliant.

## Adopted Literal Paths

| Path | Type | Role | Git | Cleanup |
| --- | --- | --- | --- | --- |
| `_site` | directory | jekyll-build-output | ignored | disposable |
| `tmp` | directory | build-staging-and-local-release-evidence | ignored | explicit |
| `.cache/scimago` | directory | external-bibliometrics-input-cache | ignored | explicit |
| `.cache/unaltraweb/manual-pdf-publication-intent.json` | file | pdf-publication-recovery-intent | ignored | explicit |
| `.cache/unaltraweb/manual-pdf-publication.json` | file | pdf-publication-provenance | ignored | explicit |
| `.cache/unaltraweb/manual-pdf-preview.json` | file | pdf-preview-ownership-receipt | ignored | explicit |
| `.cache/unaltraweb/manual-pdf-preview.lock` | file | pdf-preview-coordination-lock | ignored | explicit |
| `.cache/unaltraweb/manual-pdf-preview-recovery` | directory | pdf-preview-retained-recovery-backups | ignored | explicit |
| `_config.yml` | file | consumer-site-configuration | versioned | never |
| `.unaltraweb/scaffold.json` | file | managed-scaffold-baseline | versioned | never |
| `.unaltraweb/docker-mount.sh` | file | managed-docker-mount-helper | versioned | never |
| `.unaltraweb/computations.yml` | file | optional-consumer-computation-configuration | versioned | never |
| `.unaltraweb/computations.lock.json` | file | computation-output-provenance | consumer | explicit |

`_site` is the normal Jekyll output and can be rebuilt from retained sources,
inputs and runtimes. It is not the authoritative copy of editorial assets. This
does not promise byte-identical rebuilds after external inputs or runtimes change,
nor extend the policy to a custom Jekyll destination. Removing `_site` invalidates
any site-build evidence that refers to its previous contents.

`tmp` mixes Bundler files, render staging and locks, draft PDFs, the site-build
receipt (`tmp/.unaltraweb/site-build.json`) and local release candidates
(`tmp/manual-release`). A candidate may be the only retained record of reviewed
bytes. Review and preserve evidence and finish active operations before deliberate
cleanup; the entire tree is not unconditionally regenerable. The existing
consumer `make clean` is a separate explicit operation and refuses to discard
drafts while a preview receipt remains.

Scimago is downloaded from a mutable upstream URL or supplied as a local input.
Deleting `.cache/scimago` can lose the exact dataset used for bibliometrics. The
cache's default path is fixed, but scripts can select another input/output path;
this declaration does not cover such alternatives. Preserve the needed bytes and
provenance before cleanup. Normal builds do not fetch metrics.

`_config.yml` is consumer-owned. The scaffold baseline and Docker mount helper
are package-managed controls; the baseline is essential to distinguish package
updates from local edits. Computation configuration is created only for the
manual profile and stays consumer-owned so it can declare project inputs and
worker extensions. Its lock records output hashes, source fingerprints and image
identity; it is generated metadata, not a disposable execution lock. Consumers
usually version it with generated Markdown/figures, but this rollout does not
force that choice.

## PDF Recovery Is Not Disposable Cache

`src/unaltraweb_mcp/manual_pdf_preview.py` owns the five fixed PDF-state paths:

1. Publication intent records expected hashes before a confirmed copy, allowing
   interrupted publication to be reconciled even if draft artefacts disappear.
2. Publication provenance records the identity of deployment products without
   granting preview cleanup ownership over those products.
3. The preview receipt records exactly which ignored, untracked copies the
   preview operation owns. Cleanup requires a dry-run, explicit confirmation and
   that receipt's SHA-256, then rechecks identity, hashes, modes and Git state.
4. The visible lock and an advisory lock on the project directory coordinate
   operations. Removing the lock marker is not an unlock or recovery procedure.
5. Recovery backups preserve originals or concurrent edits when rollback cannot
   safely restore them. Failures can also report retained backups beside an
   output; those configurable locations are not covered by a broad asset policy.

Keep receipts, recovery files and their corresponding outputs together until the
owning operation is reconciled. Use `manual_pdf_preview_clean` for unchanged
receipt-owned copies, and inspect reported recovery paths when automatic recovery
fails. Never delete receipts to make an unmanaged collision disappear. This
adoption does not change confirmation, no-clobber, locking or rollback behavior.

## Provider And Editorial Boundaries

The installable dependency closure is `diavisuals`, `vegavisuals`, `unaltraweb`:
`factory_count: 3`, `dependency_factory_count: 2`. Each manifest keeps its own
binding and root. Unaltraweb does not redeclare these provider policies:

- Diavisuals owns `.cache/diavisuals` (ignored/disposable) and
  `.unaltraweb/receipts/diavisuals.json` (consumer/explicit).
- Vegavisuals owns `.cache/vegavisuals` (ignored/explicit, including publication
  recovery), `.vegavisuals.yml` (versioned/never), `.vegavisuals.lock.json` and
  `.unaltraweb/receipts/vegavisuals.json` (both consumer/explicit).

Receipts prove freshness; their presence in `generated_paths` does not imply
ignored or disposable state. `site_check` still validates their contents when
sources require them. Workspace compliance does not establish rendering freshness.

The initial selection deliberately leaves these paths without new policies:

- PDF and cover destinations and PDF build directories are configurable. The
  runtime checks the actual paths; the manual scaffold renders exact ignore rules
  from configuration. No `assets/pdf` or `assets/img` blanket policy is safe.
- Computation outputs, rendered diagrams, original capture PNGs, annotated SVGs
  and author-owned edited variants have source-dependent destinations. Preserve
  originals and edited variants and regenerate only through the owning tool after
  reviewing freshness and overwrite requirements. No glob is a literal policy.
- `.unaltraweb/web-captures.lock.json` remains runtime-managed provenance under
  the existing consumer versioning decision, outside this initial minimal list.
- Other Jekyll/Quarto caches retain existing ignore rules without a new universal
  cleanup declaration. Neither `assets`, `.cache` nor `.unaltraweb` is classified
  as one disposable tree.

## What Needs Updating

| Change | Required action |
| --- | --- |
| This discovery-policy adoption | Use a reviewed unaltraweb factory revision containing these declarations and a central manager with path-policy and installable-closure support. |
| Current v0.4.0 package/image | Already compatible; no rebuild, republish or pin change is required solely for workspace checks. The wheel does not ship the root discovery manifest. |
| Runtime or package scaffold changes in a later release | Install/select the reviewed package or MCP image containing those changes; reconnect an already-running MCP. Updating a discovery checkout alone does not replace its pinned runtime. |
| Older or drifted consumer controls | Review `scaffold_sync` against the selected package. Apply only after resolving conflicts deliberately. |
| Local ignores, tracked cache files, computation locks, renderer receipts or edited outputs | Consumer decision, in its own issue/branch and reviewed diff. No automatic migration or mass regeneration. |

The four v0.4.0 profile scaffolds already ignore `_site/`, `tmp/` and `.cache/`.
That parent rule also covers both renderer caches, including absent directories.
They create the common versioned controls; only `unaltremanual` creates
`.unaltraweb/computations.yml`. The optional `.vegavisuals.yml` is not required in
other profiles. This change leaves package assets, the managed file set and
`.unaltraweb/scaffold.json` schema/hashes unchanged.

## Existing Consumer Procedure

1. In that consumer's own session, inspect root, branch, status, upstream and
   existing reservations. Run session preflight on a clean short-lived branch.
   Preserve unrelated local work. Record the reviewed discovery commit and
   central manager revision in the integration issue.
2. Inspect `Makefile` (`MCP_IMAGE`, `MANUAL_PDF_IMAGE`), `Gemfile`, `Gemfile.lock`,
   `.github/workflows/deploy.yml`, `.unaltraweb/scaffold.json` and
   `distribution_doctor`. Use the published v0.4.0 package/image for the existing
   compatible scaffold, or a later explicitly reviewed release. Do not move the
   immutable v0.4.0 release or install an unpublished branch as a consumer runtime.
3. Call `scaffold_sync(dry_run=true)`. It manages exactly `.gitignore`,
   `.unaltraweb/docker-mount.sh`, `.github/CONTRIBUTING.md`,
   `.github/dependabot.yml`, `.github/pull_request_template.md`,
   `.github/workflows/deploy.yml`, `Makefile`, `Gemfile` and `Gemfile.lock`, with
   `.unaltraweb/scaffold.json` written last. Reserve the actual changed paths.
   `_config.yml`, README, AGENTS and editorial files are not synchronized.
4. A customized `.gitignore` or edited managed file causes a conflict and prevents
   the entire apply. Compare current bytes with the recorded baseline and package
   proposal; preserve local rules and ask the owner which changes to integrate.
   Do not forge baseline hashes, force overwrites, or remove a colliding local
   artefact. Exact current package bytes can be adopted; remaining customizations
   may intentionally remain conflicts. Policy compliance does not require
   overwriting a customized file merely to obtain a clean sync report.
5. Where the reviewed plan is conflict-free, call
   `scaffold_sync(dry_run=false, confirm_sync=true)`. A current v0.4.0 consumer
   needs no scaffold writes for this policy adoption. Inspect Git ignore matches
   and indexed descendants of every ignored policy. Decisions to untrack existing
   files require consumer review; keep the actual files and any recovery evidence.
6. Stage only reviewed versioned sources/controls (including an optional Vega
   manifest if present). Run the manager against the absolute consumer path:

   ```bash
   python3 /path/to/my-scripts-factory/src/bash/mcp_factories/mcp-factory-manager.py \
     workspace-check --dir /path/to/factories --factory unaltraweb \
     --workspace /absolute/consumer --json
   ```

   Expect all three factories with zero findings/errors. Do not bypass the
   installable dependencies. Inspect each resolved root. The command is read-only;
   it does not stage sources, repair ignores, build images or run provider checks.
7. Run `site_check` and resolve blocking findings before `build_site` or
   `make test`. For a local manual PDF review, call
   `manual_pdf_preview_prepare` before a direct MCP build/preview (managed Make
   targets already do this). Review the website/PDF, then dry-run and confirm
   receipt-bound `manual_pdf_preview_clean`. If an unmanaged PDF/cover already
   exists, preserve it and resolve ownership rather than deleting it automatically.
8. No artefact needs regeneration merely because discovery metadata changed.
   If actual inputs, sources or runtimes changed, inspect computation/capture and
   provider status and explicitly render only affected outputs under a separate
   accepted reservation. Complete the consumer PR and human review; publication
   remains a separate manual action.

## Maintainer Verification

Normal unit tests cover declarations, all four packaged profiles and sync conflict
preservation. Central-manager integration tests are opt-in so the package does
not acquire a sibling-checkout runtime dependency:

```bash
UNALTRAWEB_FACTORY_MANAGER=/path/to/my-scripts-factory/src/bash/mcp_factories/mcp-factory-manager.py \
UNALTRAWEB_FACTORIES_DIR=/path/to/factories \
PYTHONPATH=src python3 -m unittest discover -s test -p 'test_workspace_path_policies.py' -v
```

`test/workspace_consumer_smoke.py` exercises the actual `make -C` Docker stdio
launcher with an external temporary consumer, all four `new_web` profiles,
`scaffold_sync`, indexed policy sources, closure snapshots, `site_check` and a
representative `build_site`. Use its explicit manager/discovery paths and image
arguments; it never registers an MCP or edits a real consumer. Existing PDF
preview/recovery unit tests and Docker PDF integrations remain the recovery gates.
