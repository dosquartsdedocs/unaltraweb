# Minimal #121 producer repair: P1 + P2

Coordination request:
`gacontext-itemarium-readiness-20261104-unaltraweb-02290003fd784c20a1659f4f803839ef`.

Authoritative workspace: `/home/benizar/git/unaltraweb`. Branch
`fix/121-context-inputs-html` starts from the preserved review125 at
`b67a51292f680d3bc0058b272c68116c3fd75bc4`; clean preflight was ELIGIBLE.
The review branch and experimental116 at
`6a8cd85ff75c8ad41dc67f8fb1c3c5a8f8919e53` remain intact. No other checkout,
registry, real manual or teacher bank is modified by this unit.

## Implemented repairs

**P1:** `Snapshot.computation_input` validates declared check-only dependencies
separately from public sources. Only native computation input/environment
declarations use this path. Existing descriptor-relative no-follow reads,
per-file/total budgets, complete native status checks and final input/inventory
rechecks are reused. No rendering or native source execution is introduced.

The private practice root stays forbidden to images/includes/outputs, even if a
caller attempts to name it as the manual collection. Opaque inputs remain outside
the archive; fingerprints and external retained receipts bind their exact bytes.
The same role correction supports TIGIT's explicitly declared root environment
files `Dockerfile.compute-python`, `Dockerfile.compute-r`,
`requirements-compute.txt` and `requirements-compute.R`. This avoids merely moving
the first private-data error to the next environment-file error.

**P2:** HTML `alt`, `title` and `data-caption-source` values are restored before
`figure()` stores metadata and computes the ID, just as Markdown attributes were.
Tests assert exact text and identity stability when unrelated inline code is added.

No general Liquid extension, SVG raster policy, QGIS provenance adapter, W1
integration or Geo collector is included. Existing typed refusal envelopes and
v1 schema remain unchanged.

## Tests and actual producer/receiver execution

- 30 targeted context cases, including private input success, no private payload
  or path leakage, global checking for an unrelated selected chapter, missing/
  changed data, root environment fingerprints, symlink/traversal/hidden-root
  refusals, unchanged 10 MiB reader limit and private-collection refusal.
- Full local suite during implementation: **771 cases, 743 passed, 28 skips**;
  the final declaration-type regression is additionally covered in the 30-case
  targeted pass. Final-head CI retains the repository-wide gate.
- `distribution-check`, `workflow-check`, `make mcp-check`, `make mcp-smoke`: PASS.
  Base runtime and PDF toolchain layers were cached; only MCP/package layers and
  small metadata were rebuilt for the successive fixes.
  Disk observation: 15 GiB before, 14 GiB after verification. No global cleanup.
- The acceptance runner has an explicit `--private-inputs-html` fixture mode.
  It uses synthetic native computation records (not a claim of computation
  rendering), a private input sentinel and the formerly broken HTML caption.
  The **real MCP exporter** creates both transport archives. Assertions inspect
  their exact manifests/closure, restored attributes, absence of private bytes/
  paths/tokens and create-only behavior. A real CLI selects one block as well.

Installed candidate controller:
`sha256:b5b6c1e7816623a63c3340b97195253ff612458cf4b96ed443fafad2a1369bac`.
Producer version **0.8.1 candidate**, fingerprint
`sha256:2f82f9adb62a7111229e270772f00c1276ec546e9e42e4ad54e32e86e2a8ebdf`.
The isolated stdio containers have read-only rootfs, disabled network, no Docker
socket, and only their synthetic manual mounted. Both close and are confirmed absent.

Evidence below `tmp/context-p1p2-acceptance-qualified/`:

| Artifact | SHA256 |
| --- | --- |
| `producer-receipt.json` | `a610e07bc6a369079406ea93edc02581b2ec6dcbe82506ad314ed0920fec46b6` |
| `manual-fixture/tmp/manual-context/v1/manual-context.tar.gz` | `8a53b2721e24544ba45ee18b8535f298691cb857054cd7ed12189d610007c971` |
| `manual-fixture/tmp/manual-context/v2/manual-context.tar.gz` | `971d22218e3b407825643f63e524c6438a378e6a90db624afa689e4b1d66a8b9` |

Itemarium's independent source runner 0.6.2 (engine
`1a8983100c4b0c72bac74912fdde7a4d8ad14ce9970e188f13aae611dbeee813`) consumes
these exact exporter archives and passes all four checks: integrity/closure,
isolated import, existing-bank preservation and backup/reopening. Receipt:
`tmp/context-p1p2-conformance-qualified/receipt.json`, SHA256
`1660f7c576aa52e6f9fbcb39ec7d15a3a6b3c56b3a8dd63b4e2d1017d24bd9b9`.
The source-mode preliminary run remains separately retained under
`tmp/context-p1p2-acceptance-01` / `tmp/context-p1p2-conformance-01`; it predates
the 0.8.1 metadata and is not relabelled as installed-candidate proof. Intermediate
`-081` and `-081-final` runs are also retained; the qualified run includes the
HTML entity-decoding and typed-declaration corrections. Protected HTML entities
are decoded once without double-decoding surrounding attribute text.

## Reproduction and next intake

From this checkout with a prepared Python environment and the candidate image:

```bash
python scripts/test_manual_context_export.py \
  --output /absolute/unaltraweb/tmp/new-p1p2-acceptance \
  --private-inputs-html --image <exact-prepared-controller-ID>
```

Feed its returned first/next paths and hashes directly to Itemarium's documented
`manual_package_conformance.py`, with a fresh output below Web's `tmp/`. Never
manufacture replacement archives. These tests qualify the implementation; they
do not substitute for the real TIGIT owner's subsequent export and bank workflow.

Source metadata proposes **0.8.1** for package/gem artifact/controller/runtime,
with publication status `ready` after explicit closeout authorization. The existing public checkout pin stays on
0.8.0 until a new immutable publication is verified. Independent selections:

- Native Git core `9d97197dec5fc9346ab795191a3afd18884c27fb`, gem **0.7.3**.
- Workflow `3332e0b93933f12317e05f1ce8d38ce80046feab`.
- PDF **0.7.1**, OCI `sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b`.
- Classic QGIS **0.6.1**, descriptor and controller/engine IDs unchanged.

Required next gates: review/integration, exact signed candidates and receipt-only
publication, cold installed proof, then a new reviewed hub intake. The local image
is not a published or admitted point. TIGIT keeps its current activated0.8.0
selection until explicit adoption, and must report a real export's path/SHA/receipt
or the next exact blocker. No real TIGIT package is claimed by this fixture proof.

## Follow-up review: opaque YAML dependencies

PR126 discussion `4471006805` was reproduced on `b582c998`: a declared
`_practices/course/data/parameters.yml` with valid YAML anchors and a current
synthetic native computation receipt failed in `Snapshot.copy`. Check-only
dependencies now pass `opaque=True`; Reader confinement, budgets, hashes and
final source checks remain shared. Configuration reads still scan YAML even
when a previous opaque read has already staged the file.

The regression exports the anchored dataset without transporting its private
bytes/path, then rejects its changed fingerprint. A separate regression refuses
anchors on a configuration read after an opaque copy and in `_config.yml`.
The installed-export harness also includes anchored YAML alongside the CSV
input. Full local suite: 774 tests, OK (28 skipped). Earlier candidate hashes
above remain historical; the changed source requires fresh installed-candidate
and receiver evidence before publication.
