# 봇 실행 가이드

이 문서는 Quant Lab의 `Bot fleet` 기능으로 여러 봇을 만들고 실행하는 방법을 설명합니다.
현재 봇 실행은 안전하게 `paper` 또는 `dry_run`까지만 연결됩니다. 실거래 주문은 기존 execution guard에 의해 계속 잠겨 있습니다.

## 1. 로컬 실행

백엔드, 프론트엔드, 브라우저를 한 번에 실행:

```bash
python3 scripts/run_local_app.py
```

이 터미널에서 `Ctrl+C`를 누르면 스크립트가 직접 띄운 백엔드/프론트엔드를 함께 종료합니다.
브라우저를 열지 않고 서비스만 시작하려면:

```bash
python3 scripts/run_local_app.py --no-browser
```

각 서비스를 따로 띄우려면 아래 명령을 사용합니다.

백엔드:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

프론트엔드:

```bash
cd frontend
npm run dev
```

브라우저:

```text
http://127.0.0.1:5173
```

## 2. Bot Fleet 화면에서 실행하기

대시보드 상단의 `Market ticker` 아래에 `Bot fleet` 패널이 있습니다.

처음 사용할 때는:

1. `Seed fleet`을 누릅니다.
2. 샘플 봇 3개가 생성되는지 확인합니다.
3. `Run due`를 눌러 실행 시간이 도래한 봇을 모두 실행합니다.
4. 각 봇 행에서 status, final equity, return, next run을 확인합니다.

샘플 봇은 다음과 같습니다.

| 봇 | 운영 성격 | 전략 | 대상 | 모드 |
| --- | --- | --- | --- | --- |
| Trend Scout | breakout | Donchian breakout | KRW-BTC | dry_run |
| Pullback Hunter | mean reversion | RSI mean reversion | SPY | paper |
| Crossover Core | trend following | SMA crossover | KRW-BTC | paper |

## 3. 버튼 의미

- `Seed fleet`: 샘플 봇 프로필을 생성합니다.
- `Run due`: `active=true`이고 `next_run_at`이 지난 봇을 모두 실행합니다.
- `Run`: 해당 봇 1개를 즉시 실행합니다.
- `Pause`: 해당 봇을 실행 대상에서 제외합니다.
- `Resume`: 일시정지된 봇을 다시 실행 대상에 넣습니다.
- 휴지통 아이콘: 봇 프로필을 삭제합니다.
- 새로고침 아이콘: Bot Fleet 상태를 다시 불러옵니다.

## 4. 실행 모드

`paper` 모드:

- 봇이 paper session을 생성합니다.
- 거래, 수익률, drawdown, risk event를 기록합니다.
- 외부 브로커나 거래소에 주문을 제출하지 않습니다.

`dry_run` 모드:

- 먼저 paper session을 생성합니다.
- KRW crypto paper trade가 있으면 dry-run order intent를 큐에 넣습니다.
- 큐에 들어간 intent는 기존 `Order review`, precheck, runbook 흐름으로 이어집니다.
- 실제 Upbit 주문은 제출하지 않습니다.

stock/ETF 봇은 현재 paper-only 경로가 기본입니다. 실거래 브로커 라우팅은 활성화되어 있지 않습니다.

## 5. API로 실행하기

전체 상태 조회:

```bash
curl -sS http://127.0.0.1:8000/api/bots/fleet | python3 -m json.tool
```

봇 프로필 목록:

```bash
curl -sS http://127.0.0.1:8000/api/bots/profiles | python3 -m json.tool
```

봇 프로필 생성 예시:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/bots/profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Trend Scout",
    "description": "Breakout bot for KRW crypto dry-run review.",
    "operating_style": "breakout",
    "execution_mode": "dry_run",
    "interval_minutes": 120,
    "active": true,
    "priority": 80,
    "max_intents_per_run": 2,
    "conflict_policy": "allow",
    "avatar": {
      "seed": "trend-scout-breakout-v1",
      "style": "bottts",
      "accent_color": "#d59a25"
    },
    "request": {
      "symbol": "KRW-BTC",
      "timeframe": "day",
      "source": "sample",
      "strategy": "donchian_breakout",
      "initial_cash": 1000000,
      "fee_bps": 5,
      "slippage_bps": 2,
      "candle_limit": 180,
      "params": {"lookback": 20, "exit_lookback": 10},
      "risk_limits": {
        "max_position_pct": 50,
        "max_order_notional": 500000,
        "max_orders": 20,
        "max_session_loss_pct": 20,
        "kill_switch": false
      }
    }
  }' | python3 -m json.tool
```

due 봇 전체 실행:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/bots/run-due | python3 -m json.tool
```

특정 봇 실행:

```bash
BOT_ID="..."
curl -sS -X POST "http://127.0.0.1:8000/api/bots/profiles/${BOT_ID}/run" | python3 -m json.tool
```

봇 일시정지/재개:

```bash
BOT_ID="..."
curl -sS -X POST "http://127.0.0.1:8000/api/bots/profiles/${BOT_ID}/pause" | python3 -m json.tool
curl -sS -X POST "http://127.0.0.1:8000/api/bots/profiles/${BOT_ID}/resume" | python3 -m json.tool
```

봇 삭제:

```bash
BOT_ID="..."
curl -sS -X DELETE "http://127.0.0.1:8000/api/bots/profiles/${BOT_ID}" | python3 -m json.tool
```

## 6. 실행 결과 읽기

`GET /api/bots/fleet`의 핵심 필드는 다음과 같습니다.

- `summary.total_bots`: 전체 봇 수
- `summary.active_bots`: 활성 봇 수
- `summary.due_bots`: 지금 실행 가능한 봇 수
- `summary.paper_bots`: paper 모드 봇 수
- `summary.dry_run_bots`: dry-run 모드 봇 수
- `summary.open_position_bots`: 최근 실행 결과에서 포지션이 열린 봇 수
- `summary.recent_dry_run_intents`: 최근 봇 실행에서 생성된 dry-run intent 수
- `profiles`: 봇 프로필 목록. 각 프로필에는 `avatar.seed`, `avatar.style`, `avatar.accent_color`가 포함됩니다.
- `recent_runs`: 최근 봇 실행 결과

봇 실행 결과인 `BotRun`에는 다음이 들어 있습니다.

- `status`: `completed`, `halted`, `blocked`, `error`
- `session`: 생성된 paper session
- `queued`: dry-run intent 큐잉 결과
- `warnings`: sample data, source, 봇 생성 경고
- `errors`: 충돌, 데이터 오류, dry-run 큐잉 실패 사유

## 7. 리스크와 충돌 정책

각 봇은 `risk_limits`를 별도로 가집니다.

- `max_position_pct`: 최대 포지션 비중
- `max_order_notional`: 주문당 최대 금액
- `max_orders`: 세션 내 최대 주문 수
- `max_session_loss_pct`: 세션 손실 중단 기준
- `kill_switch`: true이면 주문을 만들지 않고 halted 처리

`conflict_policy`는 같은 심볼을 여러 봇이 동시에 다루는 경우를 제어합니다.

- `block_same_symbol`: 최근 다른 봇이 같은 심볼에 열린 포지션을 갖고 있으면 차단합니다.
- `allow`: 같은 심볼을 여러 봇이 공유하도록 허용합니다.

샘플 봇은 비교 실험을 쉽게 하기 위해 `allow`를 사용합니다. 실제 운영에서는 `block_same_symbol`을 기본으로 두는 편이 안전합니다.

## 8. 운영 전 체크리스트

봇을 실행하기 전에 확인하세요.

- `Live trading locked` 상태인지 확인합니다.
- `Data providers`에서 사용할 source가 `READY`인지 확인합니다.
- `Bot fleet`의 `Due now` 값이 의도와 맞는지 확인합니다.
- `Run due` 실행 후 `dry-run intents`가 늘었다면 `Order review`를 확인합니다.
- `Alert review`에 halt/error가 있으면 봇 승격을 멈춥니다.
- stock/ETF 봇은 paper-only로만 운영합니다.

## 9. 자주 생기는 상황

`No bot profiles are configured.`

- 아직 봇이 없습니다. UI에서 `Seed fleet`을 누르거나 `POST /api/bots/profiles`로 생성합니다.

`due_bots`가 0입니다.

- 아직 `next_run_at`이 지나지 않았습니다. 개별 봇의 `Run` 버튼으로 즉시 실행할 수 있습니다.

`blocked` 상태가 나옵니다.

- 같은 심볼 충돌, dry-run 라우팅 불가, paper-to-live route 제한 등으로 차단된 상태입니다. `errors` 필드를 확인합니다.

`dry_run` 봇인데 intent가 0개입니다.

- 해당 paper session에 거래가 없거나, 이미 같은 session/trade의 intent가 큐에 들어간 상태일 수 있습니다.

`sample` 또는 `sample_us` 경고가 보입니다.

- 로컬 개발용 결정론적 샘플 데이터라는 뜻입니다. 실제 시장 데이터 점검은 `upbit` 또는 `alpha_vantage` source 설정을 별도로 확인해야 합니다.

## 10. 검증 명령

봇 기능 변경 후 최소 검증:

```bash
backend/.venv/bin/python -m unittest backend.tests.test_api.ApiTests.test_bot_fleet_runs_independent_strategy_profiles
npm run build --prefix frontend
```

전체 프로젝트 검증:

```bash
python3 scripts/verify_project.py
```
