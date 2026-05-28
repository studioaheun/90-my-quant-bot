#!/usr/bin/env python3
"""Archive live-beta closeout evidence from a running Quant Lab backend."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.handoff_commands import (
        DOCKER_BACKEND_START_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        backend_health_check_command,
        live_beta_closeout_command,
        live_beta_next_command_only_command,
        live_beta_preflight_command,
        live_beta_preflight_json_command,
    )
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        DOCKER_BACKEND_START_COMMAND,
        LIVE_BETA_FINAL_GATE_COMMAND,
        LOCAL_BACKEND_START_COMMAND,
        LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        backend_health_check_command,
        live_beta_closeout_command,
        live_beta_next_command_only_command,
        live_beta_preflight_command,
        live_beta_preflight_json_command,
    )


RAW_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("health", "/api/health"),
    ("ops-self-check", "/api/ops/self-check"),
    ("execution-settings", "/api/execution/settings"),
    ("live-readiness", "/api/readiness/live"),
    ("cutover-checklist", "/api/execution/cutover-checklist"),
    ("post-cutover-monitor", "/api/execution/post-cutover-monitor"),
    ("alert-review", "/api/alerts/review?include_acknowledged=true"),
    ("operator-decisions", "/api/operator/decisions/report?limit=200"),
    ("order-audits", "/api/execution/order-audits"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive Quant Lab live-beta closeout evidence.")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--symbol", default="KRW-BTC", help="KRW crypto market symbol")
    parser.add_argument(
        "--output-dir",
        default="artifacts/live-beta",
        help="Directory where live-beta archives are created.",
    )
    parser.add_argument(
        "--archive-name",
        help="Exact archive directory name. Defaults to YYYYMMDD-SYMBOL-beta-NNN.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Report row limit")
    parser.add_argument(
        "--backup-reference",
        help="Optional database backup path or external backup reference to record in the archive.",
    )
    parser.add_argument(
        "--operator-note",
        help="Optional operator closeout note to store in the archive README.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check backend reachability, live-lock state, and blocking alerts without writing an archive.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the preflight report as JSON. Requires --preflight.",
    )
    parser.add_argument(
        "--next-command-only",
        action="store_true",
        help="Print only the recommended next command from the preflight report. Requires --preflight.",
    )
    parser.add_argument(
        "--allow-live-enabled",
        action="store_true",
        help="Allow archive creation even when live trading still appears enabled.",
    )
    return parser.parse_args()


def validate_backup_reference(reference: str | None) -> str | None:
    if reference is None:
        return None
    cleaned = reference.strip()
    if not cleaned:
        raise ValueError("--backup-reference must not be empty when provided.")
    if cleaned in {"PATH_TO_BACKUP", "<backup-path>", "<backup-reference>", "BACKUP_REFERENCE"}:
        raise ValueError("--backup-reference must be a real backup path or external backup reference, not a placeholder.")
    return cleaned


def request_json(api_base: str, path: str) -> Any:
    url = api_base.rstrip("/") + path
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} failed with {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc
    return json.loads(body) if body else None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, markdown: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def market_slug(symbol: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9-]+", "-", symbol.upper().replace("/", "-"))
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "MARKET"


def next_archive_dir(output_dir: Path, symbol: str) -> Path:
    date_prefix = datetime.now().strftime("%Y%m%d")
    base_name = f"{date_prefix}-{market_slug(symbol)}-beta"
    for sequence in range(1, 1000):
        candidate = output_dir / f"{base_name}-{sequence:03d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No available live-beta archive sequence under {output_dir}")


def report_path(path: str, **params: Any) -> str:
    encoded = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
    return path + (f"?{encoded}" if encoded else "")


def blocking_alerts(alert_review: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in alert_review.get("items", [])
        if item.get("level") in {"error", "halt"} or item.get("source") == "paper_session_halt"
    ]


def add_preflight_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append({"id": check_id, "status": status, "message": message, "details": details or {}})


def live_beta_preflight_report(
    *,
    api_base: str,
    symbol: str,
    backup_reference: str | None,
    allow_live_enabled: bool,
    requester: Any = request_json,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    try:
        health = requester(api_base, "/api/health")
    except RuntimeError as exc:
        health = None
        add_preflight_check(checks, check_id="backend_health", status="fail", message=str(exc))
    else:
        add_preflight_check(
            checks,
            check_id="backend_health",
            status="pass",
            message="Backend health endpoint is reachable.",
            details={"response": health if isinstance(health, dict) else None},
        )

    try:
        settings = requester(api_base, "/api/execution/settings")
    except RuntimeError as exc:
        settings = None
        add_preflight_check(checks, check_id="execution_settings", status="fail", message=str(exc))
    else:
        if isinstance(settings, dict):
            live_trading_enabled = bool(settings.get("live_trading_enabled"))
            adapter_ready = bool(settings.get("adapter_ready"))
            live_locked = not live_trading_enabled and not adapter_ready
            add_preflight_check(
                checks,
                check_id="live_lock",
                status="pass" if live_locked or allow_live_enabled else "fail",
                message=(
                    "Live trading flags are locked."
                    if live_locked
                    else "Live trading still appears enabled; archive only with --allow-live-enabled."
                ),
                details={
                    "live_trading_enabled": live_trading_enabled,
                    "adapter_ready": adapter_ready,
                    "allow_live_enabled": allow_live_enabled,
                },
            )
        else:
            add_preflight_check(
                checks,
                check_id="execution_settings_payload",
                status="fail",
                message="Execution settings response was not a JSON object.",
            )

    try:
        alert_review = requester(api_base, "/api/alerts/review?include_acknowledged=true")
    except RuntimeError as exc:
        alert_review = None
        add_preflight_check(checks, check_id="alert_review", status="fail", message=str(exc))
    else:
        blocking = blocking_alerts(alert_review if isinstance(alert_review, dict) else {})
        add_preflight_check(
            checks,
            check_id="blocking_alerts",
            status="pass" if not blocking else "fail",
            message=(
                "No halt/error alerts are present."
                if not blocking
                else f"{len(blocking)} blocking alert(s) are present."
            ),
            details={"blocking_alert_ids": [str(item.get("id")) for item in blocking if item.get("id")]},
        )

    add_preflight_check(
        checks,
        check_id="backup_reference",
        status="pass" if backup_reference else "warn",
        message=(
            f"Backup reference will be recorded: {backup_reference}"
            if backup_reference
            else "No backup reference was provided; archive will record 'not provided'."
        ),
    )

    status = "pass" if all(check["status"] in {"pass", "warn"} for check in checks) else "fail"
    commands = {
        "backend_start_local": LOCAL_BACKEND_START_COMMAND,
        "backend_start_local_no_reload": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        "backend_start_docker": DOCKER_BACKEND_START_COMMAND,
        "backend_health_check": backend_health_check_command(api_base),
        "preflight": live_beta_preflight_command(
            api_base=api_base,
            symbol=symbol,
            backup_reference=backup_reference,
        ),
        "preflight_json": live_beta_preflight_json_command(
            api_base=api_base,
            symbol=symbol,
            backup_reference=backup_reference,
        ),
        "next_command_only": live_beta_next_command_only_command(
            api_base=api_base,
            symbol=symbol,
            backup_reference=backup_reference,
        ),
        "archive": live_beta_closeout_command(
            api_base=api_base,
            symbol=symbol,
            backup_reference=backup_reference,
        ),
        "final_gate": LIVE_BETA_FINAL_GATE_COMMAND,
    }
    return {
        "status": status,
        "api_base": api_base,
        "symbol": symbol,
        "backup_reference": backup_reference,
        "commands": commands,
        "recommended_next": recommended_preflight_next(checks=checks, status=status, commands=commands),
        "checks": checks,
    }


def recommended_preflight_next(
    *,
    checks: list[dict[str, Any]],
    status: str,
    commands: dict[str, str],
) -> dict[str, Any]:
    checks_by_id = {str(check.get("id")): check for check in checks}
    backend_health = checks_by_id.get("backend_health")
    if backend_health and backend_health.get("status") == "fail":
        return {
            "id": "start_backend",
            "reason_check_id": "backend_health",
            "action": "Start the backend, verify health, then rerun the live-beta preflight.",
            "command": commands["backend_start_local"],
            "follow_up_commands": {
                "Start local backend without reload": commands["backend_start_local_no_reload"],
                "Start Docker backend instead": commands["backend_start_docker"],
                "Check backend health": commands["backend_health_check"],
                "Rerun JSON preflight": commands["preflight_json"],
            },
        }

    live_lock = checks_by_id.get("live_lock")
    if live_lock and live_lock.get("status") == "fail":
        return {
            "id": "lock_live_flags",
            "reason_check_id": "live_lock",
            "action": "Lock live trading and adapter flags, then rerun the live-beta preflight.",
            "command": commands["preflight"],
            "follow_up_commands": {"Rerun JSON preflight": commands["preflight_json"]},
        }

    blocking_alerts_check = checks_by_id.get("blocking_alerts")
    if blocking_alerts_check and blocking_alerts_check.get("status") == "fail":
        return {
            "id": "resolve_blocking_alerts",
            "reason_check_id": "blocking_alerts",
            "action": "Resolve or acknowledge blocking halt/error alerts, then rerun the live-beta preflight.",
            "command": commands["preflight"],
            "follow_up_commands": {"Rerun JSON preflight": commands["preflight_json"]},
        }

    if status == "pass":
        return {
            "id": "archive_live_beta_closeout",
            "reason_check_id": None,
            "action": "Preflight passed; write the live-beta closeout archive.",
            "command": commands["archive"],
            "follow_up_commands": {"Run final live-beta gate": commands["final_gate"]},
        }

    return {
        "id": "rerun_preflight",
        "reason_check_id": None,
        "action": "Review failed checks, then rerun the live-beta preflight.",
        "command": commands["preflight"],
        "follow_up_commands": {"Rerun JSON preflight": commands["preflight_json"]},
    }


def print_preflight_report(report: dict[str, Any]) -> None:
    print(f"Live-beta closeout preflight: {report['status']}")
    print(f"API base: {report['api_base']}")
    print(f"Symbol: {report['symbol']}")
    for check in report["checks"]:
        print(f"{check['status'].upper():5} {check['id']}: {check['message']}")
    recommended_next = report.get("recommended_next")
    if isinstance(recommended_next, dict):
        print("Recommended next:")
        print(f"- action: {recommended_next.get('action')}")
        print(f"- command: {recommended_next.get('command')}")
        follow_ups = recommended_next.get("follow_up_commands")
        if isinstance(follow_ups, dict) and follow_ups:
            print("- follow-up commands:")
            for label, command in follow_ups.items():
                print(f"  - {label}: {command}")
    if report.get("commands"):
        print("Commands:")
        for name, command in report["commands"].items():
            print(f"- {name}: {command}")


def preflight_report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def recommended_next_command(report: dict[str, Any]) -> str | None:
    recommended_next = report.get("recommended_next")
    if not isinstance(recommended_next, dict):
        return None
    command = recommended_next.get("command")
    return command if isinstance(command, str) and command else None


def dry_run_record_ids(order_audits: Any) -> list[str]:
    if not isinstance(order_audits, list):
        return []
    return [
        str(record.get("id"))
        for record in order_audits
        if isinstance(record, dict) and record.get("status") == "dry_run" and record.get("id")
    ]


def write_archive_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Quant Lab Live-Beta Closeout Archive",
        "",
        f"Generated at: {manifest['generated_at']}",
        f"Status: {manifest['status']}",
        f"Symbol: {manifest['symbol']}",
        f"API base: `{manifest['api_base']}`",
        "",
        "## Safety",
        "",
        f"- Live trading enabled: {manifest['safety']['live_trading_enabled']}",
        f"- Adapter ready: {manifest['safety']['adapter_ready']}",
        f"- Blocking alert count: {manifest['safety']['blocking_alert_count']}",
        f"- Backup reference: {manifest.get('backup_reference') or 'not provided'}",
        "",
        "## Included Files",
        "",
    ]
    lines.extend(f"- `{item['path']}`: {item['description']}" for item in manifest["included"])
    if manifest.get("operator_note"):
        lines.extend(["", "## Operator Note", "", manifest["operator_note"], ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        args.backup_reference = validate_backup_reference(args.backup_reference)
    except ValueError as exc:
        print(str(exc))
        return 2
    args.symbol = args.symbol.upper()
    if not args.symbol.startswith("KRW-"):
        print("Live-beta closeout archive requires a KRW-* crypto market.")
        return 2
    if args.json and not args.preflight:
        print("--json requires --preflight.")
        return 2
    if args.next_command_only and not args.preflight:
        print("--next-command-only requires --preflight.")
        return 2
    if args.json and args.next_command_only:
        print("--json cannot be combined with --next-command-only.")
        return 2
    if args.preflight:
        report = live_beta_preflight_report(
            api_base=args.api_base,
            symbol=args.symbol,
            backup_reference=args.backup_reference,
            allow_live_enabled=bool(args.allow_live_enabled),
        )
        if args.next_command_only:
            command = recommended_next_command(report)
            if not command:
                print("No recommended next command is available.")
                return 1
            print(command)
            return 0
        if args.json:
            print(preflight_report_json(report))
        else:
            print_preflight_report(report)
        return 0 if report["status"] == "pass" else 1

    output_dir = Path(args.output_dir)
    final_archive_dir = output_dir / args.archive_name if args.archive_name else next_archive_dir(output_dir, args.symbol)
    archive_dir = output_dir / f".{final_archive_dir.name}.tmp"
    raw_dir = archive_dir / "raw-json"
    runbooks_dir = archive_dir / "runbooks"
    if final_archive_dir.exists():
        raise FileExistsError(f"Live-beta archive already exists: {final_archive_dir}")
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=False)
    raw_dir.mkdir(parents=True, exist_ok=True)
    runbooks_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    raw_payloads: dict[str, Any] = {}
    included: list[dict[str, str]] = []

    try:
        for label, path in RAW_ENDPOINTS:
            payload = request_json(args.api_base, path)
            raw_payloads[label] = payload
            file_path = raw_dir / f"{label}.json"
            write_json(file_path, payload)
            included.append({"path": str(file_path.relative_to(archive_dir)), "description": f"Raw {label} response"})

        drill = request_json(
            args.api_base,
            report_path("/api/research/crypto-live-beta-drill/report", symbol=args.symbol, limit=args.limit),
        )
        write_json(archive_dir / "02-crypto-live-beta-drill.json", drill)
        write_markdown(archive_dir / "02-crypto-live-beta-drill.md", str(drill.get("markdown", "")))
        included.extend(
            [
                {"path": "02-crypto-live-beta-drill.json", "description": "Crypto live-beta drill JSON"},
                {"path": "02-crypto-live-beta-drill.md", "description": "Crypto live-beta drill Markdown"},
            ]
        )

        strategy = request_json(
            args.api_base,
            report_path("/api/research/strategy-health/handoff-report", limit=args.limit),
        )
        write_json(archive_dir / "03-strategy-health-handoff.json", strategy)
        write_markdown(archive_dir / "03-strategy-health-handoff.md", str(strategy.get("markdown", "")))
        included.extend(
            [
                {"path": "03-strategy-health-handoff.json", "description": "Strategy health handoff JSON"},
                {"path": "03-strategy-health-handoff.md", "description": "Strategy health handoff Markdown"},
            ]
        )

        cutover = request_json(args.api_base, "/api/execution/cutover-checklist/runbook")
        write_json(archive_dir / "04-live-cutover-runbook.json", cutover)
        write_markdown(archive_dir / "04-live-cutover-runbook.md", str(cutover.get("markdown", "")))
        included.extend(
            [
                {"path": "04-live-cutover-runbook.json", "description": "Live cutover runbook JSON"},
                {"path": "04-live-cutover-runbook.md", "description": "Live cutover runbook Markdown"},
            ]
        )

        closeout = request_json(args.api_base, "/api/execution/post-cutover-monitor/closeout-report")
        write_json(archive_dir / "05-live-window-closeout.json", closeout)
        write_markdown(archive_dir / "05-live-window-closeout.md", str(closeout.get("markdown", "")))
        included.extend(
            [
                {"path": "05-live-window-closeout.json", "description": "Live-window closeout JSON"},
                {"path": "05-live-window-closeout.md", "description": "Live-window closeout Markdown"},
            ]
        )

        decisions = raw_payloads.get("operator-decisions", {})
        if isinstance(decisions, dict) and decisions.get("markdown"):
            write_markdown(archive_dir / "06-operator-decisions.md", str(decisions.get("markdown", "")))
            included.append({"path": "06-operator-decisions.md", "description": "Operator decision Markdown"})

        for record_id in dry_run_record_ids(raw_payloads.get("order-audits"))[:20]:
            try:
                runbook = request_json(
                    args.api_base,
                    f"/api/execution/order-audits/{urllib.parse.quote(record_id)}/runbook",
                )
            except RuntimeError:
                continue
            filename = str(runbook.get("filename") or f"dry-run-runbook-{record_id}.md")
            write_json(runbooks_dir / f"{record_id}.json", runbook)
            write_markdown(runbooks_dir / filename, str(runbook.get("markdown", "")))
            included.extend(
                [
                    {"path": f"runbooks/{record_id}.json", "description": f"Dry-run runbook JSON for {record_id}"},
                    {"path": f"runbooks/{filename}", "description": f"Dry-run runbook Markdown for {record_id}"},
                ]
            )

        settings = raw_payloads.get("execution-settings", {})
        alert_review = raw_payloads.get("alert-review", {})
        live_trading_enabled = bool(settings.get("live_trading_enabled")) if isinstance(settings, dict) else True
        adapter_ready = bool(settings.get("adapter_ready")) if isinstance(settings, dict) else True
        blocking = blocking_alerts(alert_review if isinstance(alert_review, dict) else {})
        live_locked = not live_trading_enabled and not adapter_ready
        archive_status = "pass" if (live_locked or args.allow_live_enabled) and not blocking else "fail"
        manifest = {
            "generated_at": generated_at,
            "status": archive_status,
            "api_base": args.api_base,
            "symbol": args.symbol,
            "archive_dir": str(final_archive_dir),
            "backup_reference": args.backup_reference,
            "operator_note": args.operator_note,
            "included": included,
            "safety": {
                "live_trading_enabled": live_trading_enabled,
                "adapter_ready": adapter_ready,
                "allow_live_enabled": bool(args.allow_live_enabled),
                "blocking_alert_count": len(blocking),
                "blocking_alert_ids": [str(item.get("id")) for item in blocking if item.get("id")],
            },
        }
        write_json(archive_dir / "manifest.json", manifest)
        write_archive_readme(archive_dir / "README.md", manifest)
        archive_dir.rename(final_archive_dir)
    except Exception:
        shutil.rmtree(archive_dir, ignore_errors=True)
        raise

    print(f"Live-beta closeout archive: {final_archive_dir}")
    print(f"Status: {archive_status}")
    print(f"Live locked: {live_locked}")
    print(f"Blocking alerts: {len(blocking)}")
    if args.backup_reference:
        print(f"Backup reference: {args.backup_reference}")
    return 1 if archive_status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
