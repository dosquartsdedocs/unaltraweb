from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_workflows import JOB_ENV_RUNNER_CONTEXT, load_workflow, validate_workflows


class WorkflowTests(unittest.TestCase):
    def test_repository_workflows_satisfy_static_policy(self) -> None:
        self.assertEqual(validate_workflows(), [])

    def test_loader_preserves_on_and_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "workflow.yml"
            path.write_text("on:\n  push:\njobs: {}\n", encoding="utf-8")
            self.assertIn("on", load_workflow(path))
            path.write_text("name: first\nname: second\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
                load_workflow(path)

    def test_job_environment_runner_context_pattern_uses_only_the_context_root(self) -> None:
        self.assertIsNotNone(JOB_ENV_RUNNER_CONTEXT.search("${{ runner.temp }}/docker"))
        self.assertIsNotNone(JOB_ENV_RUNNER_CONTEXT.search("${{ format('{0}', runner['temp']) }}"))
        self.assertIsNone(JOB_ENV_RUNNER_CONTEXT.search("${{ vars.runner }}"))
        self.assertIsNone(JOB_ENV_RUNNER_CONTEXT.search("${{ inputs.runner }}"))

    def copied_repository(self, root: Path) -> Path:
        workflows = root / ".github/workflows"
        scaffold = root / "src/unaltraweb_mcp/scaffolds/common/.github/workflows"
        shutil.copytree(ROOT / ".github/workflows", workflows)
        shutil.copytree(ROOT / "src/unaltraweb_mcp/scaffolds/common/.github/workflows", scaffold)
        return workflows

    def validate_copy(self, root: Path) -> list[str]:
        workflows = self.copied_repository(root)
        with patch("scripts.validate_workflows.ROOT", root):
            return validate_workflows(workflows)

    def stable_mutation_errors(self, replacements: list[tuple[str, str]]) -> list[str]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            stable = workflows / "site-release.yml"
            text = stable.read_text(encoding="utf-8")
            for old, new in replacements:
                self.assertIn(old, text)
                text = text.replace(old, new, 1)
            stable.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                return validate_workflows(workflows)

    def docker_mutation_errors(self, replacements: list[tuple[str, str]]) -> list[str]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            docker = workflows / "docker-image.yml"
            text = docker.read_text(encoding="utf-8")
            for old, new in replacements:
                self.assertIn(old, text)
                text = text.replace(old, new, 1)
            docker.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                return validate_workflows(workflows)

    def test_scaffold_publication_policy_rejects_mutable_pin_and_missing_pdf_flags(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            caller = root / "src/unaltraweb_mcp/scaffolds/common/.github/workflows/deploy.yml"
            text = caller.read_text(encoding="utf-8")
            text = text.replace("@6427c5963d6d32845cd774dd8537fe935b42d381", "@main")
            text = text.replace("      sync-manual-pdf: true\n", "")
            caller.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("immutable unaltraweb SHA" in error for error in errors))
        self.assertTrue(any("old-compatible PDF rebuild/sync input shape" in error for error in errors))

    def test_scaffold_bootstrap_rejects_inputs_unsupported_by_the_ancestor_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            caller = root / "src/unaltraweb_mcp/scaffolds/common/.github/workflows/deploy.yml"
            caller.write_text(
                caller.read_text(encoding="utf-8").replace(
                    "      sync-manual-pdf: true\n",
                    "      sync-manual-pdf: true\n      reviewed_sha: ${{ inputs.reviewed_sha }}\n",
                ),
                encoding="utf-8",
            )
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("old-compatible PDF rebuild/sync input shape" in error for error in errors))

    def test_publication_policy_rejects_non_main_latest_and_misplaced_write_permission(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            caller = root / "src/unaltraweb_mcp/scaffolds/common/.github/workflows/deploy.yml"
            caller.write_text(
                caller.read_text(encoding="utf-8").replace("refs/heads/main", "refs/heads/trunk"),
                encoding="utf-8",
            )
            stable = workflows / "site-release.yml"
            stable.write_text(
                stable.read_text(encoding="utf-8").replace("      contents: read\n", "      contents: write\n", 1),
                encoding="utf-8",
            )
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("missing reviewed-main gate refs/heads/main" in error for error in errors))
        self.assertTrue(any("preparation job must have only contents: read" in error for error in errors))

    def test_ci_policy_requires_all_ruby_and_manual_pdf_integration_suites(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            ci = workflows / "ci.yml"
            text = ci.read_text(encoding="utf-8")
            text = text.replace("test/**/*_test.rb", "test/plugins/**/*_test.rb")
            text = text.replace("test_*_integration.py", "test_bibliography_filter_integration.py")
            ci.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("every Ruby test from a read-only source mount" in error for error in errors))
        self.assertTrue(any("every test_*_integration.py suite" in error for error in errors))

    def test_core_docker_policy_rejects_rebuild_after_exact_image_tests(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "      - name: Record tested candidate digests\n",
                    "      - name: Rebuild after exact tests\n"
                    "        if: github.ref_type == 'branch'\n"
                    "        run: docker build -t forbidden-rebuild .\n\n"
                    "      - name: Record tested candidate digests\n",
                )
            ]
        )

        self.assertTrue(any("test-candidates: tested candidates must be promoted without rebuild" in error for error in errors))

    def test_core_docker_policy_rejects_candidate_execution_with_package_write(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "      - name: Record built candidate digests\n",
                    "      - name: Execute candidate with publication credentials\n"
                    "        run: docker run --rm ghcr.io/dosquartsdedocs/unaltraweb@sha256:deadbeef true\n\n"
                    "      - name: Record built candidate digests\n",
                )
            ]
        )

        self.assertTrue(any("package-write jobs must never execute candidate images" in error for error in errors))

    def test_core_docker_policy_requires_signed_attestation_after_every_build(self) -> None:
        errors = self.docker_mutation_errors(
            [("      - name: Attest runtime candidate build provenance\n", "      - name: Skip runtime attestation\n")]
        )

        self.assertTrue(any("immediately followed by exact signed provenance" in error for error in errors))

    def test_core_docker_policy_requires_exact_attestation_action_pin(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8",
                    "actions/attest-build-provenance@v4.2.2",
                )
            ]
        )

        self.assertTrue(any("actions/attest-build-provenance must use reviewed SHA" in error for error in errors))
        self.assertTrue(any("action must use a full commit SHA" in error for error in errors))

    def test_core_docker_policy_rejects_write_authority_in_test_job(self) -> None:
        errors = self.docker_mutation_errors([("      packages: read\n", "      packages: write\n")])

        self.assertTrue(any("test-candidates: job boundary, dependency, or permissions" in error for error in errors))

    def test_core_docker_policy_rejects_an_unscoped_test_registry_secret(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "      - name: Log in to GHCR for read-only verification\n"
                    "        uses: docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9 # v3\n"
                    "        with:\n"
                    "          registry: ghcr.io\n"
                    "          username: ${{ github.actor }}\n"
                    "          password: ${{ secrets.GITHUB_TOKEN }}\n",
                    "      - name: Log in to GHCR for read-only verification\n"
                    "        uses: docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9 # v3\n"
                    "        with:\n"
                    "          registry: ghcr.io\n"
                    "          username: ${{ github.actor }}\n"
                    "          password: ${{ secrets.GHCR_WRITE_TOKEN }}\n",
                )
            ]
        )

        self.assertTrue(any("GHCR login must use only the read-scoped repository token" in error for error in errors))

    def test_core_docker_policy_requires_logout_before_candidate_execution(self) -> None:
        errors = self.docker_mutation_errors([("          docker logout ghcr.io\n", "          true\n")])

        self.assertTrue(any("GHCR credentials must be destroyed before candidate execution" in error for error in errors))

    def test_core_docker_policy_rejects_runner_context_in_job_environment(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "  test-candidates:\n"
                    "    if: github.ref_type == 'branch'\n"
                    "    needs: build-candidates\n"
                    "    runs-on: ubuntu-latest\n"
                    "    timeout-minutes: 120\n",
                    "  test-candidates:\n"
                    "    if: github.ref_type == 'branch'\n"
                    "    needs: build-candidates\n"
                    "    runs-on: ubuntu-latest\n"
                    "    timeout-minutes: 120\n"
                    "    env:\n"
                    "      DOCKER_CONFIG: ${{ runner.temp }}/unaltraweb-test-docker\n",
                )
            ]
        )

        self.assertTrue(any("job-level env cannot use the runner context" in error for error in errors))

    def test_core_docker_policy_rejects_github_token_in_candidate_execution(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "      - name: Test all Ruby files in exact runtime\n        env:\n",
                    "      - name: Test all Ruby files in exact runtime\n"
                    "        env:\n"
                    "          GH_TOKEN: ${{ github.token }}\n",
                )
            ]
        )

        self.assertTrue(any("candidate execution must not receive GitHub credentials" in error for error in errors))

    def test_core_docker_policy_rejects_broad_build_push_tags(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "          tags: ghcr.io/dosquartsdedocs/unaltraweb:sha-${{ github.sha }}\n",
                    "          tags: |\n"
                    "            ghcr.io/dosquartsdedocs/unaltraweb:sha-${{ github.sha }}\n"
                    "            ghcr.io/dosquartsdedocs/unaltraweb:main\n",
                )
            ]
        )

        self.assertTrue(any("build-push tags must not contain broad aliases" in error for error in errors))

    def test_core_docker_policy_rejects_broad_aliases_before_exact_tests(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "      - name: Test all Ruby files in exact runtime\n",
                    "      - name: Promote aliases before tests\n"
                    "        run: docker buildx imagetools create --tag \"ghcr.io/dosquartsdedocs/unaltraweb:main\" --tag \"ghcr.io/dosquartsdedocs/unaltraweb:latest\" \"ghcr.io/dosquartsdedocs/unaltraweb@${{ needs.build-candidates.outputs.runtime_digest }}\"\n\n"
                    "      - name: Test all Ruby files in exact runtime\n",
                )
            ]
        )

        self.assertTrue(any("main/latest aliases may be assigned only after test-candidates" in error for error in errors))

    def test_core_docker_policy_rejects_non_blocking_exact_tests(self) -> None:
        errors = self.docker_mutation_errors(
            [
                (
                    "      - name: Smoke test exact MCP\n        env:\n",
                    "      - name: Smoke test exact MCP\n"
                    "        continue-on-error: true\n"
                    "        env:\n",
                )
            ]
        )

        self.assertTrue(any("Smoke test exact MCP" in error for error in errors))

    def test_core_docker_policy_requires_sha_no_clobber_and_revision_checks(self) -> None:
        errors = self.docker_mutation_errors(
            [
                ("      - name: Require unused candidate SHA tags\n", "      - name: Candidate SHA tags\n"),
                ('if [ "$revision" != "$GITHUB_SHA" ]', 'if [ "$revision" != "$IMAGE_SHA" ]'),
            ]
        )

        self.assertTrue(any("fail closed before overwriting any SHA candidate" in error for error in errors))
        self.assertTrue(any("exact digests require signed provenance and revision checks" in error for error in errors))

    def test_core_docker_stable_promotion_requires_signed_source_binding(self) -> None:
        errors = self.docker_mutation_errors(
            [('--source-digest "$SOURCE_COMMIT"', '--source-digest "$GITHUB_SHA"')]
        )

        self.assertTrue(any("tag promotion must verify signed provenance bound to receipt source_commit" in error for error in errors))

    def test_core_docker_stable_promotion_uses_only_receipt_digests(self) -> None:
        errors = self.docker_mutation_errors(
            [('source = candidate["reference"] if candidate else ""', 'source = component["reference"]')]
        )

        self.assertTrue(any("may promote only immutable digests recorded in the candidate receipt" in error for error in errors))

    def test_stable_policy_requires_local_candidate_evidence_and_reviewed_core_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            stable = workflows / "site-release.yml"
            text = stable.read_text(encoding="utf-8")
            text = text.replace(
                "      candidate_manifest_sha256:\n        description: SHA-256 of the locally validated release-manifest.json candidate.\n        required: true",
                "      candidate_manifest_sha256:\n        description: SHA-256 of the locally validated release-manifest.json candidate.\n        required: false",
            )
            text = text.replace("            -e LOCAL_CORE=/reviewed-core\n", "")
            stable.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("candidate_manifest_sha256 must be required" in error for error in errors))
        self.assertTrue(any("missing stable release evidence LOCAL_CORE" in error for error in errors))

    def test_latest_policy_requires_digest_pinned_pdf_worker(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            deploy = workflows / "site-deploy.yml"
            text = deploy.read_text(encoding="utf-8")
            text = text.replace(
                "      manual-pdf-image:\n        description: Digest-pinned unaltraweb manual PDF worker image.\n        required: true",
                "      manual-pdf-image:\n        description: Digest-pinned unaltraweb manual PDF worker image.\n        required: false",
            )
            text = text.replace("unaltraweb-manual-pdf@sha256:", "unaltraweb-manual-pdf:")
            deploy.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("manual-pdf-image must be required" in error for error in errors))
        self.assertTrue(any("missing latest publication gate unaltraweb-manual-pdf@sha256:" in error for error in errors))

    def test_latest_policy_binds_pdf_worker_revision_to_defining_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            deploy = workflows / "site-deploy.yml"
            text = deploy.read_text(encoding="utf-8")
            text = text.replace("WORKFLOW_SHA: ${{ job.workflow_sha }}", "WORKFLOW_SHA: ${{ github.workflow_sha }}", 1)
            text = text.replace("org.opencontainers.image.revision", "org.opencontainers.image.version", 1)
            text = text.replace('[[ "$image_revision" != "$WORKFLOW_SHA" ]]', '[[ "$image_revision" != "$CURRENT_SHA" ]]', 1)
            deploy.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("defining job workflow identity" in error for error in errors))
        self.assertTrue(any("provenance check missing org.opencontainers.image.revision" in error for error in errors))
        self.assertTrue(any("revision label must be compared with the defining workflow SHA" in error for error in errors))
        self.assertTrue(any("must not come from the caller" in error for error in errors))

    def test_project_compute_uses_provider_identity_and_channel_specific_gates(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflows = self.copied_repository(root)
            project_compute = workflows / "project-compute-image.yml"
            text = project_compute.read_text(encoding="utf-8")
            text = text.replace("repository: ${{ job.workflow_repository }}", "repository: dosquartsdedocs/unaltraweb", 1)
            text = text.replace("ref: ${{ job.workflow_sha }}", "ref: ${{ github.workflow_sha }}", 1)
            text = text.replace(
                "      - name: Validate candidate core distribution\n        if: github.ref_type == 'branch'",
                "      - name: Validate candidate core distribution\n        if: github.ref_type == 'tag'",
                1,
            )
            project_compute.write_text(text, encoding="utf-8")
            with patch("scripts.validate_workflows.ROOT", root):
                errors = validate_workflows(workflows)

        self.assertTrue(any("provider checkout must use the defining reusable workflow" in error for error in errors))
        self.assertTrue(any("default-branch candidates must use only distribution-check" in error for error in errors))

    def test_stable_policy_rejects_disabled_or_caller_selected_privileged_verifier(self) -> None:
        errors = self.stable_mutation_errors(
            [
                (
                    "          repository: ${{ job.workflow_repository }}\n          ref: ${{ job.workflow_sha }}",
                    "          repository: dosquartsdedocs/unaltraweb\n          ref: ${{ inputs.core_sha }}",
                ),
                (
                    "        run: exec bash .unaltraweb-release-core/scripts/manual/publish_release.sh",
                    "        run: ':'",
                ),
            ]
        )

        self.assertTrue(any("exact reviewed structure" in error for error in errors))

    def test_stable_policy_requires_defining_workflow_ref_identity(self) -> None:
        errors = self.stable_mutation_errors(
            [("WORKFLOW_REF: ${{ job.workflow_ref }}", "WORKFLOW_REF: ${{ github.workflow_ref }}")]
        )

        self.assertTrue(any("bind core authority" in error for error in errors))

    def test_stable_policy_rejects_conditional_or_extended_publication_job(self) -> None:
        errors = self.stable_mutation_errors(
            [
                (
                    "      - name: Publish verified stable release\n",
                    "      - name: Publish verified stable release\n        continue-on-error: true\n",
                )
            ]
        )
        self.assertTrue(any("exact reviewed structure" in error for error in errors))

        errors = self.stable_mutation_errors(
            [
                (
                    "jobs:\n  prepare:",
                    "defaults:\n  run:\n    shell: bash {0}\n\njobs:\n  prepare:",
                )
            ]
        )
        self.assertTrue(any("authority outside the reviewed structure" in error for error in errors))

    def test_stable_policy_rejects_masked_verification_and_early_write_authority(self) -> None:
        command = "        run: exec bash .unaltraweb-release-core/scripts/manual/publish_release.sh"
        mutations = [
            [
                (
                    command,
                    "        run: |\n"
                    "          exec bash .unaltraweb-release-core/scripts/manual/publish_release.sh || :",
                )
            ],
            [
                (
                    command,
                    "        run: |\n"
                    "          printf '%s' '{\"draft\":false}' | gh api --method PATCH repos/example/releases/1 --input -\n"
                    "          exec bash .unaltraweb-release-core/scripts/manual/publish_release.sh",
                )
            ],
            [("GH_TOKEN: ${{ github.token }}", "GH_TOKEN: ${{ github['token'] }}")],
        ]
        for replacements in mutations:
            with self.subTest(replacements=replacements):
                errors = self.stable_mutation_errors(replacements)
                self.assertTrue(any("exact reviewed structure" in error for error in errors))

    def test_stable_policy_rejects_additional_write_job(self) -> None:
        errors = self.stable_mutation_errors(
            [
                (
                    "  publish:\n",
                    "  unauthorized:\n"
                    "    runs-on: ubuntu-latest\n"
                    "    permissions:\n"
                    "      contents: write\n"
                    "    steps:\n"
                    "      - run: gh api --method PATCH repos/example/releases/1\n\n"
                    "  publish:\n",
                )
            ]
        )
        self.assertTrue(any("only prepare and publish jobs" in error for error in errors))

    def test_core_docker_shell_steps_have_valid_bash_syntax(self) -> None:
        workflow = load_workflow(ROOT / ".github/workflows/docker-image.yml")
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                script = step.get("run") if isinstance(step, dict) else None
                if not isinstance(script, str):
                    continue
                completed = subprocess.run(
                    ["bash", "-n"],
                    input=script,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{job_name}/{step.get('name')}: {completed.stderr}",
                )

    def test_stable_shell_steps_have_valid_bash_syntax(self) -> None:
        workflow = load_workflow(ROOT / ".github/workflows/site-release.yml")
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                script = step.get("run") if isinstance(step, dict) else None
                if not isinstance(script, str):
                    continue
                completed = subprocess.run(
                    ["bash", "-n"],
                    input=script,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{job_name}/{step.get('name')}: {completed.stderr}",
                )
        publisher = subprocess.run(
            ["bash", "-n", str(ROOT / "scripts/manual/publish_release.sh")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(publisher.returncode, 0, publisher.stderr)


if __name__ == "__main__":
    unittest.main()
