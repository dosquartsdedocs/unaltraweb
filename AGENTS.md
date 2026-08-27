# unaltraweb Agent Contract

## Repository Role

`unaltraweb` is the reusable Jekyll core, Docker runtime, MCP factory, documentation source, and shared workflow owner for four website profiles. It is not a single consumer website.

- `unaltreselfie`: personal academic or professional sites.
- `unaltreprojecte`: projects, groups, infrastructures, and research outputs.
- `unaltremanual`: teaching manuals, courses, and book-like publications.
- `unaltredocs`: technical and operational documentation.

## Source Boundaries

- Shared Jekyll behavior belongs in `_layouts/`, `_includes/`, `_plugins/`, `_sass/`, `assets/`, and library code.
- MCP/API/CLI behavior belongs in `src/unaltraweb_mcp/` with tests under `test/`.
- Clean new-site assets belong in `src/unaltraweb_mcp/scaffolds/` and must remain package-owned.
- Public reference content belongs in `docs/_documentation/en/`.
- Repository agents belong in `.github/agents/`; reusable consumer agents, skills, contracts, and prompt sources belong in `plugins/unaltraweb-site/` and `docs/agents/`.
- `unaltraweb-template` is an external integration fixture and visual demo, not a scaffold source or runtime dependency.

Do not edit generated `_site/`, `tmp/`, Jekyll caches, computation locks, generated figures, capture outputs, or publication artefacts as substitutes for changing their source workflows.

## MCP Contract

Use `mcp-factory.yml`, `docs/agents/mcp-contract.md`, and the running server as one contract. Keep resource and tool inventories synchronized; tests enforce manifest/runtime parity.

- `unaltraweb` owns site/profile/content/manual/bibliography/build orchestration.
- `diavisuals` owns Mermaid and PlantUML rendering and styles.
- `vegavisuals` owns Vega/Vega-Lite validation, rendering, themes, and freshness.
- Advanced computation, capture, PDF, and bibliometrics implementations stay factory-owned and operate against consumer projects.

## Change Workflow

1. Inspect the affected implementation, contract documentation, and tests before editing.
2. Prefer the smallest change that preserves package-owned scaffolds and thin consumer sites.
3. Add or update tests for behavior, packaging, safety boundaries, and machine-readable inventories.
4. Run `PYTHONPATH=src python3 -m unittest discover -s test -p 'test_*.py'`.
5. Run `git diff --check`.
6. For runtime/scaffold changes, run `make mcp-check` and `make mcp-smoke` when Docker is available.
7. For public docs changes, run `make docs-build` when feasible.

## Safety And Publication

- Treat consumer paths, Make variables, symlinks, generated files, and Docker resources as security boundaries.
- Never weaken no-clobber or confinement behavior to make initialization more convenient.
- Do not fetch external metrics during normal Jekyll builds.
- Do not silently replace edited SVGs or unmanaged generated outputs.
- Do not commit visible consumer content before rendered human review.
- Do not push, merge, tag, publish gems/images, deploy, or create releases without explicit approval.

## Documentation Discipline

Describe current `unaltraweb` behavior rather than inherited `al-folio` conventions. Distinguish core-maintainer commands from generated-site commands, and distinguish built-in MCP capabilities from companion-factory tools.
