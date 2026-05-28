#!/usr/bin/env python3
"""Smoke tests for connected-runner handoff packaging helpers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_CONNECTED_RUNNER_HANDOFF = PROJECT_ROOT / "scripts" / "package_connected_runner_handoff.py"


def load_package_connected_runner_handoff():
    spec = importlib.util.spec_from_file_location(
        "package_connected_runner_handoff",
        PACKAGE_CONNECTED_RUNNER_HANDOFF,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {PACKAGE_CONNECTED_RUNNER_HANDOFF}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageConnectedRunnerHandoffSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_package_connected_runner_handoff()

    def test_generated_runner_rejects_literal_remote_placeholders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-runner-") as tmp:
            bundle_dir = Path(tmp)
            script_path = self.module.write_runner_script(bundle_dir)
            script_text = script_path.read_text(encoding="utf-8")
            syntax_ok, syntax_message = self.module.verify_runner_script_syntax(script_path)
            guard_ok, guard_message, guard_details = self.module.verify_runner_script_remote_guard(script_text)
            order_ok, order_message, order_details = self.module.verify_runner_script_order(script_text)

        if "bash is unavailable" in syntax_message or "bash is unavailable" in guard_message:
            self.skipTest("bash is unavailable")

        self.assertTrue(syntax_ok, syntax_message)
        self.assertTrue(guard_ok, guard_message)
        self.assertTrue(order_ok, order_message)
        order_rules = {rule["id"]: rule for rule in order_details["rules"]}
        self.assertEqual(
            order_rules["remote_validate_call_before_command_preflight"]["status"],
            "pass",
        )
        self.assertEqual(self.module.missing_runner_script_markers(script_text), [])
        self.assertIn("not a placeholder value", script_text)
        self.assertIn('git init "${SOURCE_DIR}"', script_text)
        self.assertIn(
            "git ls-files --others --modified --deleted --exclude-standard -z | "
            "git add --pathspec-from-file=- --pathspec-file-nul",
            script_text,
        )
        self.assertIn(self.module.CONNECTED_STRICT_GATE_COMMAND, script_text)
        self.assertIn(self.module.LIVE_BETA_FINAL_GATE_COMMAND, script_text)
        cases = {case["case"]: case for case in guard_details["cases"]}
        self.assertIn("placeholder", cases)
        self.assertIn("legacy_placeholder", cases)
        self.assertIn("placeholder_repo_url", cases)
        self.assertIn("placeholder_env_name", cases)
        self.assertIn("missing_https_host", cases)
        self.assertIn("missing_ssh_host", cases)
        self.assertIn("missing_scp_host", cases)
        self.assertIn("missing_remote_path", cases)
        self.assertIn("not a placeholder value", cases["placeholder"]["output"])
        self.assertTrue(cases["placeholder"]["preflight_only"])
        self.assertIn("not a placeholder value", cases["legacy_placeholder"]["output"])
        self.assertIn("not a placeholder value", cases["placeholder_repo_url"]["output"])
        self.assertIn("not a placeholder value", cases["placeholder_env_name"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_https_host"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_ssh_host"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_scp_host"]["output"])
        self.assertIn("HTTPS, SSH, or scp-style", cases["missing_remote_path"]["output"])

    def test_runner_order_fails_when_remote_validate_call_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-runner-") as tmp:
            script_path = self.module.write_runner_script(Path(tmp))
            script_text = script_path.read_text(encoding="utf-8")

        mutated_script = script_text.replace(
            self.module.RUNNER_REMOTE_VALIDATE_CALL_MARKER,
            "\nBRANCH_NAME=",
        )
        order_ok, order_message, order_details = self.module.verify_runner_script_order(mutated_script)
        order_rules = {rule["id"]: rule for rule in order_details["rules"]}

        self.assertFalse(order_ok)
        self.assertIn("remote_validate_call_before_command_preflight", order_message)
        self.assertEqual(order_rules["remote_validate_call_before_command_preflight"]["status"], "fail")

    def test_verify_json_only_prints_parseable_failure_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-json-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            bundle_dir.mkdir()

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_CONNECTED_RUNNER_HANDOFF),
                    "--verify",
                    str(bundle_dir),
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["bundle_dir"], str(bundle_dir.absolute()))
            self.assertEqual(payload["bundle_verification"]["status"], "fail")
            self.assertTrue((bundle_dir / "handoff-verification.json").is_file())
            self.assertNotIn("Handoff verification:", completed.stdout)

    def test_verify_summary_json_only_omits_verbose_check_details(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-summary-json-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            bundle_dir.mkdir()

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_CONNECTED_RUNNER_HANDOFF),
                    "--verify",
                    str(bundle_dir),
                    "--summary-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["bundle_dir"], str(bundle_dir.absolute()))
            self.assertEqual(payload["bundle_verification_summary"]["status"], "fail")
            self.assertGreater(payload["bundle_verification_summary"]["counts"]["fail"], 0)
            self.assertIn("failures", payload["bundle_verification_summary"])
            self.assertNotIn("bundle_verification", payload)
            self.assertNotIn("Handoff verification:", completed.stdout)

    def test_handoff_context_json_only_reads_existing_manifest_without_verifying(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-context-json-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            bundle_dir.mkdir()
            context = {
                "status": "warn",
                "next_item_id": "git_origin_remote",
                "bundle_gate_summary": {"gate_count": 5},
            }
            (bundle_dir / "manifest.json").write_text(
                json.dumps({"handoff_context": context}) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_CONNECTED_RUNNER_HANDOFF),
                    "--verify",
                    str(bundle_dir),
                    "--handoff-context-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verification_written = (bundle_dir / "handoff-verification.json").exists()

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout), context)
        self.assertEqual(completed.stderr, "")
        self.assertFalse(verification_written)

    def test_handoff_command_sequence_only_reads_existing_manifest_without_verifying(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-sequence-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            bundle_dir.mkdir()
            context = {
                "bundle_command_sequence": [
                    {"id": "verify_bundle", "command": "python3 verify.py"},
                    {"id": "preflight", "command": "PREFLIGHT_ONLY=true ./run.sh"},
                ]
            }
            (bundle_dir / "manifest.json").write_text(
                json.dumps({"handoff_context": context}) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_CONNECTED_RUNNER_HANDOFF),
                    "--verify",
                    str(bundle_dir),
                    "--handoff-command-sequence-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            verification_written = (bundle_dir / "handoff-verification.json").exists()

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "python3 verify.py\nPREFLIGHT_ONLY=true ./run.sh\n")
        self.assertEqual(completed.stderr, "")
        self.assertFalse(verification_written)

    def test_handoff_context_json_only_computes_from_package_without_creating_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-context-compute-") as tmp:
            root = Path(tmp)
            package_dir = root / "artifacts" / "evidence-packages" / "20260526-KRW-BTC-beta-001"
            output_dir = root / "artifacts" / "handoff-bundles"
            package_dir.mkdir(parents=True)
            (package_dir / "manifest.json").write_text(
                json.dumps({"generated_at": "2026-05-26T00:00:00+00:00"}) + "\n",
                encoding="utf-8",
            )
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "readiness_estimate": {
                            "percent": 96,
                            "remaining_items": 1,
                        },
                        "progress_summary": {
                            "remaining_ids": ["git_origin_remote"],
                            "remaining_by_owner": {"connected runner": 1},
                            "next_item_id": "git_origin_remote",
                            "next_item_owner": "connected runner",
                            "next_commands_by_owner": {
                                "connected runner": {
                                    "id": "git_origin_remote",
                                    "status": "warn",
                                    "automation_command": "python3 scripts/next_release_step.py --json-only",
                                    "full_flow_command": "./run-connected-runner-handoff.sh",
                                },
                            },
                            "completion_requirements": [
                                {
                                    "requirement": "real_git_remote_url",
                                    "item_ids": ["git_origin_remote"],
                                    "owners": ["connected runner"],
                                    "count": 1,
                                }
                            ],
                            "completion_plan": [
                                {
                                    "id": "git_origin_remote",
                                    "owner": "connected runner",
                                    "status": "warn",
                                    "mode": "connected_runner_preflight",
                                    "requirements": ["real_git_remote_url"],
                                    "automation_command": "python3 scripts/next_release_step.py --json-only",
                                }
                            ],
                            "repo_url": {"required": True},
                            "local_readiness": {"status": "warn"},
                            "warning_review": {"status": "pass"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_CONNECTED_RUNNER_HANDOFF),
                    "--project-root",
                    str(root),
                    "--package-dir",
                    str(package_dir),
                    "--output-dir",
                    str(output_dir),
                    "--handoff-context-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            output_created = output_dir.exists()

        self.assertEqual(completed.returncode, 0)
        context = json.loads(completed.stdout)
        self.assertEqual(context["status"], "warn")
        self.assertEqual(context["percent"], 96)
        self.assertEqual(context["next_item_id"], "git_origin_remote")
        self.assertEqual(context["release_status"], "evidence/20260526-KRW-BTC-beta-001/release-status.json")
        self.assertIn("show_handoff_context_json", context["bundle_commands"])
        self.assertEqual(completed.stderr, "")
        self.assertFalse(output_created)

    def test_handoff_command_sequence_only_computes_from_package_without_creating_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-sequence-compute-") as tmp:
            root = Path(tmp)
            package_dir = root / "artifacts" / "evidence-packages" / "20260526-KRW-BTC-beta-001"
            output_dir = root / "artifacts" / "handoff-bundles"
            package_dir.mkdir(parents=True)
            (package_dir / "manifest.json").write_text(
                json.dumps({"generated_at": "2026-05-26T00:00:00+00:00"}) + "\n",
                encoding="utf-8",
            )
            (package_dir / "release-status.json").write_text(
                json.dumps({"status": "warn", "readiness_estimate": {}, "progress_summary": {}}) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_CONNECTED_RUNNER_HANDOFF),
                    "--project-root",
                    str(root),
                    "--package-dir",
                    str(package_dir),
                    "--output-dir",
                    str(output_dir),
                    "--handoff-command-sequence-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            output_created = output_dir.exists()

        self.assertEqual(completed.returncode, 0)
        commands = completed.stdout.strip().splitlines()
        self.assertIn(
            'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" --summary-json-only',
            commands,
        )
        self.assertIn(
            'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" --handoff-command-sequence-only',
            commands,
        )
        self.assertEqual(completed.stderr, "")
        self.assertFalse(output_created)

    def test_generated_handoff_commands_quote_paths(self) -> None:
        bundle_dir = Path("/tmp/quant handoff bundle")
        package_dir = Path("/tmp/quant evidence package")

        self.assertEqual(
            self.module.connected_runner_preflight_command(bundle_dir),
            "cd '/tmp/quant handoff bundle' && "
            "PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh",
        )
        self.assertEqual(
            self.module.connected_runner_verify_command(bundle_dir),
            "python3 scripts/package_connected_runner_handoff.py --verify '/tmp/quant handoff bundle'",
        )
        self.assertEqual(
            self.module.connected_runner_verify_json_command(bundle_dir),
            "python3 scripts/package_connected_runner_handoff.py --verify '/tmp/quant handoff bundle' --json-only",
        )
        self.assertEqual(
            self.module.connected_runner_verify_summary_json_command(bundle_dir),
            "python3 scripts/package_connected_runner_handoff.py --verify "
            "'/tmp/quant handoff bundle' --summary-json-only",
        )
        self.assertEqual(
            self.module.connected_runner_acceptance_command(),
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth",
        )
        self.assertEqual(
            self.module.connected_runner_acceptance_json_command(),
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth --json-only",
        )
        self.assertEqual(
            self.module.connected_runner_acceptance_summary_json_command(),
            "python3 scripts/connected_runner_acceptance.py --handoff-root .. "
            "--require-external --check-gh-auth --summary-json-only",
        )
        self.assertEqual(
            self.module.read_only_evidence_check_command(package_dir),
            "python3 scripts/check_release_evidence.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            self.module.verify_evidence_checksums_json_command(package_dir),
            "python3 scripts/write_evidence_checksums.py --package-dir '/tmp/quant evidence package' --verify --json-only",
        )
        self.assertEqual(
            self.module.release_status_progress_command(package_dir),
            "python3 scripts/report_release_status.py --package-dir '/tmp/quant evidence package' --progress-only",
        )
        self.assertEqual(
            self.module.release_status_progress_json_command(package_dir),
            "python3 scripts/report_release_status.py --package-dir '/tmp/quant evidence package' --progress-json-only",
        )
        self.assertEqual(
            self.module.read_only_warning_review_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --no-write",
        )
        self.assertEqual(
            self.module.warning_review_json_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only",
        )
        self.assertEqual(
            self.module.warning_review_gate_json_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --json-only --fail-if-action-needed",
        )
        self.assertEqual(
            self.module.warning_review_artifacts_only_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --review-artifacts-only",
        )
        self.assertEqual(
            self.module.warning_review_next_command_only_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --next-command-only",
        )
        self.assertEqual(
            self.module.warning_review_next_command_gate_command(package_dir),
            (
                "python3 scripts/review_release_warnings.py --package-dir "
                "'/tmp/quant evidence package' --next-command-only --fail-if-action-needed"
            ),
        )
        self.assertEqual(
            self.module.warning_review_apply_command(package_dir),
            "python3 scripts/review_release_warnings.py --package-dir '/tmp/quant evidence package' --apply --operator-approved",
        )
        self.assertEqual(
            self.module.next_release_local_readiness_command_only_env_command(package_dir),
            (
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only '
                "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass"
            ),
        )
        self.assertEqual(
            self.module.next_release_local_readiness_setup_sequence_env_command(package_dir),
            (
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                "--local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass"
            ),
        )
        self.assertEqual(
            self.module.next_release_local_readiness_command_sequence_env_command(package_dir),
            (
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL '
                "--local-readiness-command-sequence-only --fail-if-local-readiness-not-pass"
            ),
        )
        self.assertEqual(
            self.module.next_release_local_readiness_setup_sequence_preview_command(package_dir),
            (
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --local-readiness-setup-sequence-only'
            ),
        )
        self.assertEqual(
            self.module.next_release_local_readiness_command_sequence_preview_command(package_dir),
            (
                "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
                '--owner "connected runner" --local-readiness-command-sequence-only'
            ),
        )
        self.assertEqual(
            self.module.LIVE_BETA_PREFLIGHT_COMMAND,
            "python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight",
        )
        self.assertEqual(
            self.module.LIVE_BETA_PREFLIGHT_JSON_COMMAND,
            self.module.LIVE_BETA_PREFLIGHT_COMMAND + " --json",
        )
        self.assertEqual(
            self.module.LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND,
            self.module.LIVE_BETA_PREFLIGHT_COMMAND + " --next-command-only",
        )
        self.assertEqual(
            self.module.LIVE_BETA_CLOSEOUT_COMMAND,
            "python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3",
        )
        self.assertEqual(
            self.module.CONNECTED_STRICT_GATE_COMMAND,
            "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth",
        )
        self.assertEqual(
            self.module.LIVE_BETA_FINAL_GATE_COMMAND,
            "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth --require-live-beta",
        )
        self.assertEqual(
            self.module.LOCAL_BACKEND_START_COMMAND,
            "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload",
        )
        self.assertEqual(
            self.module.LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
            "cd backend && . .venv/bin/activate && uvicorn app.main:app",
        )
        self.assertEqual(self.module.DOCKER_BACKEND_START_COMMAND, "docker compose start backend")
        self.assertEqual(
            self.module.backend_health_check_command(),
            "curl -fsS http://localhost:8000/api/health",
        )
        self.assertEqual(
            self.module.next_release_step_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package'",
        )
        self.assertEqual(
            self.module.next_release_operator_sequence_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --show-sequence --no-write",
        )
        self.assertEqual(
            self.module.next_release_step_origin_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-origin --no-write",
        )
        self.assertEqual(
            self.module.next_release_step_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --no-write",
        )
        self.assertEqual(
            self.module.next_release_command_only_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.module.next_release_connected_json_only_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required",
        )
        self.assertEqual(
            self.module.next_release_json_only_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.module.next_release_operator_command_only_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --command-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.module.next_release_operator_json_only_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            "--owner operator --json-only --fail-if-repo-url-required",
        )
        self.assertEqual(
            self.module.next_release_connected_sequence_origin_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-origin --show-sequence --no-write',
        )
        self.assertEqual(
            self.module.next_release_connected_sequence_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --show-sequence --no-write',
        )
        self.assertEqual(
            self.module.next_release_local_readiness_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --summary-by-owner --show-sequence '
            "--local-readiness --no-write",
        )
        self.assertEqual(
            self.module.next_release_local_readiness_json_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required --local-readiness",
        )
        self.assertEqual(
            self.module.next_release_local_readiness_gate_json_env_command(package_dir),
            "python3 scripts/next_release_step.py --package-dir '/tmp/quant evidence package' "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass",
        )

    def test_handoff_readme_includes_local_readiness_helper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-readme-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            package_dir = Path(tmp) / "package"
            bundle_dir.mkdir()
            package_dir.mkdir()

            self.module.write_handoff_readme(bundle_dir, package_dir)
            readme = (bundle_dir / "HANDOFF.md").read_text(encoding="utf-8")

        self.assertEqual(self.module.missing_handoff_readme_markers(readme), [])
        self.assertIn("--handoff-context-json-only", readme)
        self.assertIn("--handoff-command-sequence-only", readme)
        self.assertIn("--local-readiness --no-write", readme)
        self.assertIn("--local-readiness-setup-sequence-only", readme)
        self.assertIn("--local-readiness-command-sequence-only", readme)
        self.assertIn("--fail-if-local-readiness-not-pass", readme)
        self.assertIn("Docker Compose, and GitHub CLI auth checks", readme)
        self.assertIn("## Current Completion Context", readme)
        self.assertIn("Release status JSON is not available", readme)

    def test_progress_summary_checks_require_resume_commands(self) -> None:
        expected_preflight = "cd /tmp/handoff && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPO ./run-connected-runner-handoff.sh"
        expected_next_command_only = "python3 scripts/next_release_step.py --command-only"
        expected_next_json_only = "python3 scripts/next_release_step.py --json-only"
        expected_connected_command_only = "python3 scripts/next_release_step.py --owner connected --command-only"
        expected_connected_sequence = "python3 scripts/next_release_step.py --owner connected --command-sequence-only"
        expected_operator_command_only = "python3 scripts/next_release_step.py --owner operator --command-only"
        expected_operator_sequence = "python3 scripts/next_release_step.py --owner operator --command-sequence-only"
        expected_operator_review_sequence = (
            "python3 scripts/next_release_step.py --owner operator --command-sequence-only --skip-operator-approved"
        )
        expected_operator_json_only = "python3 scripts/next_release_step.py --owner operator --json-only"
        expected_remaining_sequence = "python3 scripts/next_release_step.py --command-sequence-only"
        expected_progress_json = "python3 scripts/report_release_status.py --progress-json-only"
        expected_completion_plan = "python3 scripts/report_release_status.py --completion-plan-only"
        expected_completion_plan_json = "python3 scripts/report_release_status.py --completion-plan-json-only"
        expected_completion_requirements = "python3 scripts/report_release_status.py --completion-requirements-only"
        expected_completion_requirements_json = (
            "python3 scripts/report_release_status.py --completion-requirements-json-only"
        )
        expected_owner_lanes = "python3 scripts/report_release_status.py --owner-lanes-only"
        expected_owner_lanes_json = "python3 scripts/report_release_status.py --owner-lanes-json-only"
        expected_handoff_context_json = "python3 scripts/package_connected_runner_handoff.py --handoff-context-json-only"
        expected_handoff_command_sequence = (
            "python3 scripts/package_connected_runner_handoff.py --handoff-command-sequence-only"
        )
        expected_local_readiness_setup = "python3 scripts/next_release_step.py --local-readiness-setup-sequence-only"
        expected_local_readiness_sequence = "python3 scripts/next_release_step.py --local-readiness-command-sequence-only"
        expected_local_readiness_setup_preview = (
            "python3 scripts/next_release_step.py --local-readiness-setup-sequence-only --preview"
        )
        expected_local_readiness_sequence_preview = (
            "python3 scripts/next_release_step.py --local-readiness-command-sequence-only --preview"
        )
        expected_external_readiness_summary = "python3 scripts/check_external_readiness.py --summary-json-only"
        expected_external_readiness_strict_summary = (
            "python3 scripts/check_external_readiness.py "
            "--require-git-remote --require-docker --require-gh --check-gh-auth --summary-json-only"
        )
        expected_warning_gate_json = "python3 scripts/review_release_warnings.py --json-only --fail-if-action-needed"
        expected_warning_summary_json = "python3 scripts/review_release_warnings.py --summary-json-only"
        expected_warning_gate_summary_json = (
            "python3 scripts/review_release_warnings.py --summary-json-only --fail-if-action-needed"
        )
        expected_warning_review_artifacts_only = "python3 scripts/review_release_warnings.py --review-artifacts-only"
        expected_warning_review_next_command_gate = (
            "python3 scripts/review_release_warnings.py --next-command-only --fail-if-action-needed"
        )
        expected_warning_action_plan = "/tmp/package/release-warning-actions.md"
        expected_warning_checklist = "/tmp/package/release-warning-operator-checklist.md"
        expected_operator_command = "python3 scripts/review_release_warnings.py --no-write"
        payload = {
            "progress_summary": {
                "next_command": expected_preflight,
                "next_item_id": "git_origin_remote",
                "next_item_owner": "connected runner",
                "owner_lanes": {},
                "next_commands_by_owner": {
                    "connected runner": {
                        "id": "git_origin_remote",
                        "command": expected_preflight,
                        "supporting_commands": {
                            "Show connected-runner command only from env": expected_connected_command_only,
                            "Show external readiness summary JSON": expected_external_readiness_summary,
                            "Gate external readiness summary JSON": expected_external_readiness_strict_summary,
                            "Show local readiness setup sequence": expected_local_readiness_setup,
                            "Show local readiness command sequence": expected_local_readiness_sequence,
                            "Preview local readiness setup sequence": expected_local_readiness_setup_preview,
                            "Preview local readiness command sequence": expected_local_readiness_sequence_preview,
                        },
                    },
                    "operator": {
                        "id": "warning_alerts",
                        "command": expected_operator_command,
                        "supporting_commands": {
                            "Show warning summary JSON": expected_warning_summary_json,
                            "Gate warning summary JSON": expected_warning_gate_summary_json,
                            "Show warning review artifact paths": expected_warning_review_artifacts_only,
                            "Gate warning recommended next command": expected_warning_review_next_command_gate,
                        },
                        "review_artifacts": {
                            "action_plan": expected_warning_action_plan,
                            "operator_checklist": expected_warning_checklist,
                        },
                    },
                },
                "commands": {
                    "next_command_only": expected_next_command_only,
                    "next_json_only": expected_next_json_only,
                    "connected_runner_command_only": expected_connected_command_only,
                    "connected_runner_command_sequence": expected_connected_sequence,
                    "operator_command_only": expected_operator_command_only,
                    "operator_command_sequence": expected_operator_sequence,
                    "operator_review_sequence": expected_operator_review_sequence,
                    "operator_json_only": expected_operator_json_only,
                    "remaining_sequence": expected_remaining_sequence,
                    "show_progress_json": expected_progress_json,
                    "show_completion_plan": expected_completion_plan,
                    "show_completion_plan_json": expected_completion_plan_json,
                    "show_completion_requirements": expected_completion_requirements,
                    "show_completion_requirements_json": expected_completion_requirements_json,
                    "show_owner_lanes": expected_owner_lanes,
                    "show_owner_lanes_json": expected_owner_lanes_json,
                    "handoff_context_json": expected_handoff_context_json,
                    "handoff_command_sequence": expected_handoff_command_sequence,
                    "local_readiness_setup_sequence": expected_local_readiness_setup,
                    "local_readiness_command_sequence": expected_local_readiness_sequence,
                    "local_readiness_setup_sequence_preview": expected_local_readiness_setup_preview,
                    "local_readiness_command_sequence_preview": expected_local_readiness_sequence_preview,
                    "external_readiness_summary_json": expected_external_readiness_summary,
                    "external_readiness_strict_summary_json": expected_external_readiness_strict_summary,
                    "warning_gate_json": expected_warning_gate_json,
                    "warning_summary_json": expected_warning_summary_json,
                    "warning_gate_summary_json": expected_warning_gate_summary_json,
                    "warning_next_command_gate": expected_warning_review_next_command_gate,
                    "warning_review_artifacts": expected_warning_review_artifacts_only,
                },
                "warning_review": {
                    "summary_json": expected_warning_summary_json,
                    "review_artifacts_command": expected_warning_review_artifacts_only,
                    "review_sequence_command": expected_operator_review_sequence,
                    "pre_approval_review_sequence": [
                        expected_warning_summary_json,
                        expected_warning_review_artifacts_only,
                    ],
                },
            }
        }

        checks: list[dict[str, object]] = []
        self.module.add_progress_summary_checks(
            checks,
            payload=payload,
            expected_preflight=expected_preflight,
            expected_next_command_only=expected_next_command_only,
            expected_next_json_only=expected_next_json_only,
            expected_connected_command_only=expected_connected_command_only,
            expected_connected_command_sequence=expected_connected_sequence,
            expected_operator_command_only=expected_operator_command_only,
            expected_operator_command_sequence=expected_operator_sequence,
            expected_operator_review_sequence=expected_operator_review_sequence,
            expected_operator_json_only=expected_operator_json_only,
            expected_remaining_sequence=expected_remaining_sequence,
            expected_progress_json=expected_progress_json,
            expected_completion_plan=expected_completion_plan,
            expected_completion_plan_json=expected_completion_plan_json,
            expected_completion_requirements=expected_completion_requirements,
            expected_completion_requirements_json=expected_completion_requirements_json,
            expected_owner_lanes=expected_owner_lanes,
            expected_owner_lanes_json=expected_owner_lanes_json,
            expected_handoff_context_json=expected_handoff_context_json,
            expected_handoff_command_sequence=expected_handoff_command_sequence,
            expected_local_readiness_setup_sequence=expected_local_readiness_setup,
            expected_local_readiness_command_sequence=expected_local_readiness_sequence,
            expected_local_readiness_setup_sequence_preview=expected_local_readiness_setup_preview,
            expected_local_readiness_command_sequence_preview=expected_local_readiness_sequence_preview,
            expected_external_readiness_summary_json=expected_external_readiness_summary,
            expected_external_readiness_strict_summary_json=expected_external_readiness_strict_summary,
            expected_warning_gate_json=expected_warning_gate_json,
            expected_warning_summary_json=expected_warning_summary_json,
            expected_warning_gate_summary_json=expected_warning_gate_summary_json,
            expected_warning_review_artifacts_only=expected_warning_review_artifacts_only,
            expected_warning_review_next_command_gate=expected_warning_review_next_command_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        checks_by_id = {check["id"]: check for check in checks}

        self.assertEqual(checks_by_id["release_status_json_progress_summary_next_command"]["status"], "pass")
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_next"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_external_readiness_summary_json"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_external_readiness_strict_summary_json"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_local_readiness_setup_sequence"][
                "status"
            ],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_connected_runner_local_readiness_command_sequence"][
                "status"
            ],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_local_readiness_setup_sequence_preview"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_connected_runner_local_readiness_command_sequence_preview"
            ]["status"],
            "pass",
        )
        self.assertEqual(checks_by_id["release_status_json_progress_summary_operator_next"]["status"], "pass")
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_review_artifacts"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_next_command_gate"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_action_plan_path"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_checklist_path"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_connected_runner_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_next_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_next_json_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_plan"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_plan_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_requirements"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_completion_requirements_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_owner_lanes"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_show_owner_lanes_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_owner_lanes_object"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_connected_runner_command_sequence"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_operator_command_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_operator_json_only"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_external_readiness_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id[
                "release_status_json_progress_summary_command_external_readiness_strict_summary_json"
            ]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_warning_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_command_warning_gate_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_summary_json"]["status"],
            "pass",
        )
        self.assertEqual(
            checks_by_id["release_status_json_progress_summary_operator_summary_json_gate"]["status"],
            "pass",
        )

        payload["progress_summary"]["commands"]["warning_gate_json"] = "stale command"
        failing_checks: list[dict[str, object]] = []
        self.module.add_progress_summary_checks(
            failing_checks,
            payload=payload,
            expected_preflight=expected_preflight,
            expected_next_command_only=expected_next_command_only,
            expected_next_json_only=expected_next_json_only,
            expected_connected_command_only=expected_connected_command_only,
            expected_connected_command_sequence=expected_connected_sequence,
            expected_operator_command_only=expected_operator_command_only,
            expected_operator_command_sequence=expected_operator_sequence,
            expected_operator_review_sequence=expected_operator_review_sequence,
            expected_operator_json_only=expected_operator_json_only,
            expected_remaining_sequence=expected_remaining_sequence,
            expected_progress_json=expected_progress_json,
            expected_completion_plan=expected_completion_plan,
            expected_completion_plan_json=expected_completion_plan_json,
            expected_completion_requirements=expected_completion_requirements,
            expected_completion_requirements_json=expected_completion_requirements_json,
            expected_owner_lanes=expected_owner_lanes,
            expected_owner_lanes_json=expected_owner_lanes_json,
            expected_handoff_context_json=expected_handoff_context_json,
            expected_handoff_command_sequence=expected_handoff_command_sequence,
            expected_local_readiness_setup_sequence=expected_local_readiness_setup,
            expected_local_readiness_command_sequence=expected_local_readiness_sequence,
            expected_local_readiness_setup_sequence_preview=expected_local_readiness_setup_preview,
            expected_local_readiness_command_sequence_preview=expected_local_readiness_sequence_preview,
            expected_external_readiness_summary_json=expected_external_readiness_summary,
            expected_external_readiness_strict_summary_json=expected_external_readiness_strict_summary,
            expected_warning_gate_json=expected_warning_gate_json,
            expected_warning_summary_json=expected_warning_summary_json,
            expected_warning_gate_summary_json=expected_warning_gate_summary_json,
            expected_warning_review_artifacts_only=expected_warning_review_artifacts_only,
            expected_warning_review_next_command_gate=expected_warning_review_next_command_gate,
            expected_warning_action_plan_path=expected_warning_action_plan,
            expected_warning_operator_checklist_path=expected_warning_checklist,
            expected_operator_command=expected_operator_command,
        )
        failing_by_id = {check["id"]: check for check in failing_checks}
        self.assertEqual(
            failing_by_id["release_status_json_progress_summary_command_warning_gate_json"]["status"],
            "fail",
        )

    def test_handoff_readme_summarizes_completion_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-readme-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            package_dir = Path(tmp) / "package"
            bundle_dir.mkdir()
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(
                    {
                        "status": "warn",
                        "readiness_estimate": {
                            "percent": 94,
                            "remaining_items": 6,
                            "deductions": [
                                {
                                    "id": "external_readiness_warnings",
                                    "points": 3,
                                    "detail": "3 external readiness warning check(s) remain.",
                                    "check_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                                },
                                {
                                    "id": "live_beta_archive",
                                    "points": 2,
                                    "detail": "Live-beta closeout archive is not present yet.",
                                    "check_ids": ["live_beta_archive"],
                                },
                            ],
                        },
                        "progress_summary": {
                            "completion_requirements": [
                                {
                                    "requirement": "connected_runner",
                                    "item_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                                    "owners": ["connected runner"],
                                    "count": 3,
                                },
                                {
                                    "requirement": "operator_approval",
                                    "item_ids": ["warning_actions"],
                                    "owners": ["operator"],
                                    "count": 1,
                                },
                            ]
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            self.module.write_handoff_readme(bundle_dir, package_dir)
            readme = (bundle_dir / "HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("## Current Completion Context", readme)
        self.assertIn("- Overall status: `warn`", readme)
        self.assertIn("- Approximate completion: `94%`", readme)
        self.assertIn("- Remaining handoff items: `6`", readme)
        self.assertIn("`external_readiness_warnings`: -3 point(s).", readme)
        self.assertIn("Source checks: git_origin_remote, docker_cli, github_cli.", readme)
        self.assertIn("`live_beta_archive`: -2 point(s).", readme)
        self.assertIn("Source checks: live_beta_archive.", readme)
        self.assertIn("- Completion requirements:", readme)
        self.assertIn("`connected_runner`: 3 items [connected runner] items: git_origin_remote, docker_cli, github_cli", readme)
        self.assertIn("`operator_approval`: 1 item [operator] items: warning_actions", readme)
        self.assertIn("Full status: `evidence/package/release-status.md`", readme)
        self.assertIn("export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git", readme)
        self.assertIn("PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh", readme)
        self.assertIn("Inline commands with `GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL` are still supported", readme)

    def test_manifest_handoff_context_exposes_quickstart_and_requirements(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-handoff-context-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            requirements = [
                {
                    "requirement": "connected_runner",
                    "item_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                    "owners": ["connected runner"],
                    "count": 3,
                }
            ]
            release_status = {
                "status": "warn",
                "readiness_estimate": {"percent": 96, "remaining_items": 5},
                "progress_summary": {
                    "remaining_ids": [
                        "git_origin_remote",
                        "docker_cli",
                        "github_cli",
                        "warning_alerts",
                        "warning_actions",
                    ],
                    "remaining_by_owner": {"connected runner": 3, "operator": 2},
                    "next_item_id": "git_origin_remote",
                    "next_item_owner": "connected runner",
                    "next_commands_by_owner": {
                        "connected runner": {
                            "id": "git_origin_remote",
                            "status": "warn",
                            "automation_command": "python3 scripts/next_release_step.py --json-only",
                            "full_flow_command": "./run-connected-runner-handoff.sh",
                            "supporting_commands": {
                                "Show local readiness setup sequence": "python3 scripts/next_release_step.py --local-readiness-setup-sequence-only"
                            },
                        },
                        "operator": {
                            "id": "warning_alerts",
                            "status": "warn",
                            "review_artifacts": {"operator_checklist": "/tmp/checklist.md"},
                        },
                    },
                    "completion_requirements": requirements,
                    "completion_plan": [
                        {
                            "id": "git_origin_remote",
                            "owner": "connected runner",
                            "mode": "connected_runner_preflight",
                            "requirements": ["connected_runner"],
                        },
                        {
                            "id": "warning_alerts",
                            "owner": "operator",
                            "mode": "operator_review",
                            "requirements": ["operator_review"],
                            "requires_operator_approval": False,
                            "review_artifacts": {"operator_checklist": "/tmp/checklist.md"},
                        },
                        {
                            "id": "warning_actions",
                            "owner": "operator",
                            "mode": "operator_approval",
                            "requirements": ["operator_approval"],
                            "requires_operator_approval": True,
                            "review_artifacts": {"operator_checklist": "/tmp/checklist.md"},
                        }
                    ],
                    "repo_url": {"required": True},
                    "local_readiness": {"status": "warn", "issue_ids": ["git_origin_remote"]},
                    "warning_review": {"status": "planned", "requires_operator_approval": True},
                },
            }
            (package_dir / "release-status.json").write_text(
                json.dumps(release_status) + "\n",
                encoding="utf-8",
            )

            context = self.module.handoff_manifest_context(package_dir)

        self.assertEqual(context["status"], "warn")
        self.assertEqual(context["percent"], 96)
        self.assertEqual(context["remaining_items"], 5)
        self.assertEqual(context["remaining_by_owner"], {"connected runner": 3, "operator": 2})
        self.assertEqual(context["next_item_id"], "git_origin_remote")
        self.assertEqual(context["next_item_owner"], "connected runner")
        self.assertEqual(context["owner_lanes"]["connected runner"]["remaining_ids"], ["git_origin_remote"])
        self.assertEqual(context["owner_lanes"]["connected runner"]["mode"], "connected_runner_preflight")
        self.assertTrue(context["owner_lanes"]["connected runner"]["has_automation_command"])
        self.assertTrue(context["owner_lanes"]["connected runner"]["has_full_flow_command"])
        self.assertEqual(
            context["owner_lanes"]["connected runner"]["supporting_command_labels"],
            ["Show local readiness setup sequence"],
        )
        self.assertEqual(
            context["owner_lanes"]["connected runner"]["readiness"],
            {"status": "warn", "issue_ids": ["git_origin_remote"]},
        )
        self.assertEqual(context["owner_lanes"]["operator"]["remaining_ids"], ["warning_alerts", "warning_actions"])
        self.assertFalse(context["owner_lanes"]["operator"]["next_requires_operator_approval"])
        self.assertTrue(context["owner_lanes"]["operator"]["requires_operator_approval"])
        self.assertEqual(
            context["owner_lanes"]["operator"]["review_artifacts"],
            {"operator_checklist": "/tmp/checklist.md"},
        )
        self.assertEqual(
            context["owner_lanes"]["operator"]["review"],
            {"status": "planned", "requires_operator_approval": True},
        )
        self.assertEqual(context["completion_requirements"], requirements)
        self.assertEqual(context["completion_plan"], release_status["progress_summary"]["completion_plan"])
        self.assertEqual(context["repo_url"], {"required": True})
        self.assertEqual(context["local_readiness"], {"status": "warn", "issue_ids": ["git_origin_remote"]})
        self.assertEqual(context["warning_review"], {"status": "planned", "requires_operator_approval": True})
        self.assertEqual(
            context["quickstart"]["export_repo_url"],
            "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
        )
        self.assertEqual(
            context["quickstart"]["preflight_command"],
            "PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh",
        )
        self.assertEqual(context["quickstart"]["full_flow_command"], "./run-connected-runner-handoff.sh")
        self.assertEqual(
            context["bundle_commands"]["verify_bundle_summary_json"],
            'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" --summary-json-only',
        )
        self.assertEqual(
            context["bundle_commands"]["show_handoff_context_json"],
            (
                'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" '
                "--handoff-context-json-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_handoff_command_sequence"],
            (
                'python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" '
                "--handoff-command-sequence-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["audit_completion_context_json"],
            (
                "python3 source/scripts/check_completion_audit.py --audit-path source/docs/completion-audit.md "
                '--handoff-bundle "$(pwd)" --json'
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["acceptance_summary_json"],
            (
                "cd source && python3 scripts/connected_runner_acceptance.py --handoff-root .. "
                "--require-external --check-gh-auth --summary-json-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_progress_json"],
            'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/evidence/package" --progress-json-only',
        )
        self.assertEqual(
            context["bundle_commands"]["show_completion_plan_json"],
            (
                'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/evidence/package" '
                "--completion-plan-json-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_completion_requirements_json"],
            (
                'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/evidence/package" '
                "--completion-requirements-json-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_owner_lanes_json"],
            (
                'python3 source/scripts/report_release_status.py --package-dir "$(pwd)/evidence/package" '
                "--owner-lanes-json-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_operator_review_sequence"],
            (
                'python3 source/scripts/next_release_step.py --package-dir "$(pwd)/evidence/package" '
                "--owner operator --command-sequence-only --skip-operator-approved "
                "--fail-if-repo-url-required"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_warning_summary_json"],
            (
                'python3 source/scripts/review_release_warnings.py --package-dir "$(pwd)/evidence/package" '
                "--summary-json-only"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["gate_warning_summary_json"],
            (
                'python3 source/scripts/review_release_warnings.py --package-dir "$(pwd)/evidence/package" '
                "--summary-json-only --fail-if-action-needed"
            ),
        )
        self.assertEqual(
            context["bundle_commands"]["show_warning_artifacts"],
            (
                'python3 source/scripts/review_release_warnings.py --package-dir "$(pwd)/evidence/package" '
                "--review-artifacts-only"
            ),
        )
        self.assertEqual(
            [step["id"] for step in context["bundle_command_sequence"]],
            [
                "verify_bundle",
                "show_handoff_context",
                "show_handoff_command_sequence",
                "audit_completion_context",
                "show_progress",
                "show_completion_plan",
                "show_completion_requirements",
                "show_owner_lanes",
                "export_repo_url",
                "preflight",
                "acceptance_summary",
                "full_flow",
                "show_operator_review_sequence",
                "show_warning_summary",
                "show_warning_artifacts",
                "gate_warning_summary",
            ],
        )
        self.assertEqual(
            context["bundle_command_sequence"][0]["command"],
            context["bundle_commands"]["verify_bundle_summary_json"],
        )
        self.assertEqual(
            context["bundle_command_sequence"][8]["command"],
            "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
        )
        self.assertEqual(context["bundle_command_sequence"][-1]["owner"], "operator")
        self.assertTrue(context["bundle_command_sequence"][-1]["gate"])
        self.assertEqual(context["bundle_gate_summary"]["step_count"], 16)
        self.assertEqual(context["bundle_gate_summary"]["non_gate_count"], 10)
        self.assertEqual(context["bundle_gate_summary"]["gate_count"], 6)
        self.assertEqual(
            context["bundle_gate_summary"]["gate_ids"],
            [
                "verify_bundle",
                "audit_completion_context",
                "preflight",
                "acceptance_summary",
                "full_flow",
                "gate_warning_summary",
            ],
        )
        self.assertEqual(context["bundle_gate_summary"]["gates_by_owner"], {"connected runner": 5, "operator": 1})
        self.assertEqual(
            context["bundle_gate_summary"]["first_gate_by_owner"],
            {
                "connected runner": {
                    "id": "verify_bundle",
                    "command_key": "verify_bundle_summary_json",
                },
                "operator": {
                    "id": "gate_warning_summary",
                    "command_key": "gate_warning_summary_json",
                },
            },
        )
        self.assertEqual(
            context["bundle_gate_summary"]["connected_runner_gate_ids"],
            ["verify_bundle", "audit_completion_context", "preflight", "acceptance_summary", "full_flow"],
        )
        self.assertEqual(context["bundle_gate_summary"]["operator_gate_ids"], ["gate_warning_summary"])
        self.assertEqual(
            context["bundle_gate_summary"]["first_gate"],
            {
                "id": "verify_bundle",
                "owner": "connected runner",
                "command_key": "verify_bundle_summary_json",
            },
        )
        self.assertTrue(context["bundle_gate_summary"]["requires_repo_url_export_before_preflight"])
        self.assertEqual(context["release_status"], "evidence/package/release-status.json")
        self.assertEqual(context["next_step"], "evidence/package/next-release-step.json")
        self.assertEqual(self.module.manifest_handoff_context_errors({"handoff_context": context}, release_status), [])
        bad_quickstart_context = {
            **context,
            "quickstart": {**context["quickstart"], "preflight_command": "bad"},
        }
        self.assertIn(
            "handoff_context.quickstart.preflight_command",
            self.module.manifest_handoff_context_errors({"handoff_context": bad_quickstart_context}, release_status),
        )
        stale_next_context = {**context, "next_item_id": "docker_cli"}
        self.assertIn(
            "handoff_context.next_item_id",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_next_context}, release_status),
        )
        stale_owner_lanes_context = {
            **context,
            "owner_lanes": {
                **context["owner_lanes"],
                "connected runner": {**context["owner_lanes"]["connected runner"], "next_item_id": "docker_cli"},
            },
        }
        self.assertIn(
            "handoff_context.owner_lanes",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_owner_lanes_context}, release_status),
        )
        stale_remaining_context = {**context, "remaining_ids": ["docker_cli"]}
        self.assertIn(
            "handoff_context.remaining_ids",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_remaining_context}, release_status),
        )
        stale_percent_context = {**context, "percent": 95}
        self.assertIn(
            "handoff_context.percent",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_percent_context}, release_status),
        )
        bad_bundle_command_context = {
            **context,
            "bundle_commands": {**context["bundle_commands"], "show_progress_json": "bad"},
        }
        self.assertIn(
            "handoff_context.bundle_commands.show_progress_json",
            self.module.manifest_handoff_context_errors({"handoff_context": bad_bundle_command_context}, release_status),
        )
        stale_sequence_context = {
            **context,
            "bundle_command_sequence": context["bundle_command_sequence"][:-1],
        }
        self.assertIn(
            "handoff_context.bundle_command_sequence",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_sequence_context}, release_status),
        )
        stale_gate_summary_context = {
            **context,
            "bundle_gate_summary": {**context["bundle_gate_summary"], "gate_count": 4},
        }
        self.assertIn(
            "handoff_context.bundle_gate_summary",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_gate_summary_context}, release_status),
        )
        stale_context = {**context, "completion_requirements": []}
        self.assertIn(
            "handoff_context.completion_requirements",
            self.module.manifest_handoff_context_errors({"handoff_context": stale_context}, release_status),
        )

    def test_handoff_completion_context_verifier_detects_stale_readme(self) -> None:
        release_status = {
            "status": "warn",
            "readiness_estimate": {
                "percent": 94,
                "remaining_items": 6,
                "deductions": [
                    {
                        "id": "external_readiness_warnings",
                        "points": 3,
                        "detail": "3 external readiness warning check(s) remain.",
                        "check_ids": ["git_origin_remote", "docker_cli", "github_cli"],
                    }
                ],
            },
        }
        readme = "\n".join(
            [
                "- Overall status: `warn`",
                "- Approximate completion: `94%`",
                "- Remaining handoff items: `6`",
                "`external_readiness_warnings`: -3 point(s). 3 external readiness warning check(s) remain. Source checks: git_origin_remote, docker_cli, github_cli.",
            ]
        )

        ok, message, details = self.module.verify_handoff_completion_context(readme, release_status)
        self.assertTrue(ok, message)
        self.assertEqual(details["missing_markers"], [])

        stale_ok, stale_message, stale_details = self.module.verify_handoff_completion_context(
            readme.replace("`94%`", "`95%`"),
            release_status,
        )
        self.assertFalse(stale_ok)
        self.assertIn("Approximate completion", stale_message)
        self.assertIn("- Approximate completion: `94%`", stale_details["missing_markers"])

    def test_gitignore_guard_patterns_are_required(self) -> None:
        complete_text = "\n".join(self.module.REQUIRED_GITIGNORE_PATTERNS)
        self.assertEqual(self.module.missing_gitignore_patterns_from_text(complete_text), [])

        missing = self.module.missing_gitignore_patterns_from_text(
            complete_text.replace("artifacts/\n", "")
        )
        self.assertEqual(missing, ["artifacts/"])


if __name__ == "__main__":
    unittest.main()
