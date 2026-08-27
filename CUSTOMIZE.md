# Customizing Sites

Customize generated websites from the site repository, not by editing this core directly.

For current customization guidance, use:

- `docs/customization.md` for profiles, feature toggles, local styles, manual mode, project resources and theme modes.
- `docs/distribution.md` for the split between this core and `unaltraweb-template`.
- `docs/agents/mcp-contract.md` for package-owned site creation and the MCP workflow.
- `../unaltraweb-template/README.md` for the optional full-profile demo workflow.

## Local Overrides

Child sites can override or extend the core with local files:

- `_config.yml` for site identity, URLs, profile selection and feature flags.
- `_sass/_site-custom.scss` for local CSS variables and small components.
- `_layouts/` for local layouts that intentionally override the core.
- `_pages/`, `_posts/`, `_projects/`, `_chapters/`, `_bibliography/` and `_data/` for editable content.
- `assets/` for local images, PDFs and downloads.

## Example Profile Config

```yaml
theme: unaltraweb

unaltraweb:
  site_profile: unaltreselfie
  features:
    blog: true
    cv: true
    projects: true
    publications: true
    metrics: true
```

## Local Core Development

When developing the core and template side by side, point the template to the local checkout:

```bash
cd ../unaltraweb-template
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte
```

Use only the relevant profile tests on constrained machines.
