# Distribution model

`unaltraweb` is the source of truth for reusable code. Template repositories should stay thin and contain only site-specific content and small integration files.

## User paths

### GitHub-only editing

Users can create a site from `dosquartsdedocs/unaltraweb-template`, edit content in the GitHub web UI, and let GitHub Actions build and publish the site.

This path is intended for small content edits, bibliography updates, course/manual chapter edits, and configuration changes.

### Local editing

Users who need larger edits can clone their generated site repository and use the local Docker workflow from the template:

```bash
make serve
make build
make test
```

Theme development can still happen side by side by pointing the template at a local core checkout:

```bash
make serve LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb
```

## What lives where

- `unaltraweb`: layouts, includes, Sass, assets, Jekyll plugins, Python and shell tooling, reusable GitHub Actions workflows, documentation and internal examples.
- `unaltraweb-template`: `_config.yml`, editable content, local overrides, small GitHub Actions wrapper, Dependabot config and optional local workflow helpers.

## Updates

Repositories created from a GitHub template are not linked to the template as forks, so template changes are not automatically proposed to users.

For that reason:

- normal improvements should ship through the `unaltraweb` gem or reusable workflows;
- site repositories should enable Dependabot for Bundler and GitHub Actions;
- breaking changes should be released with migration notes;
- scaffold changes should be rare and, when needed, delivered as explicit pull requests or a future `unaltraweb sync` command.
