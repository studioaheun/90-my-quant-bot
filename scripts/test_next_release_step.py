#!/usr/bin/env python3
"""Smoke tests for the next release step CLI."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEXT_RELEASE_STEP = PROJECT_ROOT / "scripts" / "next_release_step.py"


def load_next_release_step():
    spec = importlib.util.spec_from_file_location("next_release_step", NEXT_RELEASE_STEP)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {NEXT_RELEASE_STEP}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def env_without_homebrew_tools() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = "/nonexistent"
    return env


def synthetic_status(package_dir: Path, bundle_dir: Path) -> dict[str, object]:
    preflight = f"cd {bundle_dir} && PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
    full_flow = f"cd {bundle_dir} && GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh"
    return {
        "status": "warn",
        "connected_runner_handoff_bundle": str(bundle_dir),
        "readiness_estimate": {
            "percent": 94,
            "remaining_items": 3,
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
                {
                    "id": "warning_alerts",
                    "points": 1,
                    "detail": "Warning-level alerts still need operator review.",
                    "check_ids": ["warning_alerts"],
                },
            ],
        },
        "remaining_items": [
            {
                "id": "git_origin_remote",
                "status": "warn",
                "owner": "connected runner",
                "action": "Add the repository remote on the connected runner.",
                "command": "git remote add origin REPLACE_WITH_REPO_URL",
                "preferred_action": "Run the connected-runner bundle preflight first.",
                "preferred_command": preflight,
                "full_flow_command": full_flow,
                "automation_command": (
                    f"python3 scripts/next_release_step.py --package-dir {package_dir} "
                    '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
                    "--fail-if-repo-url-required"
                ),
                "verify_command": "git remote get-url origin",
                "final_verify_command": "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth",
            },
            {
                "id": "warning_alerts",
                "status": "warn",
                "owner": "operator",
                "action": "Review warning alerts.",
                "command": f"python3 scripts/review_release_warnings.py --package-dir {package_dir}",
                "automation_command": f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --json-only",
                "supporting_commands": {
                    "Show warning review artifact paths": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--review-artifacts-only"
                    ),
                    "Show warning recommended next command": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--next-command-only"
                    ),
                },
            },
            {
                "id": "warning_actions",
                "status": "planned",
                "owner": "operator",
                "action": "Apply or acknowledge warning actions.",
                "command": f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --apply --operator-approved",
                "supporting_commands": {
                    "Show warning review artifact paths": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--review-artifacts-only"
                    ),
                    "Show warning recommended next command": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--next-command-only"
                    ),
                },
            },
        ],
    }


class NextReleaseStepSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_next_release_step()

    def test_local_readiness_setup_sequence_payload_lists_every_unresolved_setup(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        repo_url_setup = self.module.git_origin_setup_command()
        concrete_repo_url_setup = self.module.git_origin_setup_command(repo_url)
        checks = [
            {
                "id": "git_origin_remote",
                "status": "warn",
                "setup_command": repo_url_setup,
                "command": "git remote get-url origin",
                "remediation": "Add origin.",
            },
            {
                "id": "docker_cli",
                "status": "warn",
                "setup_command": "docker setup",
                "command": "docker compose version",
                "remediation": "Install Docker.",
            },
            {
                "id": "github_actions_workflow",
                "status": "pass",
                "setup_command": "should not be included",
                "command": "true",
            },
        ]

        sequence = self.module.local_readiness_setup_sequence_payload(checks, repo_url=repo_url)

        self.assertEqual([item["check_id"] for item in sequence], ["git_origin_remote", "docker_cli"])
        self.assertEqual(sequence[0]["command"], concrete_repo_url_setup)
        self.assertIn(f"git remote set-url origin {repo_url}", sequence[0]["command"])
        self.assertIn(f"git remote add origin {repo_url}", sequence[0]["command"])
        self.assertEqual(sequence[0]["verify_command"], "git remote get-url origin")
        self.assertEqual(sequence[1]["remediation"], "Install Docker.")

        command_sequence = self.module.local_readiness_command_sequence_payload(sequence)

        self.assertEqual(
            command_sequence,
            [
                concrete_repo_url_setup,
                "git remote get-url origin",
                "docker setup",
                "docker compose version",
            ],
        )

    def test_repo_url_substitution_and_owner_counts(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        bundle_dir = Path("/tmp/quant handoff")
        repo_url = "https://github.com/example/quant-lab.git"
        source_dir_arg = shlex.quote(str(bundle_dir / "source"))
        report = self.module.build_report(
            package_dir,
            synthetic_status(package_dir, bundle_dir),
            "connected runner",
            repo_url,
        )

        self.assertEqual(report["filtered_remaining_count"], 1)
        self.assertEqual(report["total_remaining_count"], 3)
        self.assertEqual(report["package_dir"], str(package_dir))
        self.assertEqual(report["handoff_bundle"], str(bundle_dir))
        self.assertEqual(report["completion_deductions"][0]["id"], "external_readiness_warnings")
        self.assertEqual(report["next_item"]["completion_impact_points"], 1)
        self.assertIn(
            "Clearing git_origin_remote is expected to recover 1 completion point",
            report["next_item"]["completion_impact"],
        )
        self.assertEqual(self.module.format_remaining_counts(report), "1 for connected runner (3 total)")
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", report["next_command"])
        self.assertIn("cd '/tmp/quant handoff'", report["next_command"])
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", report["bundle_script_command"])
        self.assertNotIn("full_flow_command", report)
        self.assertEqual(
            report["manual_setup_command"],
            f"cd {source_dir_arg} && git remote add origin {repo_url}",
        )
        self.assertEqual(
            report["next_item"]["automation_command"],
            "python3 scripts/next_release_step.py --package-dir /tmp/quant evidence "
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only '
            "--fail-if-repo-url-required",
        )
        self.assertEqual(
            report["verify_command"],
            f"cd {source_dir_arg} && git remote get-url origin",
        )
        self.assertEqual(
            report["final_verify_command"],
            f"cd {source_dir_arg} && python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth",
        )
        self.assertIn("rejects missing/placeholder/invalid remote URLs first", report["next_action"])
        self.assertNotIn("REPLACE_WITH_REPO_URL", report["next_command"])
        self.assertTrue(report["repo_url_substituted"])
        self.assertFalse(report["repo_url_required"])
        self.assertEqual(report["notes"], [])
        self.assertEqual(
            report["owner_summary"],
            [
                {"owner": "connected runner", "count": 1, "statuses": {"warn": 1}, "items": ["git_origin_remote"]},
                {
                    "owner": "operator",
                    "count": 2,
                    "statuses": {"planned": 1, "warn": 1},
                    "items": ["warning_alerts", "warning_actions"],
                },
            ],
        )

    def test_print_summary_labels_connected_runner_bundle_as_full_flow(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        bundle_dir = Path("/tmp/quant handoff")
        report = self.module.build_report(package_dir, synthetic_status(package_dir, bundle_dir), "connected runner")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.module.print_summary(report)

        self.assertIn("Full flow after preflight:", output.getvalue())
        self.assertNotIn("Bundle script:", output.getvalue())

    def test_local_readiness_summary_payload_marks_overall_status_and_issues(self) -> None:
        summary, status, issues = self.module.local_readiness_summary_payload(
            [
                {"id": "git_origin_remote", "status": "pass"},
                {"id": "docker_cli", "status": "warn"},
                {"id": "github_cli", "status": "fail"},
            ]
        )

        self.assertEqual(summary, {"fail": 1, "pass": 1, "warn": 1})
        self.assertEqual(status, "fail")
        self.assertEqual(issues, ["docker_cli", "github_cli"])

        summary, status, issues = self.module.local_readiness_summary_payload(
            [
                {"id": "git_origin_remote", "status": "pass"},
                {"id": "docker_cli", "status": "pass"},
            ]
        )

        self.assertEqual(summary, {"pass": 2})
        self.assertEqual(status, "pass")
        self.assertEqual(issues, [])

    def test_markdown_includes_owner_summary(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        bundle_dir = Path("/tmp/quant handoff")
        source_dir_arg = shlex.quote(str(bundle_dir / "source"))
        report = self.module.build_report(package_dir, synthetic_status(package_dir, bundle_dir), "all")

        with tempfile.TemporaryDirectory(prefix="quant-next-step-md-") as tmp:
            markdown_path = Path(tmp) / "next-release-step.md"
            self.module.write_markdown(markdown_path, report)
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertIn("## Remaining By Owner", markdown)
        self.assertIn("## Completion Detail", markdown)
        self.assertIn("- external_readiness_warnings: -3 point(s).", markdown)
        self.assertIn("Source checks: git_origin_remote, docker_cli, github_cli.", markdown)
        self.assertIn("Completion impact: Clearing git_origin_remote is expected to recover 1 completion point", markdown)
        self.assertIn(f"Handoff bundle: `{bundle_dir}`", markdown)
        self.assertIn("## Notes", markdown)
        self.assertIn("Replace REPLACE_WITH_REPO_URL with a real HTTPS, SSH, or scp-style git remote URL", markdown)
        self.assertIn(f"cd {source_dir_arg} && git remote add origin REPLACE_WITH_REPO_URL", markdown)
        self.assertIn("- Full flow after preflight:", markdown)
        self.assertNotIn("- Bundle script:", markdown)
        self.assertIn("Repo URL export example", markdown)
        self.assertIn("export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git", markdown)
        self.assertIn("Repo URL command gate", markdown)
        self.assertIn("--repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required", markdown)
        self.assertIn("Repo URL JSON gate", markdown)
        self.assertIn(
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required',
            markdown,
        )
        self.assertIn(f"cd {source_dir_arg} && git remote get-url origin", markdown)
        self.assertIn(
            f"cd {source_dir_arg} && python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth",
            markdown,
        )
        self.assertIn("- connected runner: 1 (warn: 1)", markdown)
        self.assertIn("  Items: git_origin_remote", markdown)
        self.assertIn("- operator: 2 (planned: 1, warn: 1)", markdown)
        self.assertIn("  Items: warning_alerts, warning_actions", markdown)

    def test_operator_approval_notice_prints_for_next_apply_step(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        bundle_dir = Path("/tmp/quant handoff")
        status = synthetic_status(package_dir, bundle_dir)
        remaining_items = status["remaining_items"]
        assert isinstance(remaining_items, list)
        status["remaining_items"] = [item for item in remaining_items if item.get("id") == "warning_actions"]
        report = self.module.build_report(package_dir, status, "operator")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.module.print_summary(report)

        with tempfile.TemporaryDirectory(prefix="quant-next-step-md-") as tmp:
            markdown_path = Path(tmp) / "next-release-step.md"
            self.module.write_markdown(markdown_path, report)
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertIn("Approval: operator approval required after checklist review.", output.getvalue())
        self.assertIn("- Approval: operator approval required after checklist review.", markdown)

    def test_operator_sequence_prints_warning_review_json_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            status = synthetic_status(package_dir, bundle_dir)
            status["remaining_items"].insert(
                1,
                {
                    "id": "live_beta_archive",
                    "status": "warn",
                    "owner": "operator",
                    "action": "Archive live-beta closeout evidence.",
                    "preferred_action": "Run live-beta archive preflight first.",
                    "preferred_command": "python3 scripts/archive_live_beta_closeout.py --preflight",
                    "automation_command": "python3 scripts/archive_live_beta_closeout.py --preflight --json",
                    "full_flow_command": "python3 scripts/archive_live_beta_closeout.py",
                    "supporting_commands": {
                        "Start local backend": "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload",
                        "Check backend health": "curl -fsS http://localhost:8000/api/health",
                    },
                    "command": "python3 scripts/archive_live_beta_closeout.py",
                },
            )
            (package_dir / "release-status.json").write_text(
                json.dumps(status, indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--show-sequence",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Automation JSON:", completed.stdout)
        self.assertIn("python3 scripts/archive_live_beta_closeout.py --preflight --json", completed.stdout)
        self.assertIn("Supporting commands:", completed.stdout)
        self.assertIn("Start local backend", completed.stdout)
        self.assertIn("curl -fsS http://localhost:8000/api/health", completed.stdout)
        self.assertIn(
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --json-only",
            completed.stdout,
        )
        self.assertIn(
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir} --next-command-only",
            completed.stdout,
        )

    def test_operator_supporting_commands_print_review_helpers_before_gates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            status = synthetic_status(package_dir, bundle_dir)
            for item in status["remaining_items"]:
                if item.get("id") not in {"warning_alerts", "warning_actions"}:
                    continue
                item["supporting_commands"] = {
                    "Gate warning summary JSON": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--summary-json-only --fail-if-action-needed"
                    ),
                    "Gate warning recommended next command": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--next-command-only --fail-if-action-needed"
                    ),
                    "Show warning recommended next command": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--next-command-only"
                    ),
                    "Show warning review artifact paths": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--review-artifacts-only"
                    ),
                    "Show warning summary JSON": (
                        f"python3 scripts/review_release_warnings.py --package-dir {package_dir} "
                        "--summary-json-only"
                    ),
                }
            (package_dir / "release-status.json").write_text(
                json.dumps(status, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--show-sequence",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary_index = completed.stdout.index("Show warning summary JSON")
        artifacts_index = completed.stdout.index("Show warning review artifact paths")
        recommended_index = completed.stdout.index("Show warning recommended next command")
        gate_summary_index = completed.stdout.index("Gate warning summary JSON")
        gate_next_index = completed.stdout.index("Gate warning recommended next command")
        self.assertLess(summary_index, artifacts_index)
        self.assertLess(artifacts_index, recommended_index)
        self.assertLess(recommended_index, gate_summary_index)
        self.assertLess(gate_summary_index, gate_next_index)
        self.assertIn("Approval: operator approval required after checklist review.", completed.stdout)

    def test_build_report_uses_preferred_command_for_non_connected_runner_items(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        preflight = "python3 scripts/archive_live_beta_closeout.py --preflight"
        automation = "python3 scripts/archive_live_beta_closeout.py --preflight --json"
        closeout = "python3 scripts/archive_live_beta_closeout.py"
        status = synthetic_status(package_dir, Path("/tmp/quant handoff"))
        status["remaining_items"] = [
            {
                "id": "live_beta_archive",
                "status": "warn",
                "owner": "operator",
                "action": "Archive live-beta closeout evidence.",
                "preferred_action": "Run live-beta archive preflight first.",
                "preferred_command": preflight,
                "automation_command": automation,
                "full_flow_command": closeout,
                "supporting_commands": {"Check backend health": "curl -fsS http://localhost:8000/api/health"},
                "command": closeout,
                "final_verify_command": "python3 scripts/release_gate.py --require-live-beta",
            }
        ]
        status["readiness_estimate"]["remaining_items"] = 1

        report = self.module.build_report(package_dir, status, "operator")

        self.assertEqual(report["next_command"], preflight)
        self.assertEqual(report["next_action"], "Run live-beta archive preflight first.")
        self.assertEqual(report["next_item"]["automation_command"], automation)
        self.assertEqual(
            report["next_item"]["supporting_commands"]["Check backend health"],
            "curl -fsS http://localhost:8000/api/health",
        )
        self.assertEqual(report["full_flow_command"], closeout)

    def test_handoff_bundle_does_not_double_scope_source_fallback_commands(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        packaged_bundle_dir = Path("/tmp/packaged quant handoff")
        earlier_bundle_dir = Path("/tmp/earlier quant handoff")
        current_bundle_dir = Path("/tmp/current quant handoff")
        packaged_source_dir_arg = shlex.quote(str(packaged_bundle_dir / "source"))
        earlier_source_dir_arg = shlex.quote(str(earlier_bundle_dir / "source"))
        current_source_dir_arg = shlex.quote(str(current_bundle_dir / "source"))
        status = synthetic_status(package_dir, packaged_bundle_dir)
        first_item = status["remaining_items"][0]
        first_item["command"] = (
            f"cd {packaged_source_dir_arg} && cd {earlier_source_dir_arg} && git remote add origin REPLACE_WITH_REPO_URL"
        )
        first_item["verify_command"] = f"cd {packaged_source_dir_arg} && cd {earlier_source_dir_arg} && git remote get-url origin"
        first_item["final_verify_command"] = (
            f"cd {packaged_source_dir_arg} && cd {earlier_source_dir_arg} && "
            "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth"
        )

        report = self.module.build_report(package_dir, status, "connected runner", handoff_bundle=str(current_bundle_dir))

        self.assertEqual(report["manual_setup_command"].count(f"cd {current_source_dir_arg} && "), 1)
        self.assertEqual(report["verify_command"].count(f"cd {current_source_dir_arg} && "), 1)
        self.assertEqual(report["final_verify_command"].count(f"cd {current_source_dir_arg} && "), 1)
        self.assertNotIn(str(packaged_bundle_dir), report["manual_setup_command"])
        self.assertNotIn(str(packaged_bundle_dir), report["verify_command"])
        self.assertNotIn(str(packaged_bundle_dir), report["final_verify_command"])
        self.assertNotIn(str(earlier_bundle_dir), report["manual_setup_command"])
        self.assertNotIn(str(earlier_bundle_dir), report["verify_command"])
        self.assertNotIn(str(earlier_bundle_dir), report["final_verify_command"])

    def test_repo_url_validation(self) -> None:
        self.assertIsNone(self.module.validate_repo_url("https://github.com/example/quant-lab.git"))
        self.assertIsNone(self.module.validate_repo_url("https://github.com/example/quant-lab.git/"))
        self.assertIsNone(self.module.validate_repo_url("ssh://git@github.com/example/quant-lab.git"))
        self.assertIsNone(self.module.validate_repo_url("ssh://git@github.com/example/quant-lab.git/"))
        self.assertIsNone(self.module.validate_repo_url("git@github.com:example/quant-lab.git"))
        self.assertIsNone(self.module.validate_repo_url("git@github.com:example/quant-lab.git/"))
        self.assertEqual(
            self.module.validate_repo_url("REPO_URL"),
            "must be a real remote URL, not a placeholder.",
        )
        self.assertEqual(
            self.module.validate_repo_url("not-a-url"),
            "must be an HTTPS, SSH, or scp-style git remote URL.",
        )
        self.assertEqual(
            self.module.validate_repo_url("git@github.com:"),
            "must be an HTTPS, SSH, or scp-style git remote URL.",
        )
        self.assertEqual(
            self.module.validate_repo_url("git@:example/quant-lab.git"),
            "must be an HTTPS, SSH, or scp-style git remote URL.",
        )
        self.assertEqual(
            self.module.validate_repo_url("https:///example/quant-lab.git"),
            "must be an HTTPS, SSH, or scp-style git remote URL.",
        )
        self.assertEqual(
            self.module.validate_repo_url("ssh:///example/quant-lab.git"),
            "must be an HTTPS, SSH, or scp-style git remote URL.",
        )
        self.assertEqual(
            self.module.validate_repo_url("https://github.com/"),
            "must be an HTTPS, SSH, or scp-style git remote URL.",
        )
        self.assertEqual(
            self.module.normalize_repo_url(" https://github.com/example/quant-lab.git "),
            "https://github.com/example/quant-lab.git",
        )

    def test_build_report_rejects_invalid_repo_url(self) -> None:
        package_dir = Path("/tmp/quant-evidence")
        bundle_dir = Path("/tmp/quant-handoff")
        with self.assertRaisesRegex(ValueError, "repo_url must be a real remote URL"):
            self.module.build_report(
                package_dir,
                synthetic_status(package_dir, bundle_dir),
                "connected runner",
                "REPO_URL",
            )

    def test_cli_sequence_summary_and_repo_url_smoke(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        moved_bundle = "/tmp/moved-quant-handoff"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--handoff-bundle",
                    moved_bundle,
                    "--show-sequence",
                    "--summary-by-owner",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"Package: {package_dir}", completed.stdout)
        self.assertIn(f"Handoff bundle: {moved_bundle}", completed.stdout)
        self.assertIn("Remaining items: 1 for connected runner (3 total)", completed.stdout)
        self.assertIn("Completion deductions:", completed.stdout)
        self.assertIn("- external_readiness_warnings: -3 point(s).", completed.stdout)
        self.assertIn("Completion impact: Clearing git_origin_remote is expected to recover 1 completion point", completed.stdout)
        self.assertIn("Remaining by owner:", completed.stdout)
        self.assertIn("- connected runner: 1 (warn: 1)", completed.stdout)
        self.assertIn("- operator: 2 (planned: 1, warn: 1)", completed.stdout)
        self.assertIn("Remaining sequence:", completed.stdout)
        self.assertIn("1. git_origin_remote (connected runner, warn)", completed.stdout)
        self.assertIn("Same as Next item above.", completed.stdout)
        self.assertIn(f"cd {moved_bundle} &&", completed.stdout)
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", completed.stdout)
        self.assertIn("Automation JSON:", completed.stdout)
        self.assertIn('--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only', completed.stdout)
        self.assertNotIn("GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL", completed.stdout)
        self.assertNotIn(f"cd {bundle_dir} &&", completed.stdout)
        self.assertNotIn("Notes:", completed.stdout)

    def test_command_only_prints_only_next_command_and_implies_no_write(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--command-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            f"cd {bundle_dir} && PREFLIGHT_ONLY=true GIT_ORIGIN_URL={repo_url} ./run-connected-runner-handoff.sh\n",
        )
        self.assertEqual(completed.stderr, "")
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_command_only_can_fail_when_repo_url_placeholder_remains(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--command-only",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("literal placeholders are rejected", completed.stderr)

    def test_command_only_operator_command_does_not_require_repo_url(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--command-only",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            f"python3 scripts/review_release_warnings.py --package-dir {package_dir}\n",
        )
        self.assertNotIn("REPLACE_WITH_REPO_URL", completed.stdout)

    def test_json_only_prints_report_json_and_implies_no_write(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["package_dir"], str(package_dir))
        self.assertEqual(payload["handoff_bundle"], str(bundle_dir))
        self.assertEqual(payload["owner_filter"], "connected runner")
        self.assertEqual(payload["filtered_remaining_count"], 1)
        self.assertEqual(payload["total_remaining_count"], 3)
        self.assertEqual(payload["completion_deductions"][1]["id"], "live_beta_archive")
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", payload["next_command"])
        self.assertEqual(completed.stderr, "")
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_json_only_can_fail_when_repo_url_placeholder_remains(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--json-only",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["repo_url_required"])
        self.assertIn("Replace REPLACE_WITH_REPO_URL", payload["repo_url_gate_message"])
        self.assertIn("REPLACE_WITH_REPO_URL", payload["next_command"])
        self.assertIn("--repo-url-from-env GIT_ORIGIN_URL", payload["repo_url_command_gate"])
        self.assertIn("--command-only --fail-if-repo-url-required", payload["repo_url_command_gate"])
        self.assertEqual(
            payload["repo_url_export_command"],
            "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
        )
        self.assertIn('--owner "connected runner"', payload["repo_url_json_gate"])
        self.assertIn("--json-only --fail-if-repo-url-required", payload["repo_url_json_gate"])
        self.assertEqual(completed.stderr, "")

    def test_command_only_rejects_summary_and_sequence_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--command-only",
                    "--summary-by-owner",
                    "--show-sequence",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("--command-only cannot be combined with --show-sequence, --summary-by-owner", completed.stderr)

    def test_command_only_rejects_output_prefix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--command-only",
                    "--output-prefix",
                    str(Path(tmp) / "ignored-output"),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("--command-only cannot be combined with --output-prefix", completed.stderr)

    def test_json_only_accepts_summary_and_sequence_flags(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--json-only",
                    "--summary-by-owner",
                    "--show-sequence",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["owner_filter"], "operator")
        self.assertEqual(payload["filtered_remaining_count"], 2)
        self.assertEqual(payload["owner_summary"][0]["owner"], "connected runner")
        self.assertEqual([item["id"] for item in payload["remaining_items"]], ["warning_alerts", "warning_actions"])
        self.assertEqual(completed.stderr, "")

    def test_json_only_rejects_output_prefix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--json-only",
                    "--output-prefix",
                    str(Path(tmp) / "ignored-output"),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("--json-only cannot be combined with --output-prefix", completed.stderr)

    def test_command_only_and_json_only_conflict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--command-only",
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("--command-only cannot be combined with --json-only", completed.stderr)

    def test_owner_without_items_switches_to_quoted_all_owner_view(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant next step ") as tmp:
            package_dir = Path(tmp) / "package with spaces"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            status = synthetic_status(package_dir, bundle_dir)
            status["remaining_items"] = [
                {
                    "id": "warning_alerts",
                    "status": "warn",
                    "owner": "operator",
                    "action": "Review warning alerts.",
                    "command": f"python3 scripts/review_release_warnings.py --package-dir {package_dir}",
                }
            ]
            (package_dir / "release-status.json").write_text(
                json.dumps(status, indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        quoted_package = f"'{package_dir}'"
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Next item: none for connected runner", completed.stdout)
        self.assertIn(f"--package-dir {quoted_package} --owner all --no-write", completed.stdout)
        self.assertNotIn(f"--package-dir {package_dir} --owner all", completed.stdout)

    def test_cli_command_sequence_uses_latest_package_when_package_dir_is_omitted(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-latest-") as tmp:
            packages_dir = Path(tmp) / "packages"
            older_package = packages_dir / "20260526-KRW-BTC-beta-001"
            latest_package = packages_dir / "20260526-KRW-BTC-beta-002"
            older_bundle = Path(tmp) / "older-handoff"
            latest_bundle = Path(tmp) / "latest-handoff"
            older_package.mkdir(parents=True)
            latest_package.mkdir(parents=True)
            older_bundle.mkdir()
            latest_bundle.mkdir()
            (older_package / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_name": older_package.name,
                        "generated_at": "2026-05-25T00:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (latest_package / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_name": latest_package.name,
                        "generated_at": "2026-05-25T00:01:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (older_package / "release-status.json").write_text(
                json.dumps(synthetic_status(older_package, older_bundle), indent=2) + "\n",
                encoding="utf-8",
            )
            (latest_package / "release-status.json").write_text(
                json.dumps(synthetic_status(latest_package, latest_bundle), indent=2) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["GIT_ORIGIN_URL"] = repo_url

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--packages-dir",
                    str(packages_dir),
                    "--repo-url-from-env",
                    "GIT_ORIGIN_URL",
                    "--command-sequence-only",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(str(latest_package), completed.stdout)
        self.assertIn(str(latest_bundle), completed.stdout)
        self.assertNotIn(str(older_package), completed.stdout)
        self.assertNotIn(str(older_bundle), completed.stdout)

    def test_cli_can_read_repo_url_from_git_origin(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            repo_dir = Path(tmp) / "repo"
            package_dir.mkdir()
            bundle_dir.mkdir()
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=repo_dir, text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_dir, text=True, capture_output=True, check=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url-from-origin",
                    str(repo_dir),
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", completed.stdout)
        self.assertIn(f"git remote add origin {repo_url}", completed.stdout)
        self.assertNotIn("GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL", completed.stdout)
        self.assertNotIn("Notes:", completed.stdout)

    def test_cli_can_read_repo_url_from_inferred_handoff_source_origin(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            source_dir = bundle_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=source_dir, text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=source_dir, text=True, capture_output=True, check=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url-from-origin",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", completed.stdout)
        self.assertIn(f"git remote add origin {repo_url}", completed.stdout)
        self.assertNotIn("GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL", completed.stdout)
        self.assertNotIn("Notes:", completed.stdout)

    def test_cli_can_read_repo_url_from_env(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["GIT_ORIGIN_URL"] = repo_url

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url-from-env",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", completed.stdout)
        self.assertIn(f"git remote add origin {repo_url}", completed.stdout)
        self.assertNotIn("GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL", completed.stdout)
        self.assertNotIn("Notes:", completed.stdout)

    def test_repo_url_from_env_requires_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url-from-env",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url-from-env requires --no-write", completed.stderr)

    def test_repo_url_from_env_rejects_missing_variable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env.pop("MISSING_GIT_ORIGIN_URL", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url-from-env",
                    "MISSING_GIT_ORIGIN_URL",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("could not read $MISSING_GIT_ORIGIN_URL", completed.stderr)
        self.assertIn("export MISSING_GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git", completed.stderr)

    def test_repo_url_from_env_rejects_placeholder_with_export_hint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["GIT_ORIGIN_URL"] = "REPLACE_WITH_REPO_URL"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url-from-env",
                    "GIT_ORIGIN_URL",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("$GIT_ORIGIN_URL must be a real remote URL, not a placeholder.", completed.stderr)
        self.assertIn("export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git", completed.stderr)

    def test_json_only_repo_url_gate_prints_payload_when_env_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env.pop("MISSING_GIT_ORIGIN_URL", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url-from-env",
                    "MISSING_GIT_ORIGIN_URL",
                    "--json-only",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["repo_url_required"])
        self.assertIn("could not read $MISSING_GIT_ORIGIN_URL", payload["repo_url_error"])
        self.assertIn("could not read $MISSING_GIT_ORIGIN_URL", payload["repo_url_gate_message"])
        self.assertIn("export MISSING_GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git", payload["repo_url_error"])
        self.assertEqual(completed.stderr, "")

    def test_repo_url_from_origin_requires_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url-from-origin",
                    str(Path(tmp)),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url-from-origin requires --no-write", completed.stderr)

    def test_repo_url_and_repo_url_from_origin_conflict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url",
                    "https://github.com/example/quant-lab.git",
                    "--repo-url-from-origin",
                    str(Path(tmp)),
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url, --repo-url-from-origin, and --repo-url-from-env cannot be used together", completed.stderr)

    def test_cli_warns_when_connected_runner_repo_url_placeholder_remains(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Notes:", completed.stdout)
        self.assertIn("Replace REPLACE_WITH_REPO_URL with a real HTTPS, SSH, or scp-style git remote URL", completed.stdout)
        self.assertIn("literal placeholders are rejected", completed.stdout)
        self.assertIn("Repo URL command gate:", completed.stdout)
        self.assertIn("Repo URL export example:", completed.stdout)
        self.assertIn("export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git", completed.stdout)
        self.assertIn("--repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required", completed.stdout)
        self.assertIn("Repo URL JSON gate:", completed.stdout)
        self.assertIn(
            '--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required',
            completed.stdout,
        )

    def test_summary_omits_duplicate_repo_url_export_when_supporting_command_has_it(self) -> None:
        package_dir = Path("/tmp/quant evidence")
        bundle_dir = Path("/tmp/quant handoff")
        status = synthetic_status(package_dir, bundle_dir)
        first_item = status["remaining_items"][0]
        first_item["supporting_commands"] = {
            "Export repo URL example": self.module.repo_url_export_example_command(),
        }
        report = self.module.build_report(package_dir, status, "connected runner")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.module.print_summary(report)
        text = output.getvalue()

        self.assertEqual(text.count("export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git"), 1)
        self.assertIn("- Export repo URL example:", text)
        self.assertNotIn("Repo URL export example:", text)
        self.assertIn("Repo URL command gate:", text)

    def test_handoff_bundle_override_quotes_paths_with_spaces(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        moved_bundle = "/tmp/moved quant handoff"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--handoff-bundle",
                    moved_bundle,
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("cd '/tmp/moved quant handoff' &&", completed.stdout)
        self.assertNotIn(f"cd {moved_bundle} &&", completed.stdout)

    def test_handoff_bundle_can_supply_copied_evidence_package(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            handoff_root = Path(tmp) / "moved handoff"
            package_dir = handoff_root / "evidence" / "copied-package"
            original_bundle_dir = Path(tmp) / "original-handoff"
            package_dir.mkdir(parents=True)
            original_bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, original_bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--handoff-bundle",
                    str(handoff_root),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Remaining items: 1 for connected runner (3 total)", completed.stdout)
        self.assertIn("moved handoff' &&", completed.stdout)
        self.assertNotIn(str(original_bundle_dir), completed.stdout)
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", completed.stdout)

    def test_relative_handoff_bundle_is_printed_as_absolute_path(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            tmp_path = Path(tmp)
            package_dir = tmp_path / "package"
            original_bundle_dir = tmp_path / "original-handoff"
            package_dir.mkdir()
            original_bundle_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, original_bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--handoff-bundle",
                    "relative-handoff",
                    "--no-write",
                ],
                cwd=tmp_path,
                text=True,
                capture_output=True,
                check=False,
            )

        expected_bundle = tmp_path.resolve() / "relative-handoff"
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"Handoff bundle: {expected_bundle}", completed.stdout)
        self.assertIn(f"cd {expected_bundle} &&", completed.stdout)
        self.assertNotIn("cd relative-handoff &&", completed.stdout)

    def test_repo_url_requires_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url",
                    "https://github.com/example/quant-lab.git",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url requires --no-write", completed.stderr)

    def test_empty_repo_url_requires_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url",
                    "",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url requires --no-write", completed.stderr)

    def test_empty_repo_url_with_no_write_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url",
                    "",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url must not be empty", completed.stderr)

    def test_repo_url_rejects_placeholders_with_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            for placeholder in ("REPLACE_WITH_REPO_URL", "REPO_URL"):
                with self.subTest(placeholder=placeholder):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(NEXT_RELEASE_STEP),
                            "--package-dir",
                            str(package_dir),
                            "--repo-url",
                            placeholder,
                            "--no-write",
                        ],
                        cwd=PROJECT_ROOT,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("--repo-url must be a real remote URL", completed.stderr)

    def test_repo_url_rejects_invalid_format_with_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url",
                    "not-a-url",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--repo-url must be an HTTPS, SSH, or scp-style git remote URL", completed.stderr)

    def test_handoff_bundle_requires_no_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--handoff-bundle",
                    "/tmp/moved-handoff",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--handoff-bundle requires --no-write", completed.stderr)

    def test_json_only_can_include_local_readiness(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            repo_dir = Path(tmp) / "repo"
            package_dir.mkdir()
            bundle_dir.mkdir()
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=repo_dir, text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_dir, text=True, capture_output=True, check=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--json-only",
                    "--local-readiness",
                    "--local-readiness-source",
                    str(repo_dir),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        checks = {check["id"]: check for check in payload["local_readiness"]}
        self.assertEqual(checks["git_origin_remote"]["status"], "pass")
        self.assertIn(repo_url, checks["git_origin_remote"]["message"])
        self.assertIn("docker_cli", checks)
        self.assertIn("github_cli", checks)
        self.assertIn("local_readiness_summary", payload)
        self.assertIn(payload["local_readiness_status"], {"pass", "warn"})
        self.assertEqual(
            payload["local_readiness_issue_ids"],
            [
                check["id"]
                for check in payload["local_readiness"]
                if check.get("status") in {"fail", "warn"}
            ],
        )
        automation_command = payload["next_item"]["automation_command"]
        self.assertIn("--local-readiness", automation_command)
        self.assertIn(
            f"--local-readiness-source {shlex.quote(str(repo_dir.absolute()))}",
            automation_command,
        )
        gate_command = payload["next_item"]["local_readiness_gate_command"]
        self.assertIn("--local-readiness", gate_command)
        self.assertIn("--fail-if-local-readiness-not-pass", gate_command)
        self.assertIn(
            f"--local-readiness-source {shlex.quote(str(repo_dir.absolute()))}",
            gate_command,
        )
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_json_only_can_fail_after_printing_local_readiness_payload(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            source_dir = bundle_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--json-only",
                    "--local-readiness",
                    "--fail-if-local-readiness-not-pass",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["local_readiness_status"], "warn")
        self.assertIn("git_origin_remote", payload["local_readiness_issue_ids"])
        checks = {check["id"]: check for check in payload["local_readiness"]}
        self.assertIn("setup_command", checks["git_origin_remote"])
        self.assertIn(f"remote add origin {repo_url}", checks["git_origin_remote"]["setup_command"])
        self.assertEqual(payload["local_readiness_next_setup_check_id"], "git_origin_remote")
        self.assertIn(repo_url, payload["local_readiness_next_setup_command"])
        self.assertEqual(payload["local_readiness_next_setup"]["command"], payload["local_readiness_next_setup_command"])
        self.assertEqual(payload["local_readiness_next_setup"]["status"], "warn")
        self.assertIn("remote get-url origin", payload["local_readiness_next_setup"]["verify_command"])
        setup_sequence = payload["local_readiness_setup_sequence"]
        self.assertEqual(setup_sequence[0], payload["local_readiness_next_setup"])
        self.assertIn("git_origin_remote", [item["check_id"] for item in setup_sequence])
        command_sequence = payload["local_readiness_command_sequence"]
        self.assertEqual(command_sequence[0], payload["local_readiness_next_setup_command"])
        self.assertEqual(command_sequence[1], payload["local_readiness_next_setup"]["verify_command"])
        for tool_id in ("docker_cli", "github_cli"):
            if checks[tool_id]["status"] != "pass":
                self.assertIn("setup_command", checks[tool_id])
                self.assertIn("remediation", checks[tool_id])
                self.assertIn(tool_id, [item["check_id"] for item in setup_sequence])
        self.assertIn("--local-readiness", payload["next_item"]["automation_command"])
        self.assertIn("--fail-if-local-readiness-not-pass", payload["next_item"]["automation_command"])
        self.assertEqual(
            payload["next_item"]["automation_command"],
            payload["next_item"]["local_readiness_gate_command"],
        )

    def test_command_only_can_fail_after_printing_local_readiness_command(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            source_dir = bundle_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--command-only",
                    "--local-readiness",
                    "--fail-if-local-readiness-not-pass",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn(repo_url, completed.stdout)
        self.assertIn("PREFLIGHT_ONLY=true", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_local_readiness_setup_sequence_only_prints_setup_commands(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            source_dir = bundle_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--local-readiness-setup-sequence-only",
                    "--fail-if-local-readiness-not-pass",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        lines = completed.stdout.strip().splitlines()
        self.assertGreaterEqual(len(lines), 1)
        self.assertIn(f"remote add origin {repo_url}", lines[0])
        self.assertTrue(any("brew install --cask docker" in line for line in lines))
        self.assertTrue(any("brew install gh" in line for line in lines))
        self.assertNotIn("Status:", completed.stdout)
        self.assertNotIn("Local connected-runner readiness:", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_local_readiness_command_sequence_only_prints_setup_and_verify_commands(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            source_dir = bundle_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "connected runner",
                    "--repo-url",
                    repo_url,
                    "--local-readiness-command-sequence-only",
                    "--fail-if-local-readiness-not-pass",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        lines = completed.stdout.strip().splitlines()
        self.assertGreaterEqual(len(lines), 2)
        self.assertIn(f"remote add origin {repo_url}", lines[0])
        self.assertTrue(any("remote get-url origin" in line for line in lines))
        self.assertTrue(any("brew install --cask docker" in line for line in lines))
        self.assertTrue(any(line == "docker compose version" for line in lines))
        self.assertTrue(any("brew install gh" in line for line in lines))
        self.assertTrue(any(line == "gh auth status" for line in lines))
        self.assertNotIn("Status:", completed.stdout)
        self.assertNotIn("Local connected-runner readiness:", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_local_readiness_setup_sequence_only_rejects_json_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--local-readiness-setup-sequence-only",
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--local-readiness-setup-sequence-only cannot be combined with --json-only", completed.stderr)

    def test_local_readiness_command_sequence_only_rejects_json_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--local-readiness-command-sequence-only",
                    "--json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--local-readiness-command-sequence-only cannot be combined with --json-only", completed.stderr)

    def test_command_sequence_only_prints_deduped_remaining_commands(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            status = synthetic_status(package_dir, bundle_dir)
            remaining_items = status["remaining_items"]
            assert isinstance(remaining_items, list)
            duplicate_runner_item = dict(remaining_items[0])
            duplicate_runner_item["id"] = "docker_cli"
            remaining_items.insert(1, duplicate_runner_item)
            (package_dir / "release-status.json").write_text(
                json.dumps(status, indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--repo-url",
                    repo_url,
                    "--command-sequence-only",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stdout.strip().splitlines()
        self.assertEqual(len(lines), 5)
        self.assertIn(f"GIT_ORIGIN_URL={repo_url}", lines[0])
        self.assertIn("review_release_warnings.py", lines[1])
        self.assertIn("--summary-json-only", lines[2])
        self.assertNotIn("--fail-if-action-needed", lines[2])
        self.assertIn("--review-artifacts-only", lines[3])
        self.assertIn("--apply --operator-approved", lines[4])
        self.assertNotIn("Status:", completed.stdout)
        self.assertNotIn("Action:", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertFalse((package_dir / "next-release-step.json").exists())
        self.assertFalse((package_dir / "next-release-step.md").exists())

    def test_show_sequence_marks_repeated_commands_without_reprinting(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        package_dir = Path("/tmp/quant evidence")
        bundle_dir = Path("/tmp/quant handoff")
        status = synthetic_status(package_dir, bundle_dir)
        remaining_items = status["remaining_items"]
        assert isinstance(remaining_items, list)
        remaining_items[0]["supporting_commands"] = {
            "Export repo URL example": "export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git",
            "Show external readiness summary JSON": "python3 scripts/check_external_readiness.py --summary-json-only",
        }
        duplicate_runner_item = dict(remaining_items[0])
        duplicate_runner_item["id"] = "docker_cli"
        remaining_items.insert(1, duplicate_runner_item)
        report = self.module.build_report(package_dir, status, "connected runner", repo_url)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.module.print_sequence(report)
        text = output.getvalue()

        self.assertEqual(text.count(f"PREFLIGHT_ONLY=true GIT_ORIGIN_URL={repo_url}"), 1)
        self.assertIn("2. docker_cli (connected runner, warn)", text)
        self.assertIn("Action: same as earlier in sequence.", text)
        self.assertIn("Command: same as earlier in sequence.", text)
        self.assertIn("Automation JSON: same as earlier in sequence.", text)
        self.assertIn("Supporting commands: same as earlier in sequence.", text)
        self.assertEqual(text.count("- Export repo URL example:"), 1)

    def test_command_sequence_only_can_skip_operator_approved_commands(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            package_dir.mkdir()
            status = synthetic_status(package_dir, bundle_dir)
            (package_dir / "release-status.json").write_text(
                json.dumps(status, indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--owner",
                    "operator",
                    "--command-sequence-only",
                    "--skip-operator-approved",
                    "--fail-if-repo-url-required",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stdout.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("review_release_warnings.py", lines[0])
        self.assertIn("--summary-json-only", lines[1])
        self.assertIn("--review-artifacts-only", lines[2])
        self.assertNotIn("--operator-approved", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_skip_operator_approved_requires_command_sequence_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--skip-operator-approved",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--skip-operator-approved requires --command-sequence-only", completed.stderr)

    def test_command_sequence_only_rejects_show_sequence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--command-sequence-only",
                    "--show-sequence",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--command-sequence-only cannot be combined with --show-sequence", completed.stderr)

    def test_fail_if_local_readiness_not_pass_requires_local_readiness(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--fail-if-local-readiness-not-pass",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--fail-if-local-readiness-not-pass requires --local-readiness", completed.stderr)

    def test_handoff_bundle_defaults_local_readiness_to_source_snapshot(self) -> None:
        repo_url = "https://github.com/example/quant-lab.git"
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            bundle_dir = Path(tmp) / "handoff"
            source_dir = bundle_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=source_dir, text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=source_dir, text=True, capture_output=True, check=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, bundle_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--handoff-bundle",
                    str(bundle_dir),
                    "--json-only",
                    "--local-readiness",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        checks = {check["id"]: check for check in payload["local_readiness"]}
        self.assertEqual(payload["local_readiness_source"], str(source_dir.absolute()))
        self.assertEqual(checks["git_origin_remote"]["status"], "pass")
        self.assertIn(repo_url, checks["git_origin_remote"]["message"])
        self.assertIn("--local-readiness", payload["next_item"]["automation_command"])
        self.assertNotIn("--local-readiness-source", payload["next_item"]["automation_command"])

    def test_text_output_prints_local_readiness_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            source_dir = Path(tmp) / "source path"
            package_dir.mkdir()
            source_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--local-readiness",
                    "--local-readiness-source",
                    str(source_dir),
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Local connected-runner readiness:", completed.stdout)
        self.assertIn(f"Source: {source_dir.absolute()}", completed.stdout)
        self.assertIn("Summary: warn: 3", completed.stdout)
        self.assertIn("Overall: warn", completed.stdout)
        self.assertIn("Issues: git_origin_remote, docker_cli, github_cli", completed.stdout)
        self.assertIn("Next local setup (git_origin_remote):", completed.stdout)
        self.assertIn("Next local remediation: Add a real HTTPS, SSH, or scp-style origin remote", completed.stdout)
        self.assertIn("Next local verification:", completed.stdout)
        self.assertIn("Local setup sequence:", completed.stdout)
        self.assertIn("1. git_origin_remote: same as next local setup above.", completed.stdout)
        self.assertIn("Verify: same as next local verification above.", completed.stdout)
        self.assertIn("2. docker_cli:", completed.stdout)
        self.assertIn("3. github_cli:", completed.stdout)
        self.assertIn("Setup and verification commands are listed in the local setup sequence above.", completed.stdout)
        self.assertNotIn("Setup: see local setup sequence.", completed.stdout)
        self.assertNotIn("Command: see local setup sequence.", completed.stdout)
        self.assertIn("Remediation: Add a real HTTPS, SSH, or scp-style origin remote", completed.stdout)
        self.assertIn("Automation JSON gate:", completed.stdout)
        self.assertIn("--fail-if-local-readiness-not-pass", completed.stdout)

    def test_local_readiness_defaults_to_status_handoff_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            handoff_dir = Path(tmp) / "handoff bundle"
            source_dir = handoff_dir / "source"
            package_dir.mkdir()
            source_dir.mkdir(parents=True)
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, handoff_dir), indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--local-readiness",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                env=env_without_homebrew_tools(),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"Source: {source_dir.absolute()}", completed.stdout)
        self.assertIn("Setup and verification commands are listed in the local setup sequence above.", completed.stdout)

    def test_local_readiness_requires_read_only_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-next-step-") as tmp:
            package_dir = Path(tmp) / "package"
            package_dir.mkdir()
            (package_dir / "release-status.json").write_text(
                json.dumps(synthetic_status(package_dir, Path(tmp) / "handoff"), indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NEXT_RELEASE_STEP),
                    "--package-dir",
                    str(package_dir),
                    "--local-readiness",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--local-readiness requires --no-write or --json-only", completed.stderr)


if __name__ == "__main__":
    unittest.main()
