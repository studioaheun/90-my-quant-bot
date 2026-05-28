"""Shared command builders for release handoff artifacts."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Mapping


def shell_arg(value: Path | str) -> str:
    return shlex.quote(str(value))


REPO_URL_PLACEHOLDER = "REPLACE_WITH_REPO_URL"
LEGACY_REPO_URL_PLACEHOLDER = "<repo-url>"
GENERIC_REPO_URL_PLACEHOLDER = "REPO_URL"
ENV_REPO_URL_PLACEHOLDER = "GIT_ORIGIN_URL"
REPO_URL_PLACEHOLDERS = (
    REPO_URL_PLACEHOLDER,
    LEGACY_REPO_URL_PLACEHOLDER,
    GENERIC_REPO_URL_PLACEHOLDER,
    ENV_REPO_URL_PLACEHOLDER,
)
LIVE_BETA_BACKUP_REFERENCE_EXAMPLE = "/backups/quant-lab.sqlite3"
LOCAL_WARNING_GATE_COMMAND = "python3 scripts/release_gate.py --skip-docker --run-smoke"
CONNECTED_STRICT_GATE_COMMAND = "python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth"
LIVE_BETA_FINAL_GATE_COMMAND = f"{CONNECTED_STRICT_GATE_COMMAND} --require-live-beta"
LOCAL_BACKEND_START_COMMAND = "cd backend && . .venv/bin/activate && uvicorn app.main:app --reload"
LOCAL_BACKEND_START_NO_RELOAD_COMMAND = "cd backend && . .venv/bin/activate && uvicorn app.main:app"
DOCKER_BACKEND_START_COMMAND = "docker compose start backend"
DOCKER_SETUP_COMMAND = "brew install --cask docker && open -a Docker && docker compose version"
GITHUB_CLI_SETUP_COMMAND = "brew install gh && gh auth login && gh auth setup-git && gh auth status"

LANE_READINESS_FIELDS = (
    "status",
    "issue_ids",
    "next_setup",
    "next_setup_command",
    "setup_sequence",
    "verify_sequence",
    "command_sequence",
    "json_command",
    "command_only_gate",
    "setup_sequence_command",
    "command_sequence_command",
    "setup_sequence_preview_command",
    "command_sequence_preview_command",
    "json_gate",
    "external_summary_json",
    "external_strict_summary_json",
)

LANE_REVIEW_FIELDS = (
    "status",
    "action_needed",
    "issue_ids",
    "next_command",
    "requires_operator_approval",
    "summary_json",
    "gate_summary_json",
    "pre_approval_sequence_command",
    "gate_json",
    "next_command_gate",
    "review_artifacts_command",
    "review_artifacts",
    "review_sequence_command",
    "pre_approval_review_sequence",
    "review_sequence",
    "backend",
)

SUPPORTING_COMMAND_LABEL_ORDER = (
    "Export repo URL example",
    "Show external readiness summary JSON",
    "Gate external readiness summary JSON",
    "Show local readiness setup sequence",
    "Show local readiness command sequence",
    "Preview local readiness setup sequence",
    "Preview local readiness command sequence",
    "Show connected-runner command only from env",
    "Start local backend",
    "Start local backend without reload",
    "Start Docker backend",
    "Check backend health",
    "Show warning pre-approval sequence",
    "Show warning summary JSON",
    "Show warning review artifact paths",
    "Show warning recommended next command",
    "Gate warning summary JSON",
    "Gate warning recommended next command",
)
SUPPORTING_COMMAND_LABEL_PRIORITY = {
    label: index for index, label in enumerate(SUPPORTING_COMMAND_LABEL_ORDER)
}


def dict_payload(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def list_payload(payload: Any) -> list[Any]:
    return payload if isinstance(payload, list) else []


def compact_lane_context(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    source_payload = dict_payload(source)
    context: dict[str, Any] = {}
    for field in fields:
        value = source_payload.get(field)
        if value is None or value == [] or value == {}:
            continue
        context[field] = value
    return context


def ordered_supporting_command_labels(labels: Any) -> list[str]:
    label_values = [str(label) for label in labels if isinstance(label, str) and label]
    return sorted(
        label_values,
        key=lambda label: (SUPPORTING_COMMAND_LABEL_PRIORITY.get(label, len(SUPPORTING_COMMAND_LABEL_ORDER)), label),
    )


def ordered_supporting_commands(supporting_commands: Mapping[str, Any]) -> dict[str, str]:
    command_payload = dict_payload(supporting_commands)
    commands: dict[str, str] = {}
    for label in ordered_supporting_command_labels(command_payload):
        command = command_payload.get(label)
        if isinstance(command, str) and command:
            commands[label] = command
    return commands


def owner_lanes_summary(
    *,
    remaining_by_owner: Mapping[str, Any],
    next_commands_by_owner: Mapping[str, Any],
    completion_plan: list[Mapping[str, Any]],
    local_readiness: Mapping[str, Any] | None = None,
    warning_review: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    owners = list(remaining_by_owner)
    for item in completion_plan:
        owner = item.get("owner")
        if isinstance(owner, str) and owner not in owners:
            owners.append(owner)
    for owner in next_commands_by_owner:
        if isinstance(owner, str) and owner not in owners:
            owners.append(owner)

    lanes: dict[str, dict[str, Any]] = {}
    for owner in owners:
        owner_plan = [dict_payload(item) for item in completion_plan if item.get("owner") == owner]
        next_entry = dict_payload(next_commands_by_owner.get(owner))
        first_plan = owner_plan[0] if owner_plan else {}

        review_artifacts: dict[str, str] = {}
        for item in owner_plan:
            artifacts = dict_payload(item.get("review_artifacts"))
            if artifacts:
                review_artifacts = {
                    str(label): path
                    for label, path in sorted(artifacts.items())
                    if isinstance(path, str) and path
                }
                break
        if not review_artifacts:
            artifacts = dict_payload(next_entry.get("review_artifacts"))
            review_artifacts = {
                str(label): path
                for label, path in sorted(artifacts.items())
                if isinstance(path, str) and path
            }

        supporting_commands = dict_payload(next_entry.get("supporting_commands"))
        commands: dict[str, Any] = {}
        next_command = next_entry.get("command") or first_plan.get("command")
        if isinstance(next_command, str) and next_command:
            commands["next"] = next_command
        automation_command = next_entry.get("automation_command") or first_plan.get("automation_command")
        if isinstance(automation_command, str) and automation_command:
            commands["automation"] = automation_command
        full_flow_command = next_entry.get("full_flow_command") or first_plan.get("full_flow_command")
        if isinstance(full_flow_command, str) and full_flow_command:
            commands["full_flow"] = full_flow_command
        if supporting_commands:
            commands["supporting"] = ordered_supporting_commands(supporting_commands)

        lane: dict[str, Any] = {
            "remaining_items": remaining_by_owner.get(owner, len(owner_plan)),
            "remaining_ids": [item["id"] for item in owner_plan if isinstance(item.get("id"), str)],
            "next_item_id": next_entry.get("id") or first_plan.get("id"),
            "status": next_entry.get("status") or first_plan.get("status"),
            "mode": first_plan.get("mode"),
            "requirements": (
                first_plan.get("requirements")
                if isinstance(first_plan.get("requirements"), list)
                else []
            ),
            "next_requires_operator_approval": bool(first_plan.get("requires_operator_approval")),
            "requires_operator_approval": any(bool(item.get("requires_operator_approval")) for item in owner_plan),
            "review_artifacts": review_artifacts,
            "supporting_command_labels": ordered_supporting_command_labels(supporting_commands),
            "commands": commands,
            "has_automation_command": "automation" in commands,
            "has_full_flow_command": "full_flow" in commands,
        }
        if owner == "connected runner":
            command_values = [
                value
                for key in ("next", "automation", "full_flow")
                if isinstance((value := commands.get(key)), str) and value
            ]
            if any(REPO_URL_PLACEHOLDER in value for value in command_values):
                export_command = supporting_commands.get("Export repo URL example")
                command_gate = supporting_commands.get("Show connected-runner command only from env")
                json_gate = commands.get("automation")
                lane["repo_url"] = {
                    "required": True,
                    "placeholder": REPO_URL_PLACEHOLDER,
                    "export_command": (
                        export_command
                        if isinstance(export_command, str) and export_command
                        else repo_url_export_example_command()
                    ),
                    "note": (
                        f"Replace {REPO_URL_PLACEHOLDER} with a real HTTPS, SSH, or "
                        "scp-style git remote URL before running connected-runner commands."
                    ),
                }
                if isinstance(command_gate, str) and command_gate:
                    lane["repo_url"]["command_gate"] = command_gate
                if isinstance(json_gate, str) and json_gate:
                    lane["repo_url"]["json_gate"] = json_gate
            readiness = compact_lane_context(local_readiness, LANE_READINESS_FIELDS)
            if readiness:
                lane["readiness"] = readiness
        if owner == "operator":
            review = compact_lane_context(warning_review, LANE_REVIEW_FIELDS)
            if review:
                lane["review"] = review
        lanes[owner] = lane
    return lanes


def backend_health_check_command(api_base: str = "http://localhost:8000") -> str:
    return f"curl -fsS {shell_arg(api_base.rstrip('/') + '/api/health')}"


def warning_backend_guidance_payload(api_base: str = "http://localhost:8000") -> dict[str, str]:
    return {
        "backend": "start the backend before applying reviewed warning actions",
        "local_start_command": LOCAL_BACKEND_START_COMMAND,
        "local_start_no_reload_command": LOCAL_BACKEND_START_NO_RELOAD_COMMAND,
        "docker_start_command": DOCKER_BACKEND_START_COMMAND,
        "health_check_command": backend_health_check_command(api_base),
    }


def git_origin_setup_command(
    repo_url: Path | str = REPO_URL_PLACEHOLDER,
    *,
    git_command: str = "git",
) -> str:
    quoted_repo_url = shell_arg(repo_url)
    return (
        f"if {git_command} remote get-url origin >/dev/null 2>&1; "
        f"then {git_command} remote set-url origin {quoted_repo_url}; "
        f"else {git_command} remote add origin {quoted_repo_url}; fi"
    )


def live_beta_closeout_command(
    *,
    api_base: str = "http://localhost:8000",
    symbol: str = "KRW-BTC",
    backup_reference: str | None = LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
) -> str:
    command = (
        "python3 scripts/archive_live_beta_closeout.py "
        f"--api-base {shell_arg(api_base)} --symbol {shell_arg(symbol)}"
    )
    if backup_reference:
        command += f" --backup-reference {shell_arg(backup_reference)}"
    return command


def live_beta_preflight_command(
    *,
    api_base: str = "http://localhost:8000",
    symbol: str = "KRW-BTC",
    backup_reference: str | None = LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
) -> str:
    return live_beta_closeout_command(
        api_base=api_base,
        symbol=symbol,
        backup_reference=backup_reference,
    ) + " --preflight"


def live_beta_preflight_json_command(
    *,
    api_base: str = "http://localhost:8000",
    symbol: str = "KRW-BTC",
    backup_reference: str | None = LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
) -> str:
    return live_beta_preflight_command(
        api_base=api_base,
        symbol=symbol,
        backup_reference=backup_reference,
    ) + " --json"


def live_beta_next_command_only_command(
    *,
    api_base: str = "http://localhost:8000",
    symbol: str = "KRW-BTC",
    backup_reference: str | None = LIVE_BETA_BACKUP_REFERENCE_EXAMPLE,
) -> str:
    return live_beta_preflight_command(
        api_base=api_base,
        symbol=symbol,
        backup_reference=backup_reference,
    ) + " --next-command-only"


LIVE_BETA_CLOSEOUT_COMMAND = live_beta_closeout_command()
LIVE_BETA_PREFLIGHT_COMMAND = live_beta_preflight_command()
LIVE_BETA_PREFLIGHT_JSON_COMMAND = live_beta_preflight_json_command()
LIVE_BETA_NEXT_COMMAND_ONLY_COMMAND = live_beta_next_command_only_command()


def format_completion_deduction(deduction: Mapping[str, Any], *, code_id: bool = False) -> str:
    deduction_id = str(deduction.get("id"))
    if code_id:
        deduction_id = f"`{deduction_id}`"
    line = f"{deduction_id}: -{deduction.get('points')} point(s). {deduction.get('detail')}"
    check_ids = deduction.get("check_ids")
    if isinstance(check_ids, list) and check_ids:
        line += " Source checks: " + ", ".join(str(check_id) for check_id in check_ids) + "."
    return line


def completion_impact_for_check_id(deduction: Mapping[str, Any], check_id: str) -> dict[str, Any]:
    deduction_id = str(deduction.get("id"))
    points = deduction.get("points")
    check_ids = deduction.get("check_ids")
    source_checks = [str(source_id) for source_id in check_ids] if isinstance(check_ids, list) else []
    impact: dict[str, Any] = {
        "completion_deduction_id": deduction_id,
        "completion_deduction_points": points,
    }
    if source_checks:
        impact["completion_source_checks"] = source_checks
    if isinstance(points, int) and len(source_checks) == 1:
        impact["completion_impact_points"] = points
        impact["completion_impact"] = (
            f"Clearing {check_id} is expected to recover {points} completion point(s) "
            f"from {deduction_id}."
        )
    elif isinstance(points, int) and len(source_checks) == points:
        impact["completion_impact_points"] = 1
        impact["completion_impact"] = (
            f"Clearing {check_id} is expected to recover 1 completion point "
            f"from {deduction_id}."
        )
    else:
        source_text = ", ".join(source_checks) if source_checks else check_id
        impact["completion_impact"] = (
            f"{check_id} is linked to the -{points} point {deduction_id} deduction; "
            f"clear source checks: {source_text}."
        )
    return impact


def completion_impacts_by_check_id(deductions: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    impacts: dict[str, dict[str, Any]] = {}
    for deduction in deductions:
        check_ids = deduction.get("check_ids")
        if not isinstance(check_ids, list):
            continue
        for raw_check_id in check_ids:
            check_id = str(raw_check_id)
            impacts[check_id] = completion_impact_for_check_id(deduction, check_id)
    return impacts


def with_completion_impacts(
    items: list[Mapping[str, Any]],
    deductions: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    impacts = completion_impacts_by_check_id(deductions)
    updated: list[dict[str, Any]] = []
    for item in items:
        copied = dict(item)
        impact = impacts.get(str(copied.get("id")))
        if impact:
            copied.update(impact)
        updated.append(copied)
    return updated


def strip_leading_cd(command: str) -> str:
    stripped = command.lstrip()
    leading_spaces = len(command) - len(stripped)
    if not stripped.startswith("cd "):
        return command

    in_single_quote = False
    in_double_quote = False
    escaped = False
    for index in range(leading_spaces + 2, len(command) - 1):
        char = command[index]
        if escaped:
            escaped = False
            continue
        if char == "\\" and not in_single_quote:
            escaped = True
            continue
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue
        if char == "&" and command[index + 1] == "&" and not in_single_quote and not in_double_quote:
            return command[index + 2 :].lstrip()
    return command


def source_scoped_command(command: str | None, source_dir: Path | str) -> str | None:
    if not command:
        return command
    scoped_command = command
    while True:
        stripped = strip_leading_cd(scoped_command)
        if stripped == scoped_command:
            break
        scoped_command = stripped
    return f"cd {shell_arg(source_dir)} && {scoped_command}"


def connected_runner_preflight_command(bundle_dir: Path | str) -> str:
    return (
        f"cd {shell_arg(bundle_dir)} && "
        f"PREFLIGHT_ONLY=true GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER} ./run-connected-runner-handoff.sh"
    )


def connected_runner_full_command(bundle_dir: Path | str) -> str:
    return f"cd {shell_arg(bundle_dir)} && GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER} ./run-connected-runner-handoff.sh"


def connected_runner_bundle_script_command() -> str:
    return f"GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER} ./run-connected-runner-handoff.sh"


def connected_runner_preflight_only_command() -> str:
    return f"PREFLIGHT_ONLY=true GIT_ORIGIN_URL={REPO_URL_PLACEHOLDER} ./run-connected-runner-handoff.sh"


def repo_url_export_example_command(env_name: str = ENV_REPO_URL_PLACEHOLDER) -> str:
    return f"export {env_name}=https://github.com/OWNER/REPO.git"


def connected_runner_verify_command(bundle_dir: Path | str) -> str:
    return f"python3 scripts/package_connected_runner_handoff.py --verify {shell_arg(bundle_dir)}"


def connected_runner_verify_json_command(bundle_dir: Path | str) -> str:
    return connected_runner_verify_command(bundle_dir) + " --json-only"


def connected_runner_verify_summary_json_command(bundle_dir: Path | str) -> str:
    return connected_runner_verify_command(bundle_dir) + " --summary-json-only"


def connected_runner_handoff_context_json_command(bundle_dir: Path | str) -> str:
    return connected_runner_verify_command(bundle_dir) + " --handoff-context-json-only"


def connected_runner_handoff_command_sequence_command(bundle_dir: Path | str) -> str:
    return connected_runner_verify_command(bundle_dir) + " --handoff-command-sequence-only"


def package_connected_runner_handoff_command(package_dir: Path | str) -> str:
    return f"python3 scripts/package_connected_runner_handoff.py --package-dir {shell_arg(package_dir)}"


def connected_runner_acceptance_command() -> str:
    return "python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth"


def connected_runner_acceptance_json_command() -> str:
    return connected_runner_acceptance_command() + " --json-only"


def connected_runner_acceptance_summary_json_command() -> str:
    return connected_runner_acceptance_command() + " --summary-json-only"


def external_readiness_summary_json_command() -> str:
    return "python3 scripts/check_external_readiness.py --summary-json-only"


def external_readiness_strict_summary_json_command() -> str:
    return (
        "python3 scripts/check_external_readiness.py "
        "--require-git-remote --require-docker --require-gh --check-gh-auth --summary-json-only"
    )


def report_release_status_command(package_dir: Path | str, release_gate_path: Path | str | None = None) -> str:
    command = f"python3 scripts/report_release_status.py --package-dir {shell_arg(package_dir)}"
    if release_gate_path:
        command += f" --release-gate {shell_arg(release_gate_path)}"
    return command


def refresh_release_status_command(package_dir: Path | str, release_gate_path: Path | str | None = None) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --allow-post-checksum-write"


def read_only_release_status_command(package_dir: Path | str, release_gate_path: Path | str | None = None) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --no-write"


def release_status_json_command(package_dir: Path | str, release_gate_path: Path | str | None = None) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --json-only"


def release_status_progress_command(package_dir: Path | str, release_gate_path: Path | str | None = None) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --progress-only"


def release_status_progress_json_command(package_dir: Path | str, release_gate_path: Path | str | None = None) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --progress-json-only"


def release_status_completion_plan_command(
    package_dir: Path | str,
    release_gate_path: Path | str | None = None,
) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --completion-plan-only"


def release_status_completion_plan_json_command(
    package_dir: Path | str,
    release_gate_path: Path | str | None = None,
) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --completion-plan-json-only"


def release_status_completion_requirements_command(
    package_dir: Path | str,
    release_gate_path: Path | str | None = None,
) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --completion-requirements-only"


def release_status_completion_requirements_json_command(
    package_dir: Path | str,
    release_gate_path: Path | str | None = None,
) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --completion-requirements-json-only"


def release_status_owner_lanes_command(
    package_dir: Path | str,
    release_gate_path: Path | str | None = None,
) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --owner-lanes-only"


def release_status_owner_lanes_json_command(
    package_dir: Path | str,
    release_gate_path: Path | str | None = None,
) -> str:
    return report_release_status_command(package_dir, release_gate_path) + " --owner-lanes-json-only"


def next_release_step_command(package_dir: Path | str, *args: str) -> str:
    command = f"python3 scripts/next_release_step.py --package-dir {shell_arg(package_dir)}"
    if args:
        command += " " + " ".join(args)
    return command


def read_only_evidence_check_command(package_dir: Path | str) -> str:
    return f"python3 scripts/check_release_evidence.py --package-dir {shell_arg(package_dir)} --no-write"


def evidence_check_json_command(package_dir: Path | str) -> str:
    return f"python3 scripts/check_release_evidence.py --package-dir {shell_arg(package_dir)} --json-only"


def verify_evidence_checksums_command(package_dir: Path | str) -> str:
    return f"python3 scripts/write_evidence_checksums.py --package-dir {shell_arg(package_dir)} --verify"


def verify_evidence_checksums_json_command(package_dir: Path | str) -> str:
    return verify_evidence_checksums_command(package_dir) + " --json-only"


def read_only_warning_review_command(package_dir: Path | str) -> str:
    return f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} --no-write"


def warning_review_json_command(package_dir: Path | str) -> str:
    return f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} --json-only"


def warning_review_gate_json_command(package_dir: Path | str) -> str:
    return warning_review_json_command(package_dir) + " --fail-if-action-needed"


def warning_review_summary_json_command(package_dir: Path | str) -> str:
    return f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} --summary-json-only"


def warning_review_gate_summary_json_command(package_dir: Path | str) -> str:
    return warning_review_summary_json_command(package_dir) + " --fail-if-action-needed"


def warning_review_pre_approval_sequence_command(package_dir: Path | str) -> str:
    return (
        f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} "
        "--pre-approval-sequence-only"
    )


def warning_review_apply_command(package_dir: Path | str) -> str:
    return f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} --apply --operator-approved"


def warning_review_next_command_only_command(package_dir: Path | str) -> str:
    return f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} --next-command-only"


def warning_review_next_command_gate_command(package_dir: Path | str) -> str:
    return warning_review_next_command_only_command(package_dir) + " --fail-if-action-needed"


def warning_review_artifacts_only_command(package_dir: Path | str) -> str:
    return f"python3 scripts/review_release_warnings.py --package-dir {shell_arg(package_dir)} --review-artifacts-only"


def next_release_step_repo_command(package_dir: Path | str) -> str:
    return next_release_step_command(package_dir, "--repo-url REPO_URL", "--no-write")


def next_release_step_origin_command(package_dir: Path | str) -> str:
    return next_release_step_command(package_dir, "--repo-url-from-origin", "--no-write")


def next_release_step_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(package_dir, "--repo-url-from-env GIT_ORIGIN_URL", "--no-write")


def next_release_command_only_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--command-only",
        "--fail-if-repo-url-required",
    )


def next_release_command_sequence_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--command-sequence-only",
        "--fail-if-repo-url-required",
    )


def next_release_json_only_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--json-only",
        "--fail-if-repo-url-required",
    )


def next_release_connected_json_only_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--json-only",
        "--fail-if-repo-url-required",
    )


def next_release_connected_command_only_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--command-only",
        "--fail-if-repo-url-required",
    )


def next_release_connected_command_sequence_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--command-sequence-only",
        "--fail-if-repo-url-required",
    )


def next_release_sequence_command(package_dir: Path | str) -> str:
    return next_release_step_command(package_dir, "--show-sequence", "--no-write")


def next_release_operator_sequence_command(package_dir: Path | str) -> str:
    return next_release_step_command(package_dir, "--owner operator", "--show-sequence", "--no-write")


def next_release_operator_command_only_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--owner operator",
        "--command-only",
        "--fail-if-repo-url-required",
    )


def next_release_operator_command_sequence_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--owner operator",
        "--command-sequence-only",
        "--fail-if-repo-url-required",
    )


def next_release_operator_review_sequence_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--owner operator",
        "--command-sequence-only",
        "--skip-operator-approved",
        "--fail-if-repo-url-required",
    )


def next_release_operator_json_only_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        "--owner operator",
        "--json-only",
        "--fail-if-repo-url-required",
    )


def next_release_connected_sequence_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url REPO_URL",
        "--show-sequence",
        "--no-write",
    )


def next_release_connected_sequence_origin_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-origin",
        "--show-sequence",
        "--no-write",
    )


def next_release_connected_sequence_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--show-sequence",
        "--no-write",
    )


def next_release_local_readiness_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--summary-by-owner",
        "--show-sequence",
        "--local-readiness",
        "--no-write",
    )


def next_release_local_readiness_json_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--json-only",
        "--fail-if-repo-url-required",
        "--local-readiness",
    )


def next_release_local_readiness_command_only_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--command-only",
        "--fail-if-repo-url-required",
        "--local-readiness",
        "--fail-if-local-readiness-not-pass",
    )


def next_release_local_readiness_setup_sequence_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--local-readiness-setup-sequence-only",
        "--fail-if-local-readiness-not-pass",
    )


def next_release_local_readiness_setup_sequence_preview_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--local-readiness-setup-sequence-only",
    )


def next_release_local_readiness_command_sequence_env_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--repo-url-from-env GIT_ORIGIN_URL",
        "--local-readiness-command-sequence-only",
        "--fail-if-local-readiness-not-pass",
    )


def next_release_local_readiness_command_sequence_preview_command(package_dir: Path | str) -> str:
    return next_release_step_command(
        package_dir,
        '--owner "connected runner"',
        "--local-readiness-command-sequence-only",
    )


def next_release_local_readiness_gate_json_env_command(package_dir: Path | str) -> str:
    return next_release_local_readiness_json_env_command(package_dir) + " --fail-if-local-readiness-not-pass"
