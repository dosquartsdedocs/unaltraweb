# FAQ

## Is `unaltraweb` a website or a theme core?

It is a reusable Jekyll core distributed as a gem. Normal user sites should start from the profile-specific scaffold created by `new_web`; `dosquartsdedocs/unaltraweb-template` is the full integration demo.

## Where should demo content live?

Most demo content belongs in `unaltraweb-template`, because it validates the gem as an external dependency. The core `docs/` directory is reserved for documentation and a small public core demo/documentation site.

## How do I create a new site?

Call the `new_web` MCP tool or run `unaltraweb-mcp --project ./my-site new-web --site-profile PROFILE`. The operation creates package-owned common files, profile configuration, localized home pages, and the content paths required by the selected profile.

## How are site types selected?

Use `unaltraweb.site_profile` in `_config.yml`. Supported profiles are currently `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`.

## What does the search setting control?

Every profile builds `assets/js/content-search-index.json` and exposes full-text content search. Results represent individual occurrences, including repeated terms on one page, and destination pages provide previous/next occurrence navigation. The older `search_enabled` setting controls the separate Ninja Keys navigation and metadata palette; bibliography filtering also remains a separate, page-local tool.

## Can Jekyll builds fetch metrics from external services?

No. Normal builds must remain static. Run metrics scripts explicitly before build time, then commit the resulting local data files when appropriate.

## Why are there still `al-folio` references?

`unaltraweb` started from `al-folio`. Some inherited code, comments, demo assets and Docker assumptions remain while the core is being generalized. Replace them gradually when the replacement is clearly reusable.

## How should I validate changes?

Use the core build for internal consistency and the template tests for consumer behaviour. The template Playwright tests are heavier, so run the smallest relevant profile when resources are limited.
