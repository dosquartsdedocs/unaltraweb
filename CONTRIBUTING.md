# Contributing

This repository is the reusable `unaltraweb` core. Keep changes focused on functionality that belongs in the shared gem, not on one site's content.

## Before Changing Code

- Check `TODO.md` for current decisions and pending work.
- Check `docs/_documentation/en/40-distribution.md` to decide whether the change belongs in the core or a consumer.
- Build context before editing. This codebase still contains inherited `al-folio` pieces.
- Run the configured MCP control plane's read-only checkout preflight before editing in the repository's primary mutable checkout.

## Core vs Consumers

- Put reusable layouts, includes, Sass, assets, plugins, scripts, docs, and package-managed scaffold controls in `unaltraweb`.
- Keep site-specific content, configuration, bibliography, and generated figure bundles in the consumer repository.
- Use `unaltraweb-template` only for the full multi-profile demo and its visual smoke tests.
- Validate `new_web` and `scaffold_sync` whenever a change affects generated consumers; use the demo when profile rendering also changes.

## Verification

Core build:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

Template smoke checks:

```bash
cd ../unaltraweb-template
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreselfie PORT=4018
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte PORT=4019
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual PORT=4020
make down
```

The template tests are resource-heavy. On constrained machines, run only the relevant profile or start with `make build`.

## Pull Requests

- Reserve one focused issue and the exact paths before editing. Use one primary mutable checkout, one active editing session, and one short-lived task branch per repository; a path reservation limits review scope rather than permitting concurrent sessions.
- Use the control plane's `exec` wrapper when a process-held cooperative lease is required. Never create, switch to, move, prune, repair, or remove Git worktrees implicitly.
- For MCP-backed work, request one top-level MCP and let the control plane select its declared dependency closure. Pass a consumer root only through `MCP_CONSUMER_WORKSPACE`, and keep factory `build`, `check`, and `smoke` operations in the factory checkout.
- Use `format/<issue>-<slug>` for reusable web/PDF presentation, `feat/<issue>-<slug>` for reusable behavior, and `fix/`, `docs/`, or `chore/` for their corresponding provider work.
- Keep content, bibliography, figure specifications, and generated consumer artefacts in the consumer repository. Change reusable renderers in their provider repository, release them, and integrate the immutable revision separately.
- Keep changes small and explain why they belong in the core.
- Do not add runtime API calls to normal Jekyll builds.
- Do not commit generated local caches such as `_site/`, `tmp/`, `.cache/`, `node_modules/` or responsive image outputs.
- Do not add compatibility branches unless there is a concrete external consumer or persisted-data need.
- Open a Draft pull request early. After merge or closure, release the reservation and any cooperative lease, delete the task branch, and retain the primary checkout. `main` is the only long-lived human-maintained branch.

## Commits

Do not commit from an automation session unless explicitly requested. Before pushing, verify that `origin` points to `git@github.com:dosquartsdedocs/unaltraweb.git`.
