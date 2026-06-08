# Quant Lab Guide

Updated: 2026-05-25 KST

This guide explains how to run Quant Lab, what is currently safe to use, and what to build next.
It is a project guide, not investment advice. Keep real-money trading disabled until the paper,
dry-run, and operator approval evidence is strong enough to review calmly.

## Product Direction

Quant Lab is being built as a web-based quant trading workspace:

1. Crypto spot MVP first.
2. Guarded Upbit dry-run and live-readiness review second.
3. US stock/ETF paper trading and broker-paper expansion third.

The current recommendation remains: start with crypto spot because API/data access and small-size
testing are faster, while keeping stock/ETF paper trading open as the more stable long-term route.

## Local Runbook

One-command local app launcher:

```bash
python3 scripts/run_local_app.py
```

Use `--no-browser` to start backend/frontend without opening the browser.

Backend:

```bash
cd backend
source .venv/bin/activate
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

Verification:

```bash
python3 scripts/release_gate.py --skip-docker
python3 scripts/release_gate.py --skip-docker --run-smoke
python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth
```

## Core Workflows

### 1. Research And Backtest

Use the dashboard controls to choose:

- Source: `sample`, `upbit`, `sample_us`, or `alpha_vantage`
- Symbol: crypto pairs such as `KRW-BTC`, or stock/ETF symbols such as `SPY`, `QQQ`, `AAPL`
- Strategy: `sma_crossover`, `donchian_breakout`, or `rsi_mean_reversion`

Recommended research sequence:

1. Run a baseline backtest.
2. Run `Sweep params` to compare parameter candidates.
3. Run `Validate split` to check train/test robustness.
4. Run `Walk-forward` to check repeated out-of-sample folds.
5. Save strong portfolio scenarios before paper promotion.

Key APIs:

- `POST /api/backtests/run`
- `POST /api/backtests/sweep`
- `POST /api/backtests/validate`
- `POST /api/backtests/walk-forward`
- `POST /api/research/portfolio`

### 2. Crypto Paper To Dry-Run

Use KRW crypto sessions for the real automatic-trading MVP path.

Safe progression:

1. Create a paper session.
2. Review orders, drawdown, exposure, and guardrail events.
3. Promote only eligible paper-watchlist winners.
4. Queue dry-run order intents.
5. Review dry-run prechecks and runbooks.
6. Approve only after operator decisions are recorded.

Live Upbit orders remain locked unless all of these are set:

```bash
export QUANT_LAB_LIVE_TRADING_ENABLED=true
export QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK
export UPBIT_ACCESS_KEY="..."
export UPBIT_SECRET_KEY="..."
```

Each order still requires `live_confirmation=true`.

Key APIs:

- `POST /api/paper/sessions`
- `POST /api/paper/live-sessions`
- `POST /api/paper/watchlist/{item_id}/promote-order-intents`
- `GET /api/execution/order-audits/{record_id}/precheck`
- `GET /api/execution/order-audits/{record_id}/runbook`
- `POST /api/execution/order-audits/{record_id}/approve`
- `GET /api/research/crypto-live-beta-drill/report?symbol=KRW-BTC`

### 3. Stock/ETF Paper Path

Stock/ETF routing is paper-first. It supports:

- Local mock stock/ETF paper handoff
- Alpaca-style preview with no external submission
- Credential-gated Alpaca paper Trading API submission

The credentialed Alpaca paper adapter is intentionally blocked until every gate is present:

```bash
export ALPACA_API_KEY_ID="your-paper-key-id"
export ALPACA_API_SECRET_KEY="your-paper-secret"
export ALPACA_PAPER_BASE_URL="https://paper-api.alpaca.markets"
export ALPACA_PAPER_TRADING_ENABLED=true
export ALPACA_PAPER_TRADING_ACK=PAPER_ORDERS_OK
```

Each request must also include:

```json
{
  "adapter_id": "alpaca_us_equity_paper",
  "paper_submit_confirmation": true,
  "live_confirmation": false
}
```

The adapter rejects live-domain base URLs and blocks `live_confirmation=true`.

Key APIs:

- `GET /api/execution/broker-readiness`
- `POST /api/execution/broker-intents/evaluate`
- `GET /api/execution/broker-intents/evaluations`
- `GET /api/paper/order-notes/quality-gate`
- `GET /api/paper/stock-etf/broker-expansion-readiness`

## Safety Checklist

Before any real or external broker action, confirm:

- Tests pass.
- Provider readiness is not stale.
- Backtest, sweep, train/test, and walk-forward evidence agree.
- Paper session drawdown and exposure stay within guardrails.
- Operator journal has the required review decision.
- Dry-run or paper-broker prechecks pass.
- No dashboard panel reports hidden credential leakage.
- Live crypto and stock/ETF paper routes are not mixed.

## Current State

Implemented:

- FastAPI backend and React/Vite dashboard.
- Dark/white theme.
- Crypto and stock/ETF sample data.
- Optional Upbit public data.
- Optional Alpha Vantage daily data.
- SMA, Donchian, and RSI strategies.
- Parameter sweep, train/test validation, and walk-forward validation.
- Paper sessions, replay sessions, ticker sessions, and guardrails.
- Backtest history, comparison, portfolio research, saved scenarios, and watchlists.
- Alert review queue and operations journal.
- Upbit private read/guarded dry-run/live-readiness flow.
- Stock/ETF paper-only handoffs and quality gates.
- Credential-gated Alpaca paper Trading API adapter.
- Alpaca paper order reconciliation for saved broker intent evaluations.
- Rich Alpaca paper fill/account reconciliation evidence.
- Broker paper submission, reconciliation, and fill drift alerts.
- Crypto live beta drill report export.
- Deployment hardening artifacts and pre-market operator checklist.
- Seeded crypto drill command.
- Production observability notes and ops smoke-check command.
- Managed local smoke-test command.
- Project verification command and release-readiness checklist.
- Release gate command for verification, external readiness, optional smoke drill, evidence package, release evidence check, release status report, checksum generation/verification, and strict connected-runner validation.
- Evidence package command for verification, smoke, drill, runbook, and documentation archives.
- External readiness checker plus release evidence checker and warning review command for package contents, live-lock evidence, alert severity, smoke/drill readiness, triage, and dry-run alert actions.
- GitHub Actions CI workflow for the release gate, smoke drill, evidence packaging, release evidence checking, and artifact upload.
- Backend ops self-check API and dashboard runbook links.
- Completion audit checklist.

Known boundary:

- Crypto live routing is Upbit-only and disabled by default.
- Stock/ETF live routing is not enabled.
- Alpaca support is paper trading only and requires explicit paper gates.

## Recommended Next Work

Latest local checkpoint:

- Current completion estimate: 96%.
- Current evidence package and handoff bundle are printed by `python3 scripts/next_release_step.py --summary-by-owner --show-sequence --no-write`.
- Remaining split: connected runner owns `git_origin_remote`, `docker_cli`, and `github_cli`; operator owns `warning_alerts` and `warning_actions`.

Read-only status review after checksums are published:

```bash
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --no-write
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --json-only
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --progress-only
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --progress-json-only
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --completion-plan-only
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --completion-plan-json-only
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --completion-requirements-only
python3 scripts/report_release_status.py --package-dir PATH_TO_PACKAGE --completion-requirements-json-only
python3 scripts/write_evidence_checksums.py --package-dir PATH_TO_PACKAGE --verify --json-only
python3 scripts/check_release_evidence.py --package-dir PATH_TO_PACKAGE --json-only
```

For local resumes, omit `--package-dir` to use the latest package under `artifacts/evidence-packages`; keep `--package-dir PATH_TO_PACKAGE` when inspecting a transferred bundle, older checkpoint, or copied archive.

Use `report_release_status.py --json-only` when automation needs the compact status report as parseable JSON, `report_release_status.py --progress-only` when a resume/status check only needs the percent, remaining IDs, owner counts, and deductions, `report_release_status.py --progress-json-only` when automation needs the same compact progress data plus selected resume commands as JSON, `report_release_status.py --completion-plan-only` or `--completion-plan-json-only` when a resume handoff needs only the ordered remaining path to 100%, `report_release_status.py --completion-requirements-only` or `--completion-requirements-json-only` when a monitor needs only grouped prerequisite blockers from that path, `write_evidence_checksums.py --verify --json-only` when automation needs a transferred-package integrity result, and `check_release_evidence.py --json-only` when automation needs the full evidence-check payload. The progress JSON payload is also embedded in `release-status.json` as `progress_summary`; it includes `next_command`, `next_item_id`, `next_item_owner`, `next_commands_by_owner`, `completion_impacts`, `completion_plan`, `completion_requirements`, `repo_url`, `local_readiness`, and `warning_review`, and its command map includes global next command-only/report JSON helpers, owner-specific connected-runner/operator command-only output, connected-runner/operator sequences, operator report JSON, completion-plan text/JSON helpers, completion-requirements text/JSON helpers, connected-runner setup/verify helpers, compact external-readiness, warning-review, and bundle/acceptance summary JSON commands so resume automation can route either owner lane without scraping `release-status.md`. `progress_summary.completion_impacts` maps each deduction source check to the expected completion-point recovery before a runner or operator action is taken. `progress_summary.completion_plan` also carries completion_plan mode, completion_plan requirements metadata, and a `backend` object on approval-only warning action rows, so automation can distinguish connected-runner preflight from operator review/approval and surface repo URL, Docker, GitHub CLI, backend start/health-check, checklist, and backup-reference prerequisites before attempting a command; the text completion-plan view prints connected-runner repo URL export/gate guidance before placeholder-bearing commands. `progress_summary.completion_requirements` groups those prerequisites by requirement, item IDs, owner lanes, and count so resume automation can summarize shared blockers without re-parsing each plan entry; `progress_summary.commands.show_completion_requirements` and `progress_summary.commands.show_completion_requirements_json` expose direct helper commands for that grouped view, and the text requirements view adds connected-runner handoff/owner-command hints, repo URL gates, Docker/GitHub CLI setup/verify commands, operator review/approval hints with action-plan/checklist artifact paths, and backend start/health-check commands for warning-action apply prerequisites. The JSON requirements helper also adds a `guidance` object per actionable requirement with connected-runner handoff bundle and owner-scoped commands plus the same repo URL, setup/verify, review, approval, backend start/health-check, and warning review artifact hints while keeping `release-status.json` itself compact; the top-level `connected_runner` requirement repeats its owner-scoped repo URL gates so a runner can read the first grouped blocker as a complete preflight context. When runner commands still contain `REPLACE_WITH_REPO_URL`, `progress_summary.repo_url` exposes the placeholder, export example, command gate, JSON gate, and replacement warning from the compact progress entrypoint. `progress_summary.owner_lanes.*.repo_url` repeats the placeholder note, export example, owner-scoped command gate, and owner-scoped JSON gate in the owner view so connected-runner dashboards do not have to stitch together top-level repo URL context. `progress_summary.local_readiness` exposes connected-runner issue IDs, next setup, setup/verify sequences, flattened command sequence, and local-readiness JSON/gate command helpers from the same compact progress payload. `progress_summary.warning_review` exposes warning action-needed state, operator approval requirement, action-plan/checklist paths, summary/gate commands, and the review sequence before any approval-only apply command. The release evidence checker also verifies that progress next commands and local-readiness commands keep pointing at the embedded connected-runner handoff bundle/source path. `next_commands_by_owner` entries also carry available `automation_command`, `full_flow_command`, and `supporting_commands` fields, which lets connected-runner automation surface the owner-scoped command-only helper, compact external-readiness summary/gate commands, and local-readiness setup/verify helpers from the same owner entry, while an operator can surface owner-scoped command-only/report JSON helpers, non-gating compact warning summaries, fail-closed compact warning gates, and review artifacts before an approval-only apply command; operator entries also include `review_artifacts` with the action-plan and checklist paths. Use `--allow-post-checksum-write` only when you intentionally need to rewrite `release-status.*`, then rerun `python3 scripts/write_evidence_checksums.py --package-dir PATH_TO_PACKAGE`.

Use `report_release_status.py --owner-lanes-only` or `--owner-lanes-json-only` when automation needs only the owner-lane snapshot from `progress_summary.owner_lanes`. That view groups the remaining IDs, next item, runnable next/automation/full-flow/supporting commands, connected-runner repo URL placeholder/export/gate guidance, connected-runner readiness summary, operator review summary, operator backend start/health-check guidance, first-mode requirements, approval state, and review artifacts by owner; `progress_summary.commands.show_owner_lanes`, `progress_summary.commands.show_owner_lanes_json`, and moved-bundle `manifest.json handoff_context.bundle_commands.show_owner_lanes_json` expose the same route without scraping Markdown.

`progress_summary.warning_review.review_sequence_command` mirrors `progress_summary.commands.operator_review_sequence`, so an operator monitor can find the safe pre-approval review sequence without leaving the warning-review object. `progress_summary.warning_review.pre_approval_sequence_command` points directly to `review_release_warnings.py --pre-approval-sequence-only`, while `progress_summary.warning_review.pre_approval_review_sequence` carries the same apply-free review path as a list of summary/artifact commands for UIs or monitors that should avoid approval-only commands entirely. When warning actions need approval, `progress_summary.warning_review.backend` and `progress_summary.owner_lanes.operator.review.backend` include local backend start, no-reload fallback, Docker backend start, and health-check commands before the approval-only apply command is attempted.
The release evidence checker also compares `progress_summary.next_command` with `next-release-step.json`, so automation sees one consistent next command from either archived entrypoint. It also checks that compact progress status commands preserve the matching release gate summary path, that the embedded progress snapshot mirrors the top-level status, readiness deductions, completion impacts, remaining IDs, owner counts, and package path, that the global/owner next entries match the ordered remaining items, that local-readiness issue IDs plus next setup metadata match the connected-runner remaining items, and that warning-review issue IDs, status, approval requirement, next command, review sequence command, and review sequence match the operator warning items.
Owner-specific `progress_summary.next_commands_by_owner` entries also carry the matching completion-impact metadata when a remaining item is tied to a deduction, allowing owner-lane automation to explain the expected completion-point recovery without joining against the full remaining item list.
`progress_summary.completion_plan` keeps all remaining handoff items in execution order with each selected command, owner, status, mode, requirements, completion-impact metadata, warning-review sequence, apply-free pre-approval review sequence, operator approval requirement, and backend start/health-check guidance for approval-only warning actions, so resume automation can render the full path to 100% without scraping Markdown or accidentally skipping checklist review.

### Step 1. Connected Runner Preflight

Goal: clear the remaining runner-owned handoff items on a machine with a real Git remote, Docker, and GitHub CLI.

Deliverables:

- Configure a real `origin` remote for the handoff source or pass the remote URL directly.
- Run the connected-runner bundle preflight before dependency installation or push.
- Confirm Docker Compose and GitHub CLI auth pass on the connected runner.

macOS/Homebrew setup commands for missing runner tools:

```bash
brew install --cask docker && open -a Docker && docker compose version
brew install gh && gh auth login && gh auth setup-git && gh auth status
```

`scripts/check_external_readiness.py` includes these commands in JSON/Markdown setup fields when `docker` or `gh` are missing, so status reports and next-step manual fallbacks stay copy-pasteable without weakening the preflight gate. Add `--summary-json-only` when automation needs compact status/counts plus warning/failure IDs and setup/verify guidance while still writing the evidence files; the payload includes `guidance.next_setup_command`, `guidance.setup_sequence`, `guidance.verify_sequence`, `guidance.command_sequence`, and `guidance.repo_url` when setup commands still contain `REPLACE_WITH_REPO_URL`. Use `--require-git-remote --require-docker --require-gh --check-gh-auth --summary-json-only` when the connected runner should fail closed until every external readiness check passes.

Primary command to print the current preflight command:

```bash
python3 scripts/next_release_step.py --owner "connected runner" --summary-by-owner --show-sequence --local-readiness --no-write
```

Helper command after `origin` exists:

```bash
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-origin --show-sequence --no-write
```

When the evidence package references a handoff bundle, omitting the path makes the helper read `origin` from that bundle's `source/` directory. Pass `--repo-url-from-origin PATH_TO_SOURCE` only when overriding the inferred source path.

Helper command after `GIT_ORIGIN_URL` is exported:

```bash
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --show-sequence --no-write
```

Automation-safe single-command output:

```bash
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required
```

Automation-safe JSON output:

```bash
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required
```

Connected-runner next-step sequences include this JSON command under each runner-owned item so automation can parse the current runner-only handoff report from the same output. Release-status progress JSON also exposes the owner-scoped single-command helper as `progress_summary.commands.connected_runner_command_only`, allowing resume automation to fetch exactly the next runner command without depending on all-owner ordering. If the repository URL is missing, empty, or a placeholder, this JSON gate still prints the report with `repo_url_error` / `repo_url_gate_message` and exits non-zero.
The command-only gate also prints a concrete export hint such as `export GIT_ORIGIN_URL=https://github.com/OWNER/REPO.git` when the variable is missing, empty, or still set to a placeholder.
When the printed next connected-runner command still contains `REPLACE_WITH_REPO_URL`, the text and Markdown reports also show a `Repo URL export example`, `Repo URL command gate`, and `Repo URL JSON gate`. Use those gates in automation to fail fast until `GIT_ORIGIN_URL` contains a real HTTPS, SSH, or scp-style remote URL.
Release evidence checks fail if those top-level repo URL gates disappear while `next-release-step` still contains the placeholder.

Next-step output with local connected-runner readiness checks:

```bash
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --repo-url-from-env GIT_ORIGIN_URL --command-sequence-only --fail-if-repo-url-required
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --summary-by-owner --show-sequence --local-readiness --no-write
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --command-only --fail-if-repo-url-required --local-readiness --fail-if-local-readiness-not-pass
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --local-readiness-setup-sequence-only --fail-if-local-readiness-not-pass
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --local-readiness-command-sequence-only --fail-if-local-readiness-not-pass
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner "connected runner" --repo-url-from-env GIT_ORIGIN_URL --json-only --fail-if-repo-url-required --local-readiness
```

Use `--command-sequence-only` when terminal or shell automation needs only the remaining handoff commands, one per line. It keeps owner filtering and repo URL substitution, collapses adjacent duplicate commands, and exits non-zero with `--fail-if-repo-url-required` while a runner URL is missing or still a placeholder. Before an operator-approved warning apply, the sequence prints `review_release_warnings.py --summary-json-only` as a non-gating compact status snapshot, then `review_release_warnings.py --review-artifacts-only`, and only then the `--apply --operator-approved` command so approval automation can log the counts and surface the exact files first.
Use `--local-readiness-source PATH_TO_SOURCE` only when the inferred handoff `source/` path is not the directory you want to inspect.
The local readiness option is read-only: combine it with `--no-write` for human-readable output or with `--json-only` for automation payloads.
When JSON output includes local readiness, the payload includes `local_readiness_status`, `local_readiness_issue_ids`, top-level `local_readiness_next_setup_command`, and per-check `setup_command` / `remediation` fields for unresolved local runner gaps. The top-level `local_readiness_next_setup` object also carries the selected check `status` and `verify_command`, so automation can run the first setup command and immediately rerun the matching read-only verification command. The `local_readiness_setup_sequence` list contains every unresolved setup/verify pair in the same order as the checks, and `local_readiness_command_sequence` flattens those pairs into the exact command order to run, allowing connected-runner automation to clear `origin`, Docker, and GitHub CLI gaps without scraping text output. Connected-runner `automation_command` values keep the local-readiness flag so repeated polling continues to return the same checks. When a concrete repo URL is provided with `--repo-url` or `--repo-url-from-env`, setup commands replace `REPLACE_WITH_REPO_URL` with that validated URL.
Use `--local-readiness-setup-sequence-only` when shell automation or a connected-runner operator needs only the unresolved setup commands, one per line, without the full status report. Use `--local-readiness-command-sequence-only` when the same handoff should also print each matching verification command immediately after its setup command.
Use the command-only gate when automation needs exactly one next command but should exit non-zero until the local connected-runner checks pass. Add `--fail-if-local-readiness-not-pass` to JSON/text local-readiness output when automation should print the same payload but exit non-zero until all local readiness checks pass.
When local readiness is present without the fail flag, the text output also prints `Automation JSON gate`, and the JSON payload exposes `local_readiness_gate_command`, with `--fail-if-local-readiness-not-pass` already appended.

Inside an extracted handoff bundle, the copied evidence package is selected automatically:

```bash
python3 source/scripts/next_release_step.py --handoff-bundle "$(pwd)" --summary-by-owner --show-sequence --no-write
```

When that output shows manual setup or verification fallbacks, those commands are shell-quoted and scoped to the current bundle's `source/` so they can be copied from the extracted bundle root without guessing the working directory, even if the bundle was moved after packaging.

Add `--local-readiness` in the extracted bundle to include read-only checks for `source/` by default:

```bash
python3 source/scripts/next_release_step.py --handoff-bundle "$(pwd)" --summary-by-owner --show-sequence --local-readiness --no-write
```

The text output includes the inspected `Source:` path, a readiness status count, a `Next local setup (...)` line, `Next local verification`, `Local setup sequence`, remediation/setup lines for unresolved gaps, and a source-scoped `git -C ... remote get-url origin` command so reviewers can quickly see whether any connected-runner prerequisites remain in `warn` and reproduce the same origin check.

Standalone acceptance rehearsal from an extracted handoff bundle:

```bash
python3 source/scripts/connected_runner_acceptance.py --handoff-root "$(pwd)" --source-root "$(pwd)/source" --package-dir "$(pwd)/evidence/PACKAGE_NAME"
python3 source/scripts/connected_runner_acceptance.py --handoff-root "$(pwd)" --source-root "$(pwd)/source" --package-dir "$(pwd)/evidence/PACKAGE_NAME" --json-only
python3 source/scripts/connected_runner_acceptance.py --handoff-root "$(pwd)" --source-root "$(pwd)/source" --package-dir "$(pwd)/evidence/PACKAGE_NAME" --summary-json-only
```

For local rehearsals outside an extracted bundle, `--package-dir` can also point at an evidence package that has its sibling `PACKAGE_NAME.tgz` and `.tgz.sha256` files. Use `--json-only` when automation needs the full acceptance report on stdout, or `--summary-json-only` when a resume loop only needs status counts plus warning/failure IDs; both modes still write JSON and Markdown artifacts under the acceptance output directory.

Bundle verification can also emit a parseable stdout summary:

```bash
python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" --json-only
python3 source/scripts/package_connected_runner_handoff.py --verify "$(pwd)" --summary-json-only
```

Done when:

- `git_origin_remote`, `docker_cli`, and `github_cli` are no longer warning in the strict release gate.

### Step 2. Operator Warning And Live-Beta Closeout

Goal: close the remaining operator-owned warnings without weakening live-trading safeguards.

Deliverables:

- Review `release-warning-operator-checklist.md` and `release-warning-actions.md`.
- Apply warning acknowledgements only with `--operator-approved`.
- Live-beta archive evidence is present for the current package; after any future live-beta window, archive closeout evidence again with a real backup reference.

Operator sequence helper:

```bash
python3 scripts/next_release_step.py --package-dir PATH_TO_PACKAGE --owner operator --show-sequence --no-write
```

Read-only warning review after checksums are published:

```bash
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --no-write
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --json-only
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --json-only --fail-if-action-needed
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --summary-json-only
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --summary-json-only --fail-if-action-needed
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --review-artifacts-only
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --next-command-only
python3 scripts/review_release_warnings.py --package-dir PATH_TO_PACKAGE --next-command-only --fail-if-action-needed
```

The read-only command prints planned decisions, existing action/checklist paths when present, the recommended next action, whether that command requires operator approval, backend start/health-check commands when approval-only apply needs a running backend, and the exact apply command to run after checklist review. Use `--json-only` when automation needs the same dry-run plan as parseable JSON without mutating the evidence package; the JSON payload includes `commands.review`, `commands.json`, `commands.gate_json`, `commands.summary_json`, `commands.gate_summary_json`, `commands.review_artifacts_only`, `commands.next_command_only`, `commands.apply`, `recommended_next`, and backend guidance so automation can execute the next safe command without rebuilding shell strings. Use `--summary-json-only` when automation only needs compact counts, action-needed reasons, review artifact paths, backend preconditions, and the recommended next command. The `recommended_next` object also marks whether the command requires operator approval and lists the warning action plan/checklist paths to review first. Use `--review-artifacts-only` when automation needs only the existing action-plan and checklist paths and should fail if either file is missing. Use `--next-command-only` when automation needs only the selected warning-review command. Add `--fail-if-action-needed` to `--json-only`, `--summary-json-only`, or `--next-command-only` when automation should still receive parseable output or the selected command but exit non-zero until planned acknowledgements, failed acknowledgements, and the live-beta archive warning are resolved. Release-status handoff commands and operator next-step sequences include the JSON, summary JSON, review-artifact, and command-only gate paths for automation.

Live-beta archive preflight before writing closeout evidence:

```bash
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight --json
python3 scripts/archive_live_beta_closeout.py --api-base http://localhost:8000 --symbol KRW-BTC --backup-reference /backups/quant-lab.sqlite3 --preflight --next-command-only
```

Use `--preflight --json` when automation needs a machine-readable status report, or `--preflight --next-command-only` when it needs only the recommended next command. Operator next-step sequences include the JSON variant. When the preflight passes after a real live-beta window, rerun the same command without `--preflight` to write the archive.
The preflight JSON and text output include `backend_start_local`, `backend_start_local_no_reload`, `backend_start_docker`, and `backend_health_check` commands plus a `recommended_next` object, so a failed backend reachability check can move directly into backend startup, a no-reload fallback for restricted runners, health verification, and JSON preflight retry without reconstructing shell commands.
Release evidence checks verify those backend support commands are present anywhere live-beta closeout handoff commands are generated.

Done when:

- Warning alerts are explicitly reviewed and the final `--require-live-beta` release gate passes.
