# Bot Fleet Operator

Bot Fleet Operator는 서로 다른 운영 성격의 봇 프로필을 저장하고, 각 봇이 독립적인 전략/종목/리스크 한도로 paper session을 실행하도록 묶는 운영 화면과 API입니다.

실제 실행 절차는 [봇 실행 가이드](bot-run-guide-ko.md)를 먼저 보세요.

## 운영 모델

- `BotProfile`: 봇 이름, 운영 성격, 전략, 종목, 실행 모드, 주기, 우선순위, 리스크 한도, 프로필 아이콘 메타데이터를 저장합니다.
- `BotRun`: 봇 1회 실행 결과입니다. paper session, 리스크 이벤트, dry-run intent 생성 결과를 함께 기록합니다.
- `BotFleet`: 전체 봇 수, active/due 상태, 열린 paper sleeve, 최근 dry-run intent 수를 집계합니다.

실거래 주문은 여전히 기존 execution guard에 의해 잠겨 있습니다. 봇의 `execution_mode`가 `dry_run`이어도 KRW crypto paper trade를 dry-run order intent로 큐잉할 뿐, live order를 제출하지 않습니다.

## 참고한 구조

- Freqtrade: 여러 bot instance를 config, DB, API port 단위로 분리 운영합니다.
- Hummingbot: 여러 controller가 executor를 만들고 멈추는 multi-strategy 구조를 제공합니다.
- vn.py: 전략 인스턴스를 UI에서 초기화, 시작, 중지하는 lifecycle 운영 UX가 강합니다.

Quant Lab은 이 셋을 섞어 `봇 프로필은 독립`, `실행 결과는 중앙 저장`, `리스크와 live guard는 중앙 통제`하는 형태로 구현합니다.

## 프로필 아이콘

각 봇은 `avatar` 메타데이터를 가집니다. 프론트엔드는 이 값을 DiceBear 기반 로컬 SVG로 렌더링하므로 외부 이미지 URL을 호출하지 않습니다.

- `seed`: 같은 봇을 항상 같은 얼굴로 그리는 결정적 seed입니다.
- `style`: `pixel_art`, `pixel_art_neutral`, `bottts`, `identicon` 중 하나입니다.
- `accent_color`: 상태 링과 avatar 배경에 쓰는 대표 색상입니다.

`avatar`를 생략하면 운영 성격에 따라 기본값이 자동 지정됩니다. `trend_following`은 pixel art, `mean_reversion`은 neutral pixel art, `breakout`은 bot avatar, `portfolio_rotation`과 `defensive_monitor`는 identicon 계열을 사용합니다.

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

1. 웹 화면의 `봇 운영` 패널에서 `봇 추가`를 누릅니다.
2. `봇 실행 설정` 창에서 프리셋을 선택합니다. 프리셋은 봇 이름, 페르소나, 전략, 종목, 리스크 한도, 주기, 아이콘을 함께 채웁니다.
3. 필요한 값을 조정한 뒤 `저장` 또는 `저장 후 실행`을 누릅니다.
4. 상단 `마켓 데이터` 패널에서 데이터 소스와 종목을 고르고 현재가, 변동률, 데이터 공급자 상태, 캐시 행 수를 확인합니다.
5. `실행 대상 실행`으로 due 상태인 active 봇을 실행합니다.
6. 봇 리스트 상단의 상태 필터와 정렬 메뉴로 `전체`, `활성`, `실행 중`, `일시정지`, `완료`, `주의` 봇을 나눠 봅니다.
7. 봇 리스트 상단의 `봇 정보`, `상태`, `운용자본`, `수익률` 같은 카테고리로 각 행의 값을 빠르게 확인합니다.
8. 각 봇 행의 `상세` 버튼을 눌러 모달 형식의 `봇 상세` 화면을 엽니다.
9. `개요` 탭에서 운영 모드, 다음 실행, 리스크 한도, 최근 paper 성과를 확인합니다.
10. `백테스트` 탭에서 선택된 봇의 현재 전략/종목/파라미터로 단일 백테스트를 실행하고, 결과 곡선과 최근 동일 전략 결과를 확인합니다.
11. KRW crypto dry-run 봇은 기존 `Order review`와 strategy health trace 흐름으로 이어집니다.
12. stock/ETF 봇은 paper-only 운영으로 남기고 broker handoff 흐름과 분리합니다.

## 기본 프리셋

- `추세 추종 감시자`: KRW crypto 돌파 흐름을 추적하는 dry-run 모멘텀 봇입니다.
- `되돌림 포착가`: US ETF 과매도 반등을 paper-only로 관찰하는 RSI 봇입니다.
- `코어 크로스오버`: SMA 기준선으로 BTC paper sleeve를 안정적으로 관찰합니다.
- `변동성 돌파 사냥꾼`: 변동성 큰 crypto 자산의 짧은 돌파 구간을 작은 주문 한도로 실험합니다.
- `안전마진 관리자`: 낮은 노출과 엄격한 손실 중단선을 우선하는 방어형 봇입니다.
- `텐배거 탐색가`: 성장형 US equity 후보를 paper-only 추세 전략으로 추적합니다.
- `빅쇼트 감시자`: short 주문 없이 과열, 하락 전환, 리스크 확대 신호만 감시합니다.

봇 삭제는 확인 팝업을 거칩니다. active 봇은 예약 실행 중단 경고를 보여주며, 최근 paper position이 있으면 추가 확인 문구를 표시합니다.

## 경계

- 현재는 local scheduler와 수동 `Run due`가 봇 실행을 담당합니다.
- 같은 심볼 충돌은 `conflict_policy`로 제어합니다. 기본값은 `block_same_symbol`이고, 샘플 봇은 비교 실험을 위해 `allow`를 사용합니다.
- live order 제출, multi-account allocation, 실시간 websocket 봇 상태는 다음 확장 단계입니다.
