from __future__ import annotations

import io
import sys
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unaltraweb_mcp import cli, site_tools


class ManualPdfMcpTests(unittest.TestCase):
    @staticmethod
    def _status(*, enabled: bool = True, fresh_en: bool = True, fresh_ca: bool = True) -> dict:
        languages = [
            {
                "language": "en",
                "fresh": fresh_en,
                "ready_to_publish": fresh_en,
                "published_current": fresh_en,
                "release_selector": "latest",
                "generated_pdf": "tmp/manual-pdf/en/manual-en.pdf",
                "generated_cover": "tmp/manual-pdf/en/manual-cover-en.png",
                "published_pdf": "assets/pdf/manual-en.pdf",
                "published_cover": "assets/img/manual-cover-en.png",
            },
            {
                "language": "ca",
                "fresh": fresh_ca,
                "ready_to_publish": fresh_ca,
                "published_current": fresh_ca,
                "release_selector": "latest",
                "generated_pdf": "tmp/manual-pdf/ca/manual-ca.pdf",
                "generated_cover": "tmp/manual-pdf/ca/manual-cover-ca.png",
                "published_pdf": "assets/pdf/manual-ca.pdf",
                "published_cover": "assets/img/manual-cover-ca.png",
            },
        ]
        return {
            "ok": enabled and fresh_en and fresh_ca,
            "enabled": enabled,
            "configuration_ok": enabled,
            "ready_to_publish": enabled and fresh_en and fresh_ca,
            "languages": languages if enabled else [],
        }

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_build_uses_fixed_factory_target(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        site_tools.manual_pdf_build(project, factory, language="ca", release_selector="v2026.09")

        run_factory_make.assert_called_once_with(
            factory,
            project,
            "manual-pdf-build",
            extra_args=["MANUAL_PDF_LANG=ca"],
            env={"MANUAL_RELEASE_SELECTOR": "v2026.09"},
        )

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_publish_defaults_to_dry_run(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        result = site_tools.manual_pdf_publish(project, factory)

        self.assertTrue(result["dry_run"])
        run_factory_make.assert_called_once_with(
            factory,
            project,
            "manual-pdf-publish-worker",
            extra_args=["MANUAL_PDF_PUBLISH_DRY_RUN=1"],
            env={"MANUAL_RELEASE_SELECTOR": "latest"},
        )

    @patch("unaltraweb_mcp.cli.factory_dir", return_value=Path("/tmp/factory"))
    @patch("unaltraweb_mcp.site_tools.manual_pdf_publish", return_value={"ok": False, "error": "failed"})
    def test_publish_cli_returns_nonzero_for_failed_payload(self, _publish, _factory_dir) -> None:
        with redirect_stdout(io.StringIO()):
            result = cli.main([
                "--project",
                "/tmp/manual-site",
                "mcp",
                "manual-pdf-publish",
            ])

        self.assertEqual(result, 1)

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_real_publish_requires_confirmation(self, run_factory_make) -> None:
        with self.assertRaisesRegex(RuntimeError, "confirm_publish=True"):
            site_tools.manual_pdf_publish(Path("/tmp/manual-site"), Path("/tmp/factory"), dry_run=False)
        run_factory_make.assert_not_called()

    @patch("unaltraweb_mcp.manual_pdf_preview.record_publication")
    @patch("unaltraweb_mcp.manual_pdf_preview.begin_publication")
    @patch("unaltraweb_mcp.manual_pdf_preview.receipt_present", return_value=False)
    @patch("unaltraweb_mcp.manual_pdf_preview.project_lock", return_value=nullcontext())
    @patch("unaltraweb_mcp.site_tools.manual_pdf_status")
    @patch("unaltraweb_mcp.site_tools.run_factory_make", return_value={"ok": True})
    def test_real_publish_records_non_owning_provenance(
        self,
        run_factory_make,
        manual_pdf_status,
        _project_lock,
        _receipt_present,
        begin_publication,
        record_publication,
    ) -> None:
        status = self._status()
        status["published_current"] = True
        manual_pdf_status.return_value = status
        record_publication.return_value = {
            "path": ".cache/unaltraweb/manual-pdf-publication.json",
            "sha256": "a" * 64,
            "artifacts": 4,
        }
        begin_publication.return_value = {
            "path": ".cache/unaltraweb/manual-pdf-publication-intent.json",
            "sha256": "b" * 64,
            "artifacts": 4,
        }
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        result = site_tools.manual_pdf_publish(
            project,
            factory,
            dry_run=False,
            confirm_publish=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["publication_receipt"]["artifacts"], 4)
        run_factory_make.assert_called_once_with(
            factory,
            project.resolve(),
            "manual-pdf-publish-worker",
            extra_args=[
                "MANUAL_PDF_PUBLISH_DRY_RUN=0",
                "MANUAL_PDF_CONFIRM_PUBLISH=1",
                f"MANUAL_PDF_PUBLICATION_INTENT_SHA256={'b' * 64}",
            ],
            env={"MANUAL_RELEASE_SELECTOR": "latest"},
        )
        begin_publication.assert_called_once_with(project.resolve(), status["languages"], lock_held=True)
        record_publication.assert_called_once_with(
            project.resolve(),
            status["languages"],
            lock_held=True,
            expected_intent_sha256="b" * 64,
        )

    @patch("unaltraweb_mcp.manual_pdf_preview.receipt_present", return_value=True)
    @patch("unaltraweb_mcp.manual_pdf_preview.project_lock", return_value=nullcontext())
    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_real_publish_requires_preview_cleanup(
        self,
        run_factory_make,
        _project_lock,
        _receipt_present,
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "Clean receipt-owned"):
            site_tools.manual_pdf_publish(
                Path("/tmp/manual-site"),
                Path("/tmp/factory"),
                dry_run=False,
                confirm_publish=True,
            )
        run_factory_make.assert_not_called()

    def test_real_publish_rejects_a_reduced_postflight_inventory(self) -> None:
        preflight = self._status()
        postflight = self._status()
        postflight["languages"] = postflight["languages"][:1]
        postflight["published_current"] = True
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        with patch("unaltraweb_mcp.manual_pdf_preview.project_lock", return_value=nullcontext()), patch(
            "unaltraweb_mcp.manual_pdf_preview.receipt_present",
            return_value=False,
        ), patch(
            "unaltraweb_mcp.site_tools.manual_pdf_status",
            side_effect=[preflight, postflight],
        ), patch(
            "unaltraweb_mcp.manual_pdf_preview.begin_publication",
            return_value={"sha256": "b" * 64},
        ), patch(
            "unaltraweb_mcp.site_tools.run_factory_make",
            return_value={"ok": True},
        ), patch("unaltraweb_mcp.manual_pdf_preview.record_publication") as record_publication:
            result = site_tools.manual_pdf_publish(
                project,
                factory,
                dry_run=False,
                confirm_publish=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("inventory changed", result["error"])
        record_publication.assert_not_called()

    @patch("unaltraweb_mcp.manual_pdf_preview.config_sha256", return_value="a" * 64)
    @patch("unaltraweb_mcp.site_tools.manual_pdf_status")
    def test_preview_prepare_is_a_disabled_noop(self, manual_pdf_status, _config_sha256) -> None:
        manual_pdf_status.return_value = self._status(enabled=False)

        with patch("unaltraweb_mcp.site_tools.manual_pdf_build") as manual_pdf_build, patch(
            "unaltraweb_mcp.manual_pdf_preview.prepare"
        ) as stage:
            result = site_tools.manual_pdf_preview_prepare(Path("/tmp/manual-site"), Path("/tmp/factory"))

        self.assertTrue(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertFalse(result["publishes"])
        manual_pdf_build.assert_not_called()
        stage.assert_not_called()

    @patch("unaltraweb_mcp.manual_pdf_preview.clean")
    @patch("unaltraweb_mcp.manual_pdf_preview.prepare")
    @patch("unaltraweb_mcp.manual_pdf_preview.config_sha256", return_value="b" * 64)
    @patch("unaltraweb_mcp.site_tools.manual_pdf_build", return_value={"ok": True})
    @patch("unaltraweb_mcp.site_tools.manual_pdf_status")
    def test_preview_prepare_builds_only_stale_languages_and_stages_latest(
        self,
        manual_pdf_status,
        manual_pdf_build,
        _config_sha256,
        stage,
        clean,
    ) -> None:
        initial = self._status(fresh_en=True, fresh_ca=False)
        final = self._status()
        manual_pdf_status.side_effect = [initial, initial, final, final]
        stage.return_value = {
            "ok": True,
            "state": "staged",
            "publishes": False,
            "receipt_sha256": "a" * 64,
        }
        clean.return_value = {
            "ok": True,
            "state": "planned",
            "receipt_sha256": "a" * 64,
            "publishes": False,
        }
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        with patch("unaltraweb_mcp.manual_pdf_preview.project_lock", return_value=nullcontext()), patch(
            "unaltraweb_mcp.site_tools.manual_pdf_publish"
        ) as publish:
            result = site_tools.manual_pdf_preview_prepare(project, factory)

        self.assertTrue(result["ok"])
        self.assertFalse(result["publishes"])
        self.assertEqual(result["built_languages"], ["ca"])
        self.assertEqual(
            manual_pdf_status.call_args_list,
            [
                call(project.resolve(), factory, release_selector="latest"),
                call(project.resolve(), factory, release_selector="latest"),
                call(project.resolve(), factory, release_selector="latest"),
                call(project.resolve(), factory, release_selector="latest"),
            ],
        )
        manual_pdf_build.assert_called_once_with(project.resolve(), factory, language="ca", release_selector="latest")
        stage.assert_called_once_with(
            project.resolve(),
            final["languages"],
            expected_config_sha256="b" * 64,
            lock_held=True,
        )
        clean.assert_called_once_with(project.resolve(), lock_held=True)
        publish.assert_not_called()

    @patch("unaltraweb_mcp.manual_pdf_preview.config_sha256", return_value="c" * 64)
    @patch("unaltraweb_mcp.site_tools.manual_pdf_build", return_value={"ok": False, "error": "build failed"})
    @patch("unaltraweb_mcp.site_tools.manual_pdf_status")
    def test_preview_prepare_never_stages_after_failed_build(
        self,
        manual_pdf_status,
        _manual_pdf_build,
        _config_sha256,
    ) -> None:
        manual_pdf_status.return_value = self._status(fresh_en=False)

        with patch("unaltraweb_mcp.manual_pdf_preview.prepare") as stage, patch(
            "unaltraweb_mcp.site_tools.manual_pdf_publish"
        ) as publish:
            with patch("unaltraweb_mcp.manual_pdf_preview.project_lock", return_value=nullcontext()):
                result = site_tools.manual_pdf_preview_prepare(Path("/tmp/manual-site"), Path("/tmp/factory"))

        self.assertFalse(result["ok"])
        self.assertFalse(result["publishes"])
        stage.assert_not_called()
        publish.assert_not_called()

    @patch("unaltraweb_mcp.manual_pdf_preview.receipt_present", return_value=True)
    @patch("unaltraweb_mcp.site_tools.manual_pdf_status")
    def test_preview_prepare_requires_cleanup_before_disabling_pdf(
        self,
        manual_pdf_status,
        _receipt_present,
    ) -> None:
        manual_pdf_status.return_value = self._status(enabled=False)

        result = site_tools.manual_pdf_preview_prepare(Path("/tmp/manual-site"), Path("/tmp/factory"))

        self.assertFalse(result["ok"])
        self.assertFalse(result["enabled"])
        self.assertFalse(result["skipped"])
        self.assertIn("clean", result["error"])

    @patch("unaltraweb_mcp.manual_pdf_preview.clean")
    @patch("unaltraweb_mcp.manual_pdf_preview.prepare")
    @patch("unaltraweb_mcp.manual_pdf_preview.config_sha256", return_value="e" * 64)
    @patch("unaltraweb_mcp.site_tools.manual_pdf_status")
    def test_preview_prepare_cleans_its_staging_when_a_newer_generation_appears(
        self,
        manual_pdf_status,
        _config_sha256,
        stage,
        clean,
    ) -> None:
        fresh = self._status()
        stale = self._status()
        stale["languages"][0]["published_current"] = False
        manual_pdf_status.side_effect = [fresh, fresh, fresh, stale]
        stage.return_value = {
            "ok": True,
            "state": "staged",
            "publishes": False,
            "receipt_sha256": "f" * 64,
        }
        clean.side_effect = [
            {
                "ok": True,
                "state": "planned",
                "receipt_sha256": "f" * 64,
                "publishes": False,
            },
            {"ok": True, "state": "cleaned", "publishes": False},
        ]
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        with patch("unaltraweb_mcp.manual_pdf_preview.project_lock", return_value=nullcontext()):
            result = site_tools.manual_pdf_preview_prepare(project, factory)

        self.assertFalse(result["ok"])
        self.assertFalse(result["publishes"])
        self.assertEqual(result["cleanup"]["state"], "cleaned")
        self.assertEqual(
            clean.call_args_list,
            [
                call(project.resolve(), lock_held=True),
                call(
                    project.resolve(),
                    dry_run=False,
                    confirm_clean=True,
                    expected_receipt_sha256="f" * 64,
                    lock_held=True,
                ),
            ],
        )

    @patch("unaltraweb_mcp.manual_pdf_preview.clean")
    def test_preview_clean_delegates_confirmation_without_factory(self, clean) -> None:
        clean.return_value = {"ok": True, "publishes": False, "state": "cleaned"}

        result = site_tools.manual_pdf_preview_clean(
            Path("/tmp/manual-site"),
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256="d" * 64,
        )

        self.assertTrue(result["ok"])
        clean.assert_called_once_with(
            Path("/tmp/manual-site").resolve(),
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256="d" * 64,
        )

    @patch("unaltraweb_mcp.site_tools.manual_pdf_status", return_value={"ok": False, "error": "status failed"})
    def test_preview_prepare_does_not_treat_failed_status_as_disabled(self, _manual_pdf_status) -> None:
        result = site_tools.manual_pdf_preview_prepare(Path("/tmp/manual-site"), Path("/tmp/factory"))

        self.assertFalse(result["ok"])
        self.assertIsNone(result["enabled"])
        self.assertFalse(result["publishes"])
        self.assertEqual(result["error"], "status failed")


if __name__ == "__main__":
    unittest.main()
