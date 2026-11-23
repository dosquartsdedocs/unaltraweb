# Practice artifacts and snapshot review — 2026-11-12

## Reviewed source units

- PR129, `e4d6034278c2ada816918a2c62113fe9a5d1d466`: bounded temporary
  release-candidate transport. Remote CI/CodeQL, including Docker MCP/docs, pass.
  Its S3 path deliberately requires public-access-block/lifecycle/versioning
  observations. That is a qualification gate, not proof that the existing S4
  account supports this candidate profile. Keep its native schema2 publication
  metadata and expiration semantics distinct from durable practice products.
- PR130, `7bcd48f8900c059c465e29fffc55a62fe0b957fb`: pinned early preparation,
  native freshness gates and explicit tabular edition v2. Remote CI/CodeQL,
  including Docker MCP/docs, pass. Review covered source-only CI, original GIS
  schema preservation, private paths, recipient separation, sealed PDF/ZIP copies
  and final create-only installation. Consumer/private-GIS qualification remains
  the boundary described in `web-practices-reconciliation.md`.

Both PRs are still open; this review is local implementation review, not an
independent approval, merge, runtime selection or publication receipt.

## #114 correction

The previous release snapshot used only a fixed runtime exclusion list. It
descended into the explicitly Jekyll-excluded `.unaltramesa` tree and refused its
live Unix socket before a valid build receipt could be produced.

The corrected snapshot prunes whole private roots only when explicitly excluded:
`.unaltramesa`, `context`, `practiques`, `_practices`, `dist`, alongside existing
runtime exclusions. Includes that conflict with a private root are refused.
Jekyll implementation sources such as `_includes` stay fingerprinted even if
listed in `exclude`; that configuration is not a general fingerprint ignore list.
Admitted sockets, symlinks, nested VCS metadata and private `_site` leaks still fail.
Stable Git identity/index/blob validation remains authoritative.

Regression uses a live synthetic AF_UNIX socket, both source snapshot modes,
build receipts and latest release readiness. Changing excluded private bytes
does not stale the receipt, expose its contents or change the socket inode.

## Durable per-artifact adoption

The owner refines gaContExt #89's project-level alternatives to **one explicit
destination per artifact**, primarily for practice files. Web adopts the frozen
product/publication schemas at hub revision
`3c094009819785135bc8851b4fddd4723dbfe693`:

- Product schema SHA-256: `b75a43fb755f650a20690b03920830eb42f4638b4bb315575ae26e3043139ef0`.
- Policy schema SHA-256: `3bff0bfba6be332ef1b4cbfb7d01bee7e8edfe3251dbfed4a8c5c0b89a620d34`.

The route map is Web-owned and binds each selected native receipt, format,
audience and target. Product identity stays destination-neutral. Source-free
metadata travels with the exact PDF/ZIP; private receipts and source history do
not. Public GitHub is self-contained in the public wheel. S4 uses the optional
public Botocore SDK, named-v1 object layout and canonical restore manifest,
without importing a private hub, memory service or AWS lifecycle assumptions.

Qualification still needs the actual practice destination and explicit scoped
credentials, reviewed runtime/source integration, real selected PDF/ZIP retrieval
and owner acceptance of reader-facing links. Existing manuals and their runtime
selections are separate adoption work.

## Verification

- Full source suite: **811 tests, 28 explicit skips**, using the isolated declared-
  dependency environment at `/tmp/opencode/web-artifacts-practices-venv` with
  `PYTHONPATH=src python3 -m unittest discover -s test -p 'test_*.py'`.
- `make distribution-check`, `make workflow-check`, `make wheel-check` and
  `git diff --check` pass. The wheel check validates exact packaged modules,
  frozen schemas, generated policies and factory-free CLI discovery.
- Independent gaContExt inspection/destination planning accepts all three
  synthetic artifacts. Its native named-v1 fetch reconstructs both Web-produced
  student/teacher ZIP products in new roots, including exact manifests/sidecars.
  This is offline interoperability evidence, not remote endpoint qualification.
- The source-containing development MCP passes version, real stdio resources/
  tools and the complete PDF/practice/preview smoke. The development image layers
  current source on published MCP digest `a4f4f1b6…`; the initial from-scratch Ruby
  base build exceeded the 600-second budget during gem installation.
- `make docs-build DOCKER_IMAGE="--entrypoint= unaltraweb-mcp:dev"` passes against
  the real core gem and `unaltredocs` profile.

The first full preview smoke with the previously published PDF worker
`1bb3f2da…` correctly refused freshness: its embedded `build_pdf.py` SHA-256 is
`d31ba8eb1b2e0bd472870f94f3f2340eacf2569bdf709452d3ac6bfba70b3e96`, while the
reviewed checkout uses `d3d580ef5810383fa195da5633137123f55164b059766950dd204deba01a30bf`.
The Dockerfile, bibliography/code/figure filters and manual template match. A local
development PDF image reuses that immutable toolchain and installs the exact
current source/contract closure from the existing PDF Dockerfile's COPY list.
The matching local pair passes `make -o mcp-image -o manual-pdf-image-dev mcp-smoke
MCP_IMAGE=unaltraweb-mcp:dev MCP_SMOKE_MANUAL_PDF_IMAGE=unaltraweb-manual-pdf:dev`.
The next reviewed runtime tuple needs a matching PDF builder; the failed earlier
pair is not counted as accepted publication or hidden by a fingerprint override.
