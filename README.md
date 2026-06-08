# Quant Lab

Quant Lab is a web-based quant trading workspace. The first milestone is a crypto spot MVP: collect candles, run backtests, inspect risk metrics, then move toward paper trading before any live exchange orders.

Current scope:

- FastAPI backend with a backtest API
- React dashboard for running strategy simulations
- Dark/white dashboard theme toggle with persisted preference
- Deterministic sample market data for local development
- Optional Upbit public candle adapter for KRW crypto markets
- Deterministic US stock/ETF sample data for paper-trading expansion experiments
- Optional Alpha Vantage daily stock/ETF adapter when `ALPHA_VANTAGE_API_KEY` is configured
- Initial strategies: SMA crossover, Donchian breakout, and RSI mean reversion
- Strategy parameter sweep API and dashboard card for ranking candidate parameter sets before paper/live promotion
- Train/test backtest validation API and dashboard card for checking parameter robustness before promotion
- Rolling walk-forward validation API and dashboard card for checking repeated out-of-sample folds before promotion
- Paper trading sessions with guardrails for max position, max order size, order count, loss halt, and kill switch
- Live-replay paper sessions that advance candle-by-candle before real exchange integration
- SQLite-backed session snapshots for paper and live paper runs
- SQLite-backed Upbit candle cache for repeated backtests and paper sessions
- DuckDB-backed columnar candle mirror with Parquet export for larger research scans
- SQLite-backed backtest history with a dashboard panel for reloading, sorting, and filtering prior runs by source, strategy, and symbol
- Side-by-side dashboard comparison for selected recent backtests, including normalized equity overlays
- Portfolio research panel for comparing multiple symbols with custom allocation weights and optional monthly rebalancing
- Portfolio research presets and saved scenarios for repeatable allocation studies, including a stock/ETF RSI reversion paper preset
- Saved scenario scans with stored portfolio research results for watchlist-style review
- Scheduled scenario scan watchlist with backend due-run support and dashboard controls
- Scheduled scan alert thresholds for drawdown, total return, average edge, and return drift
- Portfolio paper watchlist that promotes saved research scenarios into recurring simulated sessions
- Bot Fleet Operator for running multiple named paper/dry-run bot profiles with different operating styles, strategies, risk limits, and schedules
- Compact alert review queue for scan threshold alerts, watchlist errors, and paper-session risk events
- Alert review filters for severity, source, and scenario triage
- Alert review acknowledgement and dismissal state persisted in SQLite
- Broker paper submission, reconciliation, and paper fill drift alerts in the operator review queue
- Live-readiness score split into system and operator views for provider, alert, paper-session, dry-run audit, runbook, and execution-guard health
- Live-order cutover checklist and arming runbook that require readiness review, dry-run approval, and live-cutover operator decisions before arming the adapter
- Live-adapter arming simulator that previews blocker changes and remaining blockers from live flag, ACK, and credential assumptions without submitting orders
- Post-cutover order monitor and closeout report for approval attempts, latest audit status, private snapshot health, and Upbit open orders during a live window
- Strategy health attribution traces linking portfolio watchlist promotion rules, paper trades, dry-run approvals, live attempts, and closeout outcomes
- Strategy health handoff report that bundles trace rows, closeout status, and linked dry-run runbook endpoints into an operator Markdown artifact
- Crypto live beta drill report that bundles KRW paper sessions, dry-run audits, prechecks, runbooks, readiness, cutover simulation, closeout, and strategy-health evidence without submitting live orders
- Deployment hardening artifacts: Docker Compose, container healthchecks, environment template, backup/restore notes, and a pre-market operator checklist
- Production observability notes and an ops smoke-check command for health, readiness, alert, monitor, drill, and artifact checks
- Backend ops self-check API with scheduler, database, artifact, live-lock, and runbook-link metadata surfaced in the dashboard setup panel
- Evidence package command that gathers verification summaries, smoke/drill artifacts, runbooks, and docs into a timestamped review bundle
- Operations journal with filters, Markdown exports, and dry-run runbook links for readiness reviews, dry-run order reviews, and paper-promotion audit notes
- Backtest metrics include buy-and-hold benchmark return, benchmark drawdown, and strategy edge
- Strategy equity chart with a buy-and-hold benchmark and edge readout
- Disabled-by-default Upbit private execution guard with order intent audit logs
- Read-only Upbit private snapshot for balances and open orders when credentials are configured
- Broker-aware paper-to-live adapter profiles that separate guarded Upbit crypto routing from stock/ETF paper-only handoffs
- Explicit broker adapter contracts for guarded Upbit crypto, mock US equity paper routing, and an Alpaca-style paper preview
- Broker readiness API and dashboard panel that expose credential boundaries, live-submission state, and contract checks
- Broker-neutral US stock/ETF paper intent evaluator and dashboard sandbox that validates mock and Alpaca-style order shapes without external broker submission
- Credential-gated Alpaca stock/ETF paper trading adapter that stays blocked until paper endpoint, credentials, ACK, env flag, and per-request paper submission confirmation are all present
- Provider-agnostic stock/ETF paper fill estimates for expected fill price, fee, cash, position, and exposure checks
- SQLite-backed broker intent evaluation history with dashboard recall for recent paper broker checks
- Exportable broker intent evaluation Markdown report for stock/ETF paper-only routing reviews, with adapter coverage counts
- Paper fill order notes that attach accepted stock/ETF broker estimates to paper sessions and compare intended fills with simulated trades
- Paper fill drift analytics that summarize intended-vs-simulated fill gaps by stock/ETF symbol and paper broker adapter
- Paper fill quality gate that marks stock/ETF paper broker routes as ready, watch, or blocked before live-broker expansion
- Stock/ETF broker expansion readiness report that lists approved-ready paper handoffs and their fill-quality evidence
- Exportable stock/ETF broker expansion package with Alpaca-style paper order payloads, quality-gate evidence, and stop conditions
- Stock/ETF broker expansion package preflight that validates payload schema, paper-only boundaries, and Alpaca preview coverage before adapter work
- Local stock/ETF broker expansion rehearsal that replays package payloads into paper-only accepted/rejected order records without external submission
- Rich Alpaca paper reconciliation with partial-fill, fill activity, fee, account cash, and broker-side position snapshots
- Paper-live routing dashboard panel that shows the active symbol route, guarded crypto dry-run path, and stock/ETF paper-only path
- Dedicated stock/ETF handoff dashboard panel with recent paper-only symbols, scenario source, journal status, and Markdown export
- Stock/ETF handoff review actions that log noted, needs-work, approved, and rejected decisions while keeping live-order routing disabled and requiring a ready paper fill quality gate before approval
- Stock/ETF handoff drill-down that loads the linked paper session trades, risk summary, promotion rule snapshot, and recent broker intent/fill evidence
- Dry-run strategy order intent queue from paper trading signals to execution audit records
- Crypto promotion from paper watchlist winners into dry-run order intent review
- Stock/ETF paper promotion into operator handoffs without live-order audit creation
- Promotion context on dry-run audits, including originating scenario and rule snapshot
- Exportable Markdown runbooks for dry-run to live-order approval review
- Manual review and approve flow for dry-run intents, still protected by the backend live-order guard
- Pre-approval checks for dry-run intents: Upbit order availability when credentials exist, minimum notional, private balance availability, fees, and estimated post-order exposure
- Execution settings API and dashboard panel for credential status, ACK lock state, guard thresholds, order-info source, and latest check timestamps
- Setup checklist panel for Upbit private keys, live-order lock flags, Alpha Vantage, and approval guardrails
- Stock/ETF paper-trading path via `sample_us` or `alpha_vantage` source and symbols such as `SPY`, `QQQ`, `AAPL`, `MSFT`, `NVDA`, and `TSLA`
- Market data provider status API and dashboard panel for source readiness, missing API keys, cache TTL, check timestamps, and latest fetch errors
- Columnar cache status and export controls in the dashboard data panel
- Stitch-inspired design pass for denser operational panels, clearer status chips, and consistent theme tokens

## Run locally

Start backend, frontend, and browser together:

```bash
python3 scripts/run_local_app.py
```

Use `Ctrl+C` in that terminal to stop the managed backend/frontend processes. Pass `--no-browser`
when you only want to start the services without opening a browser.

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`.

Docker Compose:

```bash
cp .env.example .env
docker compose up --build
```

The Compose frontend is served at `http://localhost:5173` and proxies `/api/*` to the backend. See [docs/deployment-hardening.md](docs/deployment-hardening.md) for health checks, backup/restore commands, and the pre-market operator checklist.

Seed a crypto beta drill against a running backend:

```bash
python3 scripts/seed_crypto_drill.py --api-base http://localhost:8000 --symbol KRW-BTC
```

The script creates a sample paper session, queues dry-run intents, exports linked runbooks, and writes the crypto live beta drill report under `artifacts/crypto-drills/` without changing live-order environment gates.

Run operational smoke checks against a running backend:

```bash
python3 scripts/ops_smoke_check.py --api-base http://localhost:8000 --symbol KRW-BTC
```

Add `--run-drill` to also run the seeded drill and verify exported JSON/Markdown artifacts. See [docs/production-observability.md](docs/production-observability.md) for alert cadence, scheduler triage, disk checks, log retention, and closeout archive naming.

Start a local backend, run smoke checks, and stop it afterward:

```bash
python3 scripts/run_local_smoke.py --start-backend --run-drill
```

Run the full local release gate:

```bash
python3 scripts/release_gate.py --skip-docker
```

Add `--run-smoke` when you want the gate to start a local backend, run the smoke drill, and then package the fresh evidence:

```bash
python3 scripts/release_gate.py --skip-docker --run-smoke
```

On a connected runner or Docker-enabled handoff machine, make external prerequisites blocking:

```bash
python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth
```

Lower-level commands remain available: `scripts/verify_project.py`, `scripts/run_local_smoke.py`, `scripts/package_evidence.py`, `scripts/check_release_evidence.py`, `scripts/report_release_status.py`, `scripts/review_release_warnings.py`, `scripts/connected_runner_acceptance.py`, `scripts/archive_live_beta_closeout.py`, and `scripts/write_evidence_checksums.py`.

CI:

The GitHub Actions workflow at `.github/workflows/quant-lab-ci.yml` installs backend and frontend dependencies, runs `scripts/release_gate.py --run-smoke --strict-external --check-gh-auth`, checks external readiness and the latest release evidence, queries the remote workflow/run history with `GH_TOKEN`, and uploads verification, smoke/drill, external-readiness, evidence, release-gate, handoff-bundle, and live-beta archive artifacts. Live trading flags remain locked in CI.

When release evidence has warnings, the check writes `release-warning-triage.md` and `release-warning-triage.json` inside the evidence package with the alert IDs and recommended operator actions. After release-status and next-step files are generated, the gate reruns the evidence check so copied handoff commands fail if backup placeholders return, warning `--apply` commands omit `--operator-approved`, or warning review artifact path automation disappears.
The release gate also writes `release-warning-actions.md` in dry-run mode plus `release-warning-operator-checklist.md` for the human decision path. After checksums are published, use `python3 scripts/review_release_warnings.py --package-dir PATH --no-write` to inspect the warning plan without changing package artifacts, `--json-only` when automation needs the same read-only plan as machine-readable JSON with structured follow-up commands under `commands`, `--summary-json-only` when automation only needs compact warning counts, review paths, and the recommended next command, or `--review-artifacts-only` when automation needs just the existing action-plan/checklist paths and should fail if either review artifact is missing. To acknowledge those warning alerts against a running backend, review the checklist first and rerun `python3 scripts/review_release_warnings.py --package-dir PATH --apply --operator-approved` deliberately.
The release gate writes `release-status.md`, `release-status.json`, and `next-release-step.md` at the package root so reviewers can see the latest gate status, approximate completion percentage, owner-tagged remaining handoff items, warning checks, remediation/final-verify commands, handoff commands, connected-runner bundle paths, and the nearest next command without opening each JSON file separately. After checksums are published, use `python3 scripts/report_release_status.py --package-dir PATH --no-write` for read-only status recalculation, `--json-only` when automation needs the same compact status report as machine-readable JSON, `--progress-only` when a handoff only needs the percent, remaining IDs, owner counts, and deductions, `--progress-json-only` when automation needs that same compact progress payload plus resume commands as JSON, `--completion-plan-only` / `--completion-plan-json-only` when it needs only the ordered path to 100%, or `--completion-requirements-only` / `--completion-requirements-json-only` when it needs only grouped prerequisite blockers without changing package artifacts; intentional rewrites require `--allow-post-checksum-write` and a checksum refresh. On local resumes, omit `--package-dir` to select the latest package under `artifacts/evidence-packages`; keep an explicit package path when reviewing a transferred bundle, older checkpoint, or copied archive. The progress JSON payload is also embedded in `release-status.json` as `progress_summary`; it includes the global `next_command`, `next_item_id`, `next_item_owner`, `next_commands_by_owner`, `completion_impacts`, `local_readiness`, and `warning_review` fields, and its command map includes global next command-only/report JSON helpers, owner-specific connected-runner/operator command-only output, connected-runner/operator command sequences, operator report JSON, connected-runner setup/verify helpers, compact external-readiness, warning-review, and bundle/acceptance summary JSON commands, so a resumed runner can route either owner lane without scraping Markdown or calling `next_release_step.py` first. `progress_summary.completion_impacts` maps each deduction source check to the expected completion point recovery, so automation can explain which item moves the handoff estimate before running a setup or approval command. `progress_summary.local_readiness` carries connected-runner issue IDs, next setup, setup/verify sequences, flattened command sequence, and matching JSON/gate commands for origin/Docker/GitHub CLI remediation. Origin setup commands are idempotent for handoff sources: they set the existing `origin` URL when one is present and add `origin` only when it is missing. `progress_summary.warning_review` carries warning action-needed state, operator approval requirement, action-plan/checklist paths, summary/gate commands, and the review sequence before any approval-only apply command. Each `next_commands_by_owner` entry can also include `automation_command`, `full_flow_command`, and `supporting_commands`, so connected-runner automation can surface the same owner-scoped command-only helper, compact external-readiness summary/gate commands, and local-readiness setup/verify helpers from one owner entry, while operator automation can surface its owner-scoped command-only/report JSON helpers, non-gating compact warning summaries, fail-closed compact warning gates, and checklist/review-artifact commands before an approval-only apply step; operator entries also include `review_artifacts` with the action-plan and checklist paths for consumers that should not run another command just to discover those files. Release evidence checks also fail if the embedded progress next command, owner runner command, full-flow command, local-readiness commands, or handoff-bundle summary command point at a stale connected-runner handoff bundle path. The handoff commands include human-readable warning review, `review_release_warnings.py --json-only` for operator automation, `review_release_warnings.py --json-only --fail-if-action-needed` when automation should receive the full JSON payload but fail until planned warning acknowledgements and live-beta archive work are resolved, `review_release_warnings.py --summary-json-only --fail-if-action-needed` when automation only needs compact warning counts and the same unresolved-action exit-code gate, `review_release_warnings.py --review-artifacts-only` when automation needs just the existing action-plan/checklist paths, and `review_release_warnings.py --next-command-only --fail-if-action-needed` when automation needs exactly one selected warning command. They also include `next_release_step.py --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required` for the next runner-owned command, `next_release_step.py --local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass` for unresolved connected-runner setup commands, and `--local-readiness-command-sequence-only --fail-if-local-readiness-not-pass` for setup commands followed by their matching verification commands, without scraping a full report. When a connected-runner bundle exists, `next-release-step.md` uses the safer bundle preflight as the primary command and leaves the manual setup command as a fallback, explicitly noting that preflight rejects missing/placeholder/invalid remote URLs before bundle self-verification and external checks. `check_external_readiness.py` also carries macOS/Homebrew setup commands for missing Docker Desktop and GitHub CLI in its JSON/Markdown `setup_command` fields, so reports can surface `brew install --cask docker ...` and `brew install gh ...` without making those installs part of the automatic preflight; add `--summary-json-only` when automation needs compact status/counts plus warning/failure IDs and setup/verify guidance (`guidance.next_setup_command`, `setup_sequence`, `verify_sequence`, and `command_sequence`), or use the strict summary command with `--require-git-remote --require-docker --require-gh --check-gh-auth` when the connected runner should fail until all external checks pass. On the connected runner, `python3 scripts/next_release_step.py --package-dir PATH --repo-url REPO_URL --no-write` prints the same next step with a concrete remote URL while leaving archived evidence commands portable; replace `REPO_URL` with a real HTTPS, SSH, or scp-style git remote URL because placeholder and invalid values are rejected. If `origin` is already configured, `python3 scripts/next_release_step.py --package-dir PATH --repo-url-from-origin --no-write` reads the known handoff bundle `source/` remote by default and prints the same copy-paste-ready command without rewriting archived evidence; pass `--repo-url-from-origin SOURCE_PATH` only to override the inferred source path. If the runner exports `GIT_ORIGIN_URL`, `python3 scripts/next_release_step.py --package-dir PATH --repo-url-from-env GIT_ORIGIN_URL --no-write` reads and validates that environment value instead. Add `--show-sequence` to print every remaining handoff item for the selected owner, add `--summary-by-owner` to show the remaining connected-runner/operator split, and use `--handoff-bundle "$(pwd)"` from an extracted bundle root to print commands for the current moved path; when `--package-dir` is omitted in a bundle, the latest copied package under `evidence/` is selected automatically, and manual setup/verify/final-verify fallbacks are printed with `cd HANDOFF_BUNDLE/source && ...` so their working directory is explicit. The gate also creates a connected-runner handoff bundle under `artifacts/handoff-bundles/` so the source snapshot and latest evidence archive can be moved safely even before a git remote is configured; the handoff command verifies both the unpacked bundle and the `.tgz` contents for required files, path safety, excluded local artifacts, executable mode, fail-fast command/auth preflight, remote URL guards, GitHub CLI git credential setup, command order, `bash -n` syntax for the `run-connected-runner-handoff.sh` runner script, copied evidence `release-status`/`next-release-step` commands that must point back to the packaging-time bundle path, and report paths for `handoff-verification.json` plus the sibling `.tgz.verification.json`. After extracting the bundle on a connected host, first replace `REPLACE_WITH_REPO_URL` and run `PREFLIGHT_ONLY=true GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh` for a no-install/no-push rehearsal; the script rejects missing/placeholder/invalid remote URLs first, self-verifies the bundle, then runs Docker/GitHub checks, remote reachability/setup, acceptance, dependency installation, or push. Then run `GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh` for the full flow, or initialize git in `source/`, set or add `origin`, install dependencies, then run `python3 scripts/connected_runner_acceptance.py --handoff-root .. --require-external --check-gh-auth` from the `source/` directory to record evidence archive integrity, copied handoff command consistency, and git/Docker/GitHub readiness before the strict gate. If the bundle was moved to a different absolute path after packaging, verifier/acceptance reports may warn about the path mismatch while still validating internal command consistency; run commands from the current extracted bundle root. The bundle runs `gh auth setup-git` by default before `git ls-remote`; set `SETUP_GH_GIT_AUTH=false` only when the runner already manages git credentials.
Connected-runner `HANDOFF.md` now leads with the export-first flow: `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git`, then `PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh`, then `./run-connected-runner-handoff.sh` after preflight passes. It also embeds the current `Completion requirements:` list from `progress_summary.completion_requirements`, so the runner sees shared blockers such as real repo URL, Docker CLI, GitHub CLI auth, and operator approval before invoking commands. The generated bundle `manifest.json` mirrors that context under `handoff_context.quickstart`, `handoff_context.remaining_ids`, `handoff_context.next_item_id`, `handoff_context.owner_lanes`, `handoff_context.bundle_commands`, `handoff_context.bundle_command_sequence`, `handoff_context.bundle_gate_summary`, `handoff_context.completion_plan`, and `handoff_context.completion_requirements`, giving automation the same next-step setup, current owner lane, owner-specific remaining IDs/approval state, ordered bundle-root command sequence, gate counts by owner, first gate by owner, self-verification/acceptance summary commands, bundle-root progress/plan/prerequisite polling, bundle-root operator review sequence, warning summary/artifact/gate commands, the ordered path to 100%, and grouped prerequisites without scraping `HANDOFF.md`. The same `HANDOFF.md` now includes the `--handoff-context-json-only` and `--handoff-command-sequence-only` bundle-root commands for humans who want the manifest context or ordered command list directly. Inline placeholder commands are still supported, but generated handoff verification requires this safer export-first reminder so the real remote URL is set before the runner script starts.
Use `python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-context-json-only` when automation needs exactly that manifest handoff context without rewriting verification reports; use `python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE --handoff-command-sequence-only` when it only needs the ordered commands, one per line. Generated bundle manifests expose the same helpers as `handoff_context.bundle_commands.show_handoff_context_json` and `handoff_context.bundle_commands.show_handoff_command_sequence`, plus `audit_completion_context_json`, `show_progress_json`, `show_completion_plan_json`, `show_completion_requirements_json`, `show_owner_lanes_json`, and `show_warning_artifacts` for bundle-root completion-audit coverage, progress, plan, prerequisite, owner-lane, and warning artifact polling. `python3 scripts/check_completion_audit.py --handoff-bundle PATH_TO_HANDOFF_BUNDLE` verifies that every manifest bundle command has a required completion-audit marker and matching documentation marker before handoff docs drift. `release-status.json` exposes the local bundle commands as `progress_summary.commands.handoff_context_json` and `progress_summary.commands.handoff_command_sequence`. For planning-only resumes, use `progress_summary.commands.local_readiness_setup_sequence_preview` or `progress_summary.commands.local_readiness_command_sequence_preview` to print unresolved connected-runner setup/verify commands without turning non-passing local readiness into a failed gate. For operator review before explicit approval, use `progress_summary.commands.operator_review_sequence`; it prints the warning review sequence while omitting `--apply --operator-approved`.
`progress_summary.warning_review.review_sequence_command` mirrors `progress_summary.commands.operator_review_sequence`, so operator-facing monitors can discover the safe pre-approval review command directly from the warning-review context. `progress_summary.warning_review.pre_approval_sequence_command` points straight to `review_release_warnings.py --pre-approval-sequence-only`, and `progress_summary.warning_review.pre_approval_review_sequence` also exposes the apply-free summary/artifact review commands as a plain list for consumers that should never see an approval-only apply command.
Release evidence checks also compare `progress_summary.next_command` with `next-release-step.json`, so the compact progress entrypoint and the archived next-step entrypoint cannot drift apart. They also verify that compact progress commands preserve the matching release gate summary path, that the embedded progress snapshot mirrors top-level status, readiness deductions, completion impacts, remaining IDs, owner counts, and package path, that the global/owner next entries match the ordered remaining items, that local-readiness issue IDs plus next setup metadata match the connected-runner remaining items, and that warning-review issue IDs, status, approval requirement, next command, review sequence command, and review sequence match the operator warning items.
Owner-specific `progress_summary.next_commands_by_owner` entries also include the matching completion-impact metadata when a remaining item is tied to a deduction, so automation that only reads the next owner command can still show the expected completion-point recovery.
`progress_summary.completion_plan` preserves every remaining item in order with its selected command, owner, status, mode, requirements, completion-impact metadata, warning-review sequence, apply-free pre-approval review sequence, and operator approval requirement, giving resumable automation a compact path from the current 96% state to the external/operator work needed for 100%. Human-readable completion-plan output also labels score-neutral required items such as `warning_actions`, where final completion still needs operator action even though the percentage deduction is owned by `warning_alerts`. The completion_plan mode and completion_plan requirements fields distinguish connected-runner preflight, operator review, operator approval, live-beta closeout, real repo URL, Docker CLI, GitHub CLI auth, backend, backup-reference, and checklist prerequisites without scraping command text. `progress_summary.completion_requirements` then groups those prerequisites by requirement, item IDs, owner lanes, and count so monitors can show all work blocked by the same missing setup or approval, while `progress_summary.commands.show_completion_requirements` and `progress_summary.commands.show_completion_requirements_json` expose direct helper commands for that grouped view.
`progress_summary.owner_lanes` now provides the same remaining work grouped by owner lane, including remaining IDs, the next item, runnable next/automation/full-flow/supporting commands, connected-runner readiness summary, operator review summary, first-mode requirements, approval state, and review artifacts. Use `python3 scripts/report_release_status.py --package-dir PATH --owner-lanes-only` for a human-readable lane view, or `--owner-lanes-json-only` when automation needs only that owner-lane snapshot. The same helpers are embedded as `progress_summary.commands.show_owner_lanes` and `progress_summary.commands.show_owner_lanes_json`, and moved handoff bundles expose `manifest.json handoff_context.bundle_commands.show_owner_lanes_json` for bundle-root polling.
Use `python3 scripts/report_release_status.py --package-dir PATH --completion-plan-only` for a human-readable ordered plan, or `--completion-plan-json-only` when automation needs only that ordered plan without the rest of the compact progress payload. Release evidence checks, connected-runner bundle verification, and connected-runner acceptance also fail if copied release-status artifacts lose those plan-only commands.
External-readiness `--summary-json-only` output also includes `guidance.repo_url`; when setup commands still contain `REPLACE_WITH_REPO_URL`, that object provides a replacement warning and `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git`. Release-status `--progress-json-only` and embedded `progress_summary` payloads also include `repo_url`, so resume automation can detect the same placeholder requirement from the compact progress entrypoint before invoking a runner command.
For automation that needs exactly one next command, use `python3 scripts/next_release_step.py --package-dir PATH --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required`; it prints only the command and exits non-zero while repository URL placeholders remain. Use `--command-sequence-only --fail-if-repo-url-required` when terminal or shell automation needs only the remaining handoff commands, one per line, with adjacent duplicate commands collapsed; before an operator-approved warning apply, the sequence now prints non-gating `--summary-json-only`, then the `--review-artifacts-only` checklist path command, and only then `--apply --operator-approved`. Use `--owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required` instead of `--command-only` when automation needs the runner-owned next-step report as JSON without writing files; connected-runner sequence items include this JSON command, and the JSON gate still prints a payload before exiting non-zero when the repository URL is missing or invalid. When a placeholder remains, next-step output includes `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git` as the concrete setup shape; replace `OWNER/REPO` before using it. Add `--local-readiness --no-write` when a reviewer wants the same next-step output plus read-only local checks for `origin`, Docker Compose, and GitHub CLI auth, or add `--local-readiness` to the JSON command when automation needs those checks in the same read-only payload. JSON reports generated with local readiness include `local_readiness_status`, `local_readiness_issue_ids`, `local_readiness_next_setup_command`, `local_readiness_next_setup.verify_command`, `local_readiness_setup_sequence`, `local_readiness_command_sequence`, and `local_readiness_gate_command` beside connected-runner automation commands so polling can choose either the first local setup/remediation pair, the full structured setup/verify sequence, the already flattened command list, non-gating JSON, or the exit-code gate. Add `--local-readiness-setup-sequence-only` when shell automation needs only unresolved setup commands, one per line, or `--local-readiness-command-sequence-only` when it needs each unresolved setup command followed by its verify command; add `--fail-if-local-readiness-not-pass` when either command list should still fail closed until readiness passes. Add `--fail-if-local-readiness-not-pass` when automation should still receive the JSON/text payload but exit non-zero until every local readiness check passes; combine it with `--command-only --local-readiness` when automation needs exactly one next command and a fail-closed local-readiness gate. When a handoff bundle is known from `--handoff-bundle` or release-status, the command checks that bundle's `source/` directory. Use `--local-readiness-source PATH_TO_SOURCE` only to override the inferred source path. Live-beta preflight support commands also include a no-reload local backend fallback for runners where `uvicorn --reload` file watching is blocked.
For connected-runner automation that needs parseable verification output, add `--json-only` to `python3 scripts/package_connected_runner_handoff.py --verify PATH_TO_HANDOFF_BUNDLE` or `python3 scripts/connected_runner_acceptance.py --handoff-root PATH_TO_BUNDLE --source-root PATH_TO_SOURCE --package-dir PATH_TO_PACKAGE`; add `--summary-json-only` when the resume loop only needs compact status counts plus warning/failure IDs. Both commands still write their JSON/Markdown report artifacts and preserve non-zero exit codes for failures.
It also refreshes `manifest.json` with post-package generated artifacts, then writes and verifies `evidence-checksums.json`, `evidence-checksums.sha256`, and a `.tgz.sha256` sidecar so transferred evidence packages can be checked before review. After checksums are published, use `python3 scripts/write_evidence_checksums.py --package-dir PATH --verify --json-only` when automation needs a parseable integrity result, plus `python3 scripts/check_release_evidence.py --package-dir PATH --no-write`, `python3 scripts/check_release_evidence.py --package-dir PATH --json-only`, `python3 scripts/review_release_warnings.py --package-dir PATH --no-write`, or `python3 scripts/review_release_warnings.py --package-dir PATH --json-only` for read-only inspection so review commands do not rewrite triage/action/check files or refresh the package tarball.
Local machines without Docker, a git remote, or GitHub CLI may keep `external-readiness` in warning state; a connected CI runner or Docker-enabled host should clear those external validation gaps.
After a live-beta window, run `python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight` to check backend reachability, live-lock state, and blocking alerts without writing an archive; add `--json` when automation needs a machine-readable preflight report. Generated operator next-step sequences show that JSON preflight command alongside the human-readable preflight. When that passes, rerun the same command without `--preflight`, then rerun the release gate with `--strict-external --check-gh-auth --require-live-beta`. The backup reference may be a local path or external reference, but placeholder values such as `PATH_TO_BACKUP` are rejected.

See [docs/release-readiness.md](docs/release-readiness.md) for the release-readiness checklist, evidence archive list, live flag lock check, and rollback notes.
See [docs/completion-audit.md](docs/completion-audit.md) for the current requirement-to-evidence audit and known boundaries.

By default, session snapshots are stored at `backend/data/quant_lab.sqlite3`.
Set `QUANT_LAB_DB_PATH` before starting the backend to use a different SQLite file.
The same database stores cached Upbit candles. Set `QUANT_LAB_CANDLE_CACHE_TTL_SECONDS`
to tune freshness; default is `300`, `none` keeps cached candles until overwritten,
and `off` or `disabled` forces refreshes.
Cached candles are also mirrored to DuckDB by default at `backend/data/quant_lab.duckdb`
and can be exported to Parquet at `backend/data/quant_lab_market_candles.parquet`.
Set `QUANT_LAB_DUCKDB_PATH` or `QUANT_LAB_CANDLE_PARQUET_PATH` to move those files.
Set `QUANT_LAB_COLUMNAR_CACHE_ENABLED=false` to disable the columnar mirror.
Saved portfolio scenarios can be scheduled for recurring scans and recurring paper-session batches. Set
`QUANT_LAB_RESEARCH_SCHEDULER_ENABLED=false` to disable the backend scheduler, or
`QUANT_LAB_RESEARCH_SCHEDULER_POLL_SECONDS` to adjust its polling cadence.
Live orders stay locked unless `QUANT_LAB_LIVE_TRADING_ENABLED=true`,
`QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK`, `UPBIT_ACCESS_KEY`, and
`UPBIT_SECRET_KEY` are all configured. Each order intent must also set
`live_confirmation=true`.
The dry-run execution queue is intentionally limited to KRW crypto spot sessions.
US stock/ETF symbols currently run in paper-trading mode only, but eligible
paper-watchlist sessions can be promoted into operator handoffs and exported in
the stock/ETF handoff panel or strategy health handoff report.
Credentialed Alpaca paper submission remains separately gated by
`ALPACA_PAPER_TRADING_ENABLED=true`, `ALPACA_PAPER_TRADING_ACK=PAPER_ORDERS_OK`,
`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `ALPACA_PAPER_BASE_URL`, and a
per-request `paper_submit_confirmation=true`. The adapter rejects live-domain
base URLs and keeps `live_confirmation=true` blocked.
For read-only account checks and live-order safety notes, see
[docs/upbit-private-setup.md](docs/upbit-private-setup.md).
For stock/ETF data setup, see [docs/stock-etf-data-setup.md](docs/stock-etf-data-setup.md).

Useful API routes:

- `POST /api/backtests/run`
- `POST /api/backtests/sweep`
- `POST /api/backtests/validate`
- `POST /api/backtests/walk-forward`
- `GET /api/alerts/review?severity=warning&source=paper_session_risk&scenario=core`
- `POST /api/alerts/review/{alert_id}/acknowledge`
- `GET /api/readiness/live`
- `GET /api/execution/cutover-checklist`
- `GET /api/execution/cutover-checklist/runbook`
- `POST /api/execution/cutover-checklist/simulate-arming`
- `GET /api/execution/post-cutover-monitor`
- `GET /api/execution/post-cutover-monitor/closeout-report`
- `GET /api/ops/self-check`
- `GET /api/ops/runbooks`
- `GET /api/ops/runbooks/{runbook_id}`
- `GET /api/research/strategy-health/traces`
- `GET /api/research/strategy-health/handoff-report`
- `GET /api/research/crypto-live-beta-drill/report?symbol=KRW-BTC`
- `GET /api/operator/decisions?decision_type=dry_run_approval&status=needs_work&target_id=...`
- `GET /api/operator/decisions?decision_type=dry_run_promotion&route_status=paper_only_review`
- `GET /api/operator/decisions/report`
- `POST /api/operator/decisions`
- `POST /api/research/portfolio`
- `GET /api/research/portfolio/presets`
- `POST /api/research/portfolio/scenarios`
- `GET /api/research/portfolio/scenarios`
- `GET /api/research/portfolio/scenarios/{scenario_id}`
- `DELETE /api/research/portfolio/scenarios/{scenario_id}`
- `POST /api/research/portfolio/scenarios/{scenario_id}/scan`
- `GET /api/research/portfolio/scans`
- `GET /api/research/portfolio/scans/{scan_id}`
- `GET /api/research/portfolio/watchlist`
- `POST /api/research/portfolio/watchlist`
- `POST /api/research/portfolio/watchlist/run-due`
- `DELETE /api/research/portfolio/watchlist/{item_id}`
- `GET /api/paper/watchlist`
- `POST /api/paper/watchlist`
- `POST /api/paper/watchlist/run-due`
- `POST /api/paper/watchlist/{item_id}/run`
- `POST /api/paper/watchlist/{item_id}/promote-order-intents`
- `DELETE /api/paper/watchlist/{item_id}`
- `GET /api/bots/fleet`
- `GET /api/bots/profiles`
- `POST /api/bots/profiles`
- `POST /api/bots/run-due`
- `POST /api/bots/profiles/{bot_id}/run`
- `POST /api/bots/profiles/{bot_id}/pause`
- `POST /api/bots/profiles/{bot_id}/resume`
- `DELETE /api/bots/profiles/{bot_id}`
- `GET /api/backtests/runs`
- `GET /api/backtests/runs/{run_id}`
- `GET /api/execution/status`
- `GET /api/execution/settings`
- `GET /api/execution/paper-live-adapters`
- `GET /api/execution/broker-readiness`
- `POST /api/execution/broker-intents/evaluate`
- `GET /api/execution/broker-intents/evaluations`
- `GET /api/execution/broker-intents/evaluations/{evaluation_id}/reconcile`
- `GET /api/execution/broker-intents/evaluations/report`
- `GET /api/paper/sessions/{session_id}/order-notes`
- `GET /api/paper/order-notes/analytics`
- `GET /api/paper/order-notes/quality-gate`
- `GET /api/paper/stock-etf/broker-expansion-readiness`
- `GET /api/paper/stock-etf/broker-expansion-readiness/report`
- `GET /api/paper/stock-etf/broker-expansion-readiness/package/{decision_id}`
- `GET /api/paper/stock-etf/broker-expansion-readiness/package/{decision_id}/preflight`
- `GET /api/paper/stock-etf/broker-expansion-readiness/package/{decision_id}/rehearsal`
- `GET /api/execution/private-snapshot`
- `POST /api/execution/order-intents`
- `GET /api/execution/order-audits`
- `GET /api/execution/order-audits/{record_id}`
- `GET /api/execution/order-audits/{record_id}/precheck`
- `GET /api/execution/order-audits/{record_id}/runbook`
- `POST /api/execution/order-audits/{record_id}/approve`
- `GET /api/markets/ticker`
- `GET /api/markets/providers/status`
- `GET /api/markets/cache/columnar/status`
- `POST /api/markets/cache/columnar/export`
- `POST /api/paper/sessions`
- `GET /api/paper/sessions`
- `GET /api/paper/sessions/{session_id}`
- `POST /api/paper/sessions/{session_id}/order-intents`
- `POST /api/paper/live-sessions`
- `POST /api/paper/live-sessions/{session_id}/advance`
- `POST /api/paper/ticker-sessions`
- `POST /api/paper/live-sessions/{session_id}/tick`
- `GET /api/paper/live-sessions`
- `POST /api/paper/live-sessions/{session_id}/order-intents`

## Verify

```bash
cd backend
python -m unittest discover -s tests

cd ../frontend
npm run build
```

## Planning

See [docs/quant-trading-proposal.md](docs/quant-trading-proposal.md) for the product direction and asset-class recommendation.
See [docs/quant-lab-guide.md](docs/quant-lab-guide.md) for the current runbook, safety checklist, and recommended next work.
See [docs/bot-run-guide-ko.md](docs/bot-run-guide-ko.md) for the Korean Bot Fleet execution guide.
