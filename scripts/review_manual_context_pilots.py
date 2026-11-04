"""Opt-in, version-bound #121 review against the published 0.8.0 controller.

Creates synthetic sources, invokes the REAL installed CLI without network/socket,
and retains successes AND expected refusals. It does not repair the exporter,
render figures, manufacture transport archives, or mount a teaching manual.
Native computation locks below are explicitly synthetic check fixtures, not
evidence that R/Python rendering took place. Itemarium checking is optional and
uses its read-only source tree with a separately prepared Python interpreter.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "sha256:e0502369c85c59f9e512fbd9fdb17dbc128845d057a1423375425e68ce2e79a2"
OLD_IMAGE = "sha256:ea14b1224382e47031b979d294f970b66773155584ac8f9eb94a33dc6421b0c9"
SOURCE = "54afe7588c36e959a7eb75d5f52763a7456108d7"
PRODUCER = "sha256:a678d2b2649e3479d0049ca0ca8a500aba5bb3f0a59b070cd7aaf5c0c6b466d0"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="20"><rect width="30" height="20" fill="white"/><text x="1" y="12">Fixture</text></svg>'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data.encode() if isinstance(data, str) else data)


def command(argv, *, cwd=None, expected=0, env=None):
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
    if expected is not None and result.returncode != expected:
        raise RuntimeError(f"Command failed: {argv}: {result.returncode}\n{result.stderr[-4000:]}")
    return result


def cases(root):
    from PIL import Image
    import yaml
    png = io.BytesIO()
    Image.new("RGB", (2, 2), "navy").save(png, format="PNG")
    encoded = base64.b64encode(png.getvalue()).decode()
    rows = [
        {"id": "baseline", "body": 'Text.\n\n![Alt](assets/img/plain.svg "Caption")\n', "ok": True},
        {"id": "missing-id", "no_id": True, "error": "unaltraweb.manual.id"},
        {"id": "missing-figure", "body": '![Alt](assets/img/missing.svg "Caption")\n', "error": "Missing editorial input"},
        {"id": "public-input", "compute": "assets/data/input.gpkg", "ok": True},
        {"id": "private-input", "compute": "_practices/fixture/data/input.gpkg", "error": "outside the public manual source roots"},
        {"id": "private-input-other-chapter", "compute": "_practices/fixture/data/input.gpkg", "unreferenced": True,
         "chapter": "first", "error": "outside the public manual source roots"},
        {"id": "changed-public-input", "compute": "assets/data/input.gpkg", "changed_input": True,
         "error": "source_or_environment_changed"},
        {"id": "private-image", "body": '![Alt](_practices/fixture/private.png "Private")\n',
         "extra": {"_practices/fixture/private.png": png.getvalue()}, "error": "outside the public manual source roots"},
        {"id": "components", "body": '''{% include note.md %}

{% cite fixture %}

::: table "Table caption"
| A | B |
| --- | --- |
| 1 | 2 |
:::

::: subfigures a+b "Group caption"
![A]({{ site.baseurl }}/assets/img/plain.svg "Panel A")
![B](assets/img/plain.svg "Panel B")
:::
''', "extra": {"_includes/note.md": "Term\n: Exact definition.\n\n>>>> Warning text.\n",
               "_bibliography/manual.bib": '@book{fixture, title={Fixture reference}, author={Author, A}, year={2026}}'}, "ok": True},
        {"id": "liquid-expression", "body": "Title: {{ page.title }}\n", "error": "unresolved Liquid/include"},
        {"id": "include-parameters", "body": '{% include note.md label="Example" %}\n',
         "extra": {"_includes/note.md": "A note."}, "error": "without parameters"},
        {"id": "html-caption-code", "body": '<img src="assets/img/plain.svg" alt="Alt `code`" title="Caption `literal`">\n',
         "ok": True, "expected_caption": "Caption `literal`"},
        {"id": "embedded-raster", "body": '![Raster](assets/img/embedded.svg "Raster")\n',
         "image": "assets/img/embedded.svg", "extra": {"assets/img/embedded.svg": '<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,' + encoded + '" width="2" height="2"/></svg>'},
         "error": "cannot receive SVG <image>"},
        {"id": "external-raster", "body": '![Raster](assets/img/external.svg "Raster")\n',
         "image": "assets/img/external.svg", "extra": {"assets/img/external.svg": '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.invalid/image.png"/></svg>'},
         "error": "cannot receive SVG <image>"},
        {"id": "qgis-vector", "body": '![Map](assets/img/map.svg "Map")\n', "image": "assets/img/map.svg",
         "extra": {"assets/img/map.svg": SVG.replace("<rect", '<metadata>{"producer":"unaltracaptura-qgis"}</metadata><rect')},
         "error": "QGIS capture handoff is not supported"},
        {"id": "qgis-untyped", "body": '![QGIS result](assets/img/map.svg "Authored static bytes")\n',
         "image": "assets/img/map.svg", "extra": {"assets/img/map.svg": SVG}, "ok": True},
    ]
    for row in rows:
        case = root / row["id"]
        case.mkdir()
        config = {"theme": "unaltraweb", "title": "Synthetic review", "default_lang": "ca", "languages": ["ca"],
                  "exclude": ["tmp/", "_practices/"], "unaltraweb": {"site_profile": "unaltremanual", "manual": {"id": "review-121"}}}
        if row.get("no_id"):
            del config["unaltraweb"]["manual"]["id"]
        write(case, "_config.yml", yaml.safe_dump(config))
        write(case, ".gitignore", "/tmp/\n")
        write(case, "assets/img/plain.svg", SVG)
        body = row.get("body", 'Text.\n\n![Alt](assets/img/plain.svg "Caption")\n')
        if row.get("compute"):
            write(case, ".unaltraweb/computations.yml", "version: 1\nsource_roots: [assets/compute]\n")
            write(case, row["compute"], b"OPAQUE SYNTHETIC FINGERPRINT INPUT; NOT A GIS VALIDITY TEST\n")
            front = {"title": "Computed fixture", "lang": "ca", "ref": "computed-fixture", "unaltraweb_compute": {
                "engine": "python", "mode": "figure", "inputs": [row["compute"]], "outputs": ["assets/img/result.svg"]}}
            write(case, "assets/compute/figure.qmd", "---\n" + yaml.safe_dump(front) + "---\nSynthetic source; no computation execution.\n")
            write(case, "assets/img/result.svg", SVG)
            if not row.get("unreferenced"):
                body = '![Computed](assets/compute/figure.qmd "Computed fixture")\n'
        write(case, "_chapters/ca/first.md", "---\ntitle: First\nlang: ca\nref: first\n---\n" + body)
        for name, data in row.pop("extra", {}).items():
            write(case, name, data)
        command(["git", "init", "-b", "fixture"], cwd=case)
        paths = [p.relative_to(case).as_posix() for p in case.rglob("*") if p.is_file() and ".git" not in p.parts]
        command(["git", "add", "--", *paths], cwd=case)
        command(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Synthetic review sources"], cwd=case)
    save(root / "cases.json", rows)


def worker(root):
    """Executed in the exact published image. No exporter function is replaced."""
    from unaltraweb_mcp import __version__
    from unaltraweb_mcp.manual_context import producer_identity
    assert root == Path("/cases") and os.environ.get("UW_REVIEW_WORKER") == "1"
    identity = producer_identity(Path("/opt/unaltraweb"))
    assert __version__ == "0.8.0" and identity["revision"] == PRODUCER
    rows = json.loads((root / "cases.json").read_text())
    results = []
    for row in rows:
        case = root / row["id"]
        native_status = None
        if row.get("compute"):
            spec = importlib.util.spec_from_file_location("review_native_compute", "/opt/unaltraweb/scripts/computations/render.py")
            native = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(native)
            config, config_path = native.load_config(case)
            record, = native.discover_sources(case, config)
            fingerprint, dependencies, image = native.fingerprint(case, config, config_path, record)
            saved = {"fingerprint": fingerprint, "dependencies": dependencies, "image": image,
                     "image_identity": native.inspect_image(image["image"]),
                     "outputs": [{"path": p, **native.file_signature(case / p)} for p in record["output_paths"]]}
            save(case / ".unaltraweb/computations.lock.json", {"version": 1, "records": {record["source_path"]: saved}})
            native_status = native.status(case)
            assert native_status["ok"], native_status
            if row.get("changed_input"):
                with (case / row["compute"]).open("ab") as stream:
                    stream.write(b"CHANGED INPUT\n")
        before = {p.relative_to(case).as_posix(): sha(p.read_bytes()) for p in case.rglob("*")
                  if p.is_file() and ".git" not in p.parts and "tmp" not in p.relative_to(case).parts}
        argv = [sys.executable, "-I", "-B", "-m", "unaltraweb_mcp.cli", "--project", str(case), "mcp",
                "manual-context-export", "--name", "review", "--language", "ca"]
        if row.get("chapter"):
            argv += ["--chapter", row["chapter"]]
        ran = command(argv, expected=None)
        result = json.loads(ran.stdout)
        expected = (ran.returncode == 0 and result.get("ok") is True) if row.get("ok") else (
            ran.returncode == 1 and result.get("ok") is False and row["error"] in result.get("error", ""))
        item = {"id": row["id"], "expected_behavior_observed": expected, "command": argv, "exit_code": ran.returncode,
                "result": result, "stderr": ran.stderr, "source_hashes": before,
                "synthetic_native_status": native_status, "renderer_executed": False}
        archive = case / "tmp/manual-context/review/manual-context.tar.gz"
        item["archive_created"] = archive.exists()
        if result.get("ok"):
            assert archive.is_file() and sha(archive.read_bytes()) == result["sha256"]
            with tarfile.open(archive) as content:
                members = {m.name: content.extractfile(m).read() for m in content.getmembers()}
            manifest = json.loads(members.pop("manual-context.json"))
            assert set(manifest["files"]) == set(members)
            assert all(entry["sha256"] == sha(members[p]) and entry["size_bytes"] == len(members[p]) for p, entry in manifest["files"].items())
            item["manifest"] = manifest
            if row.get("expected_caption"):
                item["expected_caption"] = row["expected_caption"]
                item["caption_preserved"] = manifest["figures"][0]["caption"] == row["expected_caption"]
        else:
            assert not archive.exists(), "A refusal left a transport package"
        assert all(sha((case / p).read_bytes()) == value for p, value in before.items())
        save(root / (row["id"] + ".result.json"), item)
        results.append(item)
    save(root / "producer-review.json", {"ok": all(row["expected_behavior_observed"] for row in results),
        "purpose": "Version-bound baseline review, not acceptance of known defects", "producer": identity,
        "synthetic_only": True, "real_manual_mounted": False, "renderer_executed": False, "cases": results})


RECEIVER = '''import json, sys
from pathlib import Path
import itemarium
from itemarium.app.media import read_image
from itemarium.app.manual_package import check_package
from itemarium.runtime_identity import source_sha256
root = Path(sys.argv[1]); engine = Path(itemarium.__file__).parent
before = source_sha256(engine); results = []
for case in json.loads((root/'cases.json').read_text()):
    result = json.loads((root/(case['id']+'.result.json')).read_text())['result']
    row = {'id':case['id']}
    if result.get('ok'):
        row['package_check'] = check_package(package_path=root/case['id']/result['path'], sha256=result['sha256'])
    if case.get('image'):
        try:
            read_image(root/case['id']/case['image']); row['image_check'] = {'ok':True}
        except ValueError as error:
            row['image_check'] = {'ok':False, 'error':str(error)}
    results.append(row)
assert source_sha256(engine) == before
report = {'engine_version':itemarium.__version__, 'engine_source_sha256':before, 'cases':results,
          'imports_performed':False, 'manufacturer_of_alternate_packages':False,
          'image_checks_are_member_validation_only':True}
with (root/'receiver-review.json').open('x') as output:
    json.dump(report, output, sort_keys=True, indent=2); output.write('\\n')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receiver-python", type=Path)
    parser.add_argument("--receiver-source", type=Path)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    if not args.output or bool(args.receiver_python) != bool(args.receiver_source):
        parser.error("Supply --output; pair --receiver-python with --receiver-source")
    if not (ROOT / "mcp-factory.yml").is_file():
        parser.error("Run this review harness from the unaltraweb source checkout")
    output = args.output.resolve()
    if output != args.output or not output.is_relative_to(ROOT / "tmp") or not output.parent.is_dir():
        parser.error("Use a new absolute output below this checkout's tmp, with an existing parent")
    observed, = json.loads(command(["docker", "image", "inspect", IMAGE]).stdout)
    assert observed["Id"] == IMAGE and observed["Config"]["Labels"]["org.opencontainers.image.revision"] == SOURCE
    output.mkdir(mode=0o700)
    cases(output)
    name = "unaltraweb-review121-" + uuid.uuid4().hex
    argv = ["docker", "run", "--rm", "--pull", "never", "--name", name, "--network", "none", "--read-only",
            "--user", f"{os.getuid()}:{os.getgid()}", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456",
            "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "UW_REVIEW_WORKER=1",
            "--mount", f"type=bind,source={output},target=/cases",
            "--mount", f"type=bind,source={Path(__file__).resolve()},target=/review.py,readonly",
            "--entrypoint", "python3", IMAGE, "-I", "-B", "/review.py", "--worker", "/cases"]
    for path in (output, Path(__file__).resolve()):
        if any(c in str(path) for c in ",\r\n"):
            raise ValueError("Review mount path needs a simple literal spelling")
    ran = command(argv, expected=None)
    save(output / "execution.json", {"command": argv, "exit_code": ran.returncode, "stdout": ran.stdout, "stderr": ran.stderr})
    command(["docker", "info", "--format", "{{.ID}}"])
    absent = command(["docker", "container", "inspect", name], expected=None)
    assert absent.returncode == 1 and "No such" in absent.stderr, "Exact review container absence not established"
    if ran.returncode:
        raise RuntimeError(ran.stderr[-6000:])
    report = json.loads((output / "producer-review.json").read_text())
    assert report["ok"], "A scenario differed from the recorded 0.8.0 behavior; inspect retained results"
    old, = json.loads(command(["docker", "image", "inspect", OLD_IMAGE]).stdout)
    assert old["Id"] == OLD_IMAGE
    old_result = command(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only",
                          "--entrypoint", "unaltraweb-mcp", OLD_IMAGE, "mcp", "manual-context-export", "--name", "probe"], expected=None)
    assert old_result.returncode == 2 and "invalid choice" in old_result.stderr
    save(output / "old-runtime.json", {"image_id": OLD_IMAGE, "exit_code": old_result.returncode, "stderr": old_result.stderr})
    if args.receiver_python:
        environment = {**os.environ, "PYTHONPATH": str(args.receiver_source.resolve()), "PYTHONDONTWRITEBYTECODE": "1"}
        # Keep a venv interpreter's spelling: resolving its python symlink would
        # silently select the system interpreter and lose the prepared dependencies.
        command([str(args.receiver_python.absolute()), "-B", "-c", RECEIVER, str(output)], env=environment)
    print(json.dumps({"ok": True, "output": str(output), "cases": len(report["cases"]),
                      "receipt_sha256": sha((output / "producer-review.json").read_bytes()), "exact_container_absent": True}, indent=2))


if __name__ == "__main__":
    main()
