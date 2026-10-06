"""Execute the actual reusable-workflow gates, including published older workers."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.validate_workflows import load_workflow, load_workflow_text


PUBLISHED_WORKERS = (
    ("0.5.0", "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:9e0b3a45753c170b795e9a9d6df61580085c113436beac5bf6c8de69b6562097",
     "d857f8c9f5fea90cf450c0b30b4e77a37b541275"),
    ("0.6.0", "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed",
     "5cf9817489c8dc47cee726bfe42fe3071cd32b85"),
)


def gate(name: str, workflow=None) -> str:
    steps = (workflow or load_workflow(ROOT / ".github/workflows/site-deploy.yml"))["jobs"]["build"]["steps"]
    return next(step["run"] for step in steps if step.get("name") == name)


def environment() -> dict[str, str]:
    result = {key: value for key, value in os.environ.items() if key not in {"BASH_ENV", "ENV"}}
    result.update({
        "CURRENT_REF": "refs/heads/main", "CURRENT_SHA": "a" * 40, "REVIEWED_SHA": "a" * 40,
        "WORKFLOW_REPOSITORY": "dosquartsdedocs/unaltraweb", "WORKFLOW_SHA": "b" * 40,
        "MANUAL_PDF_IMAGE": PUBLISHED_WORKERS[0][1],
        "RUNNER_TEMP": tempfile.gettempdir(),
    })
    return result


def run_gate(name: str, env: dict[str, str], cwd: Path, timeout: int = 10, workflow=None):
    return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", gate(name, workflow)],
                          env=env, cwd=cwd, capture_output=True, text=True, timeout=timeout)


class DeployProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="web-deploy-gate-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        binary = self.root / "bin"
        binary.mkdir()
        self.calls = self.root / "docker.jsonl"
        docker = binary / "docker"
        docker.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["DOCKER_CALLS"], "a") as stream:
    stream.write(json.dumps(args) + "\\n")
if args[0] == "pull":
    sys.exit(int(os.environ.get("PULL_STATUS", "0")))
if args[:2] == ["image", "inspect"]:
    if os.environ.get("INSPECT_STATUS"):
        sys.exit(int(os.environ["INSPECT_STATUS"]))
    print(os.environ.get("OBSERVED_PDF_REVISION", ""))
    sys.exit(0)
sys.exit(90)
''')
        docker.chmod(0o755)
        self.contract = self.root / "provider.json"
        self.contract.write_bytes((ROOT / "src/unaltraweb_mcp/component-contract.json").read_bytes())
        curl = binary / "curl"
        curl.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
expected = "https://raw.githubusercontent.com/dosquartsdedocs/unaltraweb/" + os.environ["WORKFLOW_SHA"] + "/src/unaltraweb_mcp/component-contract.json"
assert sys.argv[-1] == expected
if os.environ.get("FETCH_STATUS"):
    sys.exit(int(os.environ["FETCH_STATUS"]))
sys.stdout.buffer.write(Path(os.environ["TEST_PROVIDER_JSON"]).read_bytes())
''')
        curl.chmod(0o755)
        self.env = {**environment(), "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                    "DOCKER_CALLS": str(self.calls), "OBSERVED_PDF_REVISION": PUBLISHED_WORKERS[0][2],
                    "TEST_PROVIDER_JSON": str(self.contract), "RUNNER_TEMP": str(self.root)}

    def invoke(self, name="Verify manual PDF image provenance", **changes):
        self.calls.unlink(missing_ok=True)
        result = run_gate(name, {**self.env, **changes}, self.root)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        return result, calls

    def test_published_worker_can_predate_the_defining_workflow(self):
        for version, reference, producer in PUBLISHED_WORKERS:
            with self.subTest(version=version):
                self.assertNotEqual(producer, self.env["WORKFLOW_SHA"])
                result, calls = self.invoke(MANUAL_PDF_IMAGE=reference, OBSERVED_PDF_REVISION=producer)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([call[:1] for call in calls], [["pull"], ["image"]])
                self.assertTrue(all(call[-1] == reference for call in calls))

    def test_unknown_digest_is_rejected_before_docker_even_with_a_known_label(self):
        for reference in (
            "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:" + "1" * 64,
            "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf:0.5.0",
            PUBLISHED_WORKERS[0][1].replace("dosquartsdedocs", "unrelated"),
        ):
            with self.subTest(reference=reference):
                result, calls = self.invoke(MANUAL_PDF_IMAGE=reference)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("no reviewed producer record", result.stderr)
                self.assertEqual(calls, [])

    def test_wrong_missing_or_workflow_matched_labels_are_rejected(self):
        for revision in ("", "0" * 40, self.env["WORKFLOW_SHA"], PUBLISHED_WORKERS[1][2]):
            with self.subTest(revision=revision):
                result, calls = self.invoke(OBSERVED_PDF_REVISION=revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("recorded producer SHA", result.stderr)
                self.assertEqual(len(calls), 2)

    def test_caller_cannot_override_the_expected_producer(self):
        result, _ = self.invoke(expected_pdf_revision="0" * 40)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, _ = self.invoke(expected_pdf_revision="0" * 40, OBSERVED_PDF_REVISION="0" * 40)
        self.assertNotEqual(result.returncode, 0)

    def test_foreign_or_unbound_workflow_is_rejected_before_docker(self):
        for changes in ({"WORKFLOW_REPOSITORY": "unrelated/provider"}, {"WORKFLOW_SHA": "main"},
                        {"WORKFLOW_SHA": ""}):
            with self.subTest(changes=changes):
                result, calls = self.invoke(**changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])

    def test_pull_or_inspection_failure_is_not_masked(self):
        result, calls = self.invoke(FETCH_STATUS="22")
        self.assertEqual(result.returncode, 22)
        self.assertEqual(calls, [])
        result, calls = self.invoke(PULL_STATUS="23")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(len(calls), 1)
        result, calls = self.invoke(INSPECT_STATUS="24", image_revision=PUBLISHED_WORKERS[0][2])
        self.assertEqual(result.returncode, 24)
        self.assertEqual(len(calls), 2)

    def test_invalid_provider_records_fail_before_docker(self):
        original = self.contract.read_bytes()
        for content in (b'{}', b'{"deployment_contract":{},"deployment_contract":{}}', b'{"x":NaN}', b' ' * 262145):
            with self.subTest(content=content[:80]):
                self.contract.write_bytes(content)
                result, calls = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
        value = json.loads(original)
        value["deployment_contract"]["manual_pdf_workers"].append(value["deployment_contract"]["manual_pdf_workers"][0])
        self.contract.write_text(json.dumps(value))
        result, calls = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_consumer_contract_cannot_supply_worker_authority(self):
        (self.root / "src/unaltraweb_mcp").mkdir(parents=True)
        (self.root / "src/unaltraweb_mcp/component-contract.json").write_text('{"deployment_contract":{}}')
        result, _ = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reviewed_main_source_guard_is_preserved(self):
        result, calls = self.invoke("Validate latest publication source")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])
        for changes in ({"CURRENT_REF": "refs/heads/unreviewed"}, {"REVIEWED_SHA": "0" * 40},
                        {"REVIEWED_SHA": "main"}, {"MANUAL_PDF_IMAGE": "worker:latest"}):
            with self.subTest(changes=changes):
                result, calls = self.invoke("Validate latest publication source", **changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])


@unittest.skipUnless(os.environ.get("UNALTRAWEB_DEPLOY_PROVENANCE_DOCKER") == "1", "explicit real-Docker gate")
class PublishedDeployProvenanceTests(unittest.TestCase):
    def test_actual_published_workers_pass_a_later_reusable_workflow(self):
        """Run the original provider shell, real pulls and label checks; never deploy."""
        env = environment()
        env["WORKFLOW_SHA"] = os.environ.get("UNALTRAWEB_DEPLOY_PROVENANCE_SOURCE_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        results = []
        for version, reference, producer in PUBLISHED_WORKERS:
            with self.subTest(version=version):
                self.assertNotEqual(env["WORKFLOW_SHA"], producer)
                selected = {**env, "MANUAL_PDF_IMAGE": reference}
                for name in ("Validate latest publication source", "Verify manual PDF image provenance"):
                    checked = run_gate(name, selected, ROOT, timeout=300)
                    self.assertEqual(checked.returncode, 0, checked.stderr)
                info = json.loads(subprocess.check_output(["docker", "image", "inspect", reference], text=True))[0]
                self.assertEqual(info["Config"]["Labels"]["org.opencontainers.image.revision"], producer)
                results.append({"version": version, "reference": reference, "producer_revision": producer,
                                "image_id": info["Id"], "workflow_sha": env["WORKFLOW_SHA"], "ok": True})
        # Resolve and execute the workflow actually pinned by a generated caller.
        # Testing only the current checkout missed the historical #86 regression.
        from unaltraweb_mcp import site_tools
        with tempfile.TemporaryDirectory(prefix="web-generated-caller-") as raw:
            project = Path(raw) / "manual"
            site_tools.new_web(project, site_profile_value="unaltremanual")
            caller = load_workflow(project / ".github/workflows/deploy.yml")["jobs"]["deploy"]
            repository, workflow_sha = caller["uses"].rsplit("@", 1)
            self.assertEqual(repository, "dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml")
            pinned_bytes = subprocess.check_output(["git", "show", f"{workflow_sha}:.github/workflows/site-deploy.yml"], cwd=ROOT)
            pinned = load_workflow_text(pinned_bytes.decode())
            selected = {**env, "WORKFLOW_SHA": workflow_sha, "MANUAL_PDF_IMAGE": caller["with"]["manual-pdf-image"]}
            for name in ("Validate latest publication source", "Verify manual PDF image provenance"):
                checked = run_gate(name, selected, project, timeout=300, workflow=pinned)
                self.assertEqual(checked.returncode, 0, checked.stderr)
            generated = {"workflow_sha": workflow_sha, "workflow_file_sha256": hashlib.sha256(pinned_bytes).hexdigest(),
                         "manual_pdf_image": selected["MANUAL_PDF_IMAGE"], "ok": True}
        evidence = {"ok": True, "scope": "real published worker and actual generated-caller gates, no consumer deployment", "workers": results,
                    "generated_caller": generated}
        output = os.environ.get("UNALTRAWEB_DEPLOY_PROVENANCE_EVIDENCE")
        if output:
            with Path(output).open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, sort_keys=True), flush=True)
