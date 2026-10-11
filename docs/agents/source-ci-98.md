# Shared public-source CI — Web #98

One implementation lives in `unaltraweb_mcp.source_checks`. The package-owned
control `.github/workflows/source-checks.yml` is identical for the three manuals;
only `.unaltraweb/source-checks.json` contains project-specific data. It is a
source-conservation lane, not a site build or retained-input validation lane.

## GitHub visibility and installation boundary

[GitHub's reusable-workflow access table](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#access-to-reusable-workflows)
allows public callers to use public workflows, not private ones. Cross-owner
private access must therefore not be assumed. The repository API reported Web
as `PUBLIC` during this inspection; the design does not depend on that visibility
remaining public and no visibility setting was changed.

The local scaffold control uses public, SHA-pinned GitHub actions and the public
PyPI package. It does not call a private factory workflow or download code from a
mutable factory checkout. Public PyPI 0.7.1 and anonymous access to the selected
checker-image manifest were verified. The new runner is intended for **0.7.2**:
the prepared 0.7.2 control must be activated after that package is published.
Public 0.7.1 does not contain this entrypoint. A missing runner/install/report is
a failed/incomplete job, never a successful omission.

The runner is installed into a fresh runner-temporary venv with isolated Python
and pip, `--only-binary=:all:`, and `--no-deps`. It uses the standard library and
existing native subprocess/lifecycle helpers. Project `requirements.txt`, Python,
R, shell, models and configuration programs are never executed to discover policy.

The controller used for the existing checkers is independently pinned:

```text
ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6
```

Acquisition of this public image is explicit in the workflow. During checking,
containers use `--pull never`, network `none`, a readonly root and clone mount,
no Docker socket, 2 CPU / 4 GiB / 512 PIDs and a bounded tmpfs. The existing exact
session lifecycle handles their native labels/CIDs; the runner does not implement
another resource manager.

## Common control and site-owned parameters

The source template is:

```text
src/unaltraweb_mcp/scaffolds/common/.github/workflows/source-checks.yml.tmpl
```

It is rendered once per package version and checker-image selection, without
project title/language/profile substitutions. `new_web` includes it in the managed
scaffold baseline. A changed local workflow remains protected by the existing
no-clobber/conflict/CAS synchronization rules. The JSON policy is seeded for new
sites but remains site-owned and is never overwritten by `scaffold_sync`.

Example manual policy:

```json
{
  "schema_version": 1,
  "profile": "unaltremanual",
  "public_roots": ["_chapters", "_pages"],
  "practice_roots": ["practiques", "_practices"],
  "data_roots": ["sandbox", "dist", "assets/pdf"],
  "allow_empty_public_sources": false
}
```

The exact schema is packaged as `source-check-policy-v1.schema.json`. Policy is
bounded strict JSON in a regular, committed Git blob. Unknown keys (including
commands), duplicate keys/roots, traversal and Git-internal roots are refused.
Other site profiles use the same control with their declared public roots.

Add every activity's data/output directory to `data_roots`, including directories
holding JSON datasets. Within practice roots, source formats such as Markdown,
JSON/YAML recipes, Python/R, notebooks, `.model3`, QML/SLD and authored SVG remain
eligible. Other formats, including PDF/ZIP, raster/vector datasets and captures,
are refused when new or modified. JSON or SVG cannot be semantically classified
as code versus data by filename alone: declared data roots take precedence and
block all new/changed files there. Reproduction sources belong outside those roots.

Legacy means the **same path, mode, type and Git object** as the baseline. Such
tracked data is listed as `legacy_unchanged`, not deleted or silently migrated.
New copies/renames or modified binary bytes are not grandfathered. Deletions are
allowed. Base and head data/practice roots are combined for the PR; the same PR
cannot evade its baseline restrictions by narrowing policy. Public scope and the
empty-coverage guard similarly retain the baseline requirement until a reviewed
policy change becomes the next baseline.

## Exact scope and reports

The runner invokes the existing `profile-check` and `prose-check` CLIs. A separate
`content-approval-inventory` call is an observation for the draft/status summary,
not an approval check or promotion. The last call's bounded sample is explicitly
marked partial when counts exceed the sample. Private handouts outside those
native collections are not claimed as reviewed.

The reports directory must be new and outside the checkout. It retains each raw
structured checker result plus `summary.json` and `summary.md` containing:

- explicit covered paths and declared public scope;
- native exclusions, including unpublished/different-profile sources;
- missing/unreported coverage, unsupported languages and figures `unverified`;
- observed draft/status counts and bounded samples without changing statuses;
- refused additions/changes and unchanged legacy files;
- `not_run` for models, datasets, captures, PDF and ZIP validation.

The guard requires real text sources in the declared roots; `_config.yml` alone
does not count. An intentionally empty scope requires
`allow_empty_public_sources: true` and a nonempty `empty_reason`, and is reported
as `empty_declared`, never as checked prose. Unexpected omissions fail. Checked
text and checker metadata must match their Git blobs; comparison reads bytes
directly and does not run Git clean/textconv filters or project policy code.

Source checks preserve warnings and partial coverage rather than interpreting a
checker exit zero as full validation. Nonzero exit, `ok:false`, malformed or
truncated output, timeout and unconfirmed exact teardown fail the source job.
No `continue-on-error` masks these outcomes.

The workflow listens to `pull_request` and optional manual dispatch, with only
`contents: read`, no deployment secrets and no Pages job. PR baseline identity
comes from the event's base commit. Manual dispatch requires an explicit full
ancestor SHA. It uses the checkout's committed HEAD, not uncommitted work as a
replacement baseline. The native `site-deploy.yml` and `reviewed_sha` remain
separate; source-CI success does not authorize website/Moodle publication.

## Minimal invocation and adoption

After installing the containing public package and explicitly preparing the
checker image:

```bash
python -I -m unaltraweb_mcp.source_checks \
  --project /absolute/clean-clone \
  --base-sha FULL_ANCESTOR_COMMIT_SHA \
  --reports /absolute/reports-outside-clone
```

`unaltraweb-source-checks` exposes the same arguments. The runner itself never
pulls or builds an image. It does not require private `sandbox`, dataset, PDF or
ZIP deliveries to exist. Full scientific/output validation remains a separate
retained-input lane, with its own source/pin/hash-bound evidence.

For the existing manuals, owners can add the exact common workflow and their
JSON policy in their authorized control change. They need not copy this Python
implementation into each repository. Do not forge a new scaffold baseline or
resolve an unrelated deployment-workflow conflict to add source CI: exact package
control bytes can be adopted later by the normal baseline mechanism. Existing
Geodisseny deployment/`reviewed_sha` customization remains untouched.
