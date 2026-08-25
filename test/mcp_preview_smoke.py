from __future__ import annotations

import os
from pathlib import Path

from unaltraweb_mcp import site_tools


def create_site(project: Path) -> None:
    (project / "_pages").mkdir(parents=True, exist_ok=True)
    (project / "tmp/Gemfile.local.lock").unlink(missing_ok=True)
    (project / "_config.yml").write_text(
        "title: Preview smoke\n"
        "baseurl: \"\"\n"
        "theme: unaltraweb\n"
        "plugins: [unaltraweb]\n"
        "unaltraweb:\n"
        "  site_profile: unaltreselfie\n",
        encoding="utf-8",
    )
    (project / "Gemfile").write_text('gem "unaltraweb"\n', encoding="utf-8")
    (project / "Makefile").write_text(
        "LOCAL_CORE ?= /opt/unaltraweb\n"
        "LOCAL_GEMFILE := tmp/Gemfile.local\n\n"
        ".PHONY: local-gemfile build-native serve-native\n\n"
        "local-gemfile:\n"
        "\t@mkdir -p tmp\n"
        "\t@printf '%s\\n' 'source \"https://rubygems.org\"' 'gem \"unaltraweb\", path: \"$(LOCAL_CORE)\"' > $(LOCAL_GEMFILE)\n\n"
        "build-native: local-gemfile\n"
        "\t@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle lock --local\n"
        "\t@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle check\n"
        "\t@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle exec jekyll build --config $(LOCAL_CORE)/_config.yml,_config.yml --disable-disk-cache\n\n"
        "serve-native: local-gemfile\n"
        "\t@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle lock --local\n"
        "\t@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle check\n"
        "\t@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle exec jekyll serve --config $(LOCAL_CORE)/_config.yml,_config.yml --host $(HOST) --port $(PORT) --disable-disk-cache\n",
        encoding="utf-8",
    )
    (project / "_pages/index.md").write_text(
        "---\nlayout: default\ntitle: Home\npermalink: /\n---\nPreview smoke.\n",
        encoding="utf-8",
    )


def main() -> None:
    project = Path("/workspace")
    if not os.environ.get("UNALTRAWEB_DOCKER_ROOT"):
        raise SystemExit("UNALTRAWEB_DOCKER_ROOT must identify the mounted host fixture")
    create_site(project)
    port = int(os.environ["UNALTRAWEB_PREVIEW_PORT"])
    try:
        started = site_tools.preview_start(project, port=port, timeout_seconds=120)
        assert started["ok"] is True, started
        assert started["ready"] is True
        assert started["url"] == f"http://127.0.0.1:{port}/"

        status = site_tools.preview_status(project)
        assert status["ok"] is True
        assert status["running"] is True
        assert status["container"].startswith("unaltraweb-preview-")
    finally:
        stopped = site_tools.preview_stop(project)
        assert stopped["ok"] is True


if __name__ == "__main__":
    main()
