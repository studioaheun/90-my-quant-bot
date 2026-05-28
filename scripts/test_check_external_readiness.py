#!/usr/bin/env python3
"""Tests for external readiness setup guidance."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_EXTERNAL_READINESS = PROJECT_ROOT / "scripts" / "check_external_readiness.py"


def load_check_external_readiness():
    spec = importlib.util.spec_from_file_location("check_external_readiness", CHECK_EXTERNAL_READINESS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CHECK_EXTERNAL_READINESS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalReadinessSetupGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_check_external_readiness()

    def test_git_origin_setup_command_sets_existing_origin_or_adds_missing_origin(self) -> None:
        command = self.module.git_origin_setup_command()

        self.assertIn("git remote get-url origin", command)
        self.assertIn("git remote set-url origin REPLACE_WITH_REPO_URL", command)
        self.assertIn("git remote add origin REPLACE_WITH_REPO_URL", command)
        self.assertIn("; then ", command)
        self.assertIn("; else ", command)

    def test_missing_docker_includes_macos_setup_command(self) -> None:
        checks: list[dict[str, object]] = []

        with patch.object(self.module.shutil, "which", return_value=None):
            self.module.check_docker(checks, require_docker=False)

        self.assertEqual(checks[0]["id"], "docker_cli")
        self.assertEqual(checks[0]["status"], "warn")
        self.assertEqual(checks[0]["setup_command"], self.module.DOCKER_SETUP_COMMAND)
        self.assertIn("macOS/Homebrew", str(checks[0]["remediation"]))

    def test_missing_github_cli_includes_auth_setup_command(self) -> None:
        checks: list[dict[str, object]] = []

        with patch.object(self.module.shutil, "which", return_value=None):
            self.module.check_gh(checks, require_gh=False, check_auth=True)

        self.assertEqual(checks[0]["id"], "github_cli")
        self.assertEqual(checks[0]["status"], "warn")
        self.assertEqual(checks[0]["setup_command"], self.module.GITHUB_CLI_SETUP_COMMAND)
        self.assertIn("gh auth setup-git", str(checks[0]["setup_command"]))

    def test_markdown_renders_setup_commands_for_missing_tools(self) -> None:
        summary = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "status": "warn",
            "checks": [
                {
                    "id": "docker_cli",
                    "label": "Docker CLI",
                    "status": "warn",
                    "message": "Docker is not installed on this machine.",
                    "evidence": None,
                    "remediation": "Install Docker.",
                    "setup_command": self.module.DOCKER_SETUP_COMMAND,
                    "verify_command": "docker compose version",
                    "details": {},
                },
                {
                    "id": "github_cli",
                    "label": "GitHub CLI",
                    "status": "warn",
                    "message": "GitHub CLI is not installed.",
                    "evidence": None,
                    "remediation": "Install GitHub CLI.",
                    "setup_command": self.module.GITHUB_CLI_SETUP_COMMAND,
                    "verify_command": "gh auth status",
                    "details": {},
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "external-readiness.md"
            self.module.write_markdown(output_path, summary)
            markdown = output_path.read_text(encoding="utf-8")

        self.assertIn(self.module.DOCKER_SETUP_COMMAND, markdown)
        self.assertIn(self.module.GITHUB_CLI_SETUP_COMMAND, markdown)

    def test_unresolved_guidance_includes_setup_and_verify_sequences(self) -> None:
        summary = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "status": "warn",
            "checks": [
                {
                    "id": "docker_cli",
                    "label": "Docker CLI",
                    "status": "warn",
                    "message": "Docker is not installed.",
                    "setup_command": self.module.DOCKER_SETUP_COMMAND,
                    "verify_command": "docker compose version",
                },
                {
                    "id": "github_cli",
                    "label": "GitHub CLI",
                    "status": "warn",
                    "message": "GitHub CLI is not installed.",
                    "setup_command": self.module.GITHUB_CLI_SETUP_COMMAND,
                    "verify_command": "gh auth status",
                },
            ],
        }

        guidance = self.module.unresolved_guidance(summary)

        self.assertEqual(guidance["next_setup_command"], self.module.DOCKER_SETUP_COMMAND)
        self.assertEqual(guidance["next_setup"]["id"], "docker_cli")
        self.assertFalse(guidance["repo_url"]["required"])
        self.assertEqual(
            guidance["setup_sequence"],
            [self.module.DOCKER_SETUP_COMMAND, self.module.GITHUB_CLI_SETUP_COMMAND],
        )
        self.assertEqual(guidance["verify_sequence"], ["docker compose version", "gh auth status"])
        self.assertEqual(
            guidance["command_sequence"],
            [
                self.module.DOCKER_SETUP_COMMAND,
                "docker compose version",
                self.module.GITHUB_CLI_SETUP_COMMAND,
                "gh auth status",
            ],
        )

    def test_unresolved_guidance_marks_repo_url_placeholder(self) -> None:
        summary = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "status": "warn",
            "checks": [
                {
                    "id": "git_origin_remote",
                    "label": "Git origin remote",
                    "status": "warn",
                    "message": "Origin is missing.",
                    "setup_command": self.module.git_origin_setup_command(),
                    "verify_command": "git remote get-url origin",
                },
            ],
        }

        guidance = self.module.unresolved_guidance(summary)

        self.assertTrue(guidance["repo_url"]["required"])
        self.assertEqual(guidance["repo_url"]["placeholder"], self.module.REPO_URL_PLACEHOLDER)
        self.assertEqual(
            guidance["repo_url"]["export_command"],
            self.module.repo_url_export_example_command(),
        )
        self.assertIn(self.module.REPO_URL_PLACEHOLDER, guidance["repo_url"]["message"])
        self.assertEqual(guidance["next_setup_command"], self.module.git_origin_setup_command())
        self.assertEqual(guidance["setup_sequence"], [self.module.git_origin_setup_command()])

    def test_cli_summary_json_only_prints_compact_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quant-external-readiness-") as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_EXTERNAL_READINESS),
                    "--output-dir",
                    tmp,
                    "--summary-json-only",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            payload = json.loads(completed.stdout)
            self.assertIn(payload["status"], {"pass", "warn"})
            self.assertTrue(Path(payload["json_path"]).is_file())
            self.assertTrue(Path(payload["markdown_path"]).is_file())
            self.assertIn("check_summary", payload)
            self.assertIn("counts", payload["check_summary"])
            self.assertIn("warnings", payload["check_summary"])
            self.assertIn("guidance", payload)
            self.assertIn("setup_sequence", payload["guidance"])
            self.assertIn("verify_sequence", payload["guidance"])
            self.assertIn("command_sequence", payload["guidance"])
            self.assertIn("repo_url", payload["guidance"])
            self.assertNotIn("checks", payload)
            self.assertNotIn("External readiness:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
