# Bot Fleet Operator

Bot Fleet Operator는 서로 다른 운영 성격의 봇 프로필을 저장하고, 각 봇이 독립적인 전략/종목/리스크 한도로 paper session을 실행하도록 묶는 운영 화면과 API입니다.

## 운영 모델

- `BotProfile`: 봇 이름, 운영 성격, 전략, 종목, 실행 모드, 주기, 우선순위, 리스크 한도를 저장합니다.
- `BotRun`: 봇 1회 실행 결과입니다. paper session, 리스크 이벤트, dry-run intent 생성 결과를 함께 기록합니다.
- `BotFleet`: 전체 봇 수, active/due 상태, 열린 paper sleeve, 최근 dry-run intent 수를 집계합니다.

실거래 주문은 여전히 기존 execution guard에 의해 잠겨 있습니다. 봇의 `execution_mode`가 `dry_run`이어도 KRW crypto paper trade를 dry-run order intent로 큐잉할 뿐, live order를 제출하지 않습니다.

## 참고한 구조

- Freqtrade: 여러 bot instance를 config, DB, API port 단위로 분리 운영합니다.
- Hummingbot: 여러 controller가 executor를 만들고 멈추는 multi-strategy 구조를 제공합니다.
- vn.py: 전략 인스턴스를 UI에서 초기화, 시작, 중지하는 lifecycle 운영 UX가 강합니다.

Quant Lab은 이 셋을 섞어 `봇 프로필은 독립`, `실행 결과는 중앙 저장`, `리스크와 live guard는 중앙 통제`하는 형태로 구현합니다.

## API

- `GET /api/bots/fleet`: 전체 봇 운영 상태와 최근 실행 결과를 조회합니다.
- `GET /api/bots/profiles`: 봇 프로필 목록을 조회합니다.
- `POST /api/bots/profiles`: 봇 프로필을 생성합니다.
- `POST /api/bots/profiles/{bot_id}/run`: 특정 봇을 즉시 실행합니다.
- `POST /api/bots/run-due`: 실행 시간이 도래한 active 봇을 모두 실행합니다.
- `POST /api/bots/profiles/{bot_id}/pause`: 봇을 일시정지합니다.
- `POST /api/bots/profiles/{bot_id}/resume`: 봇을 재개합니다.
- `DELETE /api/bots/profiles/{bot_id}`: 봇 프로필을 삭제합니다.

## 초기 운영 흐름

1. 웹 화면의 `Bot fleet` 패널에서 `Seed fleet`을 눌러 샘플 봇 3개를 생성합니다.
2. `Run due`로 due 상태인 봇을 실행합니다.
3. 봇별 final equity, return, status, next run을 확인합니다.
4. KRW crypto dry-run 봇은 기존 `Order review`와 strategy health trace 흐름으로 이어집니다.
5. stock/ETF 봇은 paper-only 운영으로 남기고 broker handoff 흐름과 분리합니다.

## 경계

- 현재는 local scheduler와 수동 `Run due`가 봇 실행을 담당합니다.
- 같은 심볼 충돌은 `conflict_policy`로 제어합니다. 기본값은 `block_same_symbol`이고, 샘플 봇은 비교 실험을 위해 `allow`를 사용합니다.
- live order 제출, multi-account allocation, 실시간 websocket 봇 상태는 다음 확장 단계입니다.
