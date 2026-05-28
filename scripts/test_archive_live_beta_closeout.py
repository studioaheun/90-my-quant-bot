#!/usr/bin/env python3
"""Smoke tests for live-beta closeout archive helpers."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_LIVE_BETA_CLOSEOUT = PROJECT_ROOT / "scripts" / "archive_live_beta_closeout.py"


def load_archive_live_beta_closeout():
    spec = importlib.util.spec_from_file_location("archive_live_beta_closeout", ARCHIVE_LIVE_BETA_CLOSEOUT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {ARCHIVE_LIVE_BETA_CLOSEOUT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArchiveLiveBetaCloseoutSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_archive_live_beta_closeout()

    def test_backup_reference_validation_accepts_real_references(self) -> None:
        self.assertIsNone(self.module.validate_backup_reference(None))
        self.assertEqual(
            self.module.validate_backup_reference(" /backups/quant-lab-20260523.sqlite3 "),
            "/backups/quant-lab-20260523.sqlite3",
        )
        self.assertEqual(
            self.module.validate_backup_reference("s3://quant-lab-backups/20260523/quant-lab.sqlite3"),
            "s3://quant-lab-backups/20260523/quant-lab.sqlite3",
        )

    def test_backup_reference_validation_rejects_empty_and_placeholders(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            self.module.validate_backup_reference(" ")
        with self.assertRaisesRegex(ValueError, "not a placeholder"):
            self.module.validate_backup_reference("PATH_TO_BACKUP")
        with self.assertRaisesRegex(ValueError, "not a placeholder"):
            self.module.validate_backup_reference("<backup-reference>")

    def test_preflight_report_passes_when_live_locked_and_no_blocking_alerts(self) -> None:
        def requester(api_base: str, path: str):
            self.assertEqual(api_base, "http://testserver")
            responses = {
                "/api/health": {"status": "ok"},
                "/api/execution/settings": {
                    "live_trading_enabled": False,
                    "adapter_ready": False,
                },
                "/api/alerts/review?include_acknowledged=true": {"items": []},
            }
            return responses[path]

        report = self.module.live_beta_preflight_report(
            api_base="http://testserver",
            symbol="KRW-BTC",
            backup_reference="/backups/quant-lab.sqlite3",
            allow_live_enabled=False,
            requester=requester,
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["commands"]["preflight"],
            "python3 scripts/archive_live_beta_closeout.py --api-base http://testserver "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight",
        )
        self.assertEqual(
            report["commands"]["backend_start_local"],
            "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload",
        )
        self.assertEqual(
            report["commands"]["backend_start_local_no_reload"],
            "cd backend && . .venv/bin/activate && uvicorn app.main:app",
        )
        self.assertEqual(report["commands"]["backend_start_docker"], "docker compose start backend")
        self.assertEqual(report["commands"]["backend_health_check"], "curl -fsS http://testserver/api/health")
        self.assertEqual(
            report["commands"]["preflight_json"],
            "python3 scripts/archive_live_beta_closeout.py --api-base http://testserver "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight --json",
        )
        self.assertEqual(
            report["commands"]["next_command_only"],
            "python3 scripts/archive_live_beta_closeout.py --api-base http://testserver "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight --next-command-only",
        )
        self.assertEqual(
            report["commands"]["archive"],
            "python3 scripts/archive_live_beta_closeout.py --api-base http://testserver "
            "--symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3",
        )
        self.assertEqual(
            report["commands"]["final_gate"],
            "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth --require-live-beta",
        )
        self.assertEqual(report["recommended_next"]["id"], "archive_live_beta_closeout")
        self.assertEqual(report["recommended_next"]["command"], report["commands"]["archive"])
        self.assertEqual(
            report["recommended_next"]["follow_up_commands"]["Run final live-beta gate"],
            report["commands"]["final_gate"],
        )
        checks = {check["id"]: check for check in report["checks"]}
        self.assertEqual(checks["live_lock"]["status"], "pass")
        self.assertEqual(checks["blocking_alerts"]["status"], "pass")
        self.assertEqual(checks["backup_reference"]["status"], "pass")

    def test_preflight_report_recommends_backend_start_when_backend_is_unreachable(self) -> None:
        def requester(_api_base: str, path: str):
            raise RuntimeError(f"GET http://testserver{path} failed: connection refused")

        report = self.module.live_beta_preflight_report(
            api_base="http://testserver",
            symbol="KRW-BTC",
            backup_reference="/backups/quant-lab.sqlite3",
            allow_live_enabled=False,
            requester=requester,
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["recommended_next"]["id"], "start_backend")
        self.assertEqual(report["recommended_next"]["reason_check_id"], "backend_health")
        self.assertEqual(report["recommended_next"]["command"], report["commands"]["backend_start_local"])
        self.assertEqual(
            report["recommended_next"]["follow_up_commands"]["Start local backend without reload"],
            report["commands"]["backend_start_local_no_reload"],
        )
        self.assertEqual(
            report["recommended_next"]["follow_up_commands"]["Check backend health"],
            report["commands"]["backend_health_check"],
        )
        self.assertEqual(
            report["recommended_next"]["follow_up_commands"]["Rerun JSON preflight"],
            report["commands"]["preflight_json"],
        )

    def test_preflight_report_fails_when_live_is_not_locked(self) -> None:
        def requester(_api_base: str, path: str):
            responses = {
                "/api/health": {"status": "ok"},
                "/api/execution/settings": {
                    "live_trading_enabled": True,
                    "adapter_ready": True,
                },
                "/api/alerts/review?include_acknowledged=true": {"items": []},
            }
            return responses[path]

        report = self.module.live_beta_preflight_report(
            api_base="http://testserver",
            symbol="KRW-BTC",
            backup_reference="/backups/quant-lab.sqlite3",
            allow_live_enabled=False,
            requester=requester,
        )

        self.assertEqual(report["status"], "fail")
        checks = {check["id"]: check for check in report["checks"]}
        self.assertEqual(checks["live_lock"]["status"], "fail")
        self.assertIn("Live trading still appears enabled", checks["live_lock"]["message"])
        self.assertEqual(report["recommended_next"]["id"], "lock_live_flags")
        self.assertEqual(report["recommended_next"]["command"], report["commands"]["preflight"])

    def test_preflight_report_json_is_machine_readable(self) -> None:
        report = {
            "status": "pass",
            "api_base": "http://testserver",
            "symbol": "KRW-BTC",
            "backup_reference": "/backups/quant-lab.sqlite3",
            "checks": [{"id": "backend_health", "status": "pass", "message": "ok", "details": {}}],
        }

        payload = json.loads(self.module.preflight_report_json(report))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["checks"][0]["id"], "backend_health")

    def test_next_command_only_prints_recommended_command(self) -> None:
        report = {
            "status": "fail",
            "recommended_next": {"command": "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload"},
        }
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["archive_live_beta_closeout.py", "--preflight", "--next-command-only"]):
            with mock.patch.object(self.module, "live_beta_preflight_report", return_value=report):
                with contextlib.redirect_stdout(output):
                    code = self.module.main()

        self.assertEqual(code, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload",
        )

    def test_text_preflight_report_prints_follow_up_commands(self) -> None:
        report = self.module.live_beta_preflight_report(
            api_base="http://testserver",
            symbol="KRW-BTC",
            backup_reference="/backups/quant-lab.sqlite3",
            allow_live_enabled=False,
            requester=lambda _api_base, path: {
                "/api/health": {"status": "ok"},
                "/api/execution/settings": {"live_trading_enabled": False, "adapter_ready": False},
                "/api/alerts/review?include_acknowledged=true": {"items": []},
            }[path],
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.util; "
                    f"spec=importlib.util.spec_from_file_location('m', {str(ARCHIVE_LIVE_BETA_CLOSEOUT)!r}); "
                    "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
                    f"report={report!r}; m.print_preflight_report(report)"
                ),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Commands:", completed.stdout)
        self.assertIn("Recommended next:", completed.stdout)
        self.assertIn("backend_start_local", completed.stdout)
        self.assertIn("backend_health_check", completed.stdout)

    def test_json_requires_preflight(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ARCHIVE_LIVE_BETA_CLOSEOUT),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--json requires --preflight", completed.stdout)

    def test_next_command_only_requires_preflight(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ARCHIVE_LIVE_BETA_CLOSEOUT),
                "--next-command-only",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--next-command-only requires --preflight", completed.stdout)

    def test_json_and_next_command_only_are_mutually_exclusive(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ARCHIVE_LIVE_BETA_CLOSEOUT),
                "--preflight",
                "--json",
                "--next-command-only",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--json cannot be combined with --next-command-only", completed.stdout)


if __name__ == "__main__":
    unittest.main()
