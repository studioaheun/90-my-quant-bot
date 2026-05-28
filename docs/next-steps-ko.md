# 앞으로 해야 할 일

최신 기준 산출물은 `20260528-KRW-BTC-beta-008`입니다.

- 현재 진행률: 99%
- 현재 상태: `warn`
- 남은 항목: 2개
- 연결 러너 담당 남은 항목: 없음
- 운영자 담당: `warning_alerts`, `warning_actions`
- 현재 Git origin: `https://github.com/studioaheun/90-my-quant-bot.git`
- 최신 evidence package: `/Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008`
- 최신 handoff bundle: `/Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260528-142101`
- GitHub에 push된 브랜치: `codex/quant-lab-release`

## 1. 실제 Git 원격 저장소 URL 준비

완료했습니다. 현재 프로젝트의 `origin`은 아래 저장소로 설정되어 있습니다.

```bash
git remote get-url origin
```

현재 값:

```text
https://github.com/studioaheun/90-my-quant-bot.git
```

연결 러너 명령을 실행할 때는 아래 값을 사용합니다.

```bash
export GIT_ORIGIN_URL=https://github.com/studioaheun/90-my-quant-bot.git
```

주의할 점:

- `REPLACE_WITH_REPO_URL` 같은 placeholder 값은 거부됩니다.
- HTTPS, SSH, scp 스타일 Git remote URL만 사용합니다.
- 새 저장소라 아직 브랜치가 없을 수 있습니다. `git ls-remote --heads origin` 출력이 비어 있어도 명령이 성공하면 원격 접근 자체는 정상입니다.

## 2. Docker CLI 준비

완료했습니다. `docker` CLI와 Docker Compose 플러그인을 Homebrew formula로 설치했고, Docker가 compose 플러그인을 찾도록 `/Users/ckkim/.docker/config.json`에 `cliPluginsExtraDirs`를 추가했습니다.

검증 명령:

```bash
docker compose version
```

현재 결과:

```text
Docker Compose version 5.1.4
```

참고: Docker Desktop cask 설치는 `/usr/local/cli-plugins` 생성 시 sudo 비밀번호를 요구해 중단되었고, 대신 sudo가 필요 없는 `brew install docker docker-compose` 경로로 CLI readiness를 통과시켰습니다.

## 3. GitHub CLI 준비 및 인증

GitHub CLI 설치는 완료했습니다.

```bash
gh --version
```

현재 설치 버전:

```text
gh version 2.93.0 (2026-05-27)
```

완료했습니다. GitHub CLI는 `studioaheun` 계정으로 로그인되어 있고, Git 작업 프로토콜은 HTTPS입니다.

확인 명령:

```bash
gh auth status
```

현재 상태:

```text
Logged in to github.com account studioaheun
Git operations protocol: https
```

## 4. 연결 러너 preflight 재실행

완료했습니다. 최신 handoff bundle 루트에서 preflight가 통과했습니다. 이 명령은 원격 URL, bundle 자체 검증, Docker, GitHub CLI 인증 상태를 점검합니다.

```bash
cd /Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260528-142101
PREFLIGHT_ONLY=true GIT_ORIGIN_URL=https://github.com/studioaheun/90-my-quant-bot.git ./run-connected-runner-handoff.sh
```

전체 flow도 실행했고, `codex/quant-lab-release` 브랜치 push까지 완료했습니다.

```bash
cd /Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260528-142101
GIT_ORIGIN_URL=https://github.com/studioaheun/90-my-quant-bot.git ./run-connected-runner-handoff.sh
```

참고: 첫 push 직후 연결 러너 내부 strict gate는 GitHub Actions 원격 workflow/run visibility와 live-beta closeout archive 상태 때문에 warn/fail이 남을 수 있습니다. 로컬 기준 최신 release gate는 13개 단계가 통과했고, 최종 완료율은 99%입니다.

## 5. 운영자 warning 검토

현재 최종 100%까지 남은 항목은 운영자 검토가 필요한 warning입니다. 먼저 쓰기 없이 warning 계획과 체크리스트를 검토합니다.

```bash
python3 scripts/review_release_warnings.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008 --no-write
```

검토할 문서:

- `/Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008/release-warning-actions.md`
- `/Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008/release-warning-operator-checklist.md`
- `/Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008/release-warning-triage.md`

자동화 또는 모니터링에서 요약만 필요하면 아래 명령을 사용합니다.

```bash
python3 scripts/review_release_warnings.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008 --summary-json-only
```

## 6. 운영자 승인 후 warning action 적용

`warning_actions`는 최종 완료에 필요한 항목입니다. 다만 진행률 점수는 `warning_alerts`가 가지고 있어서, 이 항목 자체가 별도 퍼센트를 올리지는 않습니다.

적용 전 조건:

- 운영자가 `release-warning-operator-checklist.md`를 검토해야 합니다.
- 백엔드가 실행 중이어야 합니다.
- health check가 통과해야 합니다.
- `--operator-approved`를 붙이는 것은 명시적 승인 행위로 취급합니다.

로컬 백엔드 실행:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload
```

백엔드 health check:

```bash
curl -fsS http://localhost:8000/api/health
```

운영자 승인 후에만 아래 명령을 실행합니다.

```bash
python3 scripts/review_release_warnings.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008 --apply --operator-approved
```

## 7. 최종 검증

위 항목이 모두 처리된 뒤 연결 러너의 `source` 디렉터리에서 strict release gate를 실행합니다.

```bash
cd /Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260528-142101/source
python3 scripts/release_gate.py --run-smoke --strict-external --check-gh-auth
```

완료 기준:

- release gate가 통과합니다.
- GitHub CLI 인증 warning이 사라집니다.
- warning review/action 항목이 정리됩니다.
- `python3 scripts/report_release_status.py --progress-only` 결과가 100%로 올라갑니다.

## 빠른 상태 확인 명령

현재 진행률과 남은 항목:

```bash
python3 scripts/report_release_status.py --progress-only
```

남은 작업 전체 계획:

```bash
python3 scripts/report_release_status.py --completion-plan-only
```

소유자별 남은 작업:

```bash
python3 scripts/report_release_status.py --owner-lanes-only
```

최신 evidence checksum 검증:

```bash
python3 scripts/write_evidence_checksums.py --package-dir /Users/ckkim/Documents/quant/artifacts/evidence-packages/20260528-KRW-BTC-beta-008 --verify --json-only
```

최신 handoff bundle 검증:

```bash
python3 scripts/package_connected_runner_handoff.py --verify /Users/ckkim/Documents/quant/artifacts/handoff-bundles/quant-lab-connected-runner-handoff-20260528-142101 --summary-json-only
```
