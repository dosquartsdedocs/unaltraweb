"""Installed new/updated manual acceptance, including the exact reviewed #86 edit.

Uses owned synthetic consumers; executes their selected provider preflight and
real web/PDF builds. It never dispatches a hosted consumer deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

import yaml

from distributed_launcher_smoke import Client


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--legacy-image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.absolute()
    out.mkdir(parents=True, exist_ok=False)
    evidence = {"image": args.image, "legacy_image": args.legacy_image, "cases": []}

    for name in ("new", "upgrade", "reviewed-hotfix"):
        project = out / name
        project.mkdir()
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        old = name != "new"
        client = Client(args.launcher, project, args.legacy_image if old else args.image, out / (name + "-create.log"))
        try:
            client.tool("new_web", site_profile="unaltremanual", title="Deployment integration", baseurl="/integration")
            client.tool("site_source_write", path="_chapters/en/coordinates.md", create_only=True, dry_run=False,
                        content="---\nlayout: manual-chapter\ntitle: Coordinates\nlang: en\nref: coordinates\nweight: 1\npermalink: /en/chapters/coordinates/\n---\n\nA coordinate locates a point relative to an origin. A reference frame makes coordinates comparable.\n")
            if old:
                client.tool("build_site")
            config = client.tool("site_source_read", path="_config.yml")
            changed = config["content"].replace("      enabled: false\n", "      enabled: true\n", 1)
            assert changed != config["content"]
            client.tool("site_source_write", path="_config.yml", content=changed, expected_sha256=config["sha256"], dry_run=False)
        finally:
            client.close()
        (project / "author-note.txt").write_text("Authored state must survive the update.\n")
        caller = project / ".github/workflows/deploy.yml"
        if name == "reviewed-hotfix":
            assert digest(caller) == "a789870542614d5817d30ea4328c7d1ad38d27443c009c68a48ad5aaa3106b8e"
            caller.write_bytes(caller.read_bytes().replace(b"02af70001bf8085af860fd57f8d7e75ec96a89c7", b"0845277b9ddd7c7b5bdcf5d6459846a1958970f3"))
            assert digest(caller) == "c632a548d0782867be20a2a52fe03469cf63066b7364bace77fd54a226cb3b18"
        retained = ["_config.yml", "_chapters/en/coordinates.md", "README.md", "author-note.txt"]
        original = {path: digest(project / path) for path in retained}
        caches = {str(path.relative_to(project)): digest(path) for path in project.glob("tmp/**/Gemfile*") if path.is_file()}
        client = Client(args.launcher, project, args.image, out / (name + "-updated.log"))
        try:
            plan = client.tool("scaffold_sync")
            assert not plan["conflicts"]
            if name == "reviewed-hotfix":
                assert [row["id"] for row in plan["migrations"]] == ["deploy-provenance-86"]
            applied = client.tool("scaffold_sync", dry_run=False, confirm_sync=True, expected_plan_sha256=plan["plan_sha256"])
            assert applied["ok"]
            assert {path: digest(project / path) for path in retained} == original
            assert all(digest(project / path) == sha for path, sha in caches.items())
            subprocess.run(["git", "-C", str(project), "add", "--", "."], check=True)
            client.tool("site_check")
            client.tool("manual_pdf_preview_prepare")
            client.tool("build_site")
            preview = client.tool("preview_start", timeout_seconds=180)
            client.tool("http_check", paths=[preview["path"], "/integration/en/chapters/coordinates/", "/integration/assets/pdf/manual-en.pdf"])
            pdf = project / "tmp/manual-pdf/en/manual-en.pdf"
            assert pdf.is_file() and pdf.stat().st_size > 1000

            # Run exactly the remote workflow selected by the generated caller.
            called = yaml.safe_load(caller.read_text())["jobs"]["deploy"]
            match = re.fullmatch(r"dosquartsdedocs/unaltraweb/\.github/workflows/site-deploy\.yml@([0-9a-f]{40})", called["uses"])
            assert match
            workflow_sha = match[1]
            with urlopen(f"https://raw.githubusercontent.com/dosquartsdedocs/unaltraweb/{workflow_sha}/.github/workflows/site-deploy.yml", timeout=60) as response:
                workflow_bytes = response.read(262145)
            assert len(workflow_bytes) <= 262144
            workflow = yaml.safe_load(workflow_bytes)
            environment = {key: value for key, value in os.environ.items() if key not in {"BASH_ENV", "ENV"}}
            environment.update(WORKFLOW_REPOSITORY="dosquartsdedocs/unaltraweb", WORKFLOW_SHA=workflow_sha,
                               MANUAL_PDF_IMAGE=called["with"]["manual-pdf-image"], CURRENT_REF="refs/heads/main",
                               CURRENT_SHA="a" * 40, REVIEWED_SHA="a" * 40, RUNNER_TEMP=str(out))
            for step in workflow["jobs"]["build"]["steps"]:
                if step.get("name") in {"Validate latest publication source", "Verify manual PDF image provenance"}:
                    completed = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
                                               cwd=project, env=environment, capture_output=True, text=True, timeout=300)
                    assert completed.returncode == 0, completed.stderr
            evidence["cases"].append({"name": name, "ok": True, "target": plan["target"], "migrations": plan["migrations"],
                                      "workflow_sha": workflow_sha, "workflow_file_sha256": hashlib.sha256(workflow_bytes).hexdigest(),
                                      "author_hashes": original, "retained_cache_hashes": caches, "pdf_sha256": digest(pdf),
                                      "selected_workflow_gates": "passed", "site_http_pdf": "passed"})
            assert {path: digest(project / path) for path in retained} == original
            print(json.dumps({"case": name, "ok": True, "workflow_sha": workflow_sha}), flush=True)
        finally:
            try:
                client.tool("preview_stop")
            finally:
                client.close()
        (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
