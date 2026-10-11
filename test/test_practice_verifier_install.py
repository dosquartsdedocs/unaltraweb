from __future__ import annotations

import copy
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import install_practice_verifier as installer


def fixture_contract():
    # Synthetic selection for mocked installation tests; never a production pin.
    version = "9.8.7"
    sha = hashlib.sha256(b"synthetic verifier wheel").hexdigest()
    return {"wheel_contract": {"factory_required_mcp": ["manual-practice-compose"]}, "components": {
        installer.COMPONENT: {"kind": "companion", "name": "unaltracaptura_qgis", "version": version,
            "release": "v" + version, "release_status": "released", "repository": installer.REPOSITORY,
            "reference": f"{installer.REPOSITORY}/releases/download/v{version}/unaltracaptura_qgis-{version}-py3-none-any.whl#sha256={sha}",
            "included_in_wheel": False, "features": list(installer.PROFILES)}}}


class PracticeVerifierInstallTests(unittest.TestCase):
    def test_missing_final_pin_refuses_before_pip_or_network(self):
        contract = fixture_contract()
        del contract["components"][installer.COMPONENT]
        with patch.object(installer, "checked_run") as run, self.assertRaisesRegex(ValueError, "pin is missing"):
            installer.install(contract)
        run.assert_not_called()
        self.assertTrue(installer.publication_errors(contract))

    def test_only_a_released_matching_owner_url_with_nonzero_hash_is_accepted(self):
        original = fixture_contract()
        self.assertEqual(installer.selection(original)["version"], "9.8.7")
        for change in ("pending", "rc", "foreign-url", "wrong-version", "no-hash", "zero-hash", "placeholder", "missing-profile"):
            contract = copy.deepcopy(original)
            item = contract["components"][installer.COMPONENT]
            if change == "pending":
                item["release_status"] = "pending"
            elif change == "rc":
                item["version"] = "9.8.7rc2"
            elif change == "foreign-url":
                item["reference"] = item["reference"].replace("github.com", "example.invalid")
            elif change == "wrong-version":
                item["reference"] = item["reference"].replace("download/v9.8.7", "download/v9.8.6")
            elif change == "no-hash":
                item["reference"] = item["reference"].split("#")[0]
            elif change == "zero-hash":
                item["reference"] = item["reference"].split("#")[0] + "#sha256=" + "0"*64
            elif change == "placeholder":
                item["reference"] = item["reference"].split("#")[0] + "#sha256=PENDING_OWNER_PIN"
            else:
                item["features"].remove("qgis-practice-v2")
            with self.subTest(change=change), self.assertRaises(ValueError):
                installer.selection(contract)

    def test_install_keeps_url_hash_and_certifies_both_explicit_profiles(self):
        contract = fixture_contract()
        selected = installer.selection(contract)
        dist = SimpleNamespace(version=selected["version"], read_text=lambda name: json.dumps({
            "archive_info": {"hashes": {"sha256": selected["wheel_sha256"]}}}))
        calls = []
        def run(arguments, timeout=120):
            calls.append(arguments)
            if "pip" in arguments:
                self.assertEqual(timeout, 600)
                return "installed"
            profile = arguments[-1]
            self.assertEqual(arguments[-3:-1], ["practice-schema", "--profile"])
            return json.dumps({"ok": True, "profile": profile, "schema_sha256": hashlib.sha256(profile.encode()).hexdigest(),
                "installed_package": {"name": selected["package"], "version": selected["version"], "revision": "sha256:"+"a"*64}})
        with patch.object(installer, "distribution", return_value=dist), patch.object(installer, "checked_run", side_effect=run):
            result = installer.install(contract)
        self.assertEqual(calls[0][-1], selected["reference"])
        self.assertIn("--no-index", calls[0])
        self.assertIn("--no-deps", calls[0])
        self.assertEqual(set(result["profiles"]), set(installer.PROFILES))
        self.assertEqual(len(calls), 3)

    def test_index_install_or_wrong_wheel_cannot_pass_verification(self):
        selected = installer.selection(fixture_contract())
        for direct in ({}, {"archive_info": {"hashes": {"sha256": "0"*64}}}):
            with self.subTest(direct=direct), patch.object(installer, "distribution", return_value=SimpleNamespace(
                    version=selected["version"], read_text=lambda name: json.dumps(direct))), \
                    patch.object(installer, "checked_run") as run, self.assertRaisesRegex(ValueError, "selected release wheel"):
                installer.verify_installed(selected)
            run.assert_not_called()

    def test_wrong_public_profile_is_refused(self):
        selected = installer.selection(fixture_contract())
        dist = SimpleNamespace(version=selected["version"], read_text=lambda name: json.dumps({
            "archive_info": {"hashes": {"sha256": selected["wheel_sha256"]}}}))
        with patch.object(installer, "distribution", return_value=dist), patch.object(installer, "checked_run", return_value=json.dumps({
                "ok": True, "profile": "qgis-practice-v1", "schema_sha256": "a"*64,
                "installed_package": {"name": selected["package"], "version": selected["version"], "revision": "sha256:"+"b"*64}})), \
                self.assertRaisesRegex(ValueError, "requested public profile"):
            installer.verify_installed(selected)
