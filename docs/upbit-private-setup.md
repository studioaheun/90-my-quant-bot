# Upbit Private Mode Setup

Quant Lab currently uses Upbit private APIs in two separate modes:

- Read-only account checks: balances and open orders.
- Live order submission: disabled by default and guarded by multiple explicit flags.

Start with read-only access. Do not grant order permissions to an API key until the paper-trading and account snapshot flow has been verified with the exact market and strategy you intend to run.

## Required Environment Variables

Set these before starting the FastAPI backend:

```bash
export UPBIT_ACCESS_KEY="your-access-key"
export UPBIT_SECRET_KEY="your-secret-key"
```

Optional:

```bash
export UPBIT_BASE_URL="https://api.upbit.com"
export QUANT_LAB_MIN_ORDER_NOTIONAL_KRW=5000
export QUANT_LAB_APPROVAL_FEE_BPS=5
export QUANT_LAB_MAX_APPROVAL_EXPOSURE_PCT=60
```

If either key is missing, `GET /api/execution/private-snapshot` stays available but returns:

```json
{
  "exchange": "upbit",
  "credential_ready": false,
  "balances": [],
  "open_orders": []
}
```

## Check Read-Only Private Access

Start the backend in the same shell that has the environment variables:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload
```

Then check the snapshot endpoint:

```bash
curl -sS http://127.0.0.1:8000/api/execution/settings
curl -sS http://127.0.0.1:8000/api/execution/private-snapshot
```

The settings endpoint reports whether credentials and the live ACK are configured, which guard thresholds are active, and whether dry-run prechecks will use Upbit `/v1/orders/chance` or local defaults. It never returns API key values.

The dashboard execution area also has a refresh button that reloads:

- execution guard status
- execution settings
- private balances
- open orders
- recent order audit records

## Dry-Run Approval Checks

Before approving a dry-run intent, Quant Lab estimates:

- order notional against `QUANT_LAB_MIN_ORDER_NOTIONAL_KRW`
- private quote/base balances when Upbit credentials are available
- Upbit-provided fees, market min/max totals, and price unit from `/v1/orders/chance` when credentials are available
- estimated post-order exposure against `QUANT_LAB_MAX_APPROVAL_EXPOSURE_PCT`

Without private credentials, balance and exposure checks are marked as warnings and live submission remains blocked by the execution guard. Upbit's official order availability endpoint (`/v1/orders/chance`) exposes market-specific fees, supported order types, minimum/maximum order totals, and account balances; Quant Lab uses it when credentials are configured and falls back to local guard defaults otherwise.

## Live Order Lock

Live orders remain locked even when private reads work. To arm order submission, all of these must be set:

```bash
export QUANT_LAB_LIVE_TRADING_ENABLED=true
export QUANT_LAB_LIVE_TRADING_ACK=REAL_ORDERS_OK
export UPBIT_ACCESS_KEY="your-access-key"
export UPBIT_SECRET_KEY="your-secret-key"
```

Each order intent must also send `live_confirmation=true`.

Until a strategy-driven order path is deliberately implemented, use the live lock as a final safety barrier. The expected development order is:

1. Verify balances and open orders with read-only permissions.
2. Verify blocked order intents are audited locally.
3. Queue paper-session trades as dry-run strategy order intents and review the audit records.
4. Run the live-adapter arming simulator from the cutover checklist panel and confirm the preview does not introduce approval or guard blockers.
5. Export and review the live adapter arming runbook from the cutover checklist panel.
6. Review selected dry-run intents in the order review panel and approve only after confirming the backend guard state.
7. Watch the post-cutover monitor for approval attempts, blocked/failed audits, and private open orders during the live window.
8. Export the live-window closeout report after the adapter is locked again.
9. Only then test live order submission with minimal size and explicit confirmation.

## Upbit API References

- Authentication and JWT signing: https://global-docs.upbit.com/reference/authentication
- Account inquiry endpoint: https://global-docs.upbit.com/v1.2.2/reference/assets
- Available order information endpoint: https://docs-e.upbit.com/reference/available-order-information
- Open orders endpoint: https://global-docs.upbit.com/reference/list-open-orders
