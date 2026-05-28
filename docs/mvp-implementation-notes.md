# MVP Implementation Notes

Updated: 2026-05-20 KST

## Completed in the first build pass

- Added a FastAPI backend under `backend/`.
- Added a React/Vite dashboard under `frontend/`.
- Added deterministic sample OHLCV data for local development.
- Added an optional Upbit public candle adapter for KRW spot crypto markets.
- Added two initial long-only spot strategies:
  - `sma_crossover`
  - `donchian_breakout`
- Added `rsi_mean_reversion` as a third long-only strategy for oversold-entry and strength-exit experiments across crypto and stock/ETF paper runs.
- Added a strategy parameter sweep API and dashboard card that ranks candidate settings by edge, return, Sharpe, and drawdown without persisting exploratory runs.
- Added a train/test validation API and dashboard card that reports split metrics, edge gap, robustness score, and pass/watch/fail verdicts without persisting exploratory runs.
- Added a rolling walk-forward validation API and dashboard card that summarize repeated out-of-sample folds, fold verdict counts, average test return, average edge, and robustness score.
- Added a backtest engine with:
  - initial cash
  - fees in basis points
  - slippage in basis points
  - no-lookahead signal execution
  - equity curve
  - drawdown
  - Sharpe/Sortino
  - simulated order log
- Added a dashboard for:
  - market/source/strategy selection
  - strategy parameters
  - metric cards
  - equity curve
  - simulated orders table
- Added SQLite-backed paper trading session storage.
- Added live-replay paper sessions that start from a warmup window and advance candle-by-candle.
- Added risk guardrails:
  - max position percentage
  - max order notional
  - max exposure-increasing orders
  - session loss halt
  - kill switch
- Added dashboard controls and status display for paper sessions and recent risk events.
- Added dashboard controls for starting a replay session and advancing it by 5 candles at a time.
- Added auto-replay controls that advance live paper sessions one candle per timer tick.
- Added recent live replay session listing from the backend session API.
- Added a market ticker API and dashboard panel that polls sample or Upbit public last price.
- Added ticker-driven live paper sessions that seed strategy history and advance from fresh ticker ticks.
- Added SQLite-backed live paper runtime snapshots so replay/ticker sessions can be listed, fetched, and resumed after the in-memory cache is cleared or the API process restarts.
- Added a SQLite-backed Upbit candle cache keyed by source, symbol, timeframe, and timestamp. Cached candles are reused for repeated backtests/paper runs while fresh enough, reducing repeated public API calls.
- Added SQLite-backed backtest run history with summary and detail APIs.
- Added a dashboard backtest history panel that can reload previous runs into the metrics, equity curve, and orders views.
- Added history controls for sorting stored backtests by newest, edge, return, Sharpe, or drawdown and filtering them by data source, strategy, and symbol.
- Added a dashboard run comparison panel for selecting up to three recent backtests and comparing return, max drawdown, Sharpe, trades, source, and final equity side by side.
- Added normalized multi-run equity overlays for selected backtests, so strategy paths can be compared across different initial cash levels or currencies.
- Added a buy-and-hold benchmark overlay to the main equity chart with a strategy edge readout.
- Added buy-and-hold benchmark metrics to backend backtest results and persisted run summaries: final equity, return, max drawdown, and strategy edge.
- Added read-time benchmark metric backfill for legacy stored backtest runs that predate the benchmark fields.
- Added a disabled-by-default Upbit private execution adapter shell with JWT signing, order payload validation, and multi-step live-order guard flags.
- Added SQLite-backed order audit records so every live order intent is logged even when execution is blocked.
- Added a dashboard execution guard panel showing live flag state, adapter readiness, base URL, and recent order audit records.
- Added a read-only Upbit private snapshot API for balances and open orders. Without credentials it returns an explicit disabled state instead of failing the dashboard.
- Added dashboard private-read status, balance count, and open-order count to the execution guard panel.
- Added a manual execution panel refresh action so private reads, guard status, and order audit records can be rechecked on demand.
- Added Upbit private-mode setup documentation for read-only credentials and the live-order lock.
- Added a dry-run strategy order intent queue that converts recent paper-session trades into Upbit-shaped limit order intents with `dry_run` audit status.
- Added a Paper trading panel action for queueing simulated trades as dry-run order intents and refreshing the execution audit panel.
- Added a crypto-only paper-watchlist promotion action that filters recent generated paper sessions by return, drawdown, and order-count rules before queueing dry-run order intents for manual review.
- Added promotion context to dry-run audit payloads so order review can show the originating scenario and promotion rule snapshot.
- Added exportable Markdown runbooks for dry-run approval candidates, including source context, promotion rules, execution guard state, precheck results, approval procedure, and stop conditions.
- Added a guarded dry-run approval API and dashboard order review panel. Approval attempts create new audit records and still require the backend live-order guard before exchange submission.
- Added a dry-run pre-approval check API and review-panel display for estimated notional, configurable minimum order notional, private balance availability, fees, and estimated post-order exposure.
- Integrated Upbit `/v1/orders/chance` into pre-approval checks when credentials are configured, using exchange-provided fees, market min/max totals, price unit, and bid/ask account balances.
- Added an execution settings API and dashboard panel for credential presence, ACK lock state, live-confirmation requirement, guard thresholds, base URL, and whether prechecks use Upbit order availability or local defaults.
- Added a deterministic US stock/ETF sample data source (`sample_us`) with `SPY`, `QQQ`, `AAPL`, `MSFT`, `NVDA`, and `TSLA` symbols for paper-trading expansion work.
- Updated the dashboard source and symbol controls so US stock/ETF runs use USD display formatting, lower sample fees/slippage, and paper-only order handling.
- Added broker-aware paper-to-live adapter profiles that route KRW crypto sessions to guarded Upbit dry-run audits and US stock/ETF sessions to paper-only operator handoffs.
- Added explicit broker adapter contracts for guarded Upbit private API routing, a mock US equities paper broker, and an Alpaca-style paper preview, with tests that keep stock/ETF live submission disabled.
- Added a broker readiness API and dashboard panel that expose contract checks, credential boundaries, and the blocked live-submission state for stock/ETF paper routing.
- Added a broker-neutral stock/ETF paper intent evaluation API and dashboard sandbox that validates market/limit order shapes through mock and Alpaca-style paper contracts while proving no external submission is attempted.
- Added provider-agnostic stock/ETF paper fill estimates to broker intent evaluation, covering reference price, slippage, fees, cash sufficiency, position sufficiency, post-fill cash, post-fill quantity, and exposure.
- Added SQLite-backed broker intent evaluation history and a dashboard recent-evaluations list so stock/ETF paper broker checks can be recalled and filtered by paper adapter without creating live-order audits.
- Added an exportable broker intent evaluation Markdown report for stock/ETF paper-only routing reviews, including adapter coverage, the credential boundary, and external-submission-attempt summary.
- Added paper fill order notes that attach accepted stock/ETF broker estimates to linked paper sessions and compare intended fills with the latest same-side simulated trade.
- Added paper fill drift analytics that aggregate linked order notes by stock/ETF symbol and paper broker adapter, including matched-trade counts plus average and worst intended-vs-simulated price delta.
- Added a stock/ETF paper fill quality gate that classifies paper broker routes as ready, watch, or blocked using sample count, average drift, worst drift, and external-submission evidence.
- Added a stock/ETF broker expansion readiness API and Markdown report that summarize approved-ready paper-only handoffs for future paper broker adapter work.
- Added a per-candidate stock/ETF broker expansion package export with Alpaca-style paper order payload drafts, linked evaluation/order-note evidence, and explicit no-external-submission stop conditions.
- Added a stock/ETF broker expansion package preflight export that checks approved-ready state, quality gate readiness, payload schema, no-external-submission evidence, and Alpaca preview coverage.
- Added a local stock/ETF broker expansion rehearsal export that replays package payloads into paper-only accepted/rejected order records without external broker submission.
- Added a credential-gated Alpaca stock/ETF paper trading adapter that calls the paper Trading API only when paper endpoint, credentials, ACK, env flag, and per-request paper submission confirmation are all present.
- Added Alpaca paper order reconciliation for saved broker intent evaluations, including broker-side status lookup, persisted reconciliation snapshots, and a dashboard history row action.
- Added rich Alpaca paper reconciliation evidence for partial fills, fill activities, average fill price, fee, account cash/equity, position snapshots, and linked paper-fill-note comparisons.
- Added a dashboard paper-live routing panel that displays the active symbol route plus the guarded Upbit crypto and stock/ETF paper-only adapter profiles before promotion.
- Kept dry-run execution queueing limited to KRW crypto spot sessions; stock/ETF symbols now return a clear paper-only backend validation error if a direct execution queue is requested.
- Added stock/ETF paper-watchlist promotion handoffs that log operator journal decisions and appear in the strategy health handoff report without creating live-order audits.
- Added `route_status=paper_only_review` filtering for Operations journal API/list exports, plus dashboard filter controls and route badges for stock/ETF paper-only handoffs.
- Added a dedicated stock/ETF paper handoff panel with recent symbols, scenario source, route status, journal status, and a compact Markdown export.
- Added direct stock/ETF handoff review actions in the dashboard panel so operators can log noted, needs-work, approved, or rejected paper-only decisions without creating live-order audits.
- Connected stock/ETF paper-only handoff approval to the paper fill quality gate, blocking approved decisions until the gate is ready and storing gate evidence on approved operator decisions.
- Added stock/ETF handoff drill-down rows that load the linked paper session, recent simulated trades, risk summary, promotion rule snapshot, and recent broker intent/fill evaluations from the dashboard.
- Linked recent broker intent/fill evaluations into the paper-only section of the strategy health handoff report by stock/ETF symbol.
- Linked paper fill order notes into stock/ETF handoff drill-downs and strategy health handoff exports by paper session.
- Added an optional Alpha Vantage daily stock/ETF source (`alpha_vantage`) behind `ALPHA_VANTAGE_API_KEY`, with SQLite candle caching and compact daily row-count warnings.
- Added stock/ETF data setup documentation covering `sample_us`, `alpha_vantage`, API-key setup, and the paper-only execution boundary.
- Added a market data provider status API and dashboard panel showing provider readiness, required credential name, cache TTL, last successful fetch, last attempted symbol/timeframe, row count, and latest error.
- Added freshness timestamps to execution status/settings, private snapshots, provider status checks, and dry-run precheck order-info data.
- Added a dashboard setup checklist for Alpha Vantage, Upbit private keys, live-order lock flags, ACK status, and approval guardrail values.
- Added a persisted dark/white theme toggle and CSS theme-token layer across panels, controls, charts, tables, badges, and status messages.
- Refined the dashboard styling with a Stitch-inspired design pass: clearer operational hierarchy, higher-density status rows, stronger dark-mode contrast, and consistent semantic colors.
- Added portfolio research APIs and dashboard controls for multi-symbol strategy comparisons.
- Added custom portfolio allocation weights plus a `none`/`monthly` rebalancing rule. Monthly rebalancing resets sleeve values back to target weights when the candle month changes.
- Added built-in portfolio research presets for crypto-major spot, balanced US core, higher-beta US growth, and stock/ETF RSI reversion paper-trading baskets.
- Added SQLite-backed saved portfolio research scenarios, with dashboard controls to save, load, and delete repeatable allocation studies.
- Added saved-scenario scan runs that execute a stored portfolio setup, persist the full research result, and expose recent scan history in the dashboard.
- Added a scheduled portfolio scan watchlist. Saved scenarios can be watched on an interval, checked by the backend scheduler, run immediately through the due-scan API, and removed from the dashboard.
- Added alert thresholds to scheduled portfolio scans for max drawdown, minimum total return, minimum average strategy edge, and total-return drift versus the previous scan.
- Added a portfolio paper watchlist that promotes saved scenarios into recurring paper-session batches, allocates starting cash by scenario weights, and surfaces the latest generated sessions in the dashboard.
- Added a compact alert review queue API and dashboard panel that groups scheduled scan alerts, watchlist errors, paper-session halts, and paper-session risk events.
- Added broker paper submission, reconciliation, and paper fill drift alerts to the alert review queue and strategy health handoff report.
- Added alert review filters by severity, source, and scenario name/ID so the operations queue can be narrowed before acknowledgement or dismissal.
- Added persisted alert review acknowledgement and dismissal state so reviewed items are hidden from the active alert queue by default.
- Added a live-readiness score API and dashboard panel that summarizes Upbit public data, execution guard state, private-read readiness, active alerts, KRW paper evidence, dry-run audits, and runbook availability.
- Split live-readiness into system and operator views with independent scores, blocker IDs, warning IDs, and dashboard drill-down cards.
- Added a live-order cutover checklist API and dashboard panel that blocks adapter arming until readiness review, dry-run approval, and live-cutover operator decisions are logged.
- Added an exportable live adapter arming runbook that captures the cutover checklist, environment guard state, readiness checks, operator decisions, arming procedure, and stop conditions.
- Added a live-adapter arming simulator API and dashboard preview that compares the current checklist against assumed live flag, ACK, and credential configuration, then lists remaining simulated blockers without submitting orders.
- Added a post-cutover order monitor API and dashboard panel that tracks approval attempts, latest audit status, private snapshot health, and private open orders during a live window.
- Added an exportable live-window closeout report that captures final monitor checks, approval attempts, private snapshot/open orders, and operator decisions after the adapter is locked again.
- Added a strategy health attribution trace API and dashboard panel that links portfolio watchlist promotion rules, paper trade metadata, dry-run approval decisions, live approval attempts, and closeout outcomes.
- Added an exportable strategy health handoff report that bundles trace rows, closeout status, dry-run audit IDs, approval decisions, approval attempts, milestones, and linked runbook endpoints.
- Added a crypto live beta drill report API and dashboard export that bundles KRW paper sessions, dry-run audits, prechecks, runbooks, live-readiness review, cutover simulation, closeout evidence, and strategy-health traces without submitting live orders.
- Added deployment hardening artifacts: Docker Compose, backend/frontend Dockerfiles, nginx API proxy, `.env.example`, container healthchecks, backup/restore notes, and a pre-market operator checklist.
- Added a seeded crypto drill command that creates a sample KRW paper session, queues dry-run intents, exports runbooks, and writes the crypto live beta drill report without changing live-order gates.
- Added production observability notes and an ops smoke-check command for health/readiness/alert/monitor/drill checks, scheduler triage, disk usage review, log retention, and closeout archive naming.
- Added a managed local smoke-test command that can start a uvicorn backend, wait for health, run ops smoke checks and optional seeded drill, then stop the backend cleanly.
- Added a bundled project verification command and release-readiness checklist covering tests, build, script compilation, Docker config, evidence archives, live flag locks, rollback, and restore notes.
- Added an evidence package command that gathers latest verification summaries, smoke checks, crypto drill artifacts, live-beta archives, runbooks, docs, a manifest, and an optional `.tgz` review bundle.
- Added a GitHub Actions CI workflow that runs project verification, a managed local smoke drill, evidence packaging, and artifact upload with live-order flags locked.
- Expanded CI artifact uploads to retain external readiness reports, connected-runner handoff bundles, and live-beta archives alongside verification, smoke/drill, evidence, and release gate summaries.
- Added a release evidence checker that validates package contents, verification pass status, smoke/drill artifacts, live-lock evidence, alert severity, and package safety metadata before handoff.
- Added a release gate command that runs verification, optional managed smoke drill, evidence packaging, release evidence checking, and a compact JSON handoff summary in one operator-friendly command.
- Added automatic release warning triage artifacts that turn warning-only evidence states into alert IDs and recommended operator actions inside the package.
- Added a release warning review command that writes a dry-run action plan plus operator checklist and can deliberately acknowledge or dismiss warning alerts with `--apply --operator-approved`.
- Added a release status report command that summarizes the latest gate, evidence checks, external readiness, warning actions, approximate completion percentage, owner-tagged remaining handoff items, and next actions into package-level JSON and Markdown.
- Added a next release step command that reads the latest release status and writes a single-command handoff summary for connected-runner and operator follow-up.
- Added external readiness remediation and final-verify commands so connected-runner gaps include both setup guidance and the strict gate command.
- Added GitHub Actions workflow/run visibility checks to external readiness when GitHub CLI auth is available, and wired CI to provide `GH_TOKEN` for that evidence.
- Added a connected-runner handoff bundle command that packages a safe source snapshot plus the latest evidence archive when no git remote is available yet.
- Added connected-runner handoff self-verification for forbidden source paths, required files, evidence archive checksum sidecars, and manifest safety flags.
- Added connected-runner handoff tarball verification for required archive members, scoped relative paths, evidence archive presence, and forbidden source artifact exclusions.
- Added an executable connected-runner handoff script to the bundle so `GIT_ORIGIN_URL=REPLACE_WITH_REPO_URL ./run-connected-runner-handoff.sh` can initialize git, install dependencies, run acceptance, push, and rerun the strict gate.
- Added runner script executable-mode and shell-syntax checks to connected-runner handoff verification, and local fallback git identity for fresh connected-runner commits.
- Added fail-fast connected-runner script preflight for git, Python, npm, Docker Compose, GitHub CLI auth, and placeholder remote URLs before dependency installation begins.
- Added a connected-runner acceptance preflight that verifies extracted source safety, copied evidence archive integrity, bundle runner script integrity, and strict external readiness before running the final gate.
- Moved connected-runner acceptance ahead of dependency installation in the bundled runner flow so evidence/source issues fail before pip/npm work starts.
- Added `PREFLIGHT_ONLY=true` support to the connected-runner bundle script for no-install/no-push rehearsals on a connected host.
- Added tarball-level runner script syntax and preflight-marker verification so the transfer archive proves the same runner safety checks as the unpacked bundle.
- Added behavioral runner remote-guard verification so missing or placeholder `GIT_ORIGIN_URL` fails before connected-runner command, dependency, or push work begins.
- Expanded runner remote-guard verification so `REPO_URL` and `GIT_ORIGIN_URL` literal placeholders are rejected as placeholders, not only as generic invalid URLs.
- Aligned behavioral runner remote-guard verification with the documented next command by exercising guard cases with `PREFLIGHT_ONLY=true`.
- Added `test_package_connected_runner_handoff.py` so the generated runner script remote guard is covered by the normal local verification command before release packaging.
- Added `test_connected_runner_acceptance.py` so the acceptance verifier's remote guard is also covered by the normal local verification command.
- Promoted the literal-placeholder remote guard message and order into required runner script markers so handoff verification fails if the guard is removed or moved after command preflight.
- Quoted generated handoff, next-step, warning-review, checksum, and status-report path arguments so copied commands keep working when evidence or bundle paths contain spaces.
- Added runner command-order verification so remote guards, auth preflight, acceptance, dependency installation, push, and strict release gate run in the intended connected-runner sequence.
- Added invalid remote format rejection plus `git ls-remote` reachability preflight so connected-runner handoff fails before dependency installation when the target repository is unreachable.
- Added default `gh auth setup-git` setup before `git ls-remote`, with `SETUP_GH_GIT_AUTH=false` available for runners that manage git credentials separately.
- Added explicit connected-runner failure guidance when `gh auth setup-git` fails before remote reachability checks.
- Promoted the connected-runner bundle preflight to the primary `next-release-step` command when a handoff bundle exists, leaving manual `git remote add` setup as a fallback.
- Added the first connected-runner preflight and full-flow commands to `release-status.md` so the top-level status report and `next-release-step.md` point to the same safe handoff path.
- Added preferred connected-runner commands to each connected-runner remaining handoff item in `release-status.md`, ahead of the manual remediation command.
- Added copied evidence command consistency checks so handoff verification fails when bundled `release-status` or `next-release-step` artifacts point at an older connected-runner bundle.
- Added the same copied command consistency signal to connected-runner acceptance, with a warning path for bundles extracted to a different absolute path on another runner.
- Updated handoff bundle verification to preserve copied command checks after transfer by validating against the packaging-time path from `manifest.json` and warning when the current extracted path differs.
- Added connected-runner bundle self-verification to the generated runner script after remote URL guards and before external Docker/GitHub checks, remote setup, acceptance, dependency installation, or push.
- Added macOS/Homebrew setup commands for missing Docker Desktop and GitHub CLI to external-readiness JSON/Markdown so connected-runner reports show concrete manual remediation while preserving the bundle preflight as the first automated command.
- Extended `next_release_step.py --local-readiness` so text and JSON output carry per-check remediation/setup commands for unresolved `origin`, Docker, and GitHub CLI gaps.
- Added top-level `local_readiness_next_setup_command` / `local_readiness_next_setup_check_id` so automation can select the first unresolved connected-runner setup command without scanning every local-readiness check.
- Added `local_readiness_next_setup.status` and `local_readiness_next_setup.verify_command` so automation can pair the first setup command with the exact read-only verification command for that local runner gap.
- Added `local_readiness_setup_sequence` so connected-runner automation can iterate all unresolved local setup/verify pairs in readiness order.
- Added top-level `local_readiness_command_sequence` so JSON automation can consume the exact setup/verify command order without rebuilding it from structured pairs.
- Added `next_release_step.py --local-readiness-setup-sequence-only` so connected-runner shell automation can print only unresolved local setup commands while preserving the local-readiness exit-code gate.
- Added `next_release_step.py --local-readiness-command-sequence-only` so connected-runner shell automation can print unresolved setup commands followed by matching verification commands while preserving the same fail-closed gate.
- Added the setup-sequence-only and setup-and-verify local-readiness commands to release-status handoff commands, handoff README guidance, evidence command-safety checks, and connected-runner copied-command verification.
- Added `next_release_step.py --command-sequence-only` plus release-status handoff commands so shell automation can print only the remaining handoff commands, one per line, with adjacent duplicates collapsed and repo placeholders gated.
- Added `report_release_status.py --progress-only` plus a release-status handoff command so resume/status checks can print only the completion percent, remaining IDs, owner counts, and deductions without dumping the full JSON report or rewriting checked evidence.
- Added release evidence command-safety coverage so packages fail validation if generated handoff commands lose the `report_release_status.py --progress-only` compact progress path.
- Added connected-runner bundle and acceptance checks so copied evidence also fails verification if the compact progress handoff command is missing from release-status Markdown or JSON.
- Added `report_release_status.py --progress-json-only` plus release evidence, bundle, and acceptance checks so automation can parse compact progress data without dumping the full status report.
- Extended `--progress-json-only` with the selected global next command, first next command per owner, and selected resume commands for progress text/JSON, all-owner and connected-runner remaining sequences, operator sequence, local-readiness setup/verify, warning action gates, warning review artifacts, and operator-approved warning apply.
- Embedded the same compact progress payload under `release-status.json` `progress_summary`, and added a release-evidence safety check so packages fail if those resume fields disappear.
- Added explicit connected-runner bundle verification report paths to handoff packaging output and release status so preflight warnings point reviewers to `handoff-verification.json` and the tarball verification report.
- Added a `next_release_step.py --repo-url REPO_URL --no-write` mode so connected runners can print copy-paste-ready commands without mutating archived evidence command references.
- Added explicit next-step notes when connected-runner commands still contain `REPLACE_WITH_REPO_URL` so reviewers know literal placeholders are rejected before they try the bundle script.
- Clarified `next_release_step.py --owner ...` output so filtered owner views show owner-specific remaining counts alongside the total handoff count.
- Added `next_release_step.py --show-sequence` plus release-status handoff commands for printing every remaining connected-runner/operator handoff command in order.
- Added `next_release_step.py --summary-by-owner` so reviewers can see the remaining connected-runner/operator handoff split before choosing the next execution lane.
- Added the same owner split to generated `next-release-step.md` files so archived handoff evidence is self-contained even without rerunning the CLI.
- Added `next_release_step.py --repo-url` validation so placeholder, empty, and invalid-format repository URLs fail before printing connected-runner commands.
- Applied the same repository URL validation inside the next-step report builder so imported helper usage cannot bypass the CLI guard.
- Added live-beta closeout backup-reference validation so empty strings and placeholders such as `PATH_TO_BACKUP` fail before archive creation.
- Added `test_archive_live_beta_closeout.py` and wired it into `verify_project.py`, evidence packaging, release evidence checks, and connected-runner handoff requirements.
- Updated generated release status live-beta commands to use a concrete backup-reference example instead of the rejected `PATH_TO_BACKUP` placeholder, with `test_report_release_status.py` coverage.
- Added `archive_live_beta_closeout.py --preflight` and promoted generated live-beta handoff commands to run this no-write backend/live-lock/blocking-alert check before writing closeout archives.
- Added `archive_live_beta_closeout.py --preflight --json` so automation can parse live-beta preflight status without scraping text output.
- Added the live-beta JSON preflight command to generated operator next-step sequences so automation can parse archive readiness from the same handoff view.
- Updated `next_release_step.py` so non-connected-runner items also use `preferred_command` as the nearest next command and show the follow-up full-flow command after preflight.
- Added an explicit `--operator-approved` guard for `review_release_warnings.py --apply`, updated generated warning-action commands, and covered the dry-run/apply safety path with `test_review_release_warnings.py`.
- Added release evidence command-safety checks so generated handoff artifacts fail if backup-reference placeholders return or warning `--apply` commands omit `--operator-approved`, with `test_check_release_evidence.py` coverage.
- Replaced shell-unsafe generated repo URL placeholders with `REPLACE_WITH_REPO_URL`, kept legacy `<repo-url>` rejection in the runner guard, and added evidence command-safety coverage for this failure mode.
- Tightened the generated connected-runner script's remote URL guard so malformed HTTPS/SSH/scp-style values with missing host or path fail before source checks or `git ls-remote`.
- Added explicit runner order verification for the remote URL validation call so handoff checks fail if that guard is removed or moved behind command/auth preflight.
- Changed pre-generation command-safety evidence checks from pass to skipped so early package checks do not imply command artifacts were already inspected.
- Added `check_release_evidence.py --no-write` for post-checksum read-only evidence review, and switched the CI follow-up evidence check to that mode so it does not rewrite triage/check files after checksum publication.
- Added copied-command verification for the read-only evidence check command so handoff packaging and connected-runner acceptance fail if the post-checksum inspection command goes missing.
- Added `review_release_warnings.py --no-write` plus copied-command verification so post-checksum warning review does not rewrite action/checklist artifacts or refresh package tarballs.
- Updated `review_release_warnings.py --no-write` so post-checksum operator review prints existing action/checklist paths and the shell-safe `--apply --operator-approved` command without mutating package files.
- Added `review_release_warnings.py --json-only` so operator automation can read the same warning action plan as JSON without mutating checked evidence.
- Added structured warning-review command fields to the JSON action plan so automation can reuse the exact review, JSON, gate JSON, and apply commands.
- Relaxed `next_release_step.py --json-only` so `--summary-by-owner` and `--show-sequence` remain accepted for automation callers; the JSON payload already carries owner summaries and ordered remaining items.
- Updated the completion audit smoke-test count to 118 after adding JSON/sequence compatibility coverage.
- Added `review_release_warnings.py --fail-if-action-needed` so operator automation can still parse the JSON plan while using the exit code as a gate for unresolved warning actions.
- Added the warning-review JSON command to generated release-status handoff commands and copied-command verification so handoff bundles fail if the automation path goes stale.
- Added release evidence command-safety coverage for the warning-review JSON gate so packages fail validation if operator automation loses `--fail-if-action-needed`.
- Added the warning-review JSON command to operator next-step sequence output so automation can parse warning decisions from the same owner-filtered handoff view.
- Added handoff and connected-runner acceptance checks for source `.gitignore` guard patterns so generated artifacts, dependencies, local data, backups, and secrets stay out of the runner's `git add .` flow.
- Rerun the release evidence check inside `release_gate.py` after status, next-step, and warning action files are generated so command-safety checks run before checksum publication.
- Added a `test_next_release_step.py` smoke check to the verification bundle so repo URL validation/substitution, owner counts, owner summary, and sequence output are covered by `verify_project.py`.
- Promoted the next-step smoke test and related release scripts into the required connected-runner source list so handoff verification and acceptance fail if they are missing.
- Added copied evidence checks for the next-step, repo-url, all-owner sequence, and connected-runner sequence helper commands so release-status handoff commands cannot silently go stale.
- Added a `next_release_step.py --handoff-bundle PATH --no-write` mode and current-bundle HANDOFF commands so moved bundles can print commands for their actual extracted path.
- Added `next_release_step.py --command-only` plus `--fail-if-repo-url-required` so automation can fetch one next command and fail before using repository URL placeholders.
- Added `next_release_step.py --json-only` so automation can fetch the full next-step report without writing files, with conflicts rejected for other stdout modes.
- Updated the repo URL JSON gate so `--json-only --fail-if-repo-url-required` still prints the next-step payload with `repo_url_error` / `repo_url_gate_message` before exiting non-zero.
- Updated the completion audit smoke-test count to 119 after adding repo URL JSON gate payload coverage.
- Added `report_release_status.py --json-only` so automation can read the compact release status report after checksums are published without rewriting archived evidence.
- Updated the completion audit smoke-test count to 120 after adding release-status JSON output coverage.
- Added release evidence command-safety coverage so packages fail validation if generated handoff commands lose the `report_release_status.py --json-only` automation path.
- Added `check_release_evidence.py --json-only` so automation can read the full evidence-check payload after checksums are published without rewriting check or warning triage artifacts.
- Added release evidence command-safety coverage so packages fail validation if generated handoff commands lose the `check_release_evidence.py --json-only` automation path.
- Updated the completion audit smoke-test count to 121 after adding release-evidence JSON output coverage.
- Added `write_evidence_checksums.py --verify --json-only` plus handoff command-safety coverage so connected-runner automation can parse transferred-package integrity checks.
- Updated the completion audit smoke-test count to 123 after adding checksum JSON output coverage.
- Added `package_connected_runner_handoff.py --json-only` and `connected_runner_acceptance.py --json-only` so connected-runner automation can parse bundle verification and acceptance reports directly from stdout.
- Updated the completion audit smoke-test count to 125 after adding connected-runner verification JSON output coverage.
- Added connected-runner bundle verification and acceptance JSON commands to release-status handoff commands, with release evidence safety checks that fail if those automation paths disappear while human-readable variants remain.
- Promoted live-beta closeout preflight and `--preflight --json` commands into release-status handoff commands, with release evidence safety coverage so operator automation keeps a parseable no-write preflight path.
- Extended connected-runner handoff and acceptance command-consistency checks to verify live-beta preflight, live-beta preflight JSON, and live-beta closeout commands inside copied release-status artifacts.
- Added release evidence command-safety coverage for repo-url-from-env automation so generated `--json-only` and `--command-only` commands must keep `--fail-if-repo-url-required`.
- Added a connected-runner owner-scoped JSON next-step command to generated handoff commands and runner-owned sequence items, with copied-command verification.
- Added a local-readiness JSON helper command so connected-runner automation can parse origin, Docker Compose, and GitHub CLI readiness in the same owner-scoped next-step report.
- Clarified `next_release_step.py --local-readiness` help and validation so the read-only requirement explicitly allows either `--no-write` text output or `--json-only` automation payloads.
- Preserved `--local-readiness` inside connected-runner JSON `automation_command` values when local readiness is requested, so automation can keep polling the richer readiness payload.
- Added `local_readiness_status` and `local_readiness_issue_ids` to local-readiness output so connected-runner automation can branch without recomputing check summaries.
- Added `next_release_step.py --fail-if-local-readiness-not-pass` so automation can still receive the local-readiness payload while using the exit code as a gate.
- Added `local_readiness_gate_command` plus text `Automation JSON gate` output so local-readiness reports expose both the non-gating JSON poll command and the fail-fast gate command.
- Added a release-status handoff command for the local-readiness fail gate so connected-runner automation can copy the exact JSON command from package artifacts.
- Added release evidence command-safety coverage for the local-readiness JSON fail gate so packages fail validation if connected-runner automation loses `--fail-if-local-readiness-not-pass`.
- Added `next_release_step.py --command-only --local-readiness --fail-if-local-readiness-not-pass` so connected-runner automation can print exactly one next command while still failing closed until origin, Docker Compose, and GitHub CLI readiness pass.
- Updated connected-runner acceptance to distinguish unsafe source files from expected connected-runner install artifacts such as `.git`, `backend/.venv`, and `frontend/node_modules`.
- Added evidence package checksum generation and verification, including `.tgz.sha256` sidecar checks, so copied archives and package contents can be integrity-checked during handoff.
- Added a release-status handoff command and copied-command verification for local connected-runner readiness checks so reviewers can inspect `origin`, Docker Compose, and GitHub CLI auth without mutating evidence.
- Added post-package artifact inventory refresh in `manifest.json` before checksum generation so generated gate, warning, status, and next-step files are listed in the package manifest.
- Added shared release artifact selection helpers so latest-package commands prefer package metadata timestamps and beta sequence numbers over mutable directory modification times.
- Extended release artifact selection to release-gate and external-readiness JSON files so generated timestamps and path timestamps win over mutable filesystem times.
- Updated evidence packaging to use the shared artifact selector for verification, smoke, drill, live-beta, and copied verification-status sources before falling back to filesystem modification time.
- Added `test_package_evidence.py` and promoted package-evidence scripts into verification, evidence, and connected-runner handoff requirements so packaging source-selection regressions are covered end-to-end.
- Added `handoff_commands.py` to share generated handoff command builders across next-step output, release status, bundle packaging, and connected-runner acceptance, reducing drift in quoted paths and helper commands.
- Moved repo URL placeholder constants into `handoff_commands.py` so external readiness, next-step output, bundle generation, and acceptance checks reject and substitute the same placeholder values.
- Added `connected_runner_contract.py` and `test_connected_runner_contract.py` to share and directly test runner script markers, command-order rules, remote guard cases, source exclusion helpers, and required source `.gitignore` pattern parsing across bundle generation and acceptance.
- Updated `next_release_step.py --local-readiness` so extracted handoff bundles default readiness checks to `HANDOFF_BUNDLE/source` when `--local-readiness-source` is omitted, and text output prints the inspected source path, readiness status counts, and source-scoped origin check commands.
- Updated `next_release_step.py --handoff-bundle` so manual setup, verify, and final-verify fallback commands are shell-quoted and rebased to the current `HANDOFF_BUNDLE/source`.
- Updated `report_release_status.py` so connected-runner remaining-item manual remediation, verify, and final-verify commands are also shell-quoted and rebased to the current `HANDOFF_BUNDLE/source`.
- Hardened and directly tested shared source-scoped handoff command generation so repeated leading `cd ... &&` prefixes from older copied artifacts are stripped before rebasing to the current bundle while quoted `&&` remains intact.
- Extended the release manifest smoke guard so shared handoff command helpers, next-step/status CLIs, and their direct regression tests must stay in evidence and connected-runner source packages.
- Updated connected-runner acceptance so `--handoff-root` defaults source checks to the bundle's `source/` snapshot when `--source-root` is omitted, preventing local generated data from being mistaken for packaged source.
- Updated connected-runner acceptance so `--package-dir` can validate either the copied bundle evidence archive or a local evidence package with its sibling `.tgz` archive.
- Added named latest-package helpers in `release_artifacts.py` and moved package/evidence/status/warning CLI selection to those helpers so marker-file and metadata ordering rules are centralized.
- Added `release_manifest.py` to share required evidence and handoff source file lists across package creation, release evidence checks, bundle verification, and connected-runner acceptance.
- Added `test_release_manifest.py` plus `verify_project.py` coverage so shared manifest lists stay duplicate-free and include the core verification, smoke, and drill helper scripts in evidence and handoff packages; `verify_project.py` now compiles `CORE_RELEASE_SCRIPT_FILES` from the shared manifest as the single source of truth.
- Added `report_release_status.py --no-write` and a post-checksum rewrite guard so status review can run without mutating package files; intentional rewrites require `--allow-post-checksum-write` plus checksum regeneration.
- Added completion-deduction details to release status and next-step outputs so reviewers can see exactly why the current handoff estimate remains below 100%.
- Added the same completion context to generated connected-runner `HANDOFF.md` files so transferred bundles show current status, remaining item count, and completion deductions before any command runs.
- Added handoff verification checks that compare `HANDOFF.md` completion context against the copied `release-status.json`, including the tarball copy, so stale transferred status summaries fail packaging verification.
- Added the same `HANDOFF.md` completion-context comparison to connected-runner acceptance so extracted bundles fail acceptance if the README status summary drifts from copied release evidence.
- Moved the `HANDOFF.md` completion-context marker contract into `connected_runner_contract.py` so packaging and acceptance share the same stale-summary detection logic.
- Moved generated `HANDOFF.md` completion summary lines onto the same connected-runner contract markers used by verification, keeping README creation and stale-summary checks aligned.
- Added source check IDs to readiness completion deductions so release-status, next-step, and handoff context can identify the exact external, evidence, or operator checks behind the current 96% estimate.
- Added shared completion-deduction formatting so release-status and next-step Markdown/CLI output surface the same source check IDs without requiring reviewers to open the JSON.
- Extended the shared completion-deduction formatting to connected-runner `HANDOFF.md` context checks so moved bundles show the same source check IDs as release-status and next-step output.
- Linked remaining handoff items to completion-deduction impact estimates so next-step and release-status output show which checks are expected to recover specific completion points.
- Embedded `progress_summary.completion_impacts` in release-status progress JSON and evidence checks so resume automation can explain which source check recovers each remaining completion point.
- Added the same completion-impact metadata to owner-specific `progress_summary.next_commands_by_owner` entries and evidence checks so lane-specific automation can explain the expected recovery beside the next command.
- Added ordered `progress_summary.completion_plan` output and evidence checks so resume automation can render every remaining item, selected command, and expected recovery without scraping Markdown.
- Added apply-free `pre_approval_review_sequence` metadata to warning entries in `progress_summary.completion_plan` so plan-only automation can surface review commands without exposing approval-only apply commands.
- Added `report_release_status.py --completion-plan-only` and `--completion-plan-json-only`, plus handoff/evidence checks, so operators or automation can read just the ordered path from the current 96% state to 100%.
- Extended the connected-runner shared contract, bundle verifier, and acceptance verifier to fail if copied release-status progress commands lose those completion-plan text/JSON helpers.
- Added operator approval and warning-review sequence metadata to `progress_summary.completion_plan`, so the final warning action step remains visibly gated by checklist review even in plan-only automation.
- Added `progress_summary.completion_requirements` so resume monitors can group remaining completion-plan prerequisites by requirement, affected item IDs, owner lanes, and count.
- Added `report_release_status.py --completion-requirements-only` and `--completion-requirements-json-only`, plus handoff/evidence checks, so grouped prerequisite blockers can be polled without loading the full progress payload.
- Exposed those grouped prerequisite helper commands through `progress_summary.commands.show_completion_requirements` and `show_completion_requirements_json`, and extended connected-runner contract/bundle/acceptance checks to reject copied release-status artifacts that lose them.
- Added `progress_summary.owner_lanes` plus `report_release_status.py --owner-lanes-only` and `--owner-lanes-json-only`, so resume monitors can poll only the owner-lane snapshot with remaining IDs, next items, runnable command objects, connected-runner readiness summary, operator review summary, approval state, review artifacts, and automation/supporting-command availability.
- Exposed owner-lane helper commands through `progress_summary.commands.show_owner_lanes`, `show_owner_lanes_json`, and `handoff_context.bundle_commands.show_owner_lanes_json`, with evidence and bundle checks rejecting stale or missing owner-lane surfaces.
- Updated generated connected-runner `HANDOFF.md` to lead with `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git` plus `PREFLIGHT_ONLY=true ./run-connected-runner-handoff.sh`, and extended handoff README markers so verification fails if that export-first reminder disappears.
- Added grouped completion requirements to generated connected-runner `HANDOFF.md` and its shared completion-context verifier, so stale or missing runner/operator blocker summaries fail bundle verification and acceptance.
- Added `manifest.json` `handoff_context.quickstart`, `handoff_context.remaining_ids`, `handoff_context.next_item_id`, `handoff_context.owner_lanes`, `handoff_context.bundle_commands`, and `handoff_context.completion_requirements` to connected-runner bundles, plus bundle verification for stale or missing manifest handoff context.
- Added bundle-root self-verification and connected-runner acceptance summary commands to `handoff_context.bundle_commands`, so moved bundles can surface parseable validation commands without scraping `HANDOFF.md`.
- Added bundle-root warning summary and fail-closed warning summary gate commands to `handoff_context.bundle_commands`, so operator automation can inspect unresolved warning actions directly from the bundle manifest.
- Added `handoff_context.bundle_commands.show_operator_review_sequence`, so moved bundle-root workflows can print the safe pre-approval operator review command list without using packaging-time absolute paths.
- Added `handoff_context.bundle_command_sequence` to order self-verification, progress/requirements/owner-lane polling, repo URL export, preflight, acceptance, full flow, and operator warning review/gate steps for bundle-root automation.
- Added `handoff_context.bundle_gate_summary` to summarize gate counts, gate IDs, owner split, first gate, and the repo URL export-before-preflight requirement for command-sequence consumers.
- Extended `handoff_context.bundle_gate_summary` with step/non-gate counts and `first_gate_by_owner` so owner-lane automation can locate the next connected-runner or operator gate without scanning the sequence.
- Added `package_connected_runner_handoff.py --handoff-context-json-only`, `handoff_context.bundle_commands.show_handoff_context_json`, and `progress_summary.commands.handoff_context_json` so automation can read bundle manifest handoff context directly, or compute it from the selected evidence package, without running full verification.
- Added `package_connected_runner_handoff.py --handoff-command-sequence-only`, `handoff_context.bundle_commands.show_handoff_command_sequence`, and `progress_summary.commands.handoff_command_sequence` so resume automation can print the ordered bundle-root command list without rewriting verification reports.
- Added `progress_summary.commands.local_readiness_setup_sequence_preview` and `progress_summary.commands.local_readiness_command_sequence_preview` so planning-only resume automation can print connected-runner setup or setup-plus-verify commands without treating incomplete local readiness as a failed gate.
- Added `next_release_step.py --skip-operator-approved` plus `progress_summary.commands.operator_review_sequence` so operator review automation can print warning summary/artifact commands without including the final `--apply --operator-approved` command.
- Mirrored the safe operator review helper at `progress_summary.warning_review.review_sequence_command` so warning-review consumers can find the pre-approval command list without joining back to the top-level command map.
- Added `progress_summary.warning_review.pre_approval_review_sequence` so warning-review consumers can read the apply-free summary/artifact command list directly.
- Added `review_release_warnings.py --pre-approval-sequence-only` and surfaced it as `progress_summary.warning_review.pre_approval_sequence_command` so operator tooling can request only apply-free warning-review commands directly.
- Extended the shared connected-runner progress-summary contract so package verification and connected-runner acceptance fail if copied `release-status.json` loses the warning-review sequence command or apply-free pre-approval sequence.
- Added the same `--handoff-context-json-only` command to generated connected-runner `HANDOFF.md`, with verification markers so the human-readable bundle guide cannot drift from the manifest/progress JSON surfaces.
- Added a frontend theme smoke check to verify persisted dark/white theme initialization, DOM synchronization, topbar toggle labeling/icons, and light/dark CSS token parity.
- Added a completion-audit smoke check so the release context document keeps the 96% completion, completion impact, remaining owner checks, and frontend theme verification markers current.
- Updated `next_release_step.py --local-readiness` so it defaults to the handoff bundle's `source/` directory from release-status when a bundle is known, avoiding accidental checks against the project root.
- Updated `next_release_step.py --repo-url-from-origin` so an omitted path defaults to the known handoff bundle `source/`, and generated status/handoff helper commands now reserve explicit source paths for overrides.
- Added an external readiness checker for Docker, git remote, GitHub CLI, and CI workflow coverage so off-machine validation gaps are captured as evidence.
- Added backend ops self-check and runbook APIs plus dashboard setup-panel links for deployment, observability, release-readiness, and Quant Lab guide Markdown.
- Added a completion audit that maps original Quant Lab MVP requirements to implementation evidence, verification commands, safety boundaries, and optional remaining improvements.
- Added a live-beta closeout archive command that exports drill, strategy handoff, cutover runbook, closeout report, operator decisions, raw JSON, dry-run runbooks, and a live-lock safety manifest.
- Added a persisted operator decision log API and a dedicated operations journal panel with decision type, status, target filters, Markdown report export, and linked dry-run runbook exports.
- Added operator decision sections to dry-run approval runbooks so approved/needs-work reviews travel with the approval handoff.
- Added a DuckDB-backed columnar candle mirror alongside the SQLite cache, using the same source/symbol/timeframe/timestamp key.
- Added columnar cache status and Parquet export APIs, plus dashboard controls for checking rows, paths, freshness, and export state.

## Verified

Backend:

```bash
cd backend
. .venv/bin/activate
python -m unittest discover -s tests
```

Result: 81 tests passed.

Frontend:

```bash
cd frontend
npm run build
```

Result: TypeScript check and Vite production build passed.

Runtime:

- `GET /api/health` returned OK.
- `POST /api/backtests/run` returned metrics and orders with sample candles.
- `POST /api/backtests/run` returned metrics and orders with Upbit public candles.
- `POST /api/backtests/run` persisted each run and returned a stable run id.
- `GET /api/backtests/runs` returned recent run summaries for dashboard history.
- `GET /api/backtests/runs/{run_id}` returned a stored run with equity curve and orders.
- Safari verified `Compare` selections update the `Run comparison` panel and render selected run metrics.
- Safari verified selected comparison runs fetch their stored equity curves and render a normalized multi-run equity overlay.
- Safari verified the main equity chart renders strategy, buy-and-hold, and edge values for the active backtest.
- Safari verified the Backtest metrics cards and Run comparison cards render backend-provided buy-and-hold and edge values.
- `GET /api/backtests/runs` returned persisted summary metrics with `buy_and_hold_return_pct` and `strategy_edge_pct`.
- `GET /api/backtests/runs` backfilled benchmark metrics for legacy stored runs that did not include benchmark fields in their JSON payload.
- Safari verified Backtest history sorting by `Best edge`, source filtering, the empty filtered state, and a `sample_us` SPY run appearing in the stock/ETF filter.
- Frontend build verified the Backtest history source, strategy, and symbol filter controls.
- `POST /api/research/portfolio` returned a multi-symbol portfolio result with custom weights, monthly rebalance count, target/final symbol weights, aggregate equity curve, and allocation rows.
- Unit tests verified custom weighted monthly portfolio research for `SPY`, `QQQ`, and `AAPL`.
- `GET /api/research/portfolio/presets` returned the built-in crypto and stock/ETF research presets.
- Unit tests verified saved portfolio scenarios can be created, listed, fetched, and deleted.
- Unit tests verified saved portfolio scenarios can be scanned and reloaded from scan history.
- Runtime API checks created a saved scenario, scanned it, listed scan history, fetched the scan detail, and deleted the saved scenario.
- Unit tests verified portfolio watchlist items can be created, run when due, update their last scan metadata, and are removed when their scenario is deleted.
- Unit tests verified scheduled portfolio scans persist triggered alert metadata on watchlist items.
- Unit tests verified portfolio paper watchlist items can be created, run when due, generate one stored paper session per scenario symbol, and are removed when their scenario is deleted.
- Unit tests verified crypto paper-watchlist sessions can be promoted into dry-run order intent audits and stock/ETF paper-watchlist sessions become paper-only operator handoffs.
- Unit tests verified the paper-to-live adapter profile API exposes guarded Upbit crypto routing, stock/ETF paper-only routing, and an Alpaca-style paper preview route.
- Unit tests verified the mock US equities and Alpaca-style paper brokers accept valid paper order shapes, reject invalid limit orders, and block live-confirmed submissions.
- Unit tests verified the stock/ETF broker intent evaluation API records paper-only submissions across mock and Alpaca-style adapters, blocks live-confirmed intents, and reports that no external broker call was attempted.
- Unit tests verified stock/ETF paper fill estimates report expected fills, cash shortfalls, and non-fillable limit orders without any broker submission.
- Unit tests verified broker intent evaluations are persisted and can be listed or filtered by paper adapter and blocked submission status.
- Unit tests verified accepted stock/ETF broker fill estimates can create paper-session order notes with simulated-trade comparison evidence.
- Unit tests verified the broker intent evaluation report exports Markdown with SPY/QQQ/AAPL evidence, adapter coverage counts, and an explicit no-external-submission summary.
- Unit tests verified broker readiness exposes blocked Upbit guard state, credential-free stock/ETF paper-record routing, and an Alpaca preview credential boundary that never submits externally.
- Unit tests verified stock/ETF paper-only handoffs create operator journal entries, can be filtered with `route_status=paper_only_review`, and are included in the strategy health handoff report with linked broker intent/fill evaluation evidence.
- Unit tests verified promoted dry-run audits include paper-watchlist scenario and promotion-rule context.
- Unit tests verified dry-run approval runbooks include precheck sections, promoted scenario context, and linked operator review decisions.
- Unit tests verified the alert review queue includes scheduled scan alerts and paper-session risk events from watchlist runs.
- Unit tests verified alert review filters by severity, source, scenario, and invalid filter validation.
- Unit tests verified alert review items can be acknowledged and then omitted from the active queue while still available when acknowledged items are included.
- Unit tests verified `GET /api/readiness/live` reports system/operator readiness breakdowns, default warning states, and improved operator evidence after KRW paper trades are queued as dry-run audits.
- Unit tests verified `GET /api/execution/cutover-checklist` requires private reads plus explicit readiness, dry-run, and live-cutover operator decisions before it can leave the blocked state.
- Unit tests verified `GET /api/execution/cutover-checklist/runbook` exports the checklist, live guard environment, arming procedure, and linked operator decisions as Markdown.
- Unit tests verified `POST /api/execution/cutover-checklist/simulate-arming` previews current versus simulated blocker changes, returns remaining simulated blocker items, and reports that no exchange order is submitted.
- Unit tests verified `GET /api/execution/post-cutover-monitor` is idle before live approval attempts and moves to attention after a blocked approval attempt is recorded.
- Unit tests verified `GET /api/execution/post-cutover-monitor/closeout-report` exports final audit state, approval attempts, private account snapshot, and operator decisions as Markdown.
- Unit tests verified `GET /api/research/strategy-health/traces` links promoted paper watchlist rules, paper trade source metadata, dry-run approvals, blocked live attempts, and closeout status.
- Unit tests verified `GET /api/research/strategy-health/handoff-report` exports trace rows, closeout snapshots, approval decisions, approval attempts, and linked dry-run runbook endpoints as Markdown.
- Unit tests verified operator decisions are persisted, listed, filterable by decision type, target ID, and status, and exportable as Markdown reports.
- Unit tests verified cached candles are mirrored to DuckDB and exported to readable Parquet.
- `GET /api/markets/cache/columnar/status` returned DuckDB path, Parquet path, row count, source list, symbols, timeframes, and freshness metadata.
- `POST /api/markets/cache/columnar/export` wrote a filtered Parquet file for cached candle data.
- `GET /api/execution/status` returned the default locked execution state.
- `GET /api/execution/settings` returned the default locked execution settings, local guard thresholds, and no credential details.
- `GET /api/execution/private-snapshot` returned an explicit disabled state when Upbit credentials were absent.
- `POST /api/execution/order-intents` recorded a blocked Upbit order intent while live trading was disabled.
- `GET /api/execution/order-audits` returned the stored order audit records.
- `POST /api/paper/sessions/{session_id}/order-intents` converted recent paper trades into `dry_run` order audit records without exchange submission.
- `GET /api/execution/order-audits/{record_id}/precheck` returned `warn` locally because private balances were unavailable, while the minimum notional check passed.
- `GET /api/markets/ticker?symbol=SPY&source=sample_us` returned a deterministic US equity ticker payload.
- `POST /api/backtests/run` with `symbol=SPY` and `source=sample_us` returned USD-scale metrics, trades, candles, and a sample-data warning.
- `POST /api/paper/sessions` with `symbol=SPY` and `source=sample_us` created a stock/ETF paper session, while queueing execution intents for that session returned a crypto-only validation error.
- `POST /api/backtests/run` with `source=alpha_vantage` returned a clear `ALPHA_VANTAGE_API_KEY` error when the API key was not configured.
- Unit tests verified Alpha Vantage daily candles are saved to and reloaded from the SQLite candle cache.
- `GET /api/markets/providers/status` returned sample, sample US, Alpha Vantage, and Upbit public provider readiness without exposing secrets.
- After an Alpha Vantage key-missing request, `GET /api/markets/providers/status` reported the latest `ALPHA_VANTAGE_API_KEY` error for that source.
- Unit tests verified that precheck uses Upbit `/v1/orders/chance` fields when credentials are configured.
- Unit tests verified that even with live guard flags armed, a failed precheck blocks approval before `place_upbit_order` can be called.
- `POST /api/execution/order-audits/{record_id}/approve` turned a selected dry-run record into a guarded approval attempt; with live trading disabled it recorded a `blocked` audit.
- Safari verified the execution guard panel renders locked state, adapter details, private-read status, balance count, and open-order count.
- Safari verified the execution settings panel renders credential status, ACK status, local/default precheck source, fee, minimum notional, and exposure threshold.
- Browser verified the setup checklist renders the Alpha Vantage, Upbit key, live lock, ACK, and approval guardrail rows without exposing secrets.
- Browser verified provider status rows show the latest status check time and API responses include freshness timestamps.
- Safari verified the dashboard loads in dark mode, switches to white mode through the topbar toggle, and keeps the main trading panels readable after the switch.
- Safari verified the dashboard can select the US stock/ETF sample source and display stock paper-trading outputs with USD currency formatting.
- Safari verified the dashboard exposes the `Alpha Vantage daily` source option and keeps stock/ETF runs paper-only.
- Safari verified the Data providers panel renders source readiness and clears stale ticker data when Alpha Vantage is not configured.
- Safari verified the execution panel refresh button updates the last private account check timestamp without unlocking live trading.
- Safari verified the Paper trading `Queue dry-run` action creates `dry_run` audit records and keeps live trading locked.
- Safari verified the Order review panel lists dry-run intents with full crypto quantity precision and approval buttons.
- Repeated Upbit candle requests can be served from the SQLite candle cache after the first fetch.
- `POST /api/paper/sessions` returned session status, simulated orders, risk summary, and guardrail events.
- `GET /api/paper/sessions/{session_id}` returned the stored paper session from SQLite.
- `POST /api/paper/live-sessions` created a running replay session.
- `POST /api/paper/live-sessions/{session_id}/advance` advanced the replay session and updated equity/orders/risk state.
- Clearing the in-memory live runtime cache still allowed a stored live session to be fetched and advanced from SQLite.
- `GET /api/paper/live-sessions` returned recent live replay sessions for the dashboard history panel.
- `GET /api/markets/ticker` returned the current dashboard market price for sample and Upbit public sources.
- `POST /api/paper/ticker-sessions` created a live paper session seeded from recent candles.
- `POST /api/paper/live-sessions/{session_id}/tick` appended a fresh ticker tick and updated simulated equity/orders/risk state.
- Chrome rendered the dashboard at `http://127.0.0.1:5173` with final equity, return, drawdown, Sharpe, exposure, trades, chart, and orders.
- Chrome verified live-replay controls: `Start replay` moved the paper panel to running state and `Advance 5` advanced progress from `30 / 180` to `35 / 180`.
- Chrome verified auto replay controls: `Auto replay` advanced the running session without manual button presses and stopped cleanly on command.
- Safari verified the market ticker panel rendered with the selected market price.
- Safari verified ticker paper controls: `Start ticker`, `Tick now`, and `Auto tick` advanced a running ticker session from `30 / 30` to `46 / 46` and stopped cleanly.
- Release-status refresh/read-only/json, local, strict connected-runner, checksum verification, handoff packaging/verification, warning-review/apply, and final live-beta gate commands now use shared handoff command builders in status files, warning review plans, next-step fallbacks, and generated runner scripts; copied-evidence consistency checks verify final operator commands across `release-status` Markdown and JSON.
- `next_release_step.py` command variants now route through a single shared next-step command builder, reducing duplicated shell strings for owner filters, repo URL sources, local-readiness gates, and automation JSON modes.
- `archive_live_beta_closeout.py --preflight --json` now includes shared-builder follow-up commands (`preflight`, `preflight_json`, `next_command_only`, `archive`, and final live-beta gate) so operator automation can continue without reconstructing shell strings.
- Release evidence command-safety checks now verify that generated live-beta handoff commands include the full shared-builder set: preflight, JSON preflight, archive, and final live-beta gate.
- `next_release_step.py` now exposes top-level repo URL command and JSON gates whenever connected-runner commands still need a real remote URL, so automation can fail fast on missing or placeholder `GIT_ORIGIN_URL` without digging into each remaining item.
- `next_release_step.py` and release-status handoff commands now include `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git` as a structured setup example whenever connected-runner commands still need a concrete remote URL.
- Release evidence command-safety checks now verify those top-level repo URL command/JSON gates and the export example whenever `next-release-step` artifacts still contain `REPLACE_WITH_REPO_URL`.
- Live-beta closeout preflight output now includes backend start, no-reload fallback, and health-check commands in both text and JSON reports, so backend reachability failures can move directly to the next safe operator command.
- Release evidence command-safety checks now verify that generated live-beta handoff artifacts include those backend start, no-reload fallback, and health-check support commands whenever live-beta closeout commands are present.
- Live-beta closeout preflight reports now include `recommended_next` guidance so backend reachability failures point to backend startup plus health-check retry commands, while passing preflights point directly to archive creation and the final live-beta gate.
- `archive_live_beta_closeout.py --preflight --next-command-only` now prints just the selected `recommended_next.command`, and release-status handoff artifacts include that helper for command-driven operator automation.
- Live-beta backend support commands now include `backend_start_local_no_reload` so restricted runners that block reload/file watching can still start the local API before rerunning preflight.
- Warning review action plans now include `recommended_next` plus `review_release_warnings.py --next-command-only`, so operator automation can print the selected warning-review command without rewriting archived evidence.
- `review_release_warnings.py --next-command-only --fail-if-action-needed` now prints the selected warning-review command but exits non-zero while operator warning actions remain unresolved; read-only human output also shows whether the recommended next command requires operator approval.
- `review_release_warnings.py --review-artifacts-only` now prints the existing warning action-plan and operator-checklist paths, and exits non-zero if either review artifact is missing before approval.
- Release-status, connected-runner verification, acceptance, and evidence command-safety checks now track the warning review artifact path command and recommended-next command gate so copied handoff artifacts fail if review-file automation disappears or command-only warning automation drops `--fail-if-action-needed`.
- `next_release_step.py --command-sequence-only` now inserts a non-gating compact warning summary JSON command, then the warning review artifact path command, immediately before an operator-approved warning apply command when that helper is available.
- Operator progress entries now expose both non-gating and fail-closed compact warning summary commands in `supporting_commands`, so show-sequence and JSON resume callers can log warning counts before surfacing the checklist or applying acknowledgements.
- `next_release_step.py --show-sequence` now prints known supporting commands in review order instead of raw JSON key order, keeping warning summary and review-artifact helpers ahead of fail-closed gate commands in human-readable output.
- Connected-runner `next_commands_by_owner` entries now include the same owner-scoped command-only helper exposed in `progress_summary.commands.connected_runner_command_only`, so owner-only automation can fetch exactly one runner command without falling back to the global command map.
- `progress_summary.commands` now also includes `operator_command_only` and `operator_json_only`, giving operator automation the same one-command and JSON report entry points already present in the full handoff command list.
- `progress_summary.commands` now includes global `next_command_only` and `next_json_only` entries as well, so resume loops can either execute the current global next command or fetch the full next-step JSON without scraping the full handoff command list.
- `check_external_readiness.py --summary-json-only` now includes setup and verify guidance (`next_setup_command`, setup sequence, verify sequence, flattened command sequence, and repo URL placeholder metadata) so connected-runner automation can act on compact readiness output without opening the full JSON report.
- Connected-runner progress entries now expose compact external-readiness summary and strict summary JSON commands in `supporting_commands`, so owner-scoped resume callers can poll runner readiness without reading the top-level command map.

## Current local servers

Backend:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Local session database:

```text
backend/data/quant_lab.sqlite3
```

Set `QUANT_LAB_DB_PATH` to use another SQLite file for tests or local experiments.
Set `QUANT_LAB_CANDLE_CACHE_TTL_SECONDS` to control Upbit candle cache freshness. The default is `300` seconds. Use `none` to keep cached candles until overwritten, or `off`/`disabled` to force refreshes.
Set `QUANT_LAB_DUCKDB_PATH` to move the DuckDB columnar candle mirror, `QUANT_LAB_CANDLE_PARQUET_PATH` to move the Parquet export target, or `QUANT_LAB_COLUMNAR_CACHE_ENABLED=false` to disable the mirror.
Set `QUANT_LAB_RESEARCH_SCHEDULER_ENABLED=false` to disable saved scenario auto-scans, or `QUANT_LAB_RESEARCH_SCHEDULER_POLL_SECONDS` to change the backend polling interval.
Live order submission remains locked by default. To arm the Upbit adapter, all of these must be present: `QUANT_LAB_LIVE_TRADING_ENABLED=true`, `QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK`, `UPBIT_ACCESS_KEY`, and `UPBIT_SECRET_KEY`. Each order intent still requires `live_confirmation=true`.
The read-only private snapshot endpoint also uses `UPBIT_ACCESS_KEY` and `UPBIT_SECRET_KEY`; when either is missing, it returns `credential_ready=false` with empty balances and open orders.

## Next implementation steps

1. Run the connected-runner handoff preflight from the latest `artifacts/handoff-bundles/quant-lab-connected-runner-handoff-*` directory with a real `GIT_ORIGIN_URL`.
2. For local resumes, omit `--package-dir` to select the latest package under `artifacts/evidence-packages`; keep `--package-dir PATH_TO_PACKAGE` when inspecting a transferred bundle, older checkpoint, or copied archive.
3. If `origin` is already configured on the connected runner, use `python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-origin --show-sequence --no-write` to print the exact runner-owned preflight/full-flow commands without changing archived evidence; the helper reads the known handoff bundle `source/` by default, and `--repo-url-from-origin PATH_TO_SOURCE` is only needed for overrides.
4. If `GIT_ORIGIN_URL` is exported on the connected runner, use `python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --show-sequence --no-write` to reuse that environment value.
5. For automation that only needs the next command, use `python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required`.
6. For resume automation that starts from release-status progress JSON, read `progress_summary.commands.connected_runner_command_only` for the same owner-scoped single-command helper without relying on all-owner ordering.
7. For automation that needs the full report, use `python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required`.
8. If the human-readable next-step report still prints `REPLACE_WITH_REPO_URL`, use the reported `Repo URL command gate` or `Repo URL JSON gate` command for automation until `GIT_ORIGIN_URL` contains a real remote URL.
9. Add `--local-readiness --no-write` when the reviewer needs the same next-step output plus local `origin`, Docker Compose, and GitHub CLI auth checks; it checks the known handoff bundle `source/` by default, and `--local-readiness-source PATH_TO_SOURCE` is only needed for overrides.
10. From an extracted bundle root, use `python3 source/scripts/next_release_step.py --handoff-bundle "$(pwd)" --summary-by-owner --show-sequence --no-write`; the copied package under `evidence/` is selected automatically. The human sequence view folds the first item already shown in the next-step summary and collapses repeated actions, commands, and supporting commands.
11. Use `python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner operator --show-sequence --no-write` when an operator only needs the live-beta archive and warning-review sequence.
12. Use `python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --no-write` for post-checksum warning review so the action/checklist files and package tarball remain unchanged.
13. Validate the GitHub Actions workflow on a connected runner and archive its uploaded evidence package, external-readiness report, release gate summary, and `release-evidence-check.json`.
14. Run Docker Compose validation on a Docker-enabled machine and archive the result with the release-readiness evidence.
