# 앞으로 해야 할 일

최신 기준 산출물은 `20260530-KRW-BTC-beta-004`입니다.

- 현재 진행률: 100%
- 현재 상태: `pass`
- 남은 항목: 0개
- 연결 러너 담당 남은 항목: 없음
- 운영자 담당 남은 항목: 없음
- 현재 Git origin: `https://github.com/studioaheun/90-my-quant-bot.git`
- 최신 evidence package: `/Users/ckkim/Documents/quant/artifacts/evidence-packages/20260530-KRW-BTC-beta-004`
- 최신 handoff bundle: `/Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260530-073245`
- 최신 release gate summary: `/Users/ckkim/Documents/quant/artifacts/release-gate/release-gate-20260530-073245.json`
- GitHub에 push된 브랜치: `codex/quant-lab-release`

## 1. 현재 완료 상태

운영자 warning 승인을 반영했고, 새 evidence package 기준으로 warning triage가 `clear` 상태입니다.

최종 release gate는 아래 단계까지 모두 통과했습니다.

- project verification
- external readiness
- local smoke drill
- package evidence
- release evidence check
- release warning review
- release status report
- next release step report
- final release evidence check
- evidence checksum 생성 및 검증
- connected-runner handoff bundle 검증
- completion audit handoff bundle 검증

진행률 확인 명령:

```bash
python3 scripts/report_release_status.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260530-KRW-BTC-beta-004 --release-gate artifacts/release-gate/release-gate-20260530-073245.json --progress-only
```

현재 결과:

```text
Release progress: 100%
Status: pass
Remaining handoff items: 0
Deductions: none
```

## 2. 최종 산출물 검증

최신 evidence checksum 검증:

```bash
python3 scripts/write_evidence_checksums.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260530-KRW-BTC-beta-004 --verify --json-only
```

최신 handoff bundle 검증:

```bash
python3 scripts/package_connected_runner_handoff.py --verify /Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260530-073245 --summary-json-only
```

전체 release gate 재실행:

```bash
python3 scripts/release_gate.py --run-smoke
```

## 3. GitHub 반영

작업 브랜치:

```text
codex/quant-lab-release
```

원격 저장소:

```text
https://github.com/studioaheun/90-my-quant-bot.git
```

다음 단계는 이번 warning-clear/release-gate 보강 코드를 커밋하고 원격 브랜치에 push한 뒤, GitHub Actions가 통과하는지 확인하는 것입니다.

## 4. 운영 시 주의할 점

- 현재 앱은 paper/live-beta 준비 흐름까지 검증된 상태입니다.
- 실제 live trading은 의도적으로 잠겨 있어야 합니다.
- stock/ETF route는 paper fill quality gate가 충분해질 때까지 paper review 상태를 유지합니다.
- 코인 쪽 KRW-BTC 경로가 현재 release evidence의 주 경로입니다.
- `.env`, 로컬 DB, dependency folder, generated artifact는 git에 포함하지 않습니다.

## 5. 빠른 상태 확인 명령

남은 작업 계획:

```bash
python3 scripts/report_release_status.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260530-KRW-BTC-beta-004 --release-gate artifacts/release-gate/release-gate-20260530-073245.json --completion-plan-only
```

소유자별 남은 작업:

```bash
python3 scripts/report_release_status.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260530-KRW-BTC-beta-004 --release-gate artifacts/release-gate/release-gate-20260530-073245.json --owner-lanes-only
```

최종 다음 단계 안내:

```bash
python3 scripts/next_release_step.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260530-KRW-BTC-beta-004
```
