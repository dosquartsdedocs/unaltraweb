# Independent PDF worker provenance — issue 86

[Owner issue 86](https://github.com/dosquartsdedocs/unaltraweb/issues/86) records
TIG's failed latest deployment at consumer
`a87eb4fc7fe58f072413a99356d2465b36d05136`. Its published PDF 0.5.0 was produced
from `d857f8c9f5fea90cf450c0b30b4e77a37b541275`, whereas its reusable workflow
was pinned to `02af70001bf8085af860fd57f8d7e75ec96a89c7`. Comparing those two
different component identities blocked the build before Pages publication.

The original gates were re-executed with real published images: canonical 0.5.0,
0.5.1 and 0.7.0 tuples fail; the 0.6.0 tuple passes because its two revisions
happen to coincide. Retained diagnostic evidence is
`/tmp/opencode/unaltraweb-deploy-86/matrix/evidence.json`, SHA-256
`8640b7b68456b1bce42b9a0a271fe1c4853fde181eff9b3a130c990bd119142f`.

## Corrected trust binding

The reviewed provider workflow now owns these exact digest/producer records:

| PDF worker | OCI digest | Producer commit |
| --- | --- | --- |
| 0.5.0 | `sha256:9e0b3a45753c170b795e9a9d6df61580085c113436beac5bf6c8de69b6562097` | `d857f8c9f5fea90cf450c0b30b4e77a37b541275` |
| 0.6.0 | `sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed` | `5cf9817489c8dc47cee726bfe42fe3071cd32b85` |

Both references use the fixed repository
`ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf`. The gate first checks the defining
provider repository and full workflow SHA, rejects an unrecorded digest before
Docker access, pulls the exact digest and compares its actual revision label
with the recorded producer. The worker may have been released before the workflow.
The expected producer is not an input supplied by the consumer, and an inherited
environment value cannot replace it. Failed pull/inspection stops the step.

The deployment's reviewed-main guard, input interface and publication checks are
unchanged. The gate uses the already-reviewed immutable artifact identity; this
change does not introduce or claim a new live signature-verification service.
Release preparation's existing signed-image evidence remains separate.

Static workflow policy binds the whole gate, including its records and step
controls, to reviewed canonical JSON. It rejects disabled/error-tolerant gates
and refuses a BOM default whose worker has no approved record. A new worker
requires an explicit provider review, updated policy and published-image tests.

## Regression coverage

`test/test_deploy_provenance.py` executes the actual shell blocks from the reusable
workflow. Unit cases cover earlier legitimate producers, unknown digests with
plausible labels, mutable/foreign references, missing/wrong labels, a label that
matches the workflow instead of the worker, attempted expected-revision override,
foreign/unbound provider authority, pull/inspection failure and reviewed-main
ref/SHA rejection.

The independently gated Docker case executes real pulls and inspections for both
published workers against a later workflow revision. The ordinary CI distribution
job must run this case; static policy rejects silently disabling it:

```bash
UNALTRAWEB_DEPLOY_PROVENANCE_DOCKER=1 PYTHONPATH=test \
  python -m unittest test_deploy_provenance.PublishedDeployProvenanceTests
PYTHONPATH=src python3 -m unittest discover -s test -p 'test_*.py'
make workflow-check distribution-check
git diff --check
```

Local checks passed 619 Python cases, with 30 optional/environment skips, plus
the explicitly enabled real-Docker case. The actual image configuration IDs were
`sha256:c1998dc3345444cb3994ac0cd649ad80ac88dde127dec1dd9f09c719aafe170a`
for PDF 0.5.0 and
`sha256:d7e7d3243616270fc9e6eed7f8238c412dbe3d9ffc18d2832d17d66ca630d139`
for PDF 0.6.0. These tests exercise provenance gates without deploying a consumer.
Protected PR/integration results and the exact delivery commit are recorded in
issue 86 after integration.

## Urgent consumer adoption

The owner authorized a reviewed workflow-only delivery, independently of a new
gem/wheel/image release. TIG can retain its approved 0.5.0 Gem/core, PDF digest
and Vega selection and change only the `deploy.uses` revision in
`.github/workflows/deploy.yml` to the corrected provider's immutable merge SHA.
This is a reviewed local caller override; a later scaffold update must preserve
or explicitly reconcile it rather than resetting it to an older packaged pin.

In the TIG checkout, open the integration PR, verify that the content remains at
its approved baseline, repeat the local publication checks, merge, then dispatch
with the exact newly reviewed `main` SHA. Confirm the hosted build, Pages site
and downloadable PDF. The provider gate proof alone does not replace TIG's full
311-page manual validation or successful hosted deployment.
