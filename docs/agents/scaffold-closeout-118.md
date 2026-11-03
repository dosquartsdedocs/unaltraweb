# Scaffold correction #115 / #118 — 0.7.4

This owner unit starts from published 0.7.3's post-release `main`
`2f9a8bdbc84a2ce5f5d10617174d36bcbde63f95`. The separate experimental #116 WIP
was checked against its retained source inventory and preserved without source
rewrites in **`6a8cd85ff75c8ad41dc67f8fb1c3c5a8f8919e53`**, branch
`feat/116-common-practice-sdk`. This scaffold correction does not contain that
checkpoint or close its QGIS/shared-runtime gates.

Implementation branch: `fix/118-reviewed-scaffold-resolution`. Clean preflight
was eligible after preservation. No worktree, stash, reset, manual checkout edit,
hub distribution edit or global cleanup is used.

## Coherent independent tuple

The source target for package, gem artifact and controller/runtime is **0.7.4**.
The native Git adapter explicitly selects:

- Core: `9d97197dec5fc9346ab795191a3afd18884c27fb`.
- `consumer_integration.core_gem_version`: **0.7.3**, matching that actual source.
- Workflow: `3332e0b93933f12317e05f1ce8d38ce80046feab`.
- PDF 0.7.1: `ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b`.
- Classic QGIS 0.6.1 and all other independent worker/companion pins are preserved.

The generated native Gemfile/lock use the selected core's gem version, not the
wheel's release version. The controller-only `consumer-core.json` declares that
version and binds it to the BOM's exact core SHA; `consumer_advisory.py` projects
it into the public target as `core_gem_version`. The shared retained-document
checker module **and schema** remain byte-identical to the core and PDF worker.
Source validation reads the immutable Git commit's
contract and rejects a mismatch. Doctor/update comparisons use independent
component targets, so a coherent 0.7.4 MCP / 0.7.3 Git core is not perpetually
reported as out of date. Docker's existing generated Bundler state still loads
the core bundled in its selected image; author Gemfile/lock bytes stay intact.

## Reviewed resolutions

The public `scaffold_sync` tool and CLI accept an optional `review` object.
Conflicted plans expose `review_inputs` and `resolution_options`, with exact
baseline, current, package and candidate-result hashes and UTF-8 review text.
The baseline is hash-only: these fields do not pretend to recover old source bytes.

Supported conservative decisions:

| Path | Mode | Preserved behavior |
| --- | --- | --- |
| `.gitignore` | `keep` | Keep the entire current byte sequence and inode. |
| `.gitignore` | `prepend-package` | Put package rules before the entire unmodified local sequence; local order and negation precedence remain last. |
| `.github/workflows/source-checks.yml` | `pins-only` | Replace only the two package/image env scalars. |
| `.github/workflows/deploy.yml` | `pins-only` | Replace only reusable-workflow, PDF-image and Vega-revision scalars. |

Workflow changes preserve every non-pin author value and all bytes outside the
pin scalars. Required controls and ordered steps must remain; extra independent
jobs/steps are preserved. Altered trigger/permission/concurrency controls, required
job execution modifiers, aliases, ambiguous keys, unsupported structures and
unsafe paths stay blocked. There is no arbitrary replacement-content or force API.

The existing staged-write, final CAS, no-clobber installation, manifest-last commit
and rollback implementation performs the writes. A concurrent author edit is
preserved with its original recovery backup when rollback cannot safely restore
that path. The next baseline retains the actual package hash, not a counterfeit
hash of a merged file. `reviewed_resolutions` records each decision and its hashes;
subsequent plans honestly show `preserved` / `current_customized` and detect later
upstream conflicts again.

## Public migration sequence

For each idle consumer, preserve its current work and use the normal project
admission/reservation flow. After the coordinator prepares the published package:

1. Obtain a fresh `site_context` and `scaffold_sync(dry_run=true)` plan. Never
   reuse the old 0.7.3 plans or manually modify `.unaltraweb/scaffold.json`.
2. Inspect each `review_inputs` row and the full proposed `resolution_options`.
   For #118's broad `/dist/` and QGIS exclusions, `keep` preserves exact local
   bytes; `prepend-package` is available if the additional package rules are
   desired with local priority. Do not narrow the existing rules.
3. Build a review containing the selected option's `path`, `mode`, all four hash
   fields (omit its display `content`) and a concise human-reviewed `reason`:

   ```json
   {
     "schema_version": 1,
     "kind": "unaltraweb-scaffold-review",
     "base_plan_sha256": "<fresh unresolved plan hash>",
     "files": [
       {
         "path": ".gitignore",
         "mode": "keep",
         "baseline_sha256": "<from option>",
         "local_sha256": "<from option>",
         "payload_sha256": "<from option>",
         "result_sha256": "<from option>",
         "reason": "Preserve broad dist and four QGIS state exclusions"
       }
     ]
   }
   ```

   Include reviewed `pins-only` entries for the source workflow and, where
   conflicted, deployment workflow. A missing baseline hash is the empty string
   only when that exact new-managed-file option says so.
4. Call `scaffold_sync(dry_run=true, review=...)`. All conflicts must be resolved;
   review the new `resolved`, `preserved`, target tuple and **resolved** plan hash.
5. Apply the same review with `dry_run=false`, `confirm_sync=true` and that hash
   as `expected_plan_sha256`. It is mandatory for reviewed resolutions. Changes
   to local bytes, config, baseline, payload, decisions or project invalidate it.
6. Inspect the next `site_context`/plan and run `site_check`. A valid preserved
   customization remains visible; it must not be reported as pristine upstream.
   Build/review through the consumer's native commands before its own publication.

CLI equivalent: `mcp scaffold-sync --review-json JSON` for the resolved dry-run,
then the same argument plus `--apply --confirm-sync --expected-plan-sha256 HASH`.
Git commits and manual publication remain separately coordinated owner actions.

## Acceptance record

`scripts/test_scaffold_release.py` uses actual installed wheels and synthetic
consumers. The old creator is the downloaded published 0.5.0 wheel; baseline
files are never hand-written. Local ignore rules and workflow guards are then
added as author customizations. The candidate's CLI prepares the reviewed plan,
its real installed MCP applies it, and the following state is
`current_customized` with no repeated update. A stale review is refused.

`tmp/scaffold-118/acceptance-02/acceptance.json` records actual network Git fetch,
frozen Bundler resolution and consumption of **gem0.7.3 at core9d97197…**. Jekyll
build succeeds using the same explicit core/site config combination as the
generated Makefile. Gemfile, lock, ignore and manifest bytes remain unchanged by
Bundler. The first test used a bare Jekyll invocation without the core config;
its failed build log remains in `acceptance-01`, separately from the already
successful Git/gem resolution it observed.

The implementation tests also cover real ignore negations, all-path conflicts,
required workflow guards, stale input/result/decision hashes, cross-project and
unsafe-path refusal, symlinks, rollback and concurrent-edit recovery. Wheel tests
compare the complete top-level module inventory against source, excluding stale
build-cache modules and the separate #116 checkpoint.

## Published delivery and post-release selection

[Release v0.7.4](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.7.4)
is public. PR119 supplies artifact source `676caa695d8e8f84a8a11800bb5a4a17599af539`;
PR120 supplies receipt/tag target `a0b82eadceac608a7e3ce97fb6d2fd2885dd541c`.
Annotated tag object: `7ef4525c33fd6ee4b9592deec23f1d87910a4581`.

- Controller: `ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:10bcaf1411f27a518969283a77e23dcc99119014b216270b3089ba85ba0b6c7e`.
- Runtime: `ghcr.io/dosquartsdedocs/unaltraweb@sha256:5d82d15358f2785e1a548f8d3d2a0e932602e3d9d7b4d1efa330fb774c65f5cb`.
- Wheel SHA256: `0202ff0982fea276a7ba775245faa7bafd75acc5cfad3e1f549055e87cd336ec`.
- Handoff: [release-handoff.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.7.4/release-handoff.json),
  SHA256 `aaf6256f438cdb4500b3d96081a7a6edd013c44b3411744aa6738b18decbffb2`.

Trusted Publishing `40388093852`, OCI promotion `40388094024` and tag CI
`40388002315` passed. All fourteen original assets were downloaded anonymously
and matched their exact sizes/hashes, including both Docker archives. PyPI and
RubyGems bytes and OCI aliases matched. The public
[verification receipt](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.7.4/verification.json)
has SHA256 `c19b46279100d48483ff544d87a3f88fae08d2bfc9b20f302628767ecaae8d09`.

The public wheel was installed in a new environment and passed the complete
synthetic installed-MCP, reviewed-conflict, stale-CAS and frozen Git/Bundler/Jekyll
acceptance: [acceptance.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.7.4/acceptance.json).
The first invocation refused relative paths before running; the completed run
uses the required absolute paths. #115/#118 are closed with the
[full delivery](https://github.com/dosquartsdedocs/unaltraweb/issues/118#issuecomment-6426018149).

The post-release checkout launcher now selects the published controller digest
above. Existing sessions keep their loaded image; consumer/hub selection and
author review remain independent of this source pin and technical delivery.
