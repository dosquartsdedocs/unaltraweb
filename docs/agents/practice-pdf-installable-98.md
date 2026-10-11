# Web #98 — installable practice-PDF candidate

Coordination: [gaContExt #32](https://github.com/dosquartsdedocs/gacontext/issues/32).
Owner: [Web #98](https://github.com/dosquartsdedocs/unaltraweb/issues/98).
Date: 2026-10-08. **Phase 1 completed as a local immutable candidate; publication
and real-manual adoption remain separate decisions.**

## Scope and checkout

Authoritative checkout: `/home/benizar/git/unaltraweb`.
Branch: `feat/98-installable-practice-pdf`.
HEAD and exact candidate runtime source:
`d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0` (approved PR #101).
Preflight was ELIGIBLE, clean, one checkout and no competing session.

The W1 branch/PR #103 remains preserved at
`6b81fc0466254a9bc8f506335d82b5f532a4fc35`; its source and historical test resources
were not used as this candidate. The superseding shared-runtime direction in
gaContExt #30 is respected. This unit creates no job volumes, ledgers or generic
runtime implementation.

[Exact reservation](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6066502338):

- `scripts/prepare_practice_candidate.py` — explicit offline candidate preparation.
- `packaging/practice-candidate/Dockerfile` — installation onto the prepared public MCP base.
- `test/practice_candidate_smoke.py` — installed selection and actual two-recipient acceptance.
- `test/test_practice_candidate.py` — preparation identity/no-clobber/path refusal tests.
- `test/test_practice_pdf.py` — reserved, unchanged.
- `docs/agents/practice-pdf-installable-98.md` — this return.

Only the five new preparation/test/report files are local changes. Runtime code,
approved templates, package versions, consumer pins and published receipts are
unchanged on this branch. New tooling is left uncommitted: this assignment did not
grant a new commit/push/release approval. The candidate itself comes entirely from
the already committed approved source, not these uncommitted helper files.

## Immutable candidate

Candidate directory:

```text
/home/benizar/git/unaltraweb/tmp/practice-candidate-98/candidate-02/
```

| Artifact | SHA-256 |
| --- | --- |
| `candidate.json` | `68f2b87763d401e37d01eced4da66a4cfa4dc39c7c684dd457266ab4839bba42` |
| `packages/unaltraweb_mcp-0.7.1-py3-none-any.whl` | `9fb813becf28e89f6e6b39d6f045cf2236d5085de03ef9c8b5c94f2d6721516a` |
| `controller.docker.tar.gz` | `72d35901a3e890bba554e5325523ea1764d8f92a4a01e9d258891101010f9bfe` |
| `source.tar.gz` | `12cf228f87188cd51882e27d8183969818692f4ae712e51dfc2d6e0649220b22` |

The portable image archive is 523,629,933 bytes. Its real `docker image load` was
tested. The loaded **Docker configuration ID** is:

```text
sha256:b73e47d1f75b4c3f8fc3e3f86b04ddc8c1ae32029b160a1acc997a91a2ee130e
```

It has no published registry digest. The configuration ID, archive-byte digest
and registry/index digest are different identities; no registry digest is invented.

The candidate keeps the approved slice's package metadata version **0.7.1**.
It is **not the published 0.7.1 wheel or MCP image**. Install/select only by the
hashes and explicit image ID above, preferably in a separate client environment.
Do not publish these bytes under an existing 0.7.1 version or mutable alias.

Preparation used `git archive` of the approved revision, offline wheel building,
the already prepared public MCP base, and an offline image layer that installs
the candidate wheel. It does not build or pull a worker during a consumer call.
`candidate-01` retains an unsuccessful preparation: Docker interpreted a
configuration-ID `FROM` as a repository name. The corrected preparation uses the
already inspected immutable repository digest; no image was pulled by that failed
attempt. `candidate-02` is the completed delivery.

## Coherent identities

| Responsibility | Selected identity |
| --- | --- |
| Candidate controller and embedded practice template/core | `d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0` |
| Prepared controller base | `ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6` |
| Consumer website core | `3332e0b93933f12317e05f1ce8d38ce80046feab` |
| Reusable deployment workflow | `3332e0b93933f12317e05f1ce8d38ce80046feab` (independent field) |
| PDF worker | `ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b` |
| PDF worker configuration ID | `sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa` |
| Actual PDF producer source | `b7ec1d7a139c65b3b0b88699cdbeb19080f13be1` |

The installed controller, selected core Git objects and actual prepared PDF worker
agree byte-for-byte on all nine `artifact_imports.CHECKER_FILES`. In particular,
`processes.py` remains
`5ed7fd9b427042a0c2d5ec213fef1d58732d7f8e21b4705864accd764e9a9f31`.
The W1 closure mismatch is absent from this candidate; no checker or compatibility
allowlist was weakened to obtain agreement.

The original reviewed PDF hash remains
`c92ec8a0937e9c9c735171d889e5bbca19b7ccd9ccbe8d33da2b6c0e49f9a245`.
The candidate retains the approved `practice.tex` SHA-256
`971c3594107d9645579f9b45a303048452cdd982a219a64b710ff515b3053491`;
the manual preamble, layout and finish-filter hashes are in `candidate.json`.

## Select it without editing a factory or consumer scaffold

On this host the image is already loaded. On another accepted Linux/amd64 Docker
host, verify the archive SHA-256 and load `controller.docker.tar.gz`. Prepare the
exact published PDF digest explicitly if missing. Normal execution uses
`--pull never` and refuses missing/mismatched selections.

Install the hash-pinned wheel into a fresh environment. `install-requirements.txt`
in the candidate directory contains the local wheel URI and required SHA-256;
if relocated, change only that URI, retaining the hash:

```bash
python3 -m venv /absolute/practice-pdf-client
/absolute/practice-pdf-client/bin/python -m pip install \
  --no-index --no-deps --require-hashes \
  -r /absolute/candidate-02/install-requirements.txt
```

The launcher wheel is a small host adapter; the full installed implementation and
factory assets are inside the candidate image. A native wheel alone is not a TeX
installation or factory checkout.

Use this executable/argument selection for the MCP connection, with the explicit
authorised consumer in place of `/absolute/manual`:

```bash
/absolute/practice-pdf-client/bin/unaltraweb-mcp-docker serve \
  --project /absolute/manual \
  --image sha256:b73e47d1f75b4c3f8fc3e3f86b04ddc8c1ae32029b160a1acc997a91a2ee130e \
  --expected-image-id sha256:b73e47d1f75b4c3f8fc3e3f86b04ddc8c1ae32029b160a1acc997a91a2ee130e \
  --managed --offline \
  --worker-images '{"manual_pdf":{"reference":"ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b","expected_image_id":"sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa"}}'
```

The installed Make transport is also available under the directory printed by
`unaltraweb-mcp-docker path`; set `MCP_RELEASE_IMAGE` to the candidate ID and inherit
`MCP_CONSUMER_WORKSPACE` through the environment. Reconnect deliberately, then
verify `runtime_identity` and `list_tools` in that actual connection. The tested
loaded package fingerprint is
`sha256:4eedb5ad683ec76310c1bac3556e37ec5c6ce16442e23236bf33b1713652641a`.
The observed tool inventory contains `manual_practice_pdf_build`, not `job_storage`.

### Two recipient requests

The consumer supplies its own `_config.yml` manual metadata and local PNG/JPEG/PDF
resources. Keep `practiques/`, `sandbox/` and `dist/` excluded from Jekyll, and
`sandbox/` ignored by Git. Source paths, language and filename must agree:

```json
{"source":"practiques/candidate/ca/alumnat/LLEGIU-ME.md","version":"2026-10-r1","run":"lectura-01"}
{"source":"practiques/candidate/ca/docent/LLEGIU-ME.md","version":"2026-10-r1","run":"lectura-01"}
```

Call **`manual_practice_pdf_build`** for each request. ES uses `LEEME.md`; EN uses
`README.md`. Replace the fixture slug `candidate` with the selected activity slug.
`dry_run:true` plans without creating a job. Changing an existing
explicit run's inputs is a collision; choose a new run/version. An unchanged
sealed job returns `state:current` only after rechecking its complete receipt.

Equivalent commands **inside the selected controller**, with its consumer and
Docker socket mounts established by the authorised launcher:

```bash
unaltraweb-mcp --project "$MCP_CONSUMER_WORKSPACE" mcp manual-practice-pdf-build \
  --source practiques/candidate/ca/alumnat/LLEGIU-ME.md \
  --version 2026-10-r1 --run lectura-01

PRACTICE_SOURCE='practiques/candidate/ca/docent/LLEGIU-ME.md' \
PRACTICE_VERSION='2026-10-r1' PRACTICE_RUN='lectura-01' \
make --silent --no-print-directory -C /opt/unaltraweb manual-practice-pdf-build
```

These CLI and Make paths were both executed against the installed image, not
imports from the checkout. The factory Make invocation honours the inherited
consumer binding. `test/practice_candidate_smoke.py:runtime_args` records the
equivalent explicit one-shot Docker mount/socket invocation for non-stdio callers.

## Verification and PDFs

Final evidence:

```text
/home/benizar/git/unaltraweb/tmp/practice-candidate-98/acceptance-03/evidence.json
SHA-256 241adf1bcd1029f1795597dc185628bcf8a0a386cbeac9161037116b99b1d89a
```

Two synthetic consumers, each with student and teacher readings, produced four
four-page PDFs. Dimensions are A4 landscape (approximately 841.89 × 595.276 pt).
The tests inspect executed image XObjects, not merely shared PDF resources: both
logos appear only on page 1. Course names/codes, author, recipient and practice
version are present; academic year `2099/2100` is absent. DejaVu fonts are embedded;
actual Serif/Sans/Mono worker font paths and hashes are retained. The teacher-only
solution marker is absent from the student PDF.

Under `acceptance-03/consumer-N/sandbox/practiques/candidate/`:

| Consumer / recipient | PDF SHA-256 | Receipt SHA-256 |
| --- | --- | --- |
| 1 / alumnat | `6358d6c010edd81ae352937d5ff4ad641d45b365facc522d3df30fd08c187de4` | `1c68ecf8d87a777e03ce8b29c55683f86a53db2d32eba4dad3ef0281a8dd060e` |
| 1 / docent | `748fd60f78bfc87253795ca88f7c7589bc771e75c37ab2b97d39fd9f65b04167` | `fb21d904cf67fff5fcbf6d973930088653eaa72b1aff06a1238bc8435ac2cc5c` |
| 2 / alumnat | `e7e8fbe82fdb7b588b9fdb62bc8e678bea27d258a0a54ed8cc70ee7c3169e4a4` | `c283bf7c6c8521487e5a9e7a7dd2b0394ece412bf7746614f948a0ede503d135` |
| 2 / docent | `b8e213fb2f185bf17660a3240adcb0af589ac6c8c2e72fd07f348530110b76c3` | `044cb618e7ae36b5a76fdebfc0c817301685dc09dd144244594f69af93acc8a3` |

Each job directory is
`lectura-2026-10-candidate-ca-<recipient>-installed-01/`.
Its PDF is `outputs/LLEGIU-ME.pdf`, preview `outputs/preview.png`, and seal
`receipt.json`. These hashes repeated unchanged across acceptance runs 01–03.

Additional real checks passed:

- Fresh installed wheel environment; loaded MCP image, package location/fingerprint,
  actual tool inventory, explicit original consumer mapping and narrow worker mounts.
- Idempotent MCP reuse, installed CLI and factory Make reuse with identical bytes.
- Modified author source, modified snapshot font, missing input, missing image,
  wrong controller ID and wrong PDF expected ID fail without replacing sources or jobs.
- A real empty-fontconfig test fails in XeLaTeX/fontspec without producing a final
  PDF or receipt. Its failed outputs/logs are retained separately.
- All four PDFs rebuild **byte-identically offline after relocation**, using only
  the retained effective snapshot and exact PDF worker; no original site/factory mount.
- Actual Jekyll builds on isolated disposable copies produce 13 files per consumer,
  with no `practiques`, `sandbox`, `dist`, reading PDF or teacher solution marker in
  the rendered site. Author-source hashes remain unchanged.
- Exact observed backend/worker/test-container absence is recorded. **Zero job
  volumes were created.** Images, source snapshots, receipts, PDFs, negative logs
  and the install environment remain available for review.

Local source checks: **657 cases, 630 passed / 27 optional skips**,
`scripts/validate_distribution.py` and `git diff --check` pass. The installed
launcher `check` passed with the exact candidate ID. The accepted source slice's
full CI remains the PR #101 baseline; this unit does not borrow W1 CI results.

## Release blocker and next handoff

The delivered selection is usable locally by hash. A new public release is blocked
by the absence of a new publication authorisation for this unit and the normal
review/version/candidate-signing/receipt/publication gates. The package metadata
must receive a new release identity through that process; these candidate bytes
must never be uploaded as released 0.7.1. This is not a technical checker-closure
blocker: the coherent tuple above has been executed and compared exactly.

For reviewed adoption, the minimum is selecting/reconnecting the candidate MCP
and exact prepared PDF worker, checking the live tool, and reviewing only the
manual's practice source mapping, metadata, ignores and private exclusions.
No core/workflow/scaffold/figure migration is needed just to exercise this PDF tool.
The wheel alone cannot turn an already-running 0.7.1 server into the new candidate.

The coordinator still needs QGIS's **owner-defined verified descriptor/fixture**,
then may commission recipient/edition ZIP packaging. This unit implements no GIS
schema/QGZ parser or speculative ZIP composition. No real manual is declared
practice-ready: complete GIS/project/capture/two-PDF/two-ZIP acceptance and the
authorised adoption in each manual remain later phases.
