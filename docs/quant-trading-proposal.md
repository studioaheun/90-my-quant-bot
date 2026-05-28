# Quant Trading Web/App Proposal

작성일: 2026-05-18 KST

## 1. 현재 프로젝트 상태

현재 저장소는 `.git` 외에 애플리케이션 코드가 없는 초기 상태다. 따라서 기존 코드에 기능을 얹는 방식보다, 퀀트 리서치, 백테스트, 모의투자, 실거래를 단계적으로 확장하는 새 구조로 시작하는 것이 적합하다.

## 2. 결론 요약

초기 MVP는 **코인 현물 자동매매**로 시작하는 것을 권장한다. 이유는 API 접근, 24시간 데이터 수집, 소액 테스트, 오픈소스 사례가 주식보다 빠르게 검증 가능하기 때문이다. 다만 실거래는 처음부터 켜지 말고, 백테스트와 paper/dry-run을 통과한 전략만 소액 현물로 제한해야 한다.

주식은 2단계 확장으로 두는 것이 좋다. 국내 주식은 증권사 API 신청, 모의투자, HTS/브로커 제약, 실시간 데이터 조건이 필요하고, 미국 주식은 Alpaca 같은 API로 paper trading은 쉽지만 국내 사용 가능 여부, 데이터 플랜, 브로커별 규정 확인이 필요하다.

추천 방향:

1. 1차: 코인 현물 리서치/백테스트/모의투자 웹앱
2. 2차: Upbit 또는 Binance 계열 실거래 어댑터
3. 3차: 미국 ETF/주식 paper trading, 이후 국내 주식 API 연동 검토

## 3. 웹 조사 사례

### Freqtrade형 코인 봇

Freqtrade는 Python 기반 오픈소스 코인 트레이딩 봇으로, 전략을 작성하고 OHLCV 과거 데이터로 백테스트한 뒤 dry/live trading으로 이어가는 구조를 제공한다. 공식 문서상 백테스트는 거래소/페어/타임프레임별 과거 캔들 데이터를 사용하며, 수수료를 반영하고 결과를 파일로 내보내 추가 분석할 수 있다.

프로젝트에 반영할 점:

- 같은 전략 코드를 백테스트와 모의투자에 재사용한다.
- 수수료, 슬리피지, 최소 주문 단위, 포지션 제한을 백테스트부터 반영한다.
- 결과는 equity curve, drawdown, win rate, profit factor, Sharpe/Sortino로 저장한다.

출처: [Freqtrade Backtesting](https://docs.freqtrade.io/en/stable/backtesting/)

### Hummingbot형 마켓메이킹/차익거래

Hummingbot은 market making과 알고리즘 트레이딩 봇을 만들기 위한 Python 프레임워크다. 중앙화 거래소와 DEX 커넥터를 표준화하고, 전략은 script/controller 구조로 확장한다.

프로젝트에 반영할 점:

- 초반에는 단순 추세/리밸런싱 전략으로 시작한다.
- 주문장 기반 마켓메이킹, 교차거래소 차익거래는 별도 고급 모듈로 둔다.
- 실시간 주문장 전략은 지연시간, 부분체결, 재호가, 재고 리스크 관리가 갖춰진 뒤 적용한다.

출처: [Hummingbot Documentation](https://hummingbot.org/docs/)

### QuantConnect LEAN형 멀티에셋 엔진

QuantConnect의 LEAN은 오픈소스 알고리즘 트레이딩 엔진으로, 리서치, 백테스트, 실거래를 지원하고 Python/C# 알고리즘을 실행한다. 주식, 크립토, 선물, 옵션 등 멀티에셋 구조를 염두에 둔 event-driven 엔진 사례로 참고할 만하다.

프로젝트에 반영할 점:

- 자산군별 어댑터는 분리하되 전략 인터페이스는 공통화한다.
- 백테스트와 라이브 실행이 동일한 이벤트 모델을 공유하게 설계한다.
- portfolio, transaction, schedule, notification을 독립 모듈로 둔다.

출처: [QuantConnect LEAN Algorithm Engine](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine)

### CCXT형 거래소 추상화

CCXT는 거래소별 API 차이를 `fetchOHLCV`, `fetchTicker`, `fetchBalance`, `createOrder`, `cancelOrder` 같은 공통 메서드로 감싸는 라이브러리다. 코인 거래소를 여러 곳으로 확장할 때 유용하다.

프로젝트에 반영할 점:

- `ExchangeAdapter` 인터페이스를 먼저 만들고 CCXT 또는 native API를 뒤에 붙인다.
- 주문 생성, 취소, 잔고 조회, OHLCV 조회는 공통 계약으로 묶는다.
- 거래소별 rate limit, 최소 주문, 심볼 표기 차이를 어댑터에서 흡수한다.

출처: [CCXT Manual](https://github.com/ccxt/ccxt/wiki/manual)

### Alpaca형 주식/코인 paper trading

Alpaca는 주식과 크립토 Trading API, paper trading 환경을 제공한다. 공식 문서상 paper trading은 무료이며 실시간 시뮬레이션 환경으로 알고리즘을 반복 테스트할 수 있다.

프로젝트에 반영할 점:

- 미국 주식/ETF 확장 시 paper trading부터 검증한다.
- 코인과 주식이 모두 가능한 브로커 API를 2차 확장 후보로 둔다.
- 데이터 플랜, 지원 국가, 주문 타입, fractional trading 제한을 별도 체크리스트로 둔다.

출처: [Alpaca Trading API](https://docs.alpaca.markets/us/docs/trading-api)

### 한국 거래소/증권사 API

Upbit Open API는 시세, 주문, 잔고 관련 API를 제공하며 rate limit이 명확하다. 예를 들어 공식 문서 기준 quotation 계열은 초당 최대 10회, 주문 생성은 초당 최대 8회 그룹으로 안내되어 있다. 한국투자증권 eFriend Expert Open API는 시세수신, 주문송신, 잔고조회 등을 직접 처리할 수 있게 하며, 모의투자로 충분히 테스트한 뒤 사용하라고 안내한다.

프로젝트에 반영할 점:

- 한국 사용자 기준 초기 코인 거래소는 Upbit native adapter가 현실적이다.
- 국내 주식은 한국투자증권/KIS 또는 키움 API 후보를 두되, 계좌/신청/모의투자 절차를 먼저 통과해야 한다.
- 모든 실거래 API는 rate limit과 재시도 정책을 주문 엔진에 내장한다.

출처: [Upbit Rate Limits](https://docs.upbit.com/kr/reference/rate-limits), [Upbit Create Order](https://global-docs.upbit.com/reference/order), [한국투자증권 eFriend Expert Open API](https://m.truefriend.com/main/customer/systemdown/OpenAPI.jsp)

## 4. 코인 vs 주식 판단

| 기준 | 코인 | 주식 |
| --- | --- | --- |
| MVP 속도 | 빠름. 거래소 API와 오픈소스 봇 사례가 많다. | 중간. 브로커/데이터/계좌 조건 확인이 필요하다. |
| 시장 시간 | 24/7 운영. 테스트와 데이터 수집이 빠르지만 장애 대응 부담도 크다. | 장중 중심. 운영 부담은 낮지만 기회와 테스트 사이클이 느리다. |
| 데이터 접근 | 캔들/호가/체결 데이터 접근이 비교적 쉽다. | 고품질 실시간/과거 데이터는 유료 또는 제한이 많다. |
| 전략 적합성 | 모멘텀, 추세추종, 변동성 돌파, 리밸런싱에 적합하다. | ETF/팩터/섹터 로테이션, 실적/재무 기반 전략에 적합하다. |
| 리스크 | 변동성, 거래소/커스터디, 상장폐지, 24시간 급변 리스크가 크다. | 제도권 보호와 데이터 품질은 좋지만 브로커 규정, 기업 이벤트, 세금/수수료 처리가 필요하다. |
| 한국 사용자 접근성 | Upbit/Bithumb/Korbit 등 접근성이 좋다. | 국내 증권사 API는 계좌/신청/환경 제약이 있다. |

판단:

- **프로젝트를 빨리 완성하고 실제 자동매매 루프를 검증하려면 코인 현물이 더 좋다.**
- **안정성과 장기 운용을 중시하면 주식/ETF가 더 좋다.**
- 가장 균형 잡힌 선택은 `코인 현물 MVP -> 주식/ETF paper trading 확장`이다.

주의:

- 한국은 가상자산 이용자보호법이 2024-07-19부터 시행되어 이용자 자산 보호, 불공정거래 금지, VASP 감독/제재 체계를 다룬다.
- 미국 주식 day trading 규정은 2026년에 FINRA Rule 4210 개정이 진행되어 PDT 체계가 intraday margin 표준으로 전환 중이다. 실제 적용은 브로커별 공지와 계정 유형을 확인해야 한다.

출처: [FSC Virtual Asset User Protection Act](https://www.fsc.go.kr/eng/pr010101/81698), [FINRA SR-FINRA-2025-017](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2025-017)

## 5. 제안 제품

제품명 가칭: **Quant Lab**

목표는 사용자가 전략을 작성하고, 데이터로 검증하고, 모의투자에서 관찰한 뒤, 작은 금액으로 통제된 실거래를 실행할 수 있는 웹 기반 퀀트 매매 도구를 만드는 것이다.

핵심 사용자 흐름:

1. 거래소/브로커 연결 정보 등록
2. 종목/페어와 기간 선택
3. 전략 템플릿 선택 또는 Python 전략 업로드
4. 백테스트 실행
5. 성과/리스크 리포트 확인
6. paper/dry-run 실행
7. 리스크 제한을 통과한 전략만 실거래 승인

## 6. MVP 기능 범위

### 리서치/데이터

- OHLCV 수집: BTC/KRW, ETH/KRW, BTC/USDT, ETH/USDT 등 유동성 높은 페어 우선
- 데이터 저장: 로컬 개발은 Parquet/DuckDB, 서버 배포는 PostgreSQL + object storage
- 데이터 품질 체크: 결측 캔들, 중복 캔들, 거래량 0, 급격한 이상치

### 전략

- SMA/EMA crossover
- Donchian breakout
- RSI mean reversion
- 변동성 타겟 포지션 사이징
- 단순 Top-N momentum 리밸런싱

초기에는 ML/LLM 기반 예측을 넣지 않는 편이 좋다. 먼저 주문/데이터/리스크 루프가 정확해야 한다.

### 백테스트

- 수수료, 슬리피지, 최소 주문 금액, 호가 단위 반영
- walk-forward validation
- train/test 기간 분리
- 과최적화 방지용 parameter sweep 결과 저장
- 결과 지표: CAGR, MDD, Sharpe, Sortino, Calmar, turnover, exposure, hit ratio, profit factor

### 모의투자

- 실시간 시세 수집
- 가상 포트폴리오/주문장 체결 시뮬레이션
- 실시간 PnL, 포지션, 주문 로그
- Discord/Telegram/Slack 알림

### 실거래

- 기본값은 비활성화
- API key는 출금 권한 없이 거래 권한만 사용
- 전략별 최대 투입금, 일 손실 한도, 주문 빈도 제한
- kill switch
- 주문 idempotency: client order id 저장
- 체결/잔고 reconciliation

## 7. 추천 아키텍처

```text
web dashboard
  -> API server
    -> strategy registry
    -> backtest engine
    -> paper/live execution engine
    -> risk manager
    -> notification service
  -> data workers
    -> market data adapters
    -> broker/exchange adapters
  -> storage
    -> parquet/duckdb for research
    -> postgres for app state
```

기술 스택 권장:

- Backend: Python, FastAPI, Pydantic
- Quant stack: pandas 또는 polars, numpy, ta-lib/pandas-ta, vectorbt 또는 자체 light backtester
- Worker: APScheduler/Celery/RQ 중 하나
- Storage: DuckDB/Parquet 먼저, PostgreSQL은 paper/live 상태 저장부터
- Frontend: Next.js 또는 Vite React
- Charts: lightweight-charts, Recharts, Plotly
- Deployment: Docker Compose

핵심 인터페이스:

```python
class MarketDataAdapter:
    def fetch_ohlcv(self, symbol: str, timeframe: str, start: str, end: str): ...
    def stream_ticks(self, symbols: list[str]): ...

class BrokerAdapter:
    def get_balance(self): ...
    def get_positions(self): ...
    def create_order(self, order): ...
    def cancel_order(self, order_id: str): ...

class Strategy:
    def generate_signals(self, candles, portfolio, context): ...
```

## 8. 개발 로드맵

### 1주차: 프로젝트 골격

- FastAPI + React 기본 앱
- DuckDB/Parquet 데이터 저장
- 전략/백테스트 결과 스키마
- BTC/ETH 샘플 데이터 수집 CLI

### 2주차: 백테스트 MVP

- SMA crossover, Donchian breakout 구현
- 수수료/슬리피지/최소 주문 반영
- 리포트 JSON 저장
- 웹에서 equity curve와 주문 목록 확인

### 3주차: paper trading

- 실시간 가격 polling 또는 websocket
- 가상 주문/체결 엔진
- 포지션/PnL 화면
- 위험 제한과 kill switch

### 4주차: Upbit adapter

- 인증, 잔고 조회, 주문 테스트
- rate limit 관리
- 주문 생성 테스트 endpoint
- 실거래는 feature flag로 잠금

### 5주차: 소액 실거래 베타

- 현물, 유동성 높은 1~2개 페어만 허용
- 전략별 최대 금액 제한
- 체결/잔고 reconciliation
- 장애 상황 로그와 알림

### 6주차: 주식/ETF 확장 검토

- Alpaca paper trading adapter
- 국내 주식은 한국투자증권/KIS 또는 키움 API PoC
- ETF 일봉 로테이션 전략 추가

## 9. 실거래 전 체크리스트

- 최소 6개월 이상 out-of-sample 백테스트
- 수수료와 슬리피지 스트레스 테스트
- 거래소 장애/429/rate limit 재시도 테스트
- 주문 중복 방지 테스트
- API key 권한 최소화 및 secret 암호화
- paper trading 최소 2~4주
- 일 손실 한도와 전체 손실 한도 설정
- 전략별 자본 배분과 최대 포지션 제한

## 10. 최종 제안

이 프로젝트는 **코인 현물 기반 Quant Lab**으로 시작하는 것이 가장 현실적이다. 코인은 기술 검증 속도가 빠르고, Upbit/CCXT/Freqtrade/Hummingbot 같은 참고 사례가 풍부하다. 대신 위험은 높으므로 처음부터 leverage, futures, market making을 넣지 말고, 유동성 높은 현물 페어와 보수적인 추세/리밸런싱 전략으로 시작해야 한다.

주식은 버리는 선택지가 아니라 다음 단계다. 백테스트/전략/리스크/대시보드가 안정화되면 Alpaca paper trading이나 국내 증권사 모의투자로 ETF/주식 전략을 붙이면 된다. 즉, 자산군 선택은 `코인 먼저, 주식은 구조적으로 열어두기`가 가장 좋다.
