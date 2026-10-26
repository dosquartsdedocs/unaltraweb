from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from unaltraweb_mcp import artifact_handoff_v1 as h, practice_editions, practice_pdf, shared_editions as editions, shared_practices
from unaltraweb_mcp.editorial_sources import canonical, digest
from unaltraweb_mcp.shared_jobs import SharedError
from test_practice_pdf import PracticePdfFixture, ROOT


class SharedEditionTests(PracticePdfFixture):
    def setUp(self):
        super().setUp()
        (self.project / ".gitignore").write_text("sandbox/\ndist/\nincoming/\n")
        contract = editions.verifier_contract()
        self.manifest = {"kind": "mcp-artifact-bundle", "schema_version": 1, "request": "request", "dependencies": [],
            "producer": {"name": contract["provider"]["name"], "version": contract["provider"]["version"],
                         "revision": contract["provider"]["installed_revision"], "runtimes": []}, "files": []}
        self.base = self.project / "incoming/gis"
        for identifier, name, kind, role in (("request", "payload/request.json", "input", "request"),
                ("initial", "payload/projects/start.qgz", "output", "initial-project"),
                ("resolved", "payload/projects/resolved.qgz", "output", "resolved-project"),
                ("data", "payload/data/shared.gpkg", "output", "initial-data")):
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ("opaque unit fixture " + identifier).encode()
            path.write_bytes(raw)
            self.manifest["files"].append({"id": identifier, "path": name, "kind": kind, "role": role,
                "ownership": "producer", "sha256": digest(raw), "bytes": len(raw)})
        self.bundle_raw = canonical(self.manifest)
        (self.base / "bundle.json").write_bytes(self.bundle_raw)
        self.spec = {"kind": "unaltraweb-practice-edition", "schema_version": 1, "slug": "demo", "version": "r1", "language": "ca",
            "gis": {"profile": "qgis-practice-v3", "bundle": "incoming/gis/bundle.json", "sha256": digest(self.bundle_raw),
                    "verifier": editions.verifier_pin(contract)}, "readings": {}, "selection": {"alumnat": ["initial"], "docent": ["resolved"]}}
        for who in practice_editions.RECIPIENTS:
            source = f"practiques/demo/ca/{who}/LLEGIU-ME.md"
            path = self.project / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"---\ntitle: Synthetic {who}\nlang: ca\ncontent_status: draft\n---\n\nRead this synthetic practice.\n")
            self.spec["readings"][who] = {"source": source, "approved_sha256": digest(path.read_bytes())}
        self.save_spec()
        subprocess.run(["git", "add", "--", "edition.json", "_config.yml", "practiques", ".gitignore"], cwd=self.project, check=True)

    def save_spec(self):
        (self.project / "edition.json").write_bytes(canonical(self.spec))

    def plan_edition(self):
        return editions.plan(self.project, ROOT, "edition.json", "sha256:" + "a" * 64)

    def verification(self, request):
        contract = request["verifier"]
        rows = {row["id"]: row for row in self.manifest["files"]}
        result = {"request": {"config_sha256": request["config_sha256"], "fingerprint": request["fingerprint"]},
            "schema": {"ok": True, "profile": contract["profile"], "schema_sha256": contract["schema_sha256"],
                       "installed_package": {"name": contract["provider"]["name"], "version": contract["provider"]["version"],
                                             "revision": contract["provider"]["installed_revision"]}}, "reports": {}}
        for who, selected in self.spec["selection"].items():
            result["reports"][who] = {"ok": True, "profile": "qgis-practice-v3", "producer": self.manifest["producer"],
                "bundle": {key: self.spec["gis"][key] for key in ("sha256",)}, "selected": selected,
                "closure": [{**rows[selected[0]], "depends_on": ["data"]}, {**rows["data"], "depends_on": []}]}
            result["reports"][who]["bundle"]["path"] = self.spec["gis"]["bundle"]
        return result

    def test_plan_retains_complete_input_inventory_and_binds_author_approval(self):
        plan = self.plan_edition()
        self.assertEqual(len([name for name in plan["inputs"] if name.startswith("incoming/gis/")]), 5)
        self.assertFalse((self.project / "sandbox").exists())
        self.assertFalse((self.project / "dist").exists())
        editions.check_inputs(self.project, plan["inputs"])
        self.source.write_text(self.source.read_text() + "\nUnapproved change\n")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            self.plan_edition()

    def test_source_mutation_and_untracked_configuration_fail_before_reuse(self):
        plan = self.plan_edition()
        (self.base / "payload/data/shared.gpkg").write_bytes(b"changed opaque data")
        with self.assertRaises((ValueError, h.HandoffError)):
            editions.check_inputs(self.project, plan["inputs"])
        subprocess.run(["git", "rm", "--cached", "--force", "--", "edition.json"], cwd=self.project, check=True, stdout=subprocess.PIPE)
        with self.assertRaisesRegex(ValueError, "versioned"):
            self.plan_edition()

    def test_shared_profile_pin_does_not_broaden_classic_verifier(self):
        with self.assertRaisesRegex(ValueError, "explicitly selected shared"):
            practice_editions.compose(self.project, ROOT, "edition.json")
        self.spec["gis"]["verifier"]["image_id"] = "sha256:" + "0" * 64
        self.save_spec()
        with self.assertRaisesRegex(ValueError, "exact selected"):
            self.plan_edition()

    def test_private_schema_and_requested_selection_are_bound(self):
        request = self.plan_edition()
        report = self.verification(request)
        selected = editions.validated_selection(self.project, request, report)
        self.assertEqual({row["id"] for row in selected["alumnat"]["closure"]}, {"initial", "data"})
        for change in ("schema", "request", "closure"):
            wrong = copy.deepcopy(report)
            if change == "schema":
                wrong["schema"]["schema_sha256"] = "0" * 64
            elif change == "request":
                wrong["request"]["fingerprint"] = "0" * 64
            else:
                wrong["reports"]["alumnat"]["closure"].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                editions.validated_selection(self.project, request, wrong)

    def test_resolved_product_is_not_filtered_out_of_a_student_closure(self):
        self.spec["selection"]["alumnat"] = ["resolved"]
        self.save_spec()
        request = self.plan_edition()
        with self.assertRaisesRegex(ValueError, "teacher-only"):
            editions.validated_selection(self.project, request, self.verification(request))

    def test_required_export_witness_cannot_be_discarded_or_shipped_as_classroom_data(self):
        request = self.plan_edition()
        report = self.verification(request)["reports"]["docent"]
        manifest = copy.deepcopy(self.manifest)
        witness = {"id": "witness", "kind": "evidence", "role": "control", "path": "payload/controls/export.json",
                   "ownership": "producer", "sha256": "b" * 64, "bytes": 10}
        manifest["files"].append(witness)
        report["closure"][0]["depends_on"].append("witness")
        with self.assertRaisesRegex(ValueError, "dependency is missing"):
            practice_editions.validate_closure(report, manifest, ["resolved"], "docent", profile="qgis-practice-v3")
        report["closure"].append({**witness, "depends_on": []})
        with self.assertRaisesRegex(ValueError, "not classroom"):
            practice_editions.validate_closure(report, manifest, ["resolved"], "docent", profile="qgis-practice-v3")

    def test_producer_declared_resolved_container_members_are_not_student_data(self):
        request = self.plan_edition()
        report = self.verification(request)
        report["reports"]["alumnat"]["native"] = {"containers": [{"file": "data", "members": [{"role": "resolved-data"}]}]}
        with self.assertRaisesRegex(ValueError, "resolved container member"):
            editions.validated_selection(self.project, request, report)

    def test_reading_binding_cannot_reach_an_unselected_teacher_product(self):
        resolved = next(row for row in self.manifest["files"] if row["id"] == "resolved")
        self.source.write_text(self.source.read_text() + "\n[Project](project.qgz)\n")
        self.spec["readings"]["alumnat"].update(approved_sha256=digest(self.source.read_bytes()), bindings=[
            {"reference": "project.qgz", "product": "resolved", "sha256": resolved["sha256"]}])
        self.save_spec()
        request = self.plan_edition()
        selected = editions.validated_selection(self.project, request, self.verification(request))
        with self.assertRaisesRegex(ValueError, "not selected"):
            practice_pdf.prepare(self.project, ROOT, self.spec["readings"]["alumnat"]["source"], "r1", request["pdf_image"],
                                 **selected["alumnat"]["preparation"])

    def test_receiver_traversal_fails_before_reading_other_files(self):
        with patch.object(editions, "verify_product") as verify, self.assertRaises(h.HandoffError):
            editions.verify_delivered_edition(self.project, {"destination": {"path": "../outside"}}, {})
        verify.assert_not_called()

    def test_rehashed_request_cannot_change_the_approved_source_projection(self):
        request = self.plan_edition()
        editions.checked_request(self.project, request)
        request["spec"]["selection"]["alumnat"] = ["resolved"]
        request["fingerprint"] = digest(canonical({key: value for key, value in request.items() if key != "fingerprint"}))
        with self.assertRaisesRegex(ValueError, "original configuration"):
            editions.checked_request(self.project, request)
        request = self.plan_edition()
        request["schema_version"] = True
        request["fingerprint"] = digest(canonical({key: value for key, value in request.items() if key != "fingerprint"}))
        with self.assertRaisesRegex(ValueError, "Invalid retained"):
            editions.checked_request(self.project, request)

    def test_private_command_stays_within_the_sdk_argument_bound(self):
        self.assertLess(len(editions.VERIFY_CODE), 4096)
        compile(editions.VERIFY_CODE, "private-verifier", "exec")


class SharedActorFailureTests(unittest.TestCase):
    def test_deadline_failure_and_unknown_wait_keep_common_authority_and_diagnostics(self):
        context = {"job_id": "a" * 32, "owner_id": "b" * 32, "daemon_id": "daemon", "worker_user": "1000:1000", "worker_timeout_seconds": 2}
        from unittest.mock import MagicMock
        for waited, expected in (("137", "shared-worker-failed"), (SharedError("timeout", "lost wait"), "shared-worker-observation-failed")):
            job = MagicMock()
            job.workspace = "/original"
            job.call.side_effect = [{"binding": {"lease_id": "c" * 32}}, {"ok": True}, {"worker_absent": True}]
            job.create_args.return_value = ["create", "--memory", "256m", "--memory-swap", "256m", "--pids-limit", "64", "--user", "0:0"]
            with self.subTest(waited=str(waited)), patch.object(shared_practices, "_docker", side_effect=["daemon", "d" * 64, waited]):
                result = shared_practices.run_worker(job, context, "sha256:" + "e" * 64, ["python3", "-m", "domain"])
            self.assertFalse(result["ok"])
            self.assertEqual(result["code"], expected)
            self.assertEqual(result["worker"]["recovery_path"], "recovery/" + "c" * 32)
            self.assertEqual(job.call.call_args_list[1].kwargs["timeout_seconds"], 2)
            if isinstance(waited, Exception):
                self.assertEqual(job.client.call.call_args.args, ("jobs.actor-cancel",))
                self.assertEqual(job.client.call.call_args.kwargs["lease_id"], "c" * 32)
            self.assertFalse(any(call.args[0] in {"jobs.allocate", "jobs.deliver"} for call in job.call.call_args_list))
