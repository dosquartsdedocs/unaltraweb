from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from unaltraweb_mcp import manual_pdf_preview
from unaltraweb_mcp import site_tools


def create_site(project: Path) -> None:
    for child in project.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    created = site_tools.new_web(
        project,
        site_profile_value="unaltremanual",
        title="Preview smoke",
        baseurl="/preview-smoke",
        default_lang="en",
        languages=["en"],
    )
    assert created["ok"] is True, created
    config = project / "_config.yml"
    config_text = config.read_text(encoding="utf-8")
    enabled = config_text.replace("      enabled: false\n", "      enabled: true\n", 1)
    assert enabled != config_text
    config.write_text(enabled, encoding="utf-8")
    chapter = project / "_chapters/en/chapter-0.md"
    chapter.parent.mkdir(parents=True, exist_ok=True)
    chapter.write_text(
        "---\nlayout: manual-chapter\ntitle: Chapter 0\nlang: en\n"
        "ref: chapter-0\nweight: 0\npermalink: /en/chapters/chapter-0/\n---\n\n"
        "Docker-backed stale PDF preview smoke.\n",
        encoding="utf-8",
    )
    practice = project / "practiques/smoke/en/alumnat/README.md"
    practice.parent.mkdir(parents=True)
    practice.write_text("---\ntitle: Private practice smoke\nlang: en\ncontent_status: draft\n---\n\n# Begin\n\nPrivate practice sentinel.\n")
    for relative in ("sandbox/practiques/smoke/input-private.txt", "dist/practiques/smoke/private.zip"):
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"Private practice sentinel")
    subprocess.run(["git", "init", "--quiet"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "preview-smoke@example.test"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Preview Smoke"], cwd=project, check=True)
    subprocess.run(["git", "add", "--all"], cwd=project, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "Initialize preview smoke"], cwd=project, check=True)


def main() -> None:
    raw_project = os.environ.get("UNALTRAWEB_DOCKER_ROOT")
    if not raw_project:
        raise SystemExit("UNALTRAWEB_DOCKER_ROOT must identify the mounted host fixture")
    project = Path(raw_project).resolve()
    if not project.is_dir() or not Path("/workspace").samefile(project):
        raise SystemExit("The host fixture must be mounted at both its host path and /workspace")
    create_site(project)
    prepared = site_tools.manual_pdf_preview_prepare(project, Path("/opt/unaltraweb"))
    assert prepared["ok"] is True, prepared
    assert prepared["publishes"] is False, prepared
    assert prepared["built_languages"] == ["en"], prepared
    assert (project / manual_pdf_preview.RECEIPT_PATH).is_file()
    assert not (project / manual_pdf_preview.PUBLICATION_INTENT_PATH).exists()
    assert not (project / manual_pdf_preview.PUBLICATION_RECEIPT_PATH).exists()
    language = prepared["status"]["languages"][0]
    for key in ["generated_pdf", "generated_cover", "published_pdf", "published_cover"]:
        assert (project / language[key]).is_file(), language[key]

    practice = site_tools.manual_practice_pdf_build(
        project, Path("/opt/unaltraweb"), "practiques/smoke/en/alumnat/README.md", "smoke-v1")
    assert practice["ok"] is True and practice["publishes"] is False, practice
    assert practice["state"] == "built", practice
    assert (project / practice["pdf"]).is_file()
    repeated = site_tools.manual_practice_pdf_build(
        project, Path("/opt/unaltraweb"), "practiques/smoke/en/alumnat/README.md", "smoke-v1")
    assert repeated["state"] == "current", repeated
    assert site_tools.manual_pdf_status(project, Path("/opt/unaltraweb"))["languages"][0]["fresh"] is True

    try:
        started = site_tools.preview_start(project, site_profile="unaltremanual", timeout_seconds=180)
        assert started["ok"] is True, started
        assert started["ready"] is True
        port = int(started["port"])
        assert 1024 <= port <= 65535, started
        assert started["requested_port"] == 0, started
        assert started["container_port"] == 4000, started
        route = str(started["ready_path"])
        assert route in {"/preview-smoke/", "/preview-smoke/en/"}, started
        assert started["url"] == f"http://127.0.0.1:{port}{route}"

        status = site_tools.preview_status(project)
        assert status["ok"] is True
        assert status["running"] is True
        assert status["container"].startswith("unaltraweb-preview-")
        inspected = json.loads(subprocess.run(
            ["docker", "inspect", status["container"]],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout)[0]
        assert all(mount.get("Destination") != "/var/run/docker.sock" for mount in inspected.get("Mounts", []))

        checked = site_tools.http_check(project, paths=[route], timeout_seconds=2)
        assert checked["ok"] is True, checked
        assert checked["owned"] is True
        assert checked["redirects_followed"] == 0
        audit = site_tools.html_audit(project)
        assert audit["ok"] is True, audit
        manual_home = (project / "_site/en/index.html").read_text(encoding="utf-8")
        assert 'class="manual-download"' in manual_home
        assert "assets/img/manual-cover-en.png" in manual_home
        assert (project / "_site/en/chapters/chapter-0/index.html").is_file()
        for private in ("practiques", "sandbox", "dist"):
            assert not (project / "_site" / private).exists(), private
    finally:
        stopped = site_tools.preview_stop(project)
        assert stopped["ok"] is True
        cleanup_plan = site_tools.manual_pdf_preview_clean(project)
        assert cleanup_plan["ok"] is True, cleanup_plan
        cleaned = site_tools.manual_pdf_preview_clean(
            project,
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256=cleanup_plan["receipt_sha256"],
        )
        assert cleaned["ok"] is True, cleaned
    assert not (project / language["published_pdf"]).exists()
    assert not (project / language["published_cover"]).exists()
    assert not (project / manual_pdf_preview.PUBLICATION_INTENT_PATH).exists()
    assert not (project / manual_pdf_preview.PUBLICATION_RECEIPT_PATH).exists()
    assert (project / practice["pdf"]).is_file()
    assert (project / "sandbox/practiques/smoke/input-private.txt").read_bytes() == b"Private practice sentinel"
    assert (project / "dist/practiques/smoke/private.zip").read_bytes() == b"Private practice sentinel"
    assert subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=project,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout == ""


if __name__ == "__main__":
    main()
