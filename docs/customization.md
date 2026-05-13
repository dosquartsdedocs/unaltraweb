# Customization

`unaltraweb` is intended to be customized from the site repository, not by editing the core theme files.

## Local Styles

Create `_sass/_site-custom.scss` in your site repository. It is imported after the core styles, so local rules can override CSS custom properties or add small components while still receiving upstream `unaltraweb` updates.

```scss
:root {
  --global-theme-color: #2f6f5e;
  --global-hover-color: #2f6f5e;
}

html[data-theme="sepia"] {
  --global-theme-color: #6f4e1f;
}
```

## Local Layouts

Create a layout in `_layouts/` inside the site repository and reference it from page front matter.

```liquid
---
layout: page
---

<div class="my-local-layout">
  {{ content }}
</div>
```

```yaml
---
layout: my-local-layout
title: Custom Page
---
```

Jekyll resolves site files before theme files, so local layouts can extend or override core layouts without forking `unaltraweb`.

## Theme Modes

The built-in theme switch supports `system`, `light`, `sepia`, and `dark` settings. `system` follows the browser preference and resolves to light or dark; `sepia` is an explicit reading mode inspired by GitBook's sepia palette.

Theme changes are observable from JavaScript through the `unaltraweb:themechange` event:

```js
document.addEventListener("unaltraweb:themechange", (event) => {
  console.log(event.detail.theme, event.detail.themeSetting);
});
```

The active values are also available on `<html>` as `data-theme`, `data-theme-setting`, `data-theme-integration`, and `data-site-type`. These attributes are stable enough for local styles and automated browser tests.
