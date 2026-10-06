# Consolidated deployment integration — 0.7.1

Owner: [issue 93](https://github.com/dosquartsdedocs/unaltraweb/issues/93), following
the workflow-only [issue 86 correction](deploy-provenance-86.md). The owner
authorized implementation, review/integration and gated 0.7.1 publication.
Current source preparation is distinct from a published distribution; final
source, receipts, installed-byte evidence and publication are recorded in issue 93.

## One package-owned contract

The BOM now carries two additive schema-v1 fields:

- `consumer_integration.site_deploy_workflow_sha`, independent of the Gem's
  `core_sha`. Legacy records default to their core revision.
- `deployment_contract`, with exact `manual_pdf_workers` digest/producer records
  and bounded `caller_migrations` describing reviewed baseline/current hash pairs.

The package schema and semantic checks validate repository confinement, unique
records, nonzero identities, the selected PDF's membership and exact migration
identities. Existing packages, receipts and the issue-86 workflow pin remain
unchanged. PDF 0.6.0, computation/capture 0.4.0 and the accepted visual-helper
combination are reused rather than introducing additional component upgrades.

The workflow fetches at most 256 KiB of JSON from its **defining provider commit**
on the fixed canonical GitHub repository. It does not read a consumer-supplied
contract or producer SHA. Strict JSON rejects duplicate/non-finite values; records
have bounded inventory and exact digest/source syntax. Fetch, lookup, pull and
inspection failures stop publication. A selected immutable digest is checked
against its recorded producer, not a later workflow commit. Its temporary metadata
file is invocation-owned and removed on exit.

Static policy binds the generic gate code, while approved artifacts live in the
contract. Ready-source validation resolves the actual workflow Git pin, checks
its gate and compares its own producer record with the package selection.
The CI Docker test additionally creates a package caller and executes the
preflight blocks of the workflow that caller really selects. Checking only the
current checkout's YAML is insufficient.

## Reviewed hotfix migration

Only `.github/workflows/deploy.yml` is eligible for the issue-86 migration:

| Identity | SHA-256 |
| --- | --- |
| Original package baseline | `a789870542614d5817d30ea4328c7d1ad38d27443c009c68a48ad5aaa3106b8e` |
| Exact reviewed one-line hotfix | `c632a548d0782867be20a2a52fe03469cf63066b7364bace77fd54a226cb3b18` |

Both must match. The dry-run lists `deploy-provenance-86` in `migrations`, proposes
the new package-generated caller and binds that authorization to `plan_sha256`.
The existing confinement, CAS rechecks, private staging, rollback and final
manifest commit remain in force. Any additional author edit remains a conflict;
removing the migration authority changes the plan hash. This is not a general
force-sync or semantic rewrite of authored workflow YAML.

## Acceptance stages

- Unit/schema/workflow tests cover independent core/workflow pins, legacy metadata,
  invalid or ambiguous records, exact migration, preservation of additional edits,
  plan binding, provider-only contract acquisition and fail-closed network/Docker
  errors.
- `test/test_deploy_provenance.py` tests actual published PDF workers and a generated
  caller's selected workflow. CI obtains the reviewed source SHA explicitly for
  source-bound metadata access.
- `test/deployment_integration_smoke.py` uses installed launchers and owned synthetic
  manuals: fresh, populated 0.5.0 upgrade and exact reviewed hotfix. It preserves
  author/cache hashes, applies the reviewed plan, builds PDF/web, probes HTTP and
  executes the exact remotely pinned workflow's source/provenance gates.
- Final acceptance must use the downloaded same-source wheel and signed MCP
  candidate. The driver does not dispatch Pages or claim a hosted real-manual
  deployment. TIG's authorized deployment is a separate consumer-session proof.

The implementation is integrated before the containing source selects its final
reviewed core/workflow revisions. Candidate components remain pending until that
selection; release readiness and publication keep their existing strict receipt,
ancestry, signing and immutable-byte gates.
