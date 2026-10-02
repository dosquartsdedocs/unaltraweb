"""Native, create-only retained-letter integration and read-only verification."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

from . import artifact_handoff_v1 as wire
from . import letter_bundle
from .processes import run_process

ROOT = ".unaltraweb/artifacts"
WORK = "tmp/unaltraweb-artifact-imports"
ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
TAG = re.compile(r"{%\s*retained_document\s+([a-z][a-z0-9-]{0,63})\s*%}")
CONTENT_ROOTS = {"_chapters", "_pages", "_documentation"}
# The BOM is validated at package import, but its worker/self pins cannot enter
# PDF freshness: selecting a published worker must not require it to contain its
# own future digest. Actor provenance below still binds that metadata exactly.
CHECKER_FILES = ("__init__.py", "distribution.py", "component-contract.schema.json",
                 "artifact_imports.py", "artifact_handoff_v1.py", "artifact-handoff-v1.schema.json", "letter_bundle.py", "pdf_probe.py", "processes.py")


def require(condition, message, code="import"):
    wire.require(condition, code, message)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def locations(import_id):
    require(isinstance(import_id, str) and ID.fullmatch(import_id), "Invalid import ID")
    prefix = f"{ROOT}/{import_id}"
    return {"prefix": prefix, "bundle": f"{prefix}/bundle/bundle.json", "record": f"{prefix}/integration.json",
            "binding": f"{prefix}/binding.json", "pdf": f"assets/documents/{import_id}.pdf"}


def content_path(path):
    wire.safe_path(path)
    require(path.split("/")[0] in CONTENT_ROOTS and path.endswith(".md"), "Content must be Markdown in _pages, _chapters or _documentation")
    return path


def visible_tags(raw):
    text = raw.decode("utf-8")
    front = letter_bundle.FRONT_MATTER.match(text)
    if front:
        text = text[front.end():]
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", text)
    text = re.sub(r"(?s)<!--.*?-->|{%\s*(comment|raw)\s*%}.*?{%\s*end\1\s*%}", "", text)
    return {m.group(1) for m in TAG.finditer(text)}


@contextmanager
def locked(project, *, write=False):
    workspace = wire.Workspace(str(Path(project).absolute()))
    workspace.import_lock_fd = None
    try:
        if write:
            fcntl.flock(workspace.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Readers coordinate on the retained-import directory. PDF preparation
        # can already hold the broader project lock in its parent controller.
        # A directory lock survives Git cloning/relocation without a lock file.
        try:
            fd, _ = _parent(workspace, f"{ROOT}/sentinel")
        except FileNotFoundError:
            pass
        else:
            workspace.import_lock_fd = fd
            fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        yield workspace
    finally:
        if workspace.import_lock_fd is not None:
            os.close(workspace.import_lock_fd)
        workspace.close()


def read(workspace, path, limit=wire.MAX_MANIFEST_BYTES):
    return workspace.read(path, limit, collect=True)[2]


def exists(workspace, path):
    parent, _, name = path.rpartition("/")
    try:
        with workspace.directory(parent) as fd:
            os.stat(name, dir_fd=fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def binding_info(workspace, import_id):
    paths = locations(import_id)
    binding = wire.parse_json(read(workspace, paths["binding"]))
    require(set(binding) == {"schema_version", "profile", "integration", "content"} and type(binding["schema_version"]) is int and binding["schema_version"] == 1,
            "Invalid native binding record")
    require(binding["profile"] == letter_bundle.PROFILE, "Unsupported native import profile")
    require(set(binding["integration"]) == {"path", "sha256"} and binding["integration"]["path"] == paths["record"], "Invalid integration binding")
    expected = binding["integration"]["sha256"]
    require(isinstance(expected, str) and wire.HASH_RE.fullmatch(expected), "Invalid integration digest")
    verifier = wire.Verifier(workspace)
    record, _ = verifier.document(paths["record"], "integration", expected)
    require(record["integrator"]["name"] == "unaltraweb", "Unexpected integrator")
    require(record["bundle"]["path"] == paths["bundle"] and record["mappings"] == [{"source": letter_bundle.PDF_PATH, "destination": paths["pdf"]}], "Unexpected native destination mapping")
    verifier.integration(paths["record"], expected)
    domain = letter_bundle.verify(workspace, paths["bundle"], record["bundle"]["sha256"])
    require(set(binding["content"]) == {"path"}, "Invalid native content binding")
    source = content_path(binding["content"]["path"])
    source_bytes = read(workspace, source)
    require(import_id in visible_tags(source_bytes), "Native retained_document reference is missing or hidden", "reference")
    front = letter_bundle.FRONT_MATTER.match(source_bytes.decode("utf-8"))
    require(front is not None, "Native reference needs front matter", "reference")
    permalink = letter_bundle.mapping(front.group(1).encode()).get("permalink")
    require(isinstance(permalink, str) and permalink.startswith("/") and (permalink.endswith("/") or permalink.endswith(".html")),
            "Native reference needs a literal local directory or .html permalink", "reference")
    web_page = wire.safe_path(permalink[1:] + ("index.html" if permalink.endswith("/") else ""))
    inputs = [paths["binding"], paths["record"], paths["pdf"], source,
              *(wire.join(paths["bundle"].rpartition("/")[0], name) for name in domain["inventory"])]
    return {"id": import_id, "profile": letter_bundle.PROFILE, "pdf": paths["pdf"], "pages": domain["pages"],
            "content": source, "web_page": web_page, "integration": paths["record"], "integration_sha256": expected,
            "bundle": record["bundle"], "inputs": inputs}


def _check(workspace, import_id=""):
    if import_id:
        ids = [import_id]
    elif not exists(workspace, ROOT):
        ids = []
    else:
        with workspace.directory(ROOT) as fd:
            ids = sorted(os.listdir(fd))
        require(len(ids) <= 128, "Import inventory exceeds the 128-document owner bound")
    results = [binding_info(workspace, item) for item in ids]
    workspace.recheck()
    return {"ok": True, "configured": bool(ids), "imports": results}


def failure(exc, **extra):
    return {"ok": False, "error": {"code": getattr(exc, "code", "inspection"), "message": str(exc)}, **extra}


def check_imports(project, import_id="", output_folder=""):
    try:
        with locked(project) as workspace:
            result = _check(workspace, import_id)
            if output_folder and result["configured"]:
                wire.safe_path(output_folder)
                require(not exists(workspace, f"{output_folder}/{ROOT}"), "Private retained archive was exposed in the site", "reference")
                found = set()
                config = letter_bundle.mapping(read(workspace, "_config.yml"))
                baseurl = config.get("baseurl") or ""
                require(isinstance(baseurl, str) and (not baseurl or baseurl.startswith("/")), "Invalid local baseurl", "reference")
                baseurl = baseurl.removesuffix("/")
                if baseurl:
                    wire.safe_path(baseurl[1:])
                expected = {item["id"]: baseurl + "/" + item["pdf"] for item in result["imports"]}

                class References(HTMLParser):
                    def handle_starttag(self, tag, attrs):
                        attrs = dict(attrs)
                        value = attrs.get("data-retained-document")
                        if tag == "object" and value in expected and attrs.get("data") == expected[value]:
                            found.add(value)
                            self.ids.add(value)

                for item in result["imports"]:
                    # Inspect the bound native page, not unrelated large vendor
                    # demos shipped elsewhere in the site's assets directory.
                    parser = References()
                    parser.ids = set()
                    parser.feed(read(workspace, f"{output_folder}/{item['web_page']}", 16 * 1024 * 1024).decode("utf-8"))
                    require(item["id"] in parser.ids, "The bound page does not render its retained document", "reference")
                require(found == set(expected), "Rendered native PDF reference is missing", "reference")
                for item in result["imports"]:
                    original = workspace.read(item["pdf"], letter_bundle.MAX_PAYLOAD)[:2]
                    rendered = workspace.read(f"{output_folder}/{item['pdf']}", letter_bundle.MAX_PAYLOAD)[:2]
                    require(original == rendered, "Rendered PDF differs from its retained mapping", "hash")
                workspace.recheck()
            return result
    except (OSError, ValueError, RuntimeError, wire.HandoffError, KeyError, TypeError, RecursionError) as exc:
        return failure(exc)


def _parent(workspace, path, *, create=False):
    wire.safe_path(path)
    fd = os.dup(workspace.fd)
    try:
        for part in path.split("/")[:-1]:
            names = os.listdir(fd)
            require(len(names) <= wire.MAX_ENTRIES, "Destination directory exceeds bounds")
            require(not any(name.casefold() == part.casefold() and name != part for name in names), "Case-aliased destination", "conflict")
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, workspace.dir_flags, dir_fd=fd)
            os.close(fd)
            fd = child
        leaf = path.rsplit("/", 1)[-1]
        require(not any(name.casefold() == leaf.casefold() and name != leaf for name in os.listdir(fd)), "Case-aliased destination", "conflict")
        return fd, leaf
    except Exception:
        os.close(fd)
        raise


def _preflight(workspace, outputs):
    wire.unique_paths(list(outputs))
    existing = {}
    for path, data in outputs.items():
        try:
            fd, leaf = _parent(workspace, path)
        except FileNotFoundError:
            continue
        try:
            try:
                os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            actual, size, _ = workspace.read(path, max(len(data), 1))
            require((actual, size) == (digest(data), len(data)), f"Preserving differing destination: {path}", "conflict")
            existing[path] = workspace.snapshots[path]
        finally:
            os.close(fd)
    return existing


def _create(workspace, path, data):
    parent, name = _parent(workspace, path, create=True)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)


def _git_policy(project, outputs):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    def git(*args):
        return run_process(["git", "-C", str(project), *args], env=env, timeout_seconds=20)
    root = git("rev-parse", "--show-toplevel")
    require(root.returncode == 0 and Path(root.stdout.strip()).resolve() == Path(project).resolve(), "Import requires the consumer Git root")
    probe = f"{WORK}/probe/journal.json"
    require(git("check-ignore", "--quiet", "--no-index", "--", probe).returncode == 0, "The import recovery area must be ignored; review tmp/ ignore coverage")
    indexed = git("ls-files", "--", WORK)
    require(indexed.returncode == 0 and not indexed.stdout.strip(), "Import recovery area must be untracked")
    for path in outputs:
        ignored = git("check-ignore", "--quiet", "--no-index", "--", path)
        require(ignored.returncode == 1, f"Durable import destination must not be ignored: {path}")


def actor():
    root = Path(__file__).parent
    inventory = {name: digest((root / name).read_bytes()) for name in (*CHECKER_FILES, "component-contract.json")}
    version = json.loads((root / "component-contract.json").read_text())["release"]["version"]
    return {"name": "unaltraweb", "version": version, "revision": "sha256:" + digest(json_bytes(inventory)), "runtimes": []}


def import_bundle(project, path, sha256, import_id, content, title="Retained letter", *, dry_run=True, confirm_import=False):
    recovery = ""
    try:
        project = Path(project).absolute()
        paths = locations(import_id)
        content_path(content)
        require(isinstance(title, str) and 0 < len(title) <= 200 and not any(c in title for c in "\r\n{}<>`"), "Invalid plain-text title")
        with locked(project, write=True) as workspace:
            config = letter_bundle.mapping(read(workspace, "_config.yml"))
            require(config.get("unaltraweb", {}).get("site_profile") in {"unaltreselfie", "unaltreprojecte", "unaltremanual", "unaltredocs"}, "Not an initialized unaltraweb consumer")
            profile = config["unaltraweb"]["site_profile"]
            require(not content.startswith("_chapters/") or profile == "unaltremanual", "Chapters require the manual profile")
            require(not content.startswith("_documentation/") or profile == "unaltredocs", "Documentation content requires the docs profile")
            for suffix in (".qmd", ".Rmd", ".R", ".r", ".py", ".ipynb"):
                require(not exists(workspace, str(Path(content).with_suffix(suffix))), "Content path belongs to an executable source; choose a new document", "conflict")
            domain = letter_bundle.verify(workspace, path, sha256)
            if exists(workspace, paths["binding"]):
                current = binding_info(workspace, import_id)
                require(current["bundle"]["sha256"] == sha256 and current["content"] == content, "Import ID already binds different content or bundle", "conflict")
                workspace.recheck()
                return {"ok": True, "dry_run": dry_run, "reused": True, **current}
            base = path.rpartition("/")[0]
            bundle_base = paths["bundle"].rpartition("/")[0]
            outputs = {wire.join(bundle_base, name): read(workspace, wire.join(base, name), letter_bundle.MAX_PAYLOAD) for name in domain["inventory"]}
            outputs[paths["pdf"]] = read(workspace, wire.join(base, domain["pdf"]), letter_bundle.MAX_PAYLOAD)
            lang = str(config.get("default_lang") or config.get("lang") or "en")
            require(re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,30}", lang), "Invalid consumer language")
            layout = "manual-chapter" if content.startswith("_chapters/") else "page"
            front = {"layout": layout, "title": title, "lang": lang, "ref": f"retained-{import_id}", "permalink": f"/{lang}/retained/{import_id}/", "content_status": "draft"}
            # JSON scalar quoting is valid YAML; upstream prose is never evaluated.
            source = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items()) + f"\n---\n\n{{% retained_document {import_id} %}}\n"
            outputs[content] = source.encode()
            record = {"schema_version": 1, "kind": "mcp-artifact-integration", "integrator": actor(),
                      "bundle": {"path": paths["bundle"], "sha256": sha256},
                      "mappings": [{"source": domain["pdf"], "destination": paths["pdf"]}]}
            outputs[paths["record"]] = json_bytes(record)
            binding = {"schema_version": 1, "profile": letter_bundle.PROFILE,
                       "integration": {"path": paths["record"], "sha256": digest(outputs[paths["record"]])}, "content": {"path": content}}
            outputs[paths["binding"]] = json_bytes(binding)
            # Reject overlaps with the incoming seal, including source ancestors.
            require(not any(dest == base or dest.startswith(base + "/") or base.startswith(dest + "/") for dest in outputs), "Import destinations overlap the incoming bundle")
            existing = _preflight(workspace, outputs)
            _git_policy(project, outputs)
            workspace.recheck()
            plan = {"ok": True, "dry_run": dry_run, "profile": letter_bundle.PROFILE, "bundle": record["bundle"],
                    "integration": paths["record"], "integration_sha256": binding["integration"]["sha256"], "content": content,
                    "mappings": record["mappings"], "create": [p for p in outputs if p not in existing], "reuse": list(existing)}
            if dry_run:
                return plan
            require(confirm_import is True, "Real import requires confirm_import=true")
            if workspace.import_lock_fd is None:
                fd, _ = _parent(workspace, f"{ROOT}/sentinel", create=True)
                workspace.import_lock_fd = fd
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stage = f"{WORK}/{uuid.uuid4().hex}"
            recovery = f"{stage}/prepared.json"
            journal = {"profile": letter_bundle.PROFILE, "bundle_sha256": sha256,
                       "outputs": {name: {"sha256": digest(data), "bytes": len(data)} for name, data in outputs.items()}}
            _create(workspace, recovery, json_bytes(journal))
            for destination, data in outputs.items():
                _create(workspace, f"{stage}/files/{destination}", data)
            workspace.recheck()
            # Recheck every adopted/missing destination immediately before writes.
            require(_preflight(workspace, outputs) == existing, "Destinations changed after import preflight", "changed")
            for destination, data in outputs.items():
                if destination not in existing:
                    _create(workspace, destination, data)
            verified = binding_info(workspace, import_id)
            workspace.recheck()
            _create(workspace, f"{stage}/completed.json", json_bytes({"integration": paths["record"], "sha256": verified["integration_sha256"]}))
            return {**plan, "dry_run": False, "recovery": recovery, "verified": verified}
    except (OSError, ValueError, RuntimeError, wire.HandoffError, KeyError, TypeError, RecursionError) as exc:
        # Partial files and the prepared tree are retained for explicit recovery;
        # there is no destructive rollback or overwrite of later author edits.
        return failure(exc, recovery=recovery, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--import-id", default="")
    parser.add_argument("--output-folder", default="")
    args = parser.parse_args()
    result = check_imports(args.project, args.import_id, args.output_folder)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
