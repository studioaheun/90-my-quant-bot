# Stock/ETF Data Setup

Quant Lab currently supports two stock/ETF research sources:

- `sample_us`: deterministic local daily candles for offline paper-trading experiments.
- `alpha_vantage`: Alpha Vantage compact daily OHLCV data for real US stock/ETF prices.

## Alpha Vantage

Set an API key before starting the backend:

```bash
export ALPHA_VANTAGE_API_KEY="your-alpha-vantage-key"
```

Optional:

```bash
export ALPHA_VANTAGE_BASE_URL="https://www.alphavantage.co"
```

Then choose `Alpha Vantage daily` in the dashboard data-source selector. Current dashboard symbols are:

- `SPY`
- `QQQ`
- `AAPL`
- `MSFT`
- `NVDA`
- `TSLA`

The adapter uses Alpha Vantage `TIME_SERIES_DAILY` with `outputsize=compact`. That keeps requests small and matches the free-tier shape, but it generally returns only the latest 100 daily rows. If more rows are requested, the backend records a warning with the actual returned count.

The dashboard `Data providers` panel shows whether Alpha Vantage is configured, the required credential name, cache TTL, the last attempted symbol/timeframe, the latest successful fetch, and the latest provider error. The backend endpoint is:

```bash
curl -sS http://127.0.0.1:8000/api/markets/providers/status
```

## Paper-Only Boundary

Stock/ETF runs are intentionally paper-only. The dry-run execution queue and live-order approval flow are limited to KRW crypto spot sessions, because the current live execution adapter is Upbit-only.

The stock/ETF route now exposes three paper broker contracts through the paper-live adapter profile API:

- `mock_us_equity_paper`: credential-free local paper-record routing for stock/ETF handoffs.
- `alpaca_us_equity_paper_preview`: an Alpaca-style preview contract that lists future paper credentials but still records locally and never calls Alpaca.
- `alpaca_us_equity_paper`: a credential-gated Alpaca paper Trading API adapter that can submit paper stock/ETF orders only when every paper gate is satisfied.

The mock and preview contracts document the future broker boundary, accepted order shapes, and paper-record mode, but they block live-confirmed submissions and do not call any external brokerage endpoint.
The credentialed Alpaca paper adapter still blocks `live_confirmation=true`, rejects non-paper base URLs, and requires all of the following before it calls `POST /v2/orders` on Alpaca's paper API:

```bash
export ALPACA_API_KEY_ID="your-paper-key-id"
export ALPACA_API_SECRET_KEY="your-paper-secret"
export ALPACA_PAPER_BASE_URL="https://paper-api.alpaca.markets"
export ALPACA_PAPER_TRADING_ENABLED=true
export ALPACA_PAPER_TRADING_ACK=PAPER_ORDERS_OK
```

Each request must also include `paper_submit_confirmation=true`. Use `GET /api/execution/broker-readiness` or the Broker readiness dashboard panel to verify that mock/preview routes remain local-only and that the credentialed Alpaca paper route is blocked until all paper gates pass.
After a credentialed Alpaca paper evaluation is saved, use `GET /api/execution/broker-intents/evaluations/{evaluation_id}/reconcile` or the dashboard history row action to fetch broker-side paper order status and persist a reconciliation snapshot. The endpoint matches broker symbol, side, quantity, and order status against the local evaluation; missing credentials or paper gates return a local `blocked` result without calling Alpaca. Successful broker lookups also capture partial-fill state, average fill price, fill activity count, fee/commission fields when Alpaca exposes them, account cash/equity/buying power, broker-side position snapshots, and linked paper-fill-note deltas.
Broker paper submission failures, reconciliation mismatches, missing broker orders, and paper fill drift breaches now appear in `GET /api/alerts/review` under `broker_paper_submission`, `broker_reconciliation`, and `paper_fill_drift`. These alert rows include the linked evaluation/reconciliation IDs and are also summarized in the strategy health handoff report.

For contract-level paper checks, use the dashboard `US paper broker sandbox` panel or the API endpoint below. It accepts a broker-neutral order intent, validates symbol/side/quantity/order type against the selected `adapter_id`, returns the paper result, and always reports `external_submission_attempted=false`. When a `reference_price` is supplied, the same response includes a provider-agnostic paper fill estimate with expected fill price, estimated fee, cash sufficiency, position sufficiency, post-fill cash, post-fill quantity, and exposure.
Each evaluation is saved to SQLite and appears in the dashboard's recent-evaluations list. The history can also be queried with `GET /api/execution/broker-intents/evaluations`, optionally filtered by `adapter_id`, and the dashboard can export a Markdown report from `GET /api/execution/broker-intents/evaluations/report`. Stock/ETF handoff drill-downs and paper-only strategy handoff reports also surface recent broker intent/fill evaluations for the same symbol across paper adapters.

If the request includes a matching `paper_session_id` and the paper fill estimate is accepted as `estimated_fill`, Quant Lab creates a paper fill order note for that session. The note records the intended paper fill, the linked broker evaluation, and the latest same-side simulated trade so operators can compare intended-vs-simulated fills over repeated paper runs. Handoff drill-downs, strategy health handoff exports, and the dashboard's `Paper fill drift` panel include these notes. Use `GET /api/paper/order-notes/analytics` to aggregate recent notes by symbol and paper broker adapter, including matched-trade counts plus average and worst fill-price deltas. Use `GET /api/paper/order-notes/quality-gate` when you need a ready/watch/blocked verdict before expanding a stock/ETF paper route toward a real broker adapter; the default gate requires at least three linked notes, average absolute price drift at or below 0.35%, worst absolute drift at or below 1.0%, and no external submission attempts. Stock/ETF paper-only handoff approvals are blocked unless this quality gate is `ready`; successful approved decisions store the gate status, thresholds, and row evidence in the operations journal context.

After at least one handoff is approved with a ready gate, use `GET /api/paper/stock-etf/broker-expansion-readiness` or the dashboard `Stock/ETF broker expansion` panel to see which approved paper-only handoffs are ready candidates for future broker-paper adapter work. The paired `/report` endpoint exports the same evidence as Markdown. For a specific approved-ready decision, call `/package/{decision_id}` or use the panel's `Package` action to export Alpaca-style paper order payload drafts, linked fill evidence, and stop conditions. Use `/package/{decision_id}/preflight` or the panel's `Preflight` action to validate the package payload schema, quality gate, no-external-submission boundary, and Alpaca preview coverage before adapter implementation. Use `/package/{decision_id}/rehearsal` or the panel's `Rehearsal` action to replay those payloads into local paper-only accepted/rejected order records. These package payloads and rehearsals are for adapter implementation review only and are not submitted externally.

```bash
curl -sS -X POST http://127.0.0.1:8000/api/execution/broker-intents/evaluate \
  -H "Content-Type: application/json" \
  -d '{"symbol":"SPY","side":"buy","quantity":2,"order_type":"limit","limit_price":500,"reference_price":499,"cash_available":2000,"current_position_quantity":0,"portfolio_equity":2000,"paper_fee_bps":1,"paper_slippage_bps":1}'
```

```bash
curl -sS -X POST http://127.0.0.1:8000/api/execution/broker-intents/evaluate \
  -H "Content-Type: application/json" \
  -d '{"adapter_id":"alpaca_us_equity_paper_preview","symbol":"AAPL","side":"buy","quantity":1,"order_type":"market","reference_price":200,"cash_available":1000}'
```

```bash
curl -sS -X POST http://127.0.0.1:8000/api/execution/broker-intents/evaluate \
  -H "Content-Type: application/json" \
  -d '{"adapter_id":"alpaca_us_equity_paper_preview","symbol":"SPY","side":"buy","quantity":1,"order_type":"market","reference_price":420,"cash_available":1000,"paper_session_id":"replace-with-paper-session-id"}'
```

```bash
curl -sS -X POST http://127.0.0.1:8000/api/execution/broker-intents/evaluate \
  -H "Content-Type: application/json" \
  -d '{"adapter_id":"alpaca_us_equity_paper","symbol":"SPY","side":"buy","quantity":1,"order_type":"market","time_in_force":"day","reference_price":420,"cash_available":1000,"paper_submit_confirmation":true}'
```

```bash
curl -sS "http://127.0.0.1:8000/api/execution/broker-intents/evaluations?adapter_id=alpaca_us_equity_paper_preview&limit=5"
```

```bash
curl -sS "http://127.0.0.1:8000/api/execution/broker-intents/evaluations/replace-with-evaluation-id/reconcile"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/sessions/replace-with-paper-session-id/order-notes"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/order-notes/analytics?adapter_id=alpaca_us_equity_paper_preview&symbol=SPY&limit=50"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/order-notes/quality-gate?adapter_id=alpaca_us_equity_paper_preview&symbol=SPY&limit=50"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/stock-etf/broker-expansion-readiness?limit=20"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/stock-etf/broker-expansion-readiness/report?limit=50"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/stock-etf/broker-expansion-readiness/package/replace-with-approved-decision-id"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/stock-etf/broker-expansion-readiness/package/replace-with-approved-decision-id/preflight"
```

```bash
curl -sS "http://127.0.0.1:8000/api/paper/stock-etf/broker-expansion-readiness/package/replace-with-approved-decision-id/rehearsal"
```

```bash
curl -sS "http://127.0.0.1:8000/api/execution/broker-intents/evaluations/report?limit=20"
```

## API References

- Alpha Vantage stock time series documentation: https://www.alphavantage.co/documentation/
- Alpaca order submission documentation: https://docs.alpaca.markets/us/docs/working-with-orders
- Alpaca create order reference: https://docs.alpaca.markets/us/reference/postorder
