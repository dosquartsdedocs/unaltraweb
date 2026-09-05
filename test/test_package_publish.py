from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_package_publish import (
    authorize_run,
    release_packages,
    stage_candidates,
    validate_release_checkout,
)


class PackagePublishTests(unittest.TestCase):
    release_tag = "v0.3.0"
    source_commit = "a" * 40
    run_id = 123456
    repository = "dosquartsdedocs/unaltraweb"

    def write_json(self, root: Path, name: str, value: object) -> Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def fixture(self, root: Path) -> dict[str, object]:
        candidate_dir = root / "candidate"
        candidate_dir.mkdir()
        gem_name = "unaltraweb-0.3.0.gem"
        wheel_name = "unaltraweb_mcp-0.3.0-py3-none-any.whl"
        gem_bytes = b"exact gem candidate\n"
        wheel_bytes = b"exact wheel candidate\n"
        gem_sha = hashlib.sha256(gem_bytes).hexdigest()
        wheel_sha = hashlib.sha256(wheel_bytes).hexdigest()
        (candidate_dir / gem_name).write_bytes(gem_bytes)
        (candidate_dir / wheel_name).write_bytes(wheel_bytes)
        (candidate_dir / "SHA256SUMS").write_text(
            f"{gem_sha}  ./{gem_name}\n{wheel_sha}  ./{wheel_name}\n",
            encoding="utf-8",
        )
        receipt = {
            "schema_version": 1,
            "release": self.release_tag,
            "source_commit": self.source_commit,
            "components": {
                "gem": {"artifact": gem_name, "sha256": gem_sha},
                "wheel": {"artifact": wheel_name, "sha256": wheel_sha},
            },
        }
        run = {
            "id": self.run_id,
            "path": ".github/workflows/package-prepare.yml",
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": "success",
            "head_sha": self.source_commit,
            "head_branch": "main",
            "repository": {"full_name": self.repository},
            "head_repository": {"full_name": self.repository},
        }
        artifact_name = f"unaltraweb-0.3.0-{self.source_commit}"
        artifacts = {
            "total_count": 1,
            "artifacts": [{
                "id": 789,
                "name": artifact_name,
                "expired": False,
                "digest": f"sha256:{'b' * 64}",
                "workflow_run": {
                    "id": self.run_id,
                    "head_sha": self.source_commit,
                    "head_branch": "main",
                },
            }],
        }
        return {
            "candidate_dir": candidate_dir,
            "receipt": receipt,
            "run": run,
            "artifacts": artifacts,
            "gem_name": gem_name,
            "wheel_name": wheel_name,
        }

    def authorize(self, root: Path, fixture: dict[str, object]) -> dict[str, str]:
        receipt = self.write_json(root, "receipt.json", fixture["receipt"])
        return authorize_run(
            receipt,
            self.release_tag,
            hashlib.sha256(receipt.read_bytes()).hexdigest(),
            self.run_id,
            self.write_json(root, "run.json", fixture["run"]),
            self.write_json(root, "artifacts.json", fixture["artifacts"]),
            self.repository,
            "main",
        )

    def test_authorizes_only_the_exact_successful_candidate_run_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixture = self.fixture(root)
            result = self.authorize(root, fixture)

        self.assertEqual(result["artifact-id"], "789")
        self.assertEqual(result["artifact-name"], f"unaltraweb-0.3.0-{self.source_commit}")
        self.assertEqual(result["gem-artifact"], fixture["gem_name"])
        self.assertEqual(result["wheel-artifact"], fixture["wheel_name"])

    def test_rejects_candidate_run_identity_or_artifact_drift(self) -> None:
        mutations = [
            ("run", "path", ".github/workflows/other.yml"),
            ("run", "event", "push"),
            ("run", "conclusion", "failure"),
            ("run", "head_sha", "c" * 40),
            ("run", "head_branch", "feature"),
            ("artifacts", "total_count", 2),
        ]
        for target, key, value in mutations:
            with self.subTest(target=target, key=key):
                with tempfile.TemporaryDirectory() as raw:
                    root = Path(raw)
                    fixture = self.fixture(root)
                    fixture[target][key] = value  # type: ignore[index]
                    with self.assertRaises(ValueError):
                        self.authorize(root, fixture)

        artifact_mutations = {
            "name": "unrelated",
            "expired": True,
            "digest": "missing",
        }
        for key, value in artifact_mutations.items():
            with self.subTest(artifact=key):
                with tempfile.TemporaryDirectory() as raw:
                    root = Path(raw)
                    fixture = self.fixture(root)
                    fixture["artifacts"]["artifacts"][0][key] = value  # type: ignore[index]
                    with self.assertRaises(ValueError):
                        self.authorize(root, fixture)

    def test_stages_only_receipt_bound_package_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixture = self.fixture(root)
            receipt = self.write_json(root, "receipt.json", fixture["receipt"])
            output = root / "verified"
            receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
            result = stage_candidates(
                receipt,
                self.release_tag,
                receipt_sha,
                fixture["candidate_dir"],  # type: ignore[arg-type]
                output,
            )

            self.assertEqual(Path(result["gem"]).read_bytes(), b"exact gem candidate\n")
            self.assertEqual(Path(result["wheel"]).read_bytes(), b"exact wheel candidate\n")
            self.assertEqual({path.name for path in (output / "pypi").iterdir()}, {fixture["wheel_name"]})
            self.assertEqual({path.name for path in (output / "rubygems").iterdir()}, {fixture["gem_name"]})

    def test_rejects_extra_modified_or_relabelled_candidates(self) -> None:
        scenarios = ["extra", "modified", "checksums"]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                with tempfile.TemporaryDirectory() as raw:
                    root = Path(raw)
                    fixture = self.fixture(root)
                    candidate_dir = fixture["candidate_dir"]
                    if scenario == "extra":
                        (candidate_dir / "extra.txt").write_text("unexpected", encoding="utf-8")  # type: ignore[operator]
                    elif scenario == "modified":
                        (candidate_dir / fixture["wheel_name"]).write_bytes(b"modified")  # type: ignore[operator]
                    else:
                        (candidate_dir / "SHA256SUMS").write_text("wrong\n", encoding="utf-8")  # type: ignore[operator]
                    receipt = self.write_json(root, "receipt.json", fixture["receipt"])
                    receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
                    with self.assertRaises(ValueError):
                        stage_candidates(
                            receipt,
                            self.release_tag,
                            receipt_sha,
                            candidate_dir,  # type: ignore[arg-type]
                            root / "verified",
                        )

    def test_rejects_duplicate_receipt_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            receipt = Path(raw) / "receipt.json"
            receipt.write_text(
                '{"schema_version":1,"release":"v0.3.0","release":"v0.3.1"}',
                encoding="utf-8",
            )
            digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "duplicate JSON key release"):
                release_packages(receipt, self.release_tag, digest)

    def test_validates_annotated_tag_receipt_commit_without_executing_release_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repository = root / "repository"
            repository.mkdir()

            def git(*arguments: str) -> str:
                completed = subprocess.run(
                    ["git", *arguments],
                    cwd=repository,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                return completed.stdout.strip()

            git("init", "--initial-branch=main")
            git("config", "user.name", "Release Test")
            git("config", "user.email", "release@example.invalid")
            fixture = self.fixture(root)
            contract_path = repository / "src/unaltraweb_mcp/component-contract.json"
            contract_path.parent.mkdir(parents=True)
            contract_path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "release": {"version": "0.3.0", "tag": self.release_tag},
                    "components": {
                        "gem": {
                            "kind": "gem",
                            "name": "unaltraweb",
                            "version": "0.3.0",
                            "release": self.release_tag,
                            "release_status": "ready",
                        },
                        "wheel": {
                            "kind": "python-wheel",
                            "name": "unaltraweb-mcp",
                            "version": "0.3.0",
                            "release": self.release_tag,
                            "release_status": "ready",
                        },
                    },
                }),
                encoding="utf-8",
            )
            git("add", "src/unaltraweb_mcp/component-contract.json")
            git("commit", "-m", "Prepare release source")
            source_commit = git("rev-parse", "HEAD")
            fixture["receipt"]["source_commit"] = source_commit  # type: ignore[index]
            receipt = self.write_json(repository, "release-candidates.json", fixture["receipt"])
            git("add", "release-candidates.json")
            git("commit", "-m", "Record release candidates")
            git("tag", "-a", self.release_tag, "-m", self.release_tag)
            git("update-ref", "refs/remotes/origin/main", "HEAD")
            tag_object = git("rev-parse", f"refs/tags/{self.release_tag}")
            receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()

            result = validate_release_checkout(
                repository,
                receipt,
                self.release_tag,
                tag_object,
                receipt_sha,
                "main",
            )
            self.assertEqual(result["tag-object"], tag_object)
            self.assertEqual(result["source-commit"], source_commit)
            with self.assertRaisesRegex(ValueError, "tag object does not match"):
                validate_release_checkout(
                    repository,
                    receipt,
                    self.release_tag,
                    "f" * 40,
                    receipt_sha,
                    "main",
                )


if __name__ == "__main__":
    unittest.main()
