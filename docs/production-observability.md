# Production Observability Notes

This note defines the daily and per-window checks for running Quant Lab beyond a one-off local demo. It assumes live order routing remains locked by default.

## Daily Operator Cadence

Run these checks once per operating day, before reviewing any live beta candidate:

```bash
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:8000/api/ops/self-check
curl -fsS http://localhost:8000/api/execution/settings
curl -fsS http://localhost:8000/api/readiness/live
curl -fsS http://localhost:8000/api/alerts/review
curl -fsS http://localhost:8000/api/execution/post-cutover-monitor
curl -fsS "http://localhost:8000/api/research/crypto-live-beta-drill/report?symbol=KRW-BTC"
```

Or collect the same checks as files:

```bash
python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC
```

Operational runbooks are also available from the backend:

```bash
curl -fsS http://localhost:8000/api/ops/runbooks
curl -fsS http://localhost:8000/api/ops/runbooks/deployment-hardening
```

Expected baseline:

- `/api/health` responds.
- `/api/ops/self-check` reports the database path, scheduler state, artifact conventions, live lock state, and runbook API paths.
- `/api/execution/settings` shows `live_trading_enabled=false` outside a cutover window.
- `/api/readiness/live` can be `watch` or `blocked`, but blockers must be understood before promotion.
- `/api/alerts/review` has no unreviewed halt/error items.
- `/api/execution/post-cutover-monitor` has no unexpected submitted/failed approval attempts.
- The crypto drill report can be exported even when live routing is locked.

## Alert Review Cadence

Review active alerts in this order:

1. `paper_session_halt` and `paper_session_risk`
2. `broker_paper_submission`, `broker_reconciliation`, and `paper_fill_drift`
3. `portfolio_scan` and `paper_watchlist_error`

For each warning or error:

- Resolve the underlying state when possible.
- Use `POST /api/alerts/review/{alert_id}/acknowledge` with `status=noted` only when the risk is understood.
- Use `status=dismissed` only for stale or superseded items.
- Re-export the strategy health handoff or crypto drill report after clearing live-beta blockers.

Suggested cadence:

- Start of day: review all active alerts.
- Before live beta review: review all `warning` and `error` alerts.
- After closeout: review new alerts generated during the window.

## Scheduler Failure Triage

The research scheduler is controlled by:

- `QUANT_LAB_RESEARCH_SCHEDULER_ENABLED`
- `QUANT_LAB_RESEARCH_SCHEDULER_POLL_SECONDS`

If scheduled scans or paper-watchlist runs appear stale:

1. Confirm the backend process is running and `/api/health` responds.
2. Check `GET /api/research/portfolio/watchlist` and `GET /api/paper/watchlist` for active rows.
3. Run `POST /api/research/portfolio/watchlist/run-due` manually.
4. Run `POST /api/paper/watchlist/run-due` manually.
5. Inspect alert review for `paper_watchlist_error` and `portfolio_scan` items.
6. Restart the backend only after exporting or backing up current state.

For Docker Compose:

```bash
docker compose logs --tail=200 backend
docker compose restart backend
```

For local uvicorn:

```bash
tail -n 200 .codex-*.log 2>/dev/null || true
```

## Disk Usage Checks

Quant Lab persists SQLite, DuckDB, Parquet, exported artifacts, and backups. Review size before and after repeated drills:

```bash
du -sh backend/data 2>/dev/null || true
du -sh artifacts 2>/dev/null || true
du -sh backups 2>/dev/null || true
find artifacts -type f -mtime +30 -print
find backups -type f -mtime +30 -print
```

For Docker Compose:

```bash
docker system df
docker compose run --rm --no-deps backend sh -c 'du -sh /app/data'
```

Retention guidance:

- Keep at least the latest successful backup before any live beta window.
- Keep closeout and drill artifacts for the full review period.
- Remove old `artifacts/crypto-drills/*` only after the corresponding journal decisions are no longer needed.

## Log Retention

Use these conventions:

- Backend service logs: retain at least the latest 7 operating days.
- Seeded drill artifacts: retain by date and symbol under `artifacts/crypto-drills/`.
- Ops smoke checks: retain by timestamp under `artifacts/ops-smoke/`.
- Live beta evidence: retain with the closeout archive naming convention below.

Recommended lightweight archive:

```text
artifacts/live-beta/YYYYMMDD-KRW-BTC/
  01-ops-smoke-summary.json
  02-crypto-live-beta-drill.md
  03-strategy-health-handoff.md
  04-live-cutover-runbook.md
  05-live-window-closeout.md
  runbooks/
  raw-json/
```

Generate the archive from a running backend after the live window is closed and live flags are locked again:

```bash
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3
```

The preflight command checks backend reachability, live-lock state, and blocking alerts without writing an archive; add `--json` when automation needs structured output. The archive command writes into a hidden staging directory first and only publishes the final archive directory after all required API exports, Markdown files, raw JSON, and the safety manifest have been written.

## Closeout Archive Naming

Use this naming pattern for live beta review packages:

```text
YYYYMMDD-{market}-beta-{sequence}
```

Example:

```text
20260523-KRW-BTC-beta-001
```

Each archive should contain:

- Crypto live beta drill report.
- Strategy health handoff report.
- Live adapter arming runbook.
- Dry-run order runbooks.
- Post-cutover closeout report.
- Operator journal export.
- Alert review snapshot.
- Database backup reference.

For the local evidence bundle, use:

```bash
python3 scripts/release_gate.py --skip-docker --run-smoke
```

For connected runner evidence, enforce external prerequisites:

```bash
python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth
```

The release gate gathers the latest available verification, external readiness, smoke, drill, live-beta archive, runbook, and project documentation artifacts into `artifacts/evidence-packages/`; writes a compact summary under `artifacts/release-gate/`; and validates required evidence, live-lock state, smoke/drill files, external Docker/GitHub readiness, GitHub CLI auth/workflow visibility when requested, and alert severity before handoff. It reruns the evidence check after `release-status.md`, `next-release-step.md`, and warning action files exist so backup-reference placeholders, shell-unsafe repo URL placeholders, missing release-status JSON automation, missing release-evidence JSON automation, missing checksum verification JSON automation, missing live-beta preflight JSON automation, missing live-beta recommended-next command automation, missing live-beta backend support commands, repo-url-from-env automation without `--fail-if-repo-url-required`, missing command-sequence-only automation, missing repo URL export examples, warning `--apply` commands without `--operator-approved`, warning JSON or compact summary automation without `--fail-if-action-needed`, missing warning review artifact path automation, warning recommended-next command automation without `--fail-if-action-needed`, local-readiness JSON or command-only automation without `--fail-if-local-readiness-not-pass`, missing setup-sequence-only local-readiness automation, and missing setup-and-verify local-readiness automation fail before checksums are written. If warnings remain, review `release-status.md`, `release-warning-triage.md`, `release-warning-actions.md`, and `release-warning-operator-checklist.md` in the generated evidence package. Verify `manifest.json` post-package artifacts, `evidence-checksums.json`, `evidence-checksums.sha256`, the `.tgz.sha256` sidecar, any connected-runner `.tgz.verification.json` report, and the connected-runner acceptance report after copying packages; acceptance also records copied `release-status`/`next-release-step` command consistency, including the checksum verification JSON command, the read-only warning-review JSON command, the compact warning summary JSON command, the warning review artifact path command, the warning recommended-next command gate, the command-only local-readiness gate, the setup-sequence-only local-readiness command, and the setup-and-verify local-readiness command. Local-readiness JSON includes the first unresolved `local_readiness_next_setup_command` with its matching `verify_command`, plus `local_readiness_setup_sequence` for every unresolved setup/verify pair and `local_readiness_command_sequence` as the flattened command list, so connected-runner automation can apply one setup fix or iterate the full readiness sequence before rerunning the read-only probe. Use `next_release_step.py --command-sequence-only` when shell automation needs only the remaining handoff commands, use `next_release_step.py --local-readiness-setup-sequence-only` when it needs only unresolved setup commands, and use `next_release_step.py --local-readiness-command-sequence-only` when it needs setup commands followed by matching verification commands without scraping the status report. After checksums are published, use `scripts/report_release_status.py --package-dir PATH --no-write`, `scripts/check_release_evidence.py --package-dir PATH --no-write`, and `scripts/review_release_warnings.py --package-dir PATH --no-write` for read-only inspection so review commands do not rewrite status/triage/action/check files or refresh the tarball; use `scripts/report_release_status.py --package-dir PATH --json-only` for a parseable compact status report, `scripts/report_release_status.py --package-dir PATH --progress-only` for just the percent, remaining IDs, owner counts, and deductions, `scripts/write_evidence_checksums.py --package-dir PATH --verify --json-only` for a parseable integrity result, `scripts/check_release_evidence.py --package-dir PATH --json-only` for the full evidence-check payload, `scripts/review_release_warnings.py --package-dir PATH --json-only` when automation needs the full warning action plan, `scripts/review_release_warnings.py --package-dir PATH --summary-json-only` when automation needs compact warning counts plus the recommended next command, `scripts/review_release_warnings.py --package-dir PATH --review-artifacts-only` when automation needs only the existing action-plan/checklist paths, and `scripts/review_release_warnings.py --package-dir PATH --next-command-only --fail-if-action-needed` when automation needs exactly one selected warning-review command plus the unresolved-action exit-code gate. Connected-runner verifiers also accept `--json-only` on `scripts/package_connected_runner_handoff.py --verify PATH` and `scripts/connected_runner_acceptance.py ...` so remote automation can parse stdout without scraping human-readable lines. If status files must be intentionally refreshed after checksums, pass `--allow-post-checksum-write` and rerun `scripts/write_evidence_checksums.py --package-dir PATH`. For post-window review, `scripts/archive_live_beta_closeout.py` writes the live-beta archive and `check_release_evidence.py --require-live-beta` validates its closeout files and live-lock manifest. The actions file is dry-run by default; use `scripts/review_release_warnings.py --apply --operator-approved` only after an operator decides to acknowledge or dismiss warnings against a running backend and reviews the operator checklist. The package intentionally excludes `.env` and other credential-bearing files.

For compact progress polling, use `scripts/report_release_status.py --package-dir PATH --progress-json-only`; the JSON payload is also embedded in `release-status.json` as `progress_summary` and includes progress, completion-impact estimates by source check, the global next command, fail-closed global next command-only/report JSON helpers, completion-plan and completion-requirements helper commands, the first next command per owner, owner-scoped connected-runner/operator command-only helpers, operator report JSON, all-owner and connected-runner remaining sequences, connected-runner local-readiness setup/verify, compact external-readiness, warning-review, and bundle/acceptance summary JSON commands, operator sequence, warning action gates, warning artifact paths, and operator-approved warning apply commands. The connected-runner owner entry also carries the same command-only helper plus compact external-readiness summary/gate commands and local-readiness setup/verify helper commands, so automation that only reads `next_commands_by_owner` can still fetch one runner command, poll runner readiness, and guide missing origin, Docker, or GitHub CLI remediation. Operator progress commands expose the same one-command and JSON report paths for warning-review or live-beta closeout lanes. Operator entries include compact summary gates plus `review_artifacts` with the warning action-plan and checklist paths, so review UIs can deep-link the files without running a helper command. Release evidence, connected-runner handoff validation, and connected-runner acceptance fail if generated handoff commands lose this compact JSON progress path, if compact external-readiness, warning-review, warning-review pre-approval sequence, completion-requirements, or handoff summary commands disappear from that payload, or if `release-status.json` stops embedding the progress summary fields.

For compact connected-runner polling, use `--summary-json-only` on external readiness, bundle verification, and acceptance commands. External-readiness summaries include setup/verify guidance beside status counts, so automation can read `guidance.next_setup_command`, `guidance.setup_sequence`, `guidance.verify_sequence`, `guidance.command_sequence`, or `guidance.repo_url` without loading the full report. Release-status progress JSON also exposes `progress_summary.completion_impacts`, `progress_summary.repo_url`, `progress_summary.local_readiness`, and `progress_summary.warning_review` when compact resume polling needs completion recovery estimates, repo URL metadata, connected-runner setup/verify sequences, and operator warning-review state before invoking a runner or operator command. The generated handoff commands include both detailed `--json-only` and compact `--summary-json-only` forms where applicable, plus a strict external-readiness summary command with `--require-git-remote --require-docker --require-gh --check-gh-auth`, and release evidence checks fail if compact forms, progress completion impacts, progress repo URL metadata, progress local-readiness metadata, progress warning-review metadata, progress-to-next-step command equality, progress release-gate command alignment, progress handoff-bundle path alignment, progress top-level snapshot alignment, progress owner-next alignment, progress local-readiness remaining-item alignment, progress warning-review operator-item alignment, progress warning-review sequence-command alignment, or progress warning-review sequence alignment disappear.
Owner-specific progress entries also include completion-impact metadata for the selected item, so dashboards that poll only the connected-runner or operator lane can show the expected percentage recovery beside the next command.
For full progress views, `progress_summary.completion_plan` lists every remaining item in order with its selected command, mode, requirements, completion-impact metadata, warning-review sequence, apply-free pre-approval review sequence, operator approval requirement, and backend start/health-check guidance for approval-only warning actions, which lets monitors display the path to 100% without loading the full release status report or skipping checklist review. Human-readable completion-plan output also calls out score-neutral required items such as `warning_actions`, so operators can see why an item remains even when a separate warning deduction owns the percentage impact. The completion_plan mode and completion_plan requirements fields make connected-runner preflight, real repo URL, Docker CLI, GitHub CLI auth, operator review, operator approval, running backend, live-beta closeout, and backup-reference prerequisites explicit for automation. `progress_summary.completion_requirements` groups those prerequisites across the plan by item IDs, owner lanes, and count, so a monitor can show shared blockers like Docker/GitHub CLI or operator approval once instead of repeating every plan row.
For plan-only polling, `scripts/report_release_status.py --package-dir PATH --completion-plan-only` prints the same ordered plan for operators, and `--completion-plan-json-only` prints just that list for automation. For grouped prerequisite polling, `--completion-requirements-only` prints the shared blockers by requirement, item IDs, owner lanes, and count, while `--completion-requirements-json-only` prints only that grouped list for automation; both helper commands are also exposed as `progress_summary.commands.show_completion_requirements` and `progress_summary.commands.show_completion_requirements_json`. Release evidence, connected-runner bundle verification, and connected-runner acceptance fail if generated or copied release-status artifacts lose either completion-plan command, completion-plan backend guidance for approval-only warning actions, or completion-requirements command.
For owner-lane polling, `progress_summary.owner_lanes` groups each owner lane's remaining IDs, next item, runnable next/automation/full-flow/supporting commands, connected-runner readiness summary, operator review summary, first-mode requirements, approval state, and review artifacts. `scripts/report_release_status.py --package-dir PATH --owner-lanes-only` prints that lane view for operators, `--owner-lanes-json-only` prints only the lane object for automation, and both helpers are exposed through `progress_summary.commands.show_owner_lanes` and `progress_summary.commands.show_owner_lanes_json`.
Connected-runner bundle `manifest.json` also exposes `handoff_context.quickstart`, `handoff_context.remaining_ids`, `handoff_context.next_item_id`, `handoff_context.owner_lanes`, `handoff_context.bundle_commands`, `handoff_context.bundle_command_sequence`, `handoff_context.bundle_gate_summary`, `handoff_context.completion_plan`, and `handoff_context.completion_requirements`, so monitors can read the export-first preflight/full-flow commands, remaining IDs, current owner lane, owner-specific remaining IDs/approval state, ordered bundle-root command sequence, gate counts and first gate by owner, self-verification/acceptance summary commands, bundle-root progress polling, bundle-root operator review sequence, warning summary/artifact/gate commands, the ordered path to 100%, and grouped prerequisites from a stable JSON surface; bundle verification fails if that manifest context is missing or stale against copied `release-status.json`.
When a monitor needs only this handoff context, `scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-context-json-only` prints the manifest `handoff_context` without rewriting verification reports; `scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-command-sequence-only` prints only the ordered bundle-root commands, one per line. Generated manifests expose the same helpers at `handoff_context.bundle_commands.show_handoff_context_json` and `handoff_context.bundle_commands.show_handoff_command_sequence`, add `handoff_context.bundle_commands.audit_completion_context_json` for bundle-root completion-audit coverage, add `handoff_context.bundle_commands.show_progress_json` for bundle-root progress polling, add `handoff_context.bundle_commands.show_completion_plan_json` for bundle-root completion-plan polling, add `handoff_context.bundle_commands.show_completion_requirements_json` for bundle-root grouped-prerequisite polling, add `handoff_context.bundle_commands.show_owner_lanes_json` for bundle-root owner-lane polling, add `handoff_context.bundle_commands.show_warning_artifacts` for bundle-root warning checklist/action-plan discovery, and release progress exposes the local bundle paths as `progress_summary.commands.handoff_context_json` and `progress_summary.commands.handoff_command_sequence`. Run `scripts/check_completion_audit.py --handoff-bundle PATH_TO_HANDOFF_BUNDLE` when changing bundle commands; it fails if a manifest command lacks a required completion-audit marker or documentation marker. Without `--verify`, both options compute the context from the selected evidence package before a bundle is created.
Use `progress_summary.commands.local_readiness_setup_sequence_preview` and `progress_summary.commands.local_readiness_command_sequence_preview` for planning-only monitors that need unresolved connected-runner setup or setup-plus-verify commands without failing simply because local readiness is still incomplete; keep the existing `local_readiness_*` gate commands for CI or runner automation that should fail closed.
Use `progress_summary.commands.operator_review_sequence` for operator-facing monitors that need the warning review command list before approval; it omits `--apply --operator-approved`, while `progress_summary.commands.operator_command_sequence` still includes the final approved action command for deliberately approved operator runs. The same safe helper is mirrored as `progress_summary.warning_review.review_sequence_command` for consumers already scoped to warning-review metadata, and as `handoff_context.bundle_commands.show_operator_review_sequence` for moved bundle-root workflows. Consumers can also call `progress_summary.warning_review.pre_approval_sequence_command`, which points to `review_release_warnings.py --pre-approval-sequence-only`; UIs that need a plain list can use `progress_summary.warning_review.pre_approval_review_sequence`, which contains only the warning summary and review-artifact commands.

In CI, `.github/workflows/quant-lab-ci.yml` runs the same release gate with `GH_TOKEN` available for GitHub CLI workflow/run queries, a final latest-package evidence check, and artifact upload for verification, smoke/drill, external readiness, evidence packages, release gate summaries, connected-runner handoff bundles, and live-beta archives. Treat the uploaded CI evidence package as the first review source when it exists, then compare it with any local live-beta evidence from the target machine.

## Smoke-Test With Seeded Drill

When you want stronger evidence from a running backend:

```bash
python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC --run-drill
```

This waits for health, exports the core status JSON, runs the seeded crypto drill, verifies JSON/Markdown artifacts, and writes an `ops-smoke-summary.json`.

The command still does not enable live trading. Live routing remains controlled by `QUANT_LAB_LIVE_TRADING_ENABLED`, `QUANT_LAB_LIVE_TRADING_ACK`, credentials, operator decisions, and per-order confirmation.

For a local smoke test that starts and stops the backend process:

```bash
python3 scripts/run_local_smoke.py --start-backend --run-drill
```

This command writes backend logs and smoke artifacts under `artifacts/local-smoke/`.
