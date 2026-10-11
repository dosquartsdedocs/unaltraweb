# Web #98 / gaContExt #32 — verified recipient edition composition

**Completed as an immutable local candidate, 2026-10-09.** No commit, push,
publication, manual migration or general runtime work is authorised by this return.

**Current final integration: `candidate-04`**, with the explicitly selected QGIS
rc2 v1/v2 profiles described under [Native rc2 integration](#native-rc2-integration--candidate-04).
The shared reading-resource/link resolver from candidate-03 is preserved. Earlier
candidate identities and evidence remain retained historical checkpoints.

The later [working-tree consolidation](#working-tree-consolidation--independent-pdf-and-zip)
adds the independent delivery PDF. It is not part of the immutable candidate-04 image.

## Checkout, preservation and reservation

- Authoritative checkout: `/home/benizar/git/unaltraweb`.
- Branch: `feat/98-installable-practice-pdf`.
- Git HEAD/base: `d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0`.
- Preflight found one checkout, no conflicts or competing session. Its sole
  dirty-checkout finding was the five phase-1 files explicitly authorised for
  continuation. Those files and all phase-1 candidates/receipts are preserved.
- W1 remains on its existing branch/PR #103; no new generic manager or ledger.
- [Phase-2 exact reservation](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6079361656)
  and [private editorial mapping addendum](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6079528210).

Implementation paths: `src/unaltraweb_mcp/practice_editions.py`,
`practice-edition-v1.schema.json`, `practice_pdf.py`, `editorial_sources.py`,
`site_tools.py`, `cli.py`, `mcp_server.py`, `component-contract.json`; `Makefile`,
`mcp-factory.yml`, `pyproject.toml`. Tests: `test/test_practice_editions.py`,
`test/test_editorial.py`, `test/practice_editions_smoke.py`. Preparation:
`scripts/prepare_practice_editions_candidate.py` and
`packaging/practice-editions-candidate/Dockerfile`. Docs: this file and
`docs/agents/mcp-contract.md`. All changes remain uncommitted in this checkout.

## Installed candidate and identities

Delivery directory (different from phase 1):

```text
/home/benizar/git/unaltraweb/tmp/practice-editions-98/candidate-02/
```

| Artifact | SHA-256 |
| --- | --- |
| `candidate.json` | `2ca91e63446393d1d0c479609d003ba21bc9576280fc46cada58acf024cfc192` |
| `packages/unaltraweb_mcp-0.7.1-py3-none-any.whl` | `e02fec9054ebe5ac5b08e27783bb763181a04e21a64d1b577beb343e986bc86a` |
| `controller.docker.tar.gz` | `0de5df95bfb895021b127a5616cfe6b7d37df920587f7b4bcc1561b76d2421dd` |
| `source.tar.gz` | `d42689458b53479cc9cf9c4c0a215cefb1de5481b46b926fda4728df72e0528d` |
| Web composition schema | `35a10534611d36a708af455dc07329f2003817e51da5b4631efb805fcea5d168` |

Prepared controller **configuration ID** (not an invented registry digest):

```text
sha256:eb7fe76944d0c3238f2d00868cbacc76794ced8966d9b4fdad75adf606d3ab33
```

Its archive is 525,065,228 bytes and has been loaded with Docker. It identifies
the exact source snapshot by SHA-256, comprising the approved Git base and the
eleven explicit overlays listed and hashed in `candidate.json`. It does not claim
that those uncommitted bytes equal Git HEAD. Package metadata remains `0.7.1`;
this is an **unpublished hash-bound successor**, never the published 0.7.1 wheel
or image. No existing candidate/release was overwritten.

The installed QGIS dependency is the owner-delivered wheel, not copied domain
source or a Web parser:

- `unaltracaptura-qgis 0.6.0rc1`, wheel
  `82f2c6772fa8bb9aaae08237494af72df7e103038643fd6dfcdcd6f1ac45ed5f`.
- Installed source/assets revision
  `sha256:69b61a4b144d2de9a3aa6344ebfb53d93269437bbe627c899b508235b668443c`.
- Producer schema `qgis-practice-v1`, hash
  `9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445`.
- Prepared QGIS engine
  `sha256:1003721d96abe9607d8337b36851f9b29f84c2f8f92b377d1a73ff03c9d15cd2`.
- Shared transfer marker and all eight transfer-file hashes were checked. Fixture
  ZIP `ea6fbae78c93e8e0fc516a513cab246d0af7d36886585beff70cab79a65f762c`,
  complete 27-file sender seal
  `abd44b02101243a3ddfd492357c2882e6a3f62248dde192616159944c41056a4`.

The prepared PDF remains
`ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b`,
configuration ID `sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa`,
producer `b7ec1d7a139c65b3b0b88699cdbeb19080f13be1`.
Consumer core and the independent workflow pin stay
`3332e0b93933f12317e05f1ce8d38ce80046feab`. All nine retained-document checker
files still agree between installed controller, selected core and PDF worker.

## One public composition API

MCP: **`manual_practice_compose(config, dry_run=false)`**.
Schema resource: **`web://practice-edition-schema`**.
CLI inside the installed controller:

```bash
unaltraweb-mcp --project /absolute/manual mcp manual-practice-compose \
  --config practiques/candidate/edition.json --dry-run
unaltraweb-mcp --project /absolute/manual mcp manual-practice-compose \
  --config practiques/candidate/edition.json
```

The same implementation is used by the factory Make target:

```bash
MCP_CONSUMER_WORKSPACE=/absolute/manual \
PRACTICE_EDITION_CONFIG=practiques/candidate/edition.json \
make --silent --no-print-directory -C /opt/unaltraweb manual-practice-compose
```

It requires an absolute selected consumer and an indexed, non-ignored edition
configuration. It verifies Git ignores and Jekyll exclusions before work. Source
reading hashes explicitly bind the author's edition selection; mechanical review
does not confer author approval. The independent GIS activity/job version stays
in the producer report; the edition version governs only reading/delivery output.

Example versioned consumer configuration (replace the two reading hashes):

```yaml
schema_version: 1
kind: unaltraweb-practice-edition
slug: candidate
version: 2026-10-r1
language: ca
gis:
  bundle: sandbox/gis/delivery/bundle.json
  sha256: abd44b02101243a3ddfd492357c2882e6a3f62248dde192616159944c41056a4
  verifier:
    package: unaltracaptura-qgis
    version: 0.6.0rc1
    revision: sha256:69b61a4b144d2de9a3aa6344ebfb53d93269437bbe627c899b508235b668443c
    wheel_sha256: 82f2c6772fa8bb9aaae08237494af72df7e103038643fd6dfcdcd6f1ac45ed5f
    schema_sha256: 9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445
  teacher_only: [resolved-project, resolved-data, resolved-project-svg, resolved-project-original]
selection:
  alumnat: [initial-project]
  docent: [resolved-project, resolved-project-svg]
readings:
  alumnat:
    source: practiques/candidate/ca/alumnat/LLEGIU-ME.md
    approved_sha256: REPLACE_WITH_EXACT_SOURCE_SHA256
  docent:
    source: practiques/candidate/ca/docent/LLEGIU-ME.md
    approved_sha256: REPLACE_WITH_EXACT_SOURCE_SHA256
```

The producer's installed `practice-schema` identity/schema and pip-recorded wheel
hash must match the pin. Web runs public `practice-check` only, verifies the whole
bundle independently with the unchanged generic verifier, and consumes each
returned ID/path/hash/bytes/role/dependency row. It never scans QGZ or guesses a
dependency. Required dependencies cannot be silently removed by a recipient filter:
an ineligible closure is refused in its entirety. Student closures reject resolved
project/data roles and all explicitly teacher-only IDs. Source/control/rebuild
roles are not classroom delivery products.

Outputs are atomically installed as a new directory:

```text
dist/practiques/<slug>/<version>/<lang>/
  <slug>-<version>-<lang>.zip
  <slug>-<version>-<lang>.zip.receipt.json
  <slug>-docent-<version>-<lang>.zip
  <slug>-docent-<version>-<lang>.zip.receipt.json
  edition.json
```

An existing edition directory is always refused, including an unchanged repeat.
ZIP members are the exact producer closure at its unchanged `payload/...` relative
paths, the corresponding `LLEGIU-ME.pdf`/`LEEME.pdf`/`README.pdf`, and explicitly
selected author resources. Editable Markdown remains at its original versioned
consumer path and is hash-linked through external receipts and PDF snapshots.
Receipts/control scripts/reconstruction sources are not inserted into the ZIPs.
Partial same-parent candidates remain diagnosable on failure; no cleanup is implied.
Ignored `dist` remains a protected retained delivery.

## Explicit private reading mapping and editorial support

New sources use the canonical `practiques/<slug>/<lang>/<recipient>/...` path.
Existing sources can be declared once in `_config.yml`:

```yaml
exclude: [practiques/, sandbox/, dist/, _practices/]
unaltraweb:
  practices:
    readings:
      - source: _practices/tigit-projecte-territorial/ca/alumnat/LLEGIU-ME.md
        slug: tigit-projecte-territorial
        lang: ca
        recipient: alumnat
      - source: _practices/tigit-projecte-territorial/ca/docent/LLEGIU-ME.md
        slug: tigit-projecte-territorial
        lang: ca
        recipient: docent
```

Composition and `manual_practice_pdf_build` reuse the same resolver as targeted
`prose_check` and `editorial_review_prepare`. Draft/unpublished private readings
produce nonzero source/fragment coverage and original-path anchors. They stay
outside the default public corpus; selecting the whole `_practices` directory or
arbitrary `context` files is not granted by this mapping. Duplicate identities,
cross-recipient canonical paths, traversal, non-Markdown and unknown sources fail.

The installed legacy-path test reports **files_checked:1 for each recipient**,
prepares source-digest-bound fragments and records an agent pass without granting
approval. Both original reading hashes remain unchanged through PDF and ZIP
composition. Existing real TIGIT files were not moved, copied or edited here.

## Editable SVG author resources

Resources are separate from GIS IDs. Example optional edition field:

```yaml
resources:
  - path: _practices/tigit-projecte-territorial/infografia.svg
    role: editable-infographic
    sha256: REPLACE_WITH_EXACT_SVG_SHA256
    destination: resources/infografia.svg
    recipients: [alumnat, docent]
    dependencies:
      - path: _practices/tigit-projecte-territorial/map.png
        sha256: REPLACE_WITH_EXACT_PNG_SHA256
        destination: resources/map.png
```

Every selected file is confined and hashed. Bounded SVG XML/CSS references must
resolve to declared dependencies and retain the same relative relationship after
mapping. Embedded PNG/JPEG data is bounded using the existing image resource
inspector. External/imported stylesheets, remote rendering resources, scripts,
event handlers and dynamic SVG are rejected. Dependencies may be local SVG,
PNG/JPEG or declared font files; their integrity is recorded, not a promise that
every editor renders a font identically. Unreferenced neighbouring files and
destination collisions are refused. No directory is copied merely because it
contains an SVG. Opacity/visual author review and eventual publication remain
separate; the packager does not alter the author SVG or paint a background.

The installed synthetic TIGIT-shaped case includes an editable SVG plus its
declared PNG in both editions. A neighbouring `private-control.py` is preserved
at source and absent from all ZIPs. This proves selection mechanics, not approval
of TIGIT's separately authored real infographic.

## Final-ZIP acceptance (including no-private-fallback proof)

Final evidence:

```text
/home/benizar/git/unaltraweb/tmp/practice-editions-98/acceptance-03/evidence.json
SHA-256 a7a2f75aeb74738a6d1b0cebdef465017e1d4da11e00b86bbc98ddf1e4e09ecb
```

Two independent synthetic consumers with their own course metadata/readings use
the exact same GIS job/seal. Each produces an MCP edition and another version via
the public CLI: **eight final ZIPs/eight PDFs, eight actual offline QGIS reopens**.
The Make dry-run also executes the installed entry point. No GIS calculation is
invoked by composition; the eight scientific controls remain the producer's
verified retained execution evidence. Reopening is separately logged as actual
QGIS work.

For every ZIP, acceptance first extracts the **final archive**, checks exact
member inventory, hashes, sizes and relative tree against the producer closure
and declared author resources, then creates the reopen workspace. The producer
API requires its full seal, so unselected evidence remains private for validation,
but **every selected GIS file is replaced from the final extracted ZIP**.

Acceptance observes the actual running QGIS engine mounts and hashes its readonly
selected packet. That packet contains exactly the 3-file initial or 4-file resolved
GIS closure from the ZIP. The engine never mounts the complete private bundle or
the original consumer as an alternate source. Other mounts are producer runtime,
bounded controls and output. Network is `none`; exact engine absence is checked.

Both a missing and a byte-altered `payload/data/relief.tif` in new final ZIPs are
refused **even after recomputing their archive SHA-256**. The original declared
closure remains mandatory, before any private validation bundle can be used.
Those negative ZIPs and reports are retained under each `proof-N/`.

Main MCP-edition ZIPs (CLI-edition hashes/receipts are also in the evidence):

| Case | ZIP SHA-256 |
| --- | --- |
| Canonical alumnat | `a5ebe0a8487e3e9e5691cb742fad8923b3006d8c5f9e46c6eef32e54c44b42b0` |
| Canonical docent | `ae3e6fff012165e46949e49df5b11bb8e64ddae9f4122c796ecf3082943d0d6f` |
| Legacy-mapped alumnat + SVG | `b43d52f2714062b27aa0258db3e684627e321b00b954ba51afe71f7bf852dae3` |
| Legacy-mapped docent + SVG | `954f80ac61d811d86b00c027d81f6fdd686a42591e6def1b33402aa2fdc1746a` |

Locations:

```text
.../acceptance-03/consumer-1/dist/practiques/candidate/2026-10-r1/ca/
.../acceptance-03/consumer-2/dist/practiques/tigit-projecte-territorial/2026-10-r2/ca/
```

Installed negatives also cover manipulated unselected producer source, missing
closure data, resolved/student and teacher-visual/student misassignment,
reconstruction/control inclusion, swapped readings, stale approved-source hash,
wrong verifier hash and symlinked bundle ancestry. All refuse without changing
previous editions/PDFs. SVG unit negatives cover missing dependencies, broken
relative mappings, scripts and unreferenced neighbouring files.

Source tests: **667 cases, 640 passed / 27 optional skips**. Distribution and
whitespace checks pass. Exact installed controller check/smoke passes. Tuple and
portable archive load check:
`acceptance-03/tuple-check.json`, SHA-256
`73b41f0dc4109ebcd43f8d65d57651a0fcfc91d0bb022f2a93b275679311d9f3`.
PDF layout/code/year/first-page-logo and student-solution exclusion checks are
reused from phase 1. Actual isolated Jekyll builds preserve private exclusions.
No test job volumes are allocated; Web test containers and producer engines are
observed absent. Sources, PDF jobs, retained bundles, negative logs, ZIPs and
receipts remain available for independent inspection.

## Select from a consumer without local generic scripts

The hub's existing phase-1 host adapter can explicitly launch the successor:

```bash
CLIENT=/tmp/opencode/practice32-web-client-9fb813becf28
IMAGE=sha256:17ef0d24e8611a6802b3c01ff440e6e552eac728343733198056fdbc6cdf379e
"$CLIENT/bin/unaltraweb-mcp-docker" serve --project /absolute/manual \
  --image "$IMAGE" --expected-image-id "$IMAGE" --managed --offline
```

Verify the new tool/schema in that actual connection. For a one-shot CLI directly
from the consumer shell, using the same already loaded image and native mount
encoder, controller limits, ownership labels and exact session reaper shipped in
the installed adapter. The command retains the exact container ID for teardown,
including a nonzero CLI exit; it never performs factory-wide cleanup:

```bash
PROJECT="$(pwd -P)"
PROFILE="$("$CLIENT/bin/unaltraweb-mcp-docker" path)"
PROJECT_ID="$(/bin/sh "$PROFILE/scripts/unaltraweb-mcp-project-id.sh" "$PROJECT")"
SESSION="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
PM="$(/bin/sh "$PROFILE/scripts/unaltraweb-docker-mount.sh" "$PROJECT" "$PROJECT")"
SOCKET="$(realpath /var/run/docker.sock)"
SM="$(/bin/sh "$PROFILE/scripts/unaltraweb-docker-mount.sh" "$SOCKET" /var/run/docker.sock)"
CID="$(docker create --pull never --network none --init \
  --name "unaltraweb-stdio-$SESSION" --cpus 2 --memory 4g --pids-limit 512 \
  --label io.context.mcp-factory=unaltraweb --label io.context.mcp-role=stdio \
  --label "io.context.mcp-project=$PROJECT_ID" --label "io.context.mcp-session=$SESSION" \
  --user "$(id -u):$(id -g)" --group-add "$(stat -c %g "$SOCKET")" \
  --mount "$PM" --mount "$SM" -e HOME=/tmp \
  -e "MCP_CONSUMER_WORKSPACE=$PROJECT" -e "UNALTRAWEB_DOCKER_ROOT=$PROJECT" \
  -e "UNALTRAWEB_RUNTIME_SESSION=$SESSION" \
  --entrypoint unaltraweb-mcp "$IMAGE" --project "$PROJECT" \
  mcp manual-practice-compose --config practiques/candidate/edition.json)"
STATUS=0
docker start --attach "$CID" || STATUS=$?
"$CLIENT/bin/unaltraweb-mcp-docker" reap-session --project "$PROJECT" \
  --session-id "$SESSION" --container-id "$CID"
test "$STATUS" -eq 0
```

Only the native producer wheel selection and matching version/revision/schema/hash
pins need change for a compatible verifier successor. Its public return shape and
role contract remain the integration boundary. Embedded GPKG/raster/themes/layout
support is still QGIS-owned; rc1 limitations remain and Web does not certify those
unsupported resources. Publication and adoption in each real manual require their
separate authorisations. A successful synthetic composition is not a declaration
that TIG, TIGIT or Geodisseny is fully practice-ready.

## Portable reading bindings — candidate-03

### Reproduced defect and scope

The installed candidate-02 emitted the literal
`../../templates/infografia-a3.svg` in the final ZIP's student and teacher PDFs.
It resolved outside the extracted edition even though the SVG was present at
`resources/figures/plantilla-editable.svg`. The reproduction uses the actual
TIGIT source shape and the reported link at line 135 in a synthetic fixture:

```text
_practices/tigit-projecte-territorial/readings/ca/LLEGIU-ME-estudiant.md
_practices/tigit-projecte-territorial/readings/ca/LLEGIU-ME-docent.md
_practices/tigit-projecte-territorial/templates/infografia-a3.svg
```

Evidence: `tmp/practice-editions-98/links-reproduction-01/evidence.json`, SHA-256
`ade15dd78789c793c21a3e23926f06ad1b81069326ef697b67009c397aa953a1`.
The old candidates and all failed/earlier proofs remain retained.

The correction stays in the existing practice domain: `practice_pdf.py` owns one
`ReadingResources` resolver shared by image snapshotting and prose links, and
`practice_editions.py` supplies only that recipient's verified selection. The
renderer applies the authorised URL lookup to its actual Pandoc AST and refuses
any unaccounted local link. It also checks the resulting PDF's link annotations.
No GIS code, template geometry or global path-validator rule was relaxed.

### One binding format, two declaration locations

A binding has a literal `reference`, exactly one `path` or `product`, a required
`sha256`, and an optional `destination`. It can live in the shared reading mapping
under `_config.yml`, or in the selected edition's `readings.<recipient>.bindings`.
The same resolver merges them; conflicting definitions of one reference fail.
Declared references must be used by that reading.

For the Geodisseny-shaped retained capture case (replace the hash/path with the
consumer's exact inventory):

```yaml
unaltraweb:
  practices:
    readings:
      - source: practiques/accessibilitat-vilaseca/ca/alumnat/LLEGIU-ME.md
        slug: accessibilitat-vilaseca
        lang: ca
        recipient: alumnat
        bindings:
          - reference: captures/inici.png
            path: sandbox/practiques/accessibilitat-vilaseca/2026-10-07-organitzacio/captures/inici.png
            sha256: REPLACE_WITH_EXACT_PNG_SHA256
            # Optional only when this resource must also be a ZIP/link target:
            destination: resources/captures/inici.png
```

Declare the teacher reading separately. The Markdown stays
`![...](captures/inici.png)`; the source capture stays in its original run. There
is no scan of sandbox directories. A missing file, different hash, unsafe path,
unsupported image type or unbound logical reference fails.

An edition binding can instead address a producer ID:

```yaml
readings:
  docent:
    source: _practices/tigit-projecte-territorial/readings/ca/LLEGIU-ME-docent.md
    approved_sha256: REPLACE_WITH_EXACT_MARKDOWN_SHA256
    bindings:
      - reference: captures/inici.png
        product: resolved-project-original
        sha256: REPLACE_WITH_EXACT_SELECTED_PRODUCT_SHA256
```

The ID must already belong to the teacher's selected producer closure. Its
destination is inherited without moving GIS files. A path alias cannot bypass
another recipient's known GIS/author-resource selection. Literal GIS images in a
reading must also be selected; the regression fixture now explicitly selects the
annotated teacher PNG used in its Markdown rather than relying on the private
bundle containing it.

PNG/JPEG/PDF path bindings can supply reading images. When an edition additionally
declares a `resources/...` destination, those exact bytes join its ZIP as a
`reading-resource`. Extra SVG/GIS resources still require the existing verified
GIS/author-resource selection; a reading binding is not a shortcut around SVG
dependency validation or recipient policy. For an already selected resource,
any stated destination must match that selection.

### Relative prose links and standalone behavior

For a normal local link such as
`[plantilla editable A3](../../templates/infografia-a3.svg)`, the resolver applies
URL-relative normalization against the **original reading's parent**, then requires
the resulting confined source path in the recipient's authorised resource map.
It emits the encoded ZIP-relative destination from that map. `..` is handled only
as URL syntax; normalized filesystem/ZIP paths still use the strict validator.
Absolute, escaped, undeclared, other-recipient and private/control targets fail.
HTTPS theory URLs and internal anchors are retained.

Standalone `manual_practice_pdf_build` supports the same explicit image bindings,
but **refuses local file links without a portable edition context**, even if the
source file exists. It cannot claim that a PDF in a sandbox directory has a valid
relative link to an unrelated original resource. HTTP(S), mailto and internal
anchors remain supported. The public composition signature is unchanged.

Snapshots/receipts now bind:

- `inputs/original.md`: exact authored Markdown, never rewritten in the consumer;
- `inputs/source.md`: parsed body input, plus image metadata and snapshots;
- `inputs/portable-links.json`: selected target map, declared/resolved bindings,
  source paths, hashes, bytes and source-URL → ZIP-URL mappings;
- `outputs/source.effective.json` and `.md`: actual effective Pandoc source after
  the authorised link pass; image layout still consumes the captured metadata;
- `outputs/practice.tex`, final PDF/preview and renderer link report, all hashed.

The target map and bindings participate in the existing fingerprint/no-clobber
contract. Bound source hashes are rechecked before sealing/delivery. Edition
receipts retain the mapping and effective-source hashes alongside GIS/PDF identity.

### Immutable successor and installed evidence

Directory:

```text
/home/benizar/git/unaltraweb/tmp/practice-editions-98/candidate-03/
```

| Artifact | SHA-256 |
| --- | --- |
| `candidate.json` | `7df6364d249dea3eeafbe1f89ebadbc4a16ce90502cb528ab97c0e261182e4e4` |
| Web wheel | `809a8afe0ce52d013391d2bfc0edbb2a908c81fdef53b9fe3e99e652c8923687` |
| `controller.docker.tar.gz` | `7fd63303a1dbab7f1b7b226ebb4e361bfc0008afe29ead4e149a88c232ea6eec` |
| `source.tar.gz` | `780a80d29255c8a60430af053689ab20473c940b3ab955be187e360052b90785` |
| Composition schema | `3b3334946c765f98188c5daa668c933ab81eaaabb8cf4898324f6d26b2974acd` |

Configuration ID:
`sha256:9f4370dc8d0e0681226f165f38b0c758fde949c62b6d23427c70c810f0cdf1f5`.
This remains an unpublished hash-bound candidate, not new bytes published as 0.7.1.
The selected QGIS rc1 and PDF/core/workflow tuple remain unchanged; no compatibility
with an undelivered QGIS successor is inferred.

Installed link/binding proof:

```text
tmp/practice-editions-98/links-acceptance-04/evidence.json
SHA-256 e6d2c24dd0c1727e9650b2b0b28596964842b47f6ee8539b89166eddb27ba5a7
```

The final ZIP PDFs now point to `resources/figures/plantilla-editable.svg`, and to
the recipient's declared capture destination. Every inspected local annotation
target exists inside the extracted edition. The exact HTTPS URL survives; the
internal link resolves through an actual named PDF destination to its expected
heading. Original Markdown/config/resources keep their hashes. Effective-source
and receipt hashes are checked independently.

Two additional standalone Geodisseny-shaped readings retain literal
`captures/inici.png` and compile from the declared separate run. Both dry-runs and
builds pass without any neighbouring capture directory or source rewrite. Changed
capture hashes, absent captures and removed bindings fail; no sandbox discovery
occurs. Other negatives cover undeclared/missing/teacher-only/escaped prose targets,
an unselected GIS product binding and standalone local-file-link refusal.

The bounded one-shot CLI example above was executed with observed **2 CPUs,
4 GiB, 512 PIDs**, native factory/role/project/session labels and exact native
`reap-session` cleanup:
`links-acceptance-04/review/native-cli.json`, SHA-256
`4bd9ff25ecd245c5c9f2a5038a29360ad2b2fc208bea1f5ec28c8fc64adb3f7f`.

Full GIS/ZIP/private-editorial/layout regression:
`tmp/practice-editions-98/acceptance-04/evidence.json`, SHA-256
`1fa74f1a030ef3b0028277babe252c15866c79a7cf3a15825a8c89c2de732393`.
It repeats the final-archive closure/mount/reopen tests, recalculated-archive
negatives, original-path private reviews and template checks. Original no-link
student ZIP hashes remain unchanged; teacher packages explicitly add their selected
annotated capture. **672 tests: 645 passed / 27 optional skips**, plus all 28 practice
tests with the real PDF worker enabled, installed check/smoke, and coherent
nine-checker/archive-load verification. Tuple receipt:
`links-acceptance-04/tuple-check.json`, SHA-256
`d8e50846bad79ab679f9da6aef70760d55d32198f1e13565989e27f1ed87593f`.

Additional reserved paths for this revision:
`scripts/manual/render_practice.py`, `test/practice_links_smoke.py`.
All prior candidates and receipts remain immutable. Branch/HEAD are unchanged;
the work is uncommitted and no real manual, producer checkout, release or general
runtime infrastructure was edited by this unit.

## Native rc2 integration — candidate-04

**Completed, local unpublished candidate.** The authoritative checkout/branch and
Git base remain unchanged. All source changes are uncommitted; candidates 02/03,
their bins/schemas/receipts and the earlier GIS selection remain preserved.
The exact continuing reservation is recorded in
[Web #98](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6084077906).
The [completed integration return](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6084722283)
records the selected candidate and installed acceptance evidence.
The only new source path is `test/practice_native_editions_smoke.py`; production
changes are limited to profile identity/invocation and explicit native export roles
in the existing adapter/schema. No GIS parser or dependency discovery is added.

### Verified producer and minimal adapter delta

Shared input: `/tmp/opencode/practice32-qgis-0.6.0rc2-round32-n1/`.
The `ready.json` SHA-256
`49a8887587eb5942aae7aa76b678acd617cec799294c350fe5fc6d344d881a1a`, all eleven files,
the 43-member fixture seal and descriptor were rehashed before use.

- Package: `unaltracaptura-qgis 0.6.0rc2`.
- Wheel: `1a7456c0b81e0a4729b702b60d9340456efea9a88b9f5c21b97c8ff4823d09bf`.
- Installed source/assets:
  `sha256:5922d3dc411c14c7c3c2d9257a78b4d42f42fb1aae8451bcf245ca44a0e91992`.
- V2 schema: `528c8be229c72c346f134ffaa60094f94224094a25b6fb11bcc87802ddc7fffb`.
- V1 schema unchanged: `9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445`.
- Native fixture ZIP: `5598a98c6bd42561935ed3eb1c674dae34ff6ba2ce0fff9384c6ebf80d3f4e53`.
- Native sender seal: `7f26db5a8cc05af081ea21a65d7d167e05f4b6b1a2a7a6e9b361c91066605507`.
- Native descriptor: `3118638d53c63ef2c059d73f744b2ac399aa1f2e2c21f27f0026f3fbbb122df7`.
- Engine remains `sha256:1003721d96abe9607d8337b36851f9b29f84c2f8f92b377d1a73ff03c9d15cd2`.

`gis.profile` now selects the domain explicitly. V2 identity calls exactly
`practice-schema --profile qgis-practice-v2`; the returned schema pin/profile and
installed wheel/content identity must all agree. Legacy omitted profile means v1
only, using its established public default so an old rc1 v1 selection is not
silently reinterpreted. New configurations should state either profile explicitly.
The later `practice-check` result must match the selected profile, independently
of package version. A verifier package can therefore verify an older producer's
seal without pretending their versions/content revisions are identical.

V2 delivery adds only the declared `map-svg`/`map-pdf` output roles. Fonts, symbols,
Shapefile/CSV sidecars and other dependencies retain their returned roles and are
included through the exact producer closure, not filename heuristics. `teacher_only`
and resolved-role segregation still apply to the entire closure. No GPKG container
is split: its internal-member safety belongs to the producer verifier.

### Exact profile configuration

For the native fixture (the reading/version/recipient fields stay as documented
above):

```yaml
gis:
  profile: qgis-practice-v2
  bundle: sandbox/gis/native/bundle.json
  sha256: 7f26db5a8cc05af081ea21a65d7d167e05f4b6b1a2a7a6e9b361c91066605507
  verifier:
    package: unaltracaptura-qgis
    version: 0.6.0rc2
    revision: sha256:5922d3dc411c14c7c3c2d9257a78b4d42f42fb1aae8451bcf245ca44a0e91992
    wheel_sha256: 1a7456c0b81e0a4729b702b60d9340456efea9a88b9f5c21b97c8ff4823d09bf
    schema_sha256: 528c8be229c72c346f134ffaa60094f94224094a25b6fb11bcc87802ddc7fffb
  teacher_only:
    - buffer-data
    - infographic-pdf
    - infographic-svg
    - joined-data
    - resolved-project
    - resolved-project-original
    - resolved-project-png
    - resolved-project-svg
    - route-closed
    - route-open
selection:
  alumnat: [initial-project]
  docent: [resolved-project, infographic-svg, infographic-pdf, resolved-project-png]
```

For an unchanged rc1/v1 bundle with the **same rc2 verifier**, select
`profile: qgis-practice-v1`, use its own sender seal
`abd44b02101243a3ddfd492357c2882e6a3f62248dde192616159944c41056a4`, and set
`schema_sha256: 9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445`.
Verifier version/revision/wheel remain the rc2 values above. Both combinations were
executed. A v2 bundle with v1 profile/pin, a v1 schema hash under v2 or a wrong wheel
pin is refused rather than treated as a compatible success.

Inside the selected Web controller, these are the actual installed producer CLIs:

```bash
unaltracaptura-qgis practice-schema --profile qgis-practice-v2
unaltracaptura-qgis practice-check --workspace "$MCP_CONSUMER_WORKSPACE" \
  --path sandbox/gis/native/bundle.json \
  --sha256 7f26db5a8cc05af081ea21a65d7d167e05f4b6b1a2a7a6e9b361c91066605507 \
  --select initial-project
unaltracaptura-qgis practice-reopen --workspace "$MCP_CONSUMER_WORKSPACE" \
  --path sandbox/gis/native/bundle.json \
  --sha256 7f26db5a8cc05af081ea21a65d7d167e05f4b6b1a2a7a6e9b361c91066605507 \
  --select resolved-project --output sandbox/native-reopen-01.json
```

Use the native bounded/labelled controller selection and teardown documented above,
changing the one-shot entrypoint to `unaltracaptura-qgis` for a host-shell invocation.
The verifier is installed in that image; a separate old QGIS connection on the host
does not determine this composition's verifier. Reopen needs the already prepared
engine; checking/selection alone does not start GIS or fetch data.

### Candidate identities and tuple

```text
/home/benizar/git/unaltraweb/tmp/practice-editions-98/candidate-04/
```

| Artifact | SHA-256 |
| --- | --- |
| `candidate.json` | `c79e688b95b4f94f2e2fc9df154611cae3611ab628ee0bc4e9f2cba08fdc3fc7` |
| Web wheel | `df1ca9d239c25342a81950f4906589a6f94f0deae192a99c3affd227597cbaa9` |
| `controller.docker.tar.gz` | `392853842dc49dafe15d10d37a7456d52add2d341b90ff3e3fe8142f66a9f9f3` |
| `source.tar.gz` | `8810efd4f4725eea5910996b790b9704786ef42b683c26e1c4d0ae12be24616e` |
| Web composition schema | `06707a0d847715f85576fd2f3118d132808c8cf5dbd522333bbabf4759bd867d` |

Controller configuration ID:
`sha256:17ef0d24e8611a6802b3c01ff440e6e552eac728343733198056fdbc6cdf379e`.
Actual serving package fingerprint:
`sha256:5b8de154fc10665f71056b2887959d41a2a6f5fb5726611d1ee3482c7d7b3d36`.
The archive was loaded and the image's source label matches its exact source
snapshot. It is a local hash-bound candidate, not a new published 0.7.1 artifact.
The embedded GIS package is rc2; the prepared PDF worker stays at its published
0.7.1 digest/configuration ID and producer `b7ec1d…`. Consumer core and independent
workflow remain `3332e0b…`. All nine retained-document checkers still agree.

### Actual native final-ZIP acceptance

Evidence:

```text
tmp/practice-editions-98/native-acceptance-01/evidence.json
SHA-256 1c7feca296ab5b991fe7c63d4cadcfb6f996f904abac20020aa661355adb2507
```

The installed public verifier returns exact closures **11 / 9 / 2** for
`initial-project`, `resolved-project`, `infographic-svg`. The student ZIP retains
the initial atomic GPKG, fonts/symbol, complete Shapefile and CSV/CSVT relationships;
the teacher ZIP adds the selected solved projects/data and native SVG/PDF exports.
The reading PDF is still the approved Web landscape template, separate from the
QGIS-native map-export PDF. Its local export links resolve inside the final ZIP.

Both final ZIPs were extracted, exactly inventoried and hashed. Actual QGIS workers
mounted only their selected extracted-byte packets plus provider controls/output;
the private full bundle/original was not mounted as a fallback. Fresh public
reopen observations include:

- embedded GPKG `inici` actually reopened, with its `mdt` and `ortofoto` subdatasets;
- 600×640 EPSG:25831 raster grid, 1-band elevation / 3-band orthophoto;
- 22-feature Shapefile and typed table, with all declared sidecars retained;
- saved `Principal` / `Referència` themes and layer membership;
- editable `Infografia base`, independent `principal` and `localitzador` frames at
  1:15,000 / 1:75,000, with distinct extents matching their physical mm dimensions.

Those are assertions over the producer's public observations, not native-format
inspection implemented in Web. Scientific Geodisseny D/E controls and the real
TIGIT programme still belong to the upcoming authorised consumer runs.

Delivered native examples:

```text
.../native-acceptance-01/consumer/dist/practiques/candidate/2026-10-native-r1/ca/
```

| ZIP | Bytes | SHA-256 |
| --- | ---: | --- |
| `candidate-2026-10-native-r1-ca.zip` | 1591610 | `0c0f9536b7fa5a98254e698e4444fa5436f7e28ddf27be6ae2a3a5cfc0b39368` |
| `candidate-docent-2026-10-native-r1-ca.zip` | 2215680 | `0cf2b6440fea0953966a1194f4e8feb49c398adb24437071cd9e3df119c85b80` |

Their external receipt hashes are respectively
`8d2ca66cadc8e94255c8f6505d9a7a97833209cd9222e0ac7a57b6bde89d239a` and
`81d94c76aa87756702a9a42ab772101081b94e36c26b4bacdd6607ef7f2d63d6`.

The corresponding reading PDFs retain the approved A4 landscape layout and
first-page-only logos:

| Recipient | Pages | PDF SHA-256 |
| --- | ---: | --- |
| Alumnat | 4 | `d875d11b282983912ec4c783943815ea27eeb6d7056ef7e6cf1615bd05ee09fb` |
| Docent | 6 | `0326b75e690cba90f30aed7b66c45a2d7dc136fc2f3d954155fe9ee7c668ef47` |

Retained PDF paths, also recorded with their receipts in the acceptance evidence:

```text
/home/benizar/git/unaltraweb/tmp/practice-editions-98/native-acceptance-01/consumer/sandbox/practiques/candidate/lectura-2026-10-native-r1-ca-alumnat-edition-c7bdde58ad8f483f/outputs/LLEGIU-ME.pdf
/home/benizar/git/unaltraweb/tmp/practice-editions-98/native-acceptance-01/consumer/sandbox/practiques/candidate/lectura-2026-10-native-r1-ca-docent-edition-c7bdde58ad8f483f/outputs/LLEGIU-ME.pdf
```

Native negatives refuse missing font, altered sidecar, teacher export in student
selection and incorrect profile/schema/wheel pins without changing existing
deliveries. Final ZIPs with a Shapefile dependency removed/altered are also refused
after recalculating the archive hash; the original complete closure remains required.

### Regressions and final gates

- Same rc2 verifier over unchanged v1 data: complete installed composition, two
  consumers, additional CLI editions and final-ZIP offline reopens pass. Evidence
  `rc2-v1-acceptance-01/evidence.json`, SHA-256
  `ac64b727ada3d9d4e4391bc35421fdb0ebbb5317968e27050d55cd057dc22ca1`.
  ZIP hashes match the preceding rc1-verifier run; only verifier-bound receipts differ.
- TIGIT relative SVG links, HTTPS/internal anchors, Geodisseny retained-run image
  bindings, original-source/effective-source receipts, private anchored reviews,
  standalone refusal and bounded CLI teardown all pass with rc2. Evidence
  `rc2-links-acceptance-01/evidence.json`, SHA-256
  `358fa4e2cac126ea6e67325aa3cb0b100e60e1554abacfbe59fbf8f3d8cbedab`.
- Tuple, archive load, loaded fingerprint and actual embedded-reopen supplementary
  verification: `native-acceptance-01/tuple-check.json`, SHA-256
  `0bfbfc46cf621ef235f7eedf874d1a86bc9053f73367311b02ce1792c442d698`.
- **674 source tests: 647 passed / 27 optional skips**; distribution/whitespace and
  installed controller check/smoke pass. Original sources and prior candidates are
  preserved. Exact test controllers/engines are observed absent; zero job volumes.

This final candidate is available for the coordinator's explicit selection in all
three manual sessions. No publication or automatic scaffold/workflow migration is
required for the private practice circuit. The remaining step is each real manual's
authorised model/data/readings/adoption run, followed by human delivery/publication
decisions. No real manual is declared ready solely from this synthetic acceptance.

## Working-tree consolidation — independent PDF and ZIP

The author clarified the delivery contract: reproducibility code and draft
readings are versioned; data/PDFs stay outside Git and each activity supplies a
PDF and a ZIP for Moodle. The source compositor now stages, for each recipient:

```text
dist/practiques/<slug>/<version>/<lang>/
  <slug>[-docent]-<version>-<lang>.pdf
  <slug>[-docent]-<version>-<lang>.pdf.receipt.json
  <slug>[-docent]-<version>-<lang>.zip
  <slug>[-docent]-<version>-<lang>.zip.receipt.json
  edition.json
```

The independent PDF is an exact checked copy of the sealed reading job, not a
second render. The ZIP keeps the same `LLEGIU-ME.pdf`/`LEEME.pdf`/`README.pdf`
member. Its receipt adds `reading.delivery`; `packages.<recipient>` keeps its
existing ZIP fields and adds `pdf`. The PDF receipt binds its source job/receipt,
paired ZIP and edition receipt without a cyclic hash dependency. The complete
directory is installed with the same atomic no-replace operation. Failed copies
or receipts leave only a retained unpublished staging attempt.

The PDF is readable separately; its relative links still refer to the ZIP tree.
For local access to linked SVGs/data, extract the paired ZIP beside the PDF.
Uploading the two files separately to Moodle does not itself recreate that tree
as web URLs. No authored Markdown, approval status or link bytes are rewritten.

Four additional composition regressions cover byte equality, exactly one build
per reading, paired receipts, no-clobber, partial-failure atomicity, dry-run and
refusal of symlink/hash-drift copies. A read-only-source redelivery proof also
used the previously sealed native fixture PDFs with **zero renders/GIS runs**:

```text
/home/benizar/git/unaltraweb/tmp/practice-standalone-pdf-98/evidence.json
SHA-256 e830e214cbde8a76b90a2daee9b0e5a785fe9e79f0ad5ded4cd190284b625bf9
```

Both independent PDFs match their previous sealed bytes (`d875d11b…` alumnat,
`0326b75e…` docent), and both regenerated ZIPs match the previous ZIP hashes
exactly. This copy/packaging proof complements the full composition unit tests;
it is not a new installed-controller acceptance or a replacement of candidate-04.

The normal `Dockerfile.mcp` now invokes `scripts/install_practice_verifier.py`.
That installer accepts only the released QGIS wheel URL+SHA from the component
BOM, preserves pip direct-URL identity, and checks both explicit public profiles.
The final owner pin has not arrived: no placeholder is inserted into the BOM.
Source validation reports the required verifier as pending, publication preflight
refuses it, and image installation fails before pip/network until it is declared.
The existing PDF 0.7.1/workflow pins and nine shared checkers remain unchanged.

The retained controller/PDF archive route for D1 is documented in
[practice-runtime-archives-98.md](practice-runtime-archives-98.md).
