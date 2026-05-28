# Quant Lab Completion Audit

This audit maps the original Quant Lab MVP goal to current implementation evidence, verification commands, known boundaries, and remaining optional improvements.

## Status Summary

Current state: operational MVP for research, paper trading, dry-run review, operator evidence, and guarded crypto live-beta preparation.

Estimated completion:

- Release handoff completion: 96%
- Operational quant MVP: 95-96%
- Full production automation: 88-90%

Latest local release checkpoint, verified on 2026-05-26 KST:

- Release status: warning-only gate, 96% complete.
- Current status reports include completion-deduction details and completion impact estimates so reviewers can see that the 96% estimate comes from connected-runner external warnings and warning-alert operator review; `live_beta_archive` evidence is now present.
- Current evidence package and connected-runner handoff paths are printed by `python3 scripts/next_release_step.py --summary-by-owner --show-sequence --no-write`.
- Current release gate summaries are written under `artifacts/release-gate/`.
- Remaining items: `git_origin_remote`, `docker_cli`, `github_cli`, `warning_alerts`, and `warning_actions`.
- Local blockers are environmental or operator-owned: this machine currently has no configured git `origin`, no Docker CLI, and no GitHub CLI.

The application can research strategies, run backtests and validation, create paper sessions, promote KRW crypto paper trades into guarded dry-run audits, export runbooks and drill evidence, manage alerts and operator decisions, and prepare a controlled Upbit crypto live-beta review. Stock/ETF work is intentionally paper-only.

## Requirement-To-Evidence Map

| Requirement | Status | Evidence |
| --- | --- | --- |
| Research quant trading examples and asset-class recommendation | Complete | `docs/quant-trading-proposal.md` recommends crypto-first, stock/ETF as structured paper expansion. |
| Web-based quant workspace | Complete | FastAPI backend, React/Vite dashboard, `README.md` run instructions. |
| Crypto market data | Complete | Deterministic sample source, optional Upbit public candle source, ticker endpoint. |
| Stock/ETF research path | Complete for paper research | `sample_us`, optional Alpha Vantage, stock/ETF docs, USD formatting, paper-only execution boundary. |
| Backtesting | Complete | SMA crossover, Donchian breakout, RSI mean reversion, buy-and-hold benchmark, backtest history. |
| Parameter robustness | Complete | Sweep, train/test validation, walk-forward validation APIs and dashboard panels. |
| Paper trading | Complete | Paper sessions, live replay sessions, ticker sessions, guardrails, persisted sessions. |
| Portfolio research | Complete | Portfolio presets, weights, monthly rebalance, saved scenarios, scans, scan watchlists. |
| Paper-to-execution handoff | Complete for guarded review | KRW crypto dry-run audit queue; stock/ETF paper-only handoff path. |
| Private exchange integration | Complete as guarded Upbit path | Disabled-by-default Upbit private read, dry-run prechecks, live-order guard, ACK and per-order confirmation. |
| Stock/ETF broker expansion | Complete for paper and rehearsal | Mock broker, Alpaca preview, credential-gated Alpaca paper adapter, reconciliation, package/preflight/rehearsal. |
| Alerts and operations | Complete | Alert review queue, acknowledgements, operations journal, decision logs, active alert handoff sections. |
| Readiness and cutover evidence | Complete | Live readiness, cutover checklist, arming simulator, runbook export, post-cutover monitor, closeout report. |
| Strategy health and drill evidence | Complete | Strategy health traces/handoff report, crypto live beta drill report, seeded drill script. |
| Dark/white theme and design pass | Complete | Persisted theme toggle and dense operational dashboard styling. |
| Deployment hardening | Complete for local/small-server use | `.env.example`, Docker Compose, Dockerfiles, nginx proxy, health checks, backup/restore notes. |
| Observability and verification | Complete | Ops self-check API, ops smoke checks, managed local smoke test, external readiness checker, CI workflow, verification bundle, release gate command, evidence package command, release evidence checker, release status report, checksum verification, release readiness checklist. |

## Verification Evidence

Latest verified commands:

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests
npm run build
python3 scripts/verify_project.py --skip-docker
python3 scripts/release_gate.py --skip-docker --run-smoke
python3 scripts/check_frontend_theme.py
python3 scripts/check_external_readiness.py --summary-json-only
python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE
python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --json-only
python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --summary-json-only
python3 scripts/check_completion_audit.py --handoff-bundle PATH_TO_HANDOFF_BUNDLE
python3 scripts/connected_runner_acceptance.py --handoff-root PATH_TO_HANDOFF_BUNDLE --source-root PATH_TO_SOURCE --package-dir PATH_TO_COPIED_OR_LOCAL_EVIDENCE_PACKAGE
python3 scripts/connected_runner_acceptance.py --handoff-root PATH_TO_HANDOFF_BUNDLE --source-root PATH_TO_SOURCE --package-dir PATH_TO_COPIED_OR_LOCAL_EVIDENCE_PACKAGE --json-only
python3 scripts/connected_runner_acceptance.py --handoff-root PATH_TO_HANDOFF_BUNDLE --source-root PATH_TO_SOURCE --package-dir PATH_TO_COPIED_OR_LOCAL_EVIDENCE_PACKAGE --summary-json-only
export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git
Completion requirements:
manifest.json handoff_context.quickstart
manifest.json handoff_context.completion_plan
manifest.json handoff_context.completion_requirements
manifest.json handoff_context.remaining_ids
manifest.json handoff_context.next_item_id
manifest.json handoff_context.owner_lanes
manifest.json handoff_context.bundle_commands
manifest.json handoff_context.bundle_command_sequence
manifest.json handoff_context.bundle_gate_summary
manifest.json handoff_context.bundle_gate_summary.first_gate_by_owner
package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-context-json-only
package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-command-sequence-only
manifest.json handoff_context.bundle_commands.show_handoff_context_json
manifest.json handoff_context.bundle_commands.show_handoff_command_sequence
manifest.json handoff_context.bundle_commands.audit_completion_context_json
manifest.json handoff_context.bundle_commands.show_completion_plan_json
manifest.json handoff_context.bundle_commands.show_completion_requirements_json
manifest.json handoff_context.bundle_commands.show_progress_json
manifest.json handoff_context.bundle_commands.verify_bundle_summary_json
manifest.json handoff_context.bundle_commands.acceptance_summary_json
manifest.json handoff_context.bundle_commands.show_owner_lanes_json
manifest.json handoff_context.bundle_commands.show_operator_review_sequence
manifest.json handoff_context.bundle_commands.show_warning_summary_json
manifest.json handoff_context.bundle_commands.show_warning_artifacts
manifest.json handoff_context.bundle_commands.gate_warning_summary_json
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --no-write
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --progress-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --progress-json-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-plan-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-plan-json-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-requirements-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --completion-requirements-json-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --owner-lanes-only
python3 scripts/report_release_status.py --package-dir PATH_TO_EVIDENCE_PACKAGE --owner-lanes-json-only
release-status.json progress_summary.completion_impacts
release-status.json progress_summary.completion_plan
release-status.json progress_summary.completion_requirements
release-status.json progress_summary.commands.show_completion_requirements
release-status.json progress_summary.commands.show_completion_requirements_json
release-status.json progress_summary.owner_lanes
release-status.json progress_summary.owner_lanes.*.commands
release-status.json progress_summary.owner_lanes.*.readiness
release-status.json progress_summary.owner_lanes.*.review
release-status.json progress_summary.commands.show_owner_lanes
release-status.json progress_summary.commands.show_owner_lanes_json
completion_plan mode
completion_plan requirements
completion_plan pre_approval_review_sequence
release-status.json progress_summary.next_commands_by_owner
release-status.json progress_summary.warning_review
release-status.json progress_summary.warning_review.review_sequence_command
release-status.json progress_summary.warning_review.pre_approval_review_sequence
release-status.json progress_summary.warning_review.pre_approval_sequence_command
release-status.json progress_summary.commands.handoff_context_json
release-status.json progress_summary.commands.handoff_command_sequence
release-status.json progress_summary.commands.operator_review_sequence
python3 scripts/next_release_step.py --skip-operator-approved
python3 scripts/review_release_warnings.py --package-dir PATH_TO_EVIDENCE_PACKAGE --pre-approval-sequence-only
python3 scripts/next_release_step.py --package-dir PATH_TO_EVIDENCE_PACKAGE --local-readiness-command-sequence-only --fail-if-local-readiness-not-pass
release-status.json progress_summary.commands.local_readiness_setup_sequence_preview
release-status.json progress_summary.commands.local_readiness_command_sequence_preview
python3 scripts/check_release_evidence.py --package-dir PATH_TO_EVIDENCE_PACKAGE --no-write
python3 scripts/check_release_evidence.py --package-dir PATH_TO_EVIDENCE_PACKAGE --json-only
python3 scripts/review_release_warnings.py --package-dir PATH_TO_EVIDENCE_PACKAGE --no-write
python3 scripts/review_release_warnings.py --package-dir PATH_TO_EVIDENCE_PACKAGE --json-only
python3 scripts/review_release_warnings.py --package-dir PATH_TO_EVIDENCE_PACKAGE --summary-json-only
python3 scripts/write_evidence_checksums.py --package-dir PATH_TO_EVIDENCE_PACKAGE --verify
python3 scripts/write_evidence_checksums.py --package-dir PATH_TO_EVIDENCE_PACKAGE --verify --json-only
```

Omit `--package-dir` to select the latest local evidence package for resume/status commands; keep the explicit path when reviewing a transferred or archived package.

Latest known results:

- Script smoke tests: 207 passing.
- Backend tests: 81 passing.
- Frontend TypeScript and Vite production build: passing.
- Frontend theme smoke: passing for persisted dark/white theme initialization, DOM sync, toggle labeling/icons, and light/dark CSS token parity.
- Project verification bundle: passing with Docker Compose config skipped because Docker is not installed on this machine.
- Package evidence selection smoke: passing, including generated-at-first source artifact selection.
- Latest handoff verification: passing for unpacked bundle and tarball.
- Latest connected-runner acceptance: passing for source safety, copied evidence integrity, runner ordering, and archive sidecars, with external readiness still warning until a connected runner provides `origin`, Docker, and GitHub CLI.
- Latest evidence checksum verification: passing.
- Latest read-only release evidence check: passing with warning-only items for external readiness and warning alert review; live-beta archive evidence is present.

Use this command for a compact verification summary:

```bash
python3 scripts/release_gate.py --skip-docker
```

When Docker is available, run without `--skip-docker` so `docker compose config` is also checked.

## Key Operating Commands

Run locally:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

Run with Docker Compose:

```bash
cp .env.example .env
docker compose up --build
```

Create a crypto drill evidence package:

```bash
python3 scripts/seed_crypto_drill.py --api-base http://localhost:8000 --symbol KRW-BTC
```

Run operational smoke checks:

```bash
python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC
```

Start a local backend, run smoke checks, and stop it:

```bash
python3 scripts/run_local_smoke.py --start-backend --run-drill
```

Package the latest review evidence:

```bash
python3 scripts/release_gate.py --skip-docker --run-smoke
```

CI verification:

```text
.github/workflows/quant-lab-ci.yml
```

The workflow runs the release gate, managed local smoke drill, evidence packaging, release evidence checking, and artifact upload while live trading flags remain locked.

## Safety Boundaries

- Live crypto routing is Upbit-only.
- Live trading is disabled by default.
- Live orders require `QUANT_LAB_LIVE_TRADING_ENABLED=true`, `QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK`, Upbit credentials, operator decisions, and per-order `live_confirmation=true`.
- Stock/ETF routing is paper-only.
- Alpaca support is paper trading only and requires explicit Alpaca paper gates.
- The app does not provide tax, legal, investment, or brokerage compliance advice.
- Verification scripts should be run sequentially; backend tests exercise shared SQLite/DuckDB cache paths and process environment variables.

## Release Readiness Gate

Treat the project as ready for controlled live-beta review only when:

- `python3 scripts/verify_project.py` passes, or passes with Docker explicitly skipped on machines without Docker.
- `python3 scripts/release_gate.py` writes a passing or warning-only summary under `artifacts/release-gate/`.
- `python3 scripts/check_external_readiness.py` records Docker/GitHub runner gaps as evidence, and `check_external_readiness.py --summary-json-only` gives automation compact status/counts plus warning/failure IDs and setup/verify guidance while still writing evidence files.
- `python3 scripts/check_release_evidence.py --no-write` passes for the attached package after checksums are published, and `--json-only` gives automation the same evidence-check payload without mutating checked evidence.
- `python3 scripts/report_release_status.py --package-dir PATH --no-write` can recalculate status without mutating checked evidence.
- `python3 scripts/report_release_status.py --package-dir PATH --progress-only` can print the current percent, remaining IDs, owner counts, and deductions without mutating checked evidence.
- `python3 scripts/report_release_status.py --package-dir PATH --progress-json-only` can print the same compact progress data as JSON without mutating checked evidence, and `release-status.json` embeds `progress_summary.completion_impacts`, `progress_summary.completion_plan`, `progress_summary.completion_requirements`, `progress_summary.owner_lanes`, `progress_summary.owner_lanes.*.commands`, `progress_summary.owner_lanes.*.repo_url`, `progress_summary.owner_lanes.*.readiness`, `progress_summary.owner_lanes.*.review`, `progress_summary.commands.show_completion_requirements`, `progress_summary.commands.show_completion_requirements_json`, `progress_summary.commands.show_owner_lanes`, `progress_summary.commands.show_owner_lanes_json`, `progress_summary.next_commands_by_owner`, `progress_summary.warning_review`, `progress_summary.warning_review.review_sequence_command`, `progress_summary.warning_review.pre_approval_review_sequence`, and `progress_summary.warning_review.pre_approval_sequence_command` with completion-point recovery by source check, an ordered path through all remaining items, completion_plan mode, completion_plan requirements, completion_plan pre_approval_review_sequence, grouped prerequisite blockers, direct grouped-requirement helper commands, owner-lane snapshots with runnable next/automation/full-flow/supporting command objects, connected-runner repo URL placeholder/export/gate guidance, connected-runner readiness summaries, operator review summaries, operator backend start/health-check guidance, direct owner-lane helper commands, each owner's next command, warning review gates/artifact paths, a direct non-approved operator review sequence helper, an apply-free pre-approval review list and helper command, approval-only apply metadata, available automation/supporting commands, external-readiness compact gates, and `--summary-json-only` handoff checks for consumers that only read the archived evidence package.
- `python3 scripts/report_release_status.py --package-dir PATH --completion-plan-only` and `--completion-plan-json-only` can print only the ordered remaining plan to 100%, including mode, prerequisite requirements, connected-runner repo URL export/gate guidance, operator approval, backend start/health-check hints before approval-only warning apply commands, and warning-review sequence metadata, so resume operators can inspect the 96% -> 100% path without loading the full progress payload.
- `python3 scripts/report_release_status.py --package-dir PATH --completion-requirements-only` and `--completion-requirements-json-only` can print only the grouped prerequisite blockers, item IDs, owner lanes, and counts from the completion plan, so monitoring can summarize shared runner/operator blockers without loading the full progress payload; the text view also adds connected-runner handoff/owner-command hints, connected-runner repo URL gates, Docker/GitHub CLI setup/verify commands, operator review/approval hints with action-plan/checklist artifact paths, and backend start/health-check commands for warning-action apply prerequisites, while the JSON helper adds the same actionable hints under per-requirement `guidance` and repeats repo URL gates on the top-level `connected_runner` requirement.
- `python3 scripts/report_release_status.py --package-dir PATH --owner-lanes-only` and `--owner-lanes-json-only` can print only the owner-lane snapshots, including each owner lane's remaining IDs, next item, runnable next/automation/full-flow/supporting commands, connected-runner repo URL export and gate guidance, connected-runner readiness summary, operator review summary, first-mode requirements, approval state, and review artifacts.
- Omit `--package-dir` to select the latest local evidence package for resume/status commands; keep the explicit path when reviewing a transferred or archived package.
- `python3 scripts/next_release_step.py --package-dir PATH_TO_EVIDENCE_PACKAGE --local-readiness-command-sequence-only --fail-if-local-readiness-not-pass` can print unresolved runner setup commands followed by matching verification commands without mutating checked evidence.
- `python3 scripts/review_release_warnings.py --package-dir PATH --no-write` can show planned warning actions without rewriting action/checklist files, `--json-only` gives automation the same plan as machine-readable output, `--summary-json-only` gives compact warning counts plus recommended-next metadata and backend start/health-check guidance, and `--pre-approval-sequence-only` prints only the apply-free summary/artifact commands before an operator-approved apply is considered.
- Any warning-only state has a generated `release-warning-triage.md` with operator actions.
- Any warning alert action has a dry-run `release-warning-actions.md` and `release-warning-operator-checklist.md` before an operator uses `--apply --operator-approved`.
- The package root has a generated `release-status.md` for operator handoff.
- The package root has generated checksum files and the `.tgz` has a SHA-256 sidecar.
- Any connected-runner handoff archive has a generated `.tgz.verification.json` report for required members, path safety, and source artifact exclusions.
- Any connected-runner handoff extraction has a generated acceptance report before final strict release gating.
- Connected-runner bundle verification and acceptance can use `--summary-json-only` when automation needs compact status/counts plus warning/failure IDs instead of verbose nested check details.
- Any post-window live-beta evidence is generated with `scripts/archive_live_beta_closeout.py` and passes the `--require-live-beta` release evidence gate.
- `/api/ops/self-check` reports expected database paths, artifact paths, scheduler state, live-lock status, and runbook links.
- `/api/alerts/review` has no unresolved halt/error items for the target market.
- `GET /api/research/crypto-live-beta-drill/report?symbol=KRW-BTC` exports successfully.
- Relevant dry-run runbooks are exported and reviewed.
- Readiness review, dry-run approval, and live cutover decisions are logged.
- A database backup is created before the live beta window.
- The closeout report is exported after the window.

## Remaining Optional Improvements

These are not required for the current operational MVP, but would make the system more production-like:

- Run Docker Compose validation on a machine with Docker installed.
- Validate the CI workflow in a connected GitHub runner.
- Add an authenticated deployment mode before exposing beyond localhost or a private network.
- Add structured log shipping and retention outside local Docker logs.
- Add broker-specific production monitoring for any future live stock/ETF adapter.
- Add immutable remote storage for evidence packages after live beta windows.
- Add dashboard-native links to generated artifact folders when served from a controlled file host.

## Final Assessment

Quant Lab is ready for disciplined local operator review and controlled crypto live-beta preparation. It is not a fully automated production trading system, and that is intentional: live order routing remains explicitly gated, reviewed, and disabled by default.
