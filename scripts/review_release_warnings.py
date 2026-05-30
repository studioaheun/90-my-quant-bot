#!/usr/bin/env python3
"""Create or apply operator actions for release warning triage."""

from __future__ import annotations

import argparse
import json
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.handoff_commands import (
        read_only_warning_review_command as warning_review_command,
        warning_review_apply_command as warning_apply_command,
        warning_review_artifacts_only_command as warning_artifacts_only_command,
        warning_backend_guidance_payload as shared_warning_backend_guidance_payload,
        warning_review_gate_summary_json_command as warning_gate_summary_json_command,
        warning_review_gate_json_command as warning_gate_json_command,
        warning_review_json_command as warning_json_command,
        warning_review_next_command_only_command as warning_next_command_only_command,
        warning_review_pre_approval_sequence_command as warning_pre_approval_sequence_command,
        warning_review_summary_json_command as warning_summary_json_command,
    )
    from scripts.release_artifacts import latest_warning_triage_package_dir
except ModuleNotFoundError:  # pragma: no cover - supports running from scripts/
    from handoff_commands import (
        read_only_warning_review_command as warning_review_command,
        warning_review_apply_command as warning_apply_command,
        warning_review_artifacts_only_command as warning_artifacts_only_command,
        warning_backend_guidance_payload as shared_warning_backend_guidance_payload,
        warning_review_gate_summary_json_command as warning_gate_summary_json_command,
        warning_review_gate_json_command as warning_gate_json_command,
        warning_review_json_command as warning_json_command,
        warning_review_next_command_only_command as warning_next_command_only_command,
        warning_review_pre_approval_sequence_command as warning_pre_approval_sequence_command,
        warning_review_summary_json_command as warning_summary_json_command,
    )
    from release_artifacts import latest_warning_triage_package_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Quant Lab release warning triage.")
    parser.add_argument(
        "--package-dir",
        help="Evidence package directory. Defaults to the latest artifacts/evidence-packages/* package.",
    )
    parser.add_argument(
        "--packages-dir",
        default="artifacts/evidence-packages",
        help="Directory containing evidence package directories",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument(
        "--status",
        choices=("acknowledged", "dismissed"),
        default="acknowledged",
        help="Alert review status to submit when --apply is used",
    )
    parser.add_argument(
        "--note",
        default="Reviewed from release warning triage; warning accepted for controlled paper/live-beta preparation.",
        help="Operator note for alert acknowledgements",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="POST acknowledgements to a running backend. Without this flag the command is dry-run only.",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        help="Required with --apply after the operator reviews release-warning-operator-checklist.md.",
    )
    parser.add_argument(
        "--output-prefix",
        help="Output prefix for action plan files. Defaults to release-warning-actions in the package.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help=(
            "Print the warning action plan without writing action/checklist files or refreshing the package tarball. "
            "Use this after checksums have been published."
        ),
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the warning action plan as JSON without writing files. Implies --no-write.",
    )
    parser.add_argument(
        "--summary-json-only",
        action="store_true",
        help="Print compact warning action status/counts and recommended next command as JSON. Implies --no-write.",
    )
    parser.add_argument(
        "--next-command-only",
        action="store_true",
        help=(
            "Print only the recommended next warning-review command without writing files. "
            "Use after reviewing JSON/checklist context."
        ),
    )
    parser.add_argument(
        "--pre-approval-sequence-only",
        action="store_true",
        help=(
            "Print only apply-free warning review commands, one per line, for operator review before "
            "any --apply --operator-approved command is considered."
        ),
    )
    parser.add_argument(
        "--review-artifacts-only",
        action="store_true",
        help=(
            "Print only the existing warning action plan and operator checklist paths, one per line. "
            "Fails if either review artifact is missing. Implies --no-write."
        ),
    )
    parser.add_argument(
        "--fail-if-action-needed",
        action="store_true",
        help=(
            "Exit non-zero after printing or writing the plan when warning acknowledgements, failed "
            "acknowledgements, or a live-beta archive still need operator action."
        ),
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def request_json(
    *,
    api_base: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    url = api_base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc
    return json.loads(body) if body else None


def acknowledgement_payload(*, status: str, note: str, alert: dict[str, Any]) -> dict[str, str]:
    title = alert.get("title") or alert.get("id")
    return {
        "status": status,
        "note": f"{note} Alert: {title}",
    }


def write_operator_checklist(*, package_dir: Path, plan: dict[str, Any], path: Path) -> None:
    lines = [
        "# Release Warning Operator Checklist",
        "",
        f"Generated at: {plan['generated_at']}",
        f"Package: {package_dir}",
        f"Action plan: {plan['markdown_path']}",
        "",
        "## Purpose",
        "",
        "Use this checklist before applying warning acknowledgements. It is intentionally separate from the dry-run action plan so an operator can record the decision path before changing backend alert state.",
        "",
        "## Pre-Apply Checks",
        "",
        "- [ ] Backend is running at the intended `--api-base`.",
        "- [ ] The package path matches the evidence package under review.",
        "- [ ] Live trading flags remain locked unless an approved live-beta window is active.",
        "- [ ] Warning alerts below are understood as non-blocking preparation findings, not ignored production failures.",
        "",
        "## Apply Command",
        "",
        "Run only after the operator checks the relevant boxes below:",
        "",
        "```bash",
        warning_apply_command(package_dir),
        "```",
        "",
        "## Alert Decisions",
        "",
    ]
    actions = plan.get("alert_actions", [])
    if not actions:
        lines.append("- No warning alerts require operator decisions.")
    for index, action in enumerate(actions, start=1):
        lines.extend(
            [
                f"### {index}. {action.get('title') or action.get('alert_id')}",
                "",
                f"- Alert id: {action.get('alert_id')}",
                f"- Source: {action.get('source')}",
                f"- Rule: {action.get('rule')}",
                f"- Symbol: {action.get('symbol')}",
                f"- Recommended action: {action.get('recommended_action')}",
                "",
                "- [ ] Acknowledge as an expected guardrail for this preparation package.",
                "- [ ] Dismiss as not relevant to this release package.",
                "- [ ] Remediate first, then regenerate the release package.",
                "",
            ]
        )
        if action.get("source") == "broker_paper_submission":
            lines.extend(
                [
                    "Broker-paper submission check:",
                    "",
                    "- [ ] Confirm the blocked Alpaca paper submission was intentional.",
                    "- [ ] If Alpaca paper submission evidence is required, rerun with `paper_submit_confirmation=true` before approving.",
                    "",
                ]
            )
        if action.get("source") == "paper_fill_drift":
            lines.extend(
                [
                    "Paper-fill quality check:",
                    "",
                    "- [ ] Keep the stock/ETF route in paper review until at least three linked paper fill notes exist.",
                    "- [ ] Do not mark the stock/ETF handoff approved until the paper fill quality gate is ready.",
                    "",
                ]
            )

    live_beta = plan.get("live_beta_archive", {})
    lines.extend(
        [
            "## Live Beta Archive",
            "",
            f"- Status: {live_beta.get('status')}",
            f"- Recommended action: {live_beta.get('recommended_action')}",
            "- [ ] If no real live-beta window has run yet, keep this as a preparation warning.",
            "- [ ] After a real live-beta window, archive closeout evidence and rerun the final live-beta gate.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def apply_acknowledgement(
    *,
    api_base: str,
    status: str,
    note: str,
    alert: dict[str, Any],
) -> dict[str, Any]:
    alert_id = str(alert["id"])
    response = request_json(
        api_base=api_base,
        method="POST",
        path=f"/api/alerts/review/{urllib.parse.quote(alert_id, safe='')}/acknowledge",
        payload=acknowledgement_payload(status=status, note=note, alert=alert),
    )
    return {
        "alert_id": alert_id,
        "status": "applied",
        "request_status": status,
        "response": response,
    }


def write_outputs(
    *,
    package_dir: Path,
    output_prefix: Path,
    plan: dict[str, Any],
) -> None:
    json_path = output_prefix.with_suffix(".json")
    markdown_path = output_prefix.with_suffix(".md")
    checklist_path = output_prefix.parent / "release-warning-operator-checklist.md"
    plan["json_path"] = str(json_path)
    plan["markdown_path"] = str(markdown_path)
    plan["operator_checklist_path"] = str(checklist_path)
    json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Release Warning Actions",
        "",
        f"Generated at: {plan['generated_at']}",
        f"Package: {package_dir}",
        f"Mode: {plan['mode']}",
        f"Status: {plan['status']}",
        "",
        "## Summary",
        "",
        f"- Warning alerts: {plan['summary']['warning_alerts']}",
        f"- Planned acknowledgements: {plan['summary']['planned']}",
        f"- Applied acknowledgements: {plan['summary']['applied']}",
        f"- Failed acknowledgements: {plan['summary']['failed']}",
        f"- Live beta archive missing: {'yes' if plan['summary']['live_beta_archive_missing'] else 'no'}",
        f"- Action needed: {'yes' if plan['summary']['action_needed'] else 'no'}",
        "",
        "## Commands",
        "",
        "```bash",
        plan["commands"]["review"],
        plan["commands"]["json"],
        plan["commands"]["gate_json"],
        plan["commands"]["summary_json"],
        plan["commands"]["gate_summary_json"],
        plan["commands"]["pre_approval_sequence"],
        plan["commands"]["review_artifacts_only"],
        plan["commands"]["next_command_only"],
        plan["commands"]["apply"],
        "```",
        "",
        "## Alert Actions",
        "",
    ]
    if not plan["alert_actions"]:
        lines.append("- No warning alert actions were required.")
    else:
        for index, action in enumerate(plan["alert_actions"], start=1):
            lines.extend(
                [
                    f"### {index}. {action.get('title') or action.get('alert_id')}",
                    "",
                    f"- Alert id: {action.get('alert_id')}",
                    f"- Source: {action.get('source')}",
                    f"- Rule: {action.get('rule')}",
                    f"- Symbol: {action.get('symbol')}",
                    f"- Mode: {action.get('mode')}",
                    f"- Status: {action.get('status')}",
                    f"- Recommended action: {action.get('recommended_action')}",
                    f"- Operator note: {action.get('operator_note')}",
                    "",
                ]
            )
            if action.get("error"):
                lines.extend([f"- Error: {action['error']}", ""])

    lines.extend(
        [
            "## Live Beta Archive",
            "",
            f"- Status: {plan['live_beta_archive']['status']}",
            f"- Recommended action: {plan['live_beta_archive']['recommended_action']}",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    write_operator_checklist(package_dir=package_dir, plan=plan, path=checklist_path)


def action_needed_summary(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    summary = plan.get("summary", {})
    reasons: list[str] = []
    if int(summary.get("failed") or 0) > 0:
        reasons.append("failed_acknowledgements")
    if int(summary.get("planned") or 0) > 0:
        reasons.append("planned_acknowledgements")
    if bool(summary.get("live_beta_archive_missing")):
        reasons.append("live_beta_archive")
    return bool(reasons), reasons


def backend_guidance_payload() -> dict[str, str]:
    return shared_warning_backend_guidance_payload()


def recommended_next_action(plan: dict[str, Any]) -> dict[str, Any]:
    summary = plan.get("summary", {})
    commands = plan.get("commands", {})
    review_artifacts = {
        "action_plan": plan.get("markdown_path"),
        "operator_checklist": plan.get("operator_checklist_path"),
    }
    if int(summary.get("failed") or 0) > 0:
        return {
            "id": "review_failed_warning_actions",
            "reason": "failed_acknowledgements",
            "action": "Review failed warning acknowledgements before retrying.",
            "command": commands.get("review"),
            "follow_up_commands": {"Gate warning action plan JSON": commands.get("gate_json")},
            "requires_operator_approval": False,
            "review_artifacts": review_artifacts,
        }
    if int(summary.get("planned") or 0) > 0:
        return {
            "id": "apply_reviewed_warning_actions",
            "reason": "planned_acknowledgements",
            "action": "After operator checklist review, apply the planned warning acknowledgements.",
            "command": commands.get("apply"),
            "follow_up_commands": {"Gate warning action plan JSON": commands.get("gate_json")},
            "requires_operator_approval": True,
            "review_artifacts": review_artifacts,
            "backend": backend_guidance_payload(),
        }
    if bool(summary.get("live_beta_archive_missing")):
        return {
            "id": "review_live_beta_archive_warning",
            "reason": "live_beta_archive",
            "action": "Review the live-beta archive warning and run the live-beta closeout flow if applicable.",
            "command": commands.get("review"),
            "follow_up_commands": {"Gate warning action plan JSON": commands.get("gate_json")},
            "requires_operator_approval": False,
            "review_artifacts": review_artifacts,
        }
    return {
        "id": "gate_warning_actions_clear",
        "reason": None,
        "action": "Warning action plan is clear; run the JSON gate to confirm.",
        "command": commands.get("gate_json"),
        "follow_up_commands": {},
        "requires_operator_approval": False,
        "review_artifacts": review_artifacts,
    }


def recommended_next_command(plan: dict[str, Any]) -> str | None:
    recommended_next = plan.get("recommended_next")
    if not isinstance(recommended_next, dict):
        return None
    command = recommended_next.get("command")
    return command if isinstance(command, str) and command else None


def pre_approval_sequence(plan: dict[str, Any]) -> list[str]:
    commands = plan.get("commands") if isinstance(plan.get("commands"), dict) else {}
    return [
        command
        for command in (
            commands.get("summary_json"),
            commands.get("review_artifacts_only"),
        )
        if isinstance(command, str) and command
    ]


def summary_payload(plan: dict[str, Any]) -> dict[str, Any]:
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    recommended_next = plan.get("recommended_next") if isinstance(plan.get("recommended_next"), dict) else {}
    commands = plan.get("commands") if isinstance(plan.get("commands"), dict) else {}
    return {
        "status": plan.get("status"),
        "package_dir": plan.get("package_dir"),
        "triage_path": plan.get("triage_path"),
        "json_path": plan.get("json_path"),
        "markdown_path": plan.get("markdown_path"),
        "operator_checklist_path": plan.get("operator_checklist_path"),
        "action_needed": bool(summary.get("action_needed")),
        "action_needed_reasons": summary.get("action_needed_reasons") or [],
        "counts": {
            "warning_alerts": summary.get("warning_alerts", 0),
            "planned": summary.get("planned", 0),
            "applied": summary.get("applied", 0),
            "failed": summary.get("failed", 0),
            "live_beta_archive_missing": bool(summary.get("live_beta_archive_missing")),
        },
        "recommended_next": {
            "id": recommended_next.get("id"),
            "reason": recommended_next.get("reason"),
            "command": recommended_next.get("command"),
            "requires_operator_approval": bool(recommended_next.get("requires_operator_approval")),
            "review_artifacts": recommended_next.get("review_artifacts") or {},
            "backend": recommended_next.get("backend") or {},
        },
        "backend": plan.get("backend") or recommended_next.get("backend") or {},
        "commands": {
            key: commands[key]
            for key in (
                "summary_json",
                "gate_summary_json",
                "pre_approval_sequence",
                "next_command_only",
                "review_artifacts_only",
                "apply",
            )
            if key in commands
        },
    }


def review_artifact_paths(plan: dict[str, Any]) -> list[Path]:
    return [
        Path(str(plan["markdown_path"])),
        Path(str(plan["operator_checklist_path"])),
    ]


def print_review_artifacts_only(plan: dict[str, Any]) -> int:
    paths = review_artifact_paths(plan)
    for path in paths:
        print(path)
    return 0 if all(path.is_file() for path in paths) else 1


def refresh_package_tarball(package_dir: Path) -> Path | None:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = read_json(manifest_path)
    tarball = manifest.get("tarball")
    if not isinstance(tarball, str) or not tarball:
        return None
    tarball_path = Path(tarball)
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(package_dir, arcname=package_dir.name)
    return tarball_path


def main() -> int:
    args = parse_args()
    read_only = (
        args.no_write
        or args.json_only
        or args.summary_json_only
        or args.next_command_only
        or args.pre_approval_sequence_only
        or args.review_artifacts_only
    )
    if args.json_only and args.apply:
        print("--json-only cannot be combined with --apply.")
        return 2
    if args.summary_json_only and args.apply:
        print("--summary-json-only cannot be combined with --apply.")
        return 2
    if args.next_command_only and args.apply:
        print("--next-command-only cannot be combined with --apply.")
        return 2
    if args.pre_approval_sequence_only and args.apply:
        print("--pre-approval-sequence-only cannot be combined with --apply.")
        return 2
    if args.review_artifacts_only and args.apply:
        print("--review-artifacts-only cannot be combined with --apply.")
        return 2
    if args.next_command_only and args.json_only:
        print("--json-only cannot be combined with --next-command-only.")
        return 2
    if args.next_command_only and args.summary_json_only:
        print("--summary-json-only cannot be combined with --next-command-only.")
        return 2
    if args.review_artifacts_only and args.json_only:
        print("--json-only cannot be combined with --review-artifacts-only.")
        return 2
    if args.review_artifacts_only and args.summary_json_only:
        print("--summary-json-only cannot be combined with --review-artifacts-only.")
        return 2
    if args.review_artifacts_only and args.next_command_only:
        print("--next-command-only cannot be combined with --review-artifacts-only.")
        return 2
    if args.pre_approval_sequence_only and args.json_only:
        print("--json-only cannot be combined with --pre-approval-sequence-only.")
        return 2
    if args.pre_approval_sequence_only and args.summary_json_only:
        print("--summary-json-only cannot be combined with --pre-approval-sequence-only.")
        return 2
    if args.pre_approval_sequence_only and args.next_command_only:
        print("--next-command-only cannot be combined with --pre-approval-sequence-only.")
        return 2
    if args.pre_approval_sequence_only and args.review_artifacts_only:
        print("--review-artifacts-only cannot be combined with --pre-approval-sequence-only.")
        return 2
    if args.json_only and args.summary_json_only:
        print("--json-only cannot be combined with --summary-json-only.")
        return 2
    if args.apply and not args.operator_approved:
        print("--operator-approved is required with --apply after reviewing release-warning-operator-checklist.md.")
        return 2
    if args.no_write and args.apply:
        print("--no-write cannot be combined with --apply.")
        return 2
    if read_only and args.output_prefix:
        print("--no-write cannot be combined with --output-prefix.")
        return 2
    package_dir = Path(args.package_dir) if args.package_dir else latest_warning_triage_package_dir(Path(args.packages_dir))
    package_dir = package_dir.absolute()
    triage_path = package_dir / "release-warning-triage.json"
    triage = read_json(triage_path)
    output_prefix = Path(args.output_prefix) if args.output_prefix else package_dir / "release-warning-actions"

    actions: list[dict[str, Any]] = []
    failures = 0
    for alert in triage.get("warning_alerts", []):
        action = {
            "alert_id": alert.get("id"),
            "title": alert.get("title"),
            "source": alert.get("source"),
            "rule": alert.get("rule"),
            "symbol": alert.get("symbol"),
            "recommended_action": alert.get("recommended_action"),
            "operator_note": acknowledgement_payload(status=args.status, note=args.note, alert=alert)["note"],
            "mode": "apply" if args.apply else "dry_run",
            "status": "planned",
            "response": None,
            "error": None,
        }
        if args.apply:
            try:
                result = apply_acknowledgement(
                    api_base=args.api_base,
                    status=args.status,
                    note=args.note,
                    alert=alert,
                )
                action["status"] = result["status"]
                action["response"] = result["response"]
            except RuntimeError as exc:
                failures += 1
                action["status"] = "failed"
                action["error"] = str(exc)
        actions.append(action)

    live_beta_archive_missing = bool(triage.get("summary", {}).get("live_beta_archive_missing"))
    planned_count = sum(1 for action in actions if action["status"] == "planned")
    applied_count = sum(1 for action in actions if action["status"] == "applied")
    if failures:
        plan_status = "fail"
    elif args.apply and actions:
        plan_status = "applied"
    elif planned_count or live_beta_archive_missing:
        plan_status = "planned"
    else:
        plan_status = "clear"

    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir),
        "triage_path": str(triage_path),
        "api_base": args.api_base,
        "mode": "apply" if args.apply else "dry_run",
        "operator_approved": bool(args.operator_approved),
        "status": plan_status,
        "json_path": str(output_prefix.with_suffix(".json")),
        "markdown_path": str(output_prefix.with_suffix(".md")),
        "operator_checklist_path": str(output_prefix.parent / "release-warning-operator-checklist.md"),
        "summary": {
            "warning_alerts": len(actions),
            "planned": planned_count,
            "applied": applied_count,
            "failed": failures,
            "live_beta_archive_missing": live_beta_archive_missing,
        },
        "live_beta_archive": triage.get("live_beta_archive", {}),
        "commands": {
            "review": warning_review_command(package_dir),
            "json": warning_json_command(package_dir),
            "gate_json": warning_gate_json_command(package_dir),
            "summary_json": warning_summary_json_command(package_dir),
            "gate_summary_json": warning_gate_summary_json_command(package_dir),
            "pre_approval_sequence": warning_pre_approval_sequence_command(package_dir),
            "apply": warning_apply_command(package_dir),
            "next_command_only": warning_next_command_only_command(package_dir),
            "review_artifacts_only": warning_artifacts_only_command(package_dir),
        },
        "alert_actions": actions,
    }
    action_needed, action_needed_reasons = action_needed_summary(plan)
    plan["summary"]["action_needed"] = action_needed
    plan["summary"]["action_needed_reasons"] = action_needed_reasons
    plan["recommended_next"] = recommended_next_action(plan)
    plan["backend"] = (
        plan["recommended_next"].get("backend")
        if isinstance(plan["recommended_next"], dict)
        else {}
    ) or {}
    if args.next_command_only:
        command = recommended_next_command(plan)
        if not command:
            print("No recommended next warning-review command is available.")
            return 1
        print(command)
        return 1 if args.fail_if_action_needed and action_needed else 0
    if args.pre_approval_sequence_only:
        for command in pre_approval_sequence(plan):
            print(command)
        return 1 if args.fail_if_action_needed and action_needed else 0
    if args.review_artifacts_only:
        return print_review_artifacts_only(plan)
    if args.summary_json_only:
        print(json.dumps(summary_payload(plan), indent=2, sort_keys=True))
        return 1 if failures or (args.fail_if_action_needed and action_needed) else 0
    if args.json_only:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 1 if failures or (args.fail_if_action_needed and action_needed) else 0

    tarball_path = None
    if not read_only:
        write_outputs(package_dir=package_dir, output_prefix=output_prefix, plan=plan)
        tarball_path = refresh_package_tarball(package_dir)

    for action in actions:
        print(f"{action['status'].upper():8} {action['alert_id']}: {action['recommended_action']}")
    if action_needed:
        print(f"Action needed: yes ({', '.join(action_needed_reasons)})")
    else:
        print("Action needed: no")
    if read_only:
        print("Warning action plan: not written (--no-write)")
        print("Operator checklist: not written (--no-write)")
        existing_action_path = output_prefix.with_suffix(".md")
        existing_checklist_path = output_prefix.parent / "release-warning-operator-checklist.md"
        if existing_action_path.is_file():
            print(f"Existing warning action plan: {existing_action_path}")
        if existing_checklist_path.is_file():
            print(f"Existing operator checklist: {existing_checklist_path}")
        recommended_next = plan.get("recommended_next", {})
        if isinstance(recommended_next, dict):
            action = recommended_next.get("action")
            command = recommended_next.get("command")
            requires_operator_approval = bool(recommended_next.get("requires_operator_approval"))
            backend = recommended_next.get("backend")
            if action:
                print(f"Recommended next action: {action}")
            if command:
                print(f"Recommended next command: {command}")
            print(
                "Recommended next requires operator approval: "
                f"{'yes' if requires_operator_approval else 'no'}"
            )
            if isinstance(backend, dict) and backend:
                for key, label in (
                    ("local_start_command", "Backend local start"),
                    ("local_start_no_reload_command", "Backend local start no reload"),
                    ("docker_start_command", "Backend Docker start"),
                    ("health_check_command", "Backend health check"),
                ):
                    value = backend.get(key)
                    if isinstance(value, str) and value:
                        print(f"{label}: {value}")
        print(f"Apply command after checklist review: {warning_apply_command(package_dir)}")
    else:
        print(f"Warning action plan: {output_prefix.with_suffix('.md')}")
        print(f"Operator checklist: {output_prefix.parent / 'release-warning-operator-checklist.md'}")
    if tarball_path:
        print(f"Refreshed tarball: {tarball_path}")
    return 1 if failures or (args.fail_if_action_needed and action_needed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
