# Contributing

This repository is the reusable `unaltraweb` core. Keep changes focused on functionality that belongs in the shared gem, not on one site's content.

## Before Changing Code

- Check `TODO.md` for current decisions and pending work.
- Check `docs/distribution.md` to decide whether the change belongs in the core or in `../unaltraweb-template`.
- Build context before editing. This codebase still contains inherited `al-folio` pieces.

## Core vs Template

- Put reusable layouts, includes, Sass, assets, plugins, scripts and docs in `unaltraweb`.
- Put starter content, demo pages, local workflow glue and visual smoke tests in `unaltraweb-template`.
- Validate profile behaviour through the template whenever the change affects gem consumers.

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

- Keep changes small and explain why they belong in the core.
- Do not add runtime API calls to normal Jekyll builds.
- Do not commit generated local caches such as `_site/`, `tmp/`, `.cache/`, `node_modules/` or responsive image outputs.
- Do not add compatibility branches unless there is a concrete external consumer or persisted-data need.

## Commits

Do not commit from an automation session unless explicitly requested. Before pushing, verify that `origin` points to `git@github.com:dosquartsdedocs/unaltraweb.git`.
