import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, Protocol

from .models import BrokerAdapterContract, StockPaperBrokerAdapterId


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
BrokerValidationStatus = Literal["accepted", "rejected"]
BrokerSubmissionStatus = Literal["paper_recorded", "blocked", "rejected"]
BrokerOrderLookupStatus = Literal["found", "blocked", "not_found", "error"]
ALPACA_PAPER_TRADING_ACK_VALUE = "PAPER_ORDERS_OK"
DEFAULT_ALPACA_PAPER_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class BrokerOrderIntent:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = "market"
    limit_price: Optional[float] = None
    time_in_force: str = "day"
    client_order_id: Optional[str] = None
    live_confirmation: bool = False
    paper_submit_confirmation: bool = False


@dataclass(frozen=True)
class BrokerValidationResult:
    status: BrokerValidationStatus
    reason: str
    normalized_symbol: str
    estimated_notional: Optional[float] = None


@dataclass(frozen=True)
class BrokerSubmissionResult:
    status: BrokerSubmissionStatus
    reason: str
    broker_order_id: Optional[str] = None
    normalized_symbol: Optional[str] = None
    estimated_notional: Optional[float] = None
    external_submission_attempted: bool = False


@dataclass(frozen=True)
class BrokerOrderStatusResult:
    status: BrokerOrderLookupStatus
    reason: str
    broker_order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    order_status: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    quantity: Optional[float] = None
    filled_quantity: Optional[float] = None
    average_fill_price: Optional[float] = None
    filled_notional: Optional[float] = None
    broker_fee: Optional[float] = None
    partial_fill: Optional[bool] = None
    fill_activity_count: int = 0
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    position_quantity: Optional[float] = None
    position_market_value: Optional[float] = None
    position_cost_basis: Optional[float] = None
    position_unrealized_pl: Optional[float] = None
    position_snapshot: Optional[dict[str, Any]] = None
    account_cash: Optional[float] = None
    account_equity: Optional[float] = None
    account_buying_power: Optional[float] = None
    account_snapshot: Optional[dict[str, Any]] = None
    fill_activities: Optional[list[dict[str, Any]]] = None
    external_lookup_attempted: bool = False
    raw_payload: Optional[dict[str, Any]] = None


AlpacaPaperTransport = Callable[
    [str, dict[str, str], dict[str, str], int],
    tuple[int, dict[str, Any], dict[str, str]],
]
AlpacaPaperGetTransport = Callable[
    [str, dict[str, str], int],
    tuple[int, dict[str, Any], dict[str, str]],
]


class BrokerAdapter(Protocol):
    contract: BrokerAdapterContract

    def validate_order(self, intent: BrokerOrderIntent) -> BrokerValidationResult:
        ...

    def submit_order(self, intent: BrokerOrderIntent) -> BrokerSubmissionResult:
        ...


UPBIT_CRYPTO_SPOT_BROKER_CONTRACT = BrokerAdapterContract(
    id="upbit_private_api",
    label="Upbit private API",
    provider_type="exchange",
    submission_mode="guarded_live",
    live_order_supported=True,
    dry_run_supported=True,
    account_snapshot_supported=True,
    required_credentials=[
        "UPBIT_ACCESS_KEY",
        "UPBIT_SECRET_KEY",
        "QUANT_LAB_LIVE_TRADING_ACK",
    ],
    supported_order_types=["limit", "market"],
    notes=[
        "Live submission remains disabled until every Quant Lab live guard is satisfied.",
        "Each approval still requires live_confirmation=true.",
    ],
)

US_EQUITY_PAPER_BROKER_CONTRACT = BrokerAdapterContract(
    id="mock_us_equity_paper",
    label="Mock US equities paper broker",
    provider_type="paper_broker",
    submission_mode="paper_record_only",
    live_order_supported=False,
    dry_run_supported=False,
    account_snapshot_supported=False,
    required_credentials=[],
    supported_order_types=["market", "limit"],
    notes=[
        "US stock/ETF orders are recorded for operator review only.",
        "No live brokerage credentials or external order endpoints are wired.",
    ],
)


ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT = BrokerAdapterContract(
    id="alpaca_us_equity_paper_preview",
    label="Alpaca US equities paper preview",
    provider_type="paper_broker",
    submission_mode="paper_record_only",
    live_order_supported=False,
    dry_run_supported=False,
    account_snapshot_supported=False,
    required_credentials=[
        "ALPACA_API_KEY_ID",
        "ALPACA_API_SECRET_KEY",
        "ALPACA_PAPER_BASE_URL",
    ],
    supported_order_types=["market", "limit"],
    notes=[
        "This preview adapter validates Alpaca-style paper order shape without calling Alpaca.",
        "Credentials are listed for the future external paper-broker milestone, not read by this preview.",
        "Live-confirmed submissions remain blocked.",
    ],
)


ALPACA_US_EQUITY_PAPER_CONTRACT = BrokerAdapterContract(
    id="alpaca_us_equity_paper",
    label="Alpaca US equities paper trading",
    provider_type="paper_broker",
    submission_mode="external_paper",
    live_order_supported=False,
    dry_run_supported=False,
    account_snapshot_supported=False,
    required_credentials=[
        "ALPACA_API_KEY_ID",
        "ALPACA_API_SECRET_KEY",
        "ALPACA_PAPER_BASE_URL",
        "ALPACA_PAPER_TRADING_ENABLED",
        "ALPACA_PAPER_TRADING_ACK",
    ],
    supported_order_types=["market", "limit"],
    notes=[
        "Submits only to Alpaca's paper Trading API after explicit paper gates are satisfied.",
        f"Requires ALPACA_PAPER_TRADING_ACK={ALPACA_PAPER_TRADING_ACK_VALUE}.",
        "Live-confirmed submissions remain blocked by contract.",
    ],
)


class MockUsEquityPaperBroker:
    contract = US_EQUITY_PAPER_BROKER_CONTRACT

    def __init__(self, contract: Optional[BrokerAdapterContract] = None):
        if contract is not None:
            self.contract = contract

    def validate_order(self, intent: BrokerOrderIntent) -> BrokerValidationResult:
        symbol = intent.symbol.strip().upper()
        if not symbol:
            return BrokerValidationResult(
                status="rejected",
                reason="US equity symbol is required.",
                normalized_symbol=symbol,
            )
        if intent.quantity <= 0:
            return BrokerValidationResult(
                status="rejected",
                reason="Order quantity must be positive.",
                normalized_symbol=symbol,
            )
        if intent.order_type == "limit" and (intent.limit_price is None or intent.limit_price <= 0):
            return BrokerValidationResult(
                status="rejected",
                reason="Limit orders require a positive limit_price.",
                normalized_symbol=symbol,
            )
        notional = intent.quantity * intent.limit_price if intent.limit_price else None
        return BrokerValidationResult(
            status="accepted",
            reason=f"{self.contract.label} accepted the paper order shape.",
            normalized_symbol=symbol,
            estimated_notional=notional,
        )

    def submit_order(self, intent: BrokerOrderIntent) -> BrokerSubmissionResult:
        validation = self.validate_order(intent)
        if validation.status != "accepted":
            return BrokerSubmissionResult(
                status="rejected",
                reason=validation.reason,
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
            )
        if intent.live_confirmation:
            return BrokerSubmissionResult(
                status="blocked",
                reason=f"Live US equity order submission is disabled for {self.contract.label}.",
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
            )
        order_id = intent.client_order_id or f"paper-{validation.normalized_symbol}"
        return BrokerSubmissionResult(
            status="paper_recorded",
            reason=f"Order recorded by {self.contract.label}; no external broker was called.",
            broker_order_id=order_id,
            normalized_symbol=validation.normalized_symbol,
            estimated_notional=validation.estimated_notional,
        )


def _json_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body or "{}"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed: dict[str, Any] = json.loads(body or "{}")
        except json.JSONDecodeError:
            parsed = {"message": body}
        return exc.code, parsed, dict(exc.headers)


def _json_get_transport(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body or "{}"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed: dict[str, Any] = json.loads(body or "{}")
        except json.JSONDecodeError:
            parsed = {"message": body}
        return exc.code, parsed, dict(exc.headers)


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _alpaca_paper_base_url() -> str:
    return os.environ.get("ALPACA_PAPER_BASE_URL", "").strip().rstrip("/")


def _alpaca_paper_base_is_safe(base_url: str) -> bool:
    return base_url.startswith("https://paper-api.alpaca.markets")


def _alpaca_paper_auth_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY_ID"],
        "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET_KEY"],
        "Content-Type": "application/json",
    }


def _alpaca_paper_gate_failure() -> Optional[str]:
    if os.environ.get("ALPACA_PAPER_TRADING_ENABLED", "").lower() != "true":
        return "ALPACA_PAPER_TRADING_ENABLED is not true."
    if os.environ.get("ALPACA_PAPER_TRADING_ACK") != ALPACA_PAPER_TRADING_ACK_VALUE:
        return f"Set ALPACA_PAPER_TRADING_ACK={ALPACA_PAPER_TRADING_ACK_VALUE}."
    if not _env_present("ALPACA_API_KEY_ID") or not _env_present("ALPACA_API_SECRET_KEY"):
        return "Alpaca paper API credentials are missing."
    base_url = _alpaca_paper_base_url()
    if not base_url:
        return "ALPACA_PAPER_BASE_URL is required for paper submission."
    if not _alpaca_paper_base_is_safe(base_url):
        return "ALPACA_PAPER_BASE_URL must point at Alpaca's paper API domain."
    return None


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_optional(values: list[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _activity_float(activity: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _optional_float(activity.get(key))
        if value is not None:
            return value
    return None


def _alpaca_fill_activity_evidence(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, list):
        return {
            "activities": [],
            "activity_count": 0,
            "average_fill_price": None,
            "filled_notional": None,
            "broker_fee": None,
        }

    activities = [activity for activity in payload if isinstance(activity, dict)]
    quantities: list[Optional[float]] = []
    notionals: list[Optional[float]] = []
    fees: list[Optional[float]] = []
    for activity in activities:
        quantity = _activity_float(activity, "qty", "quantity")
        price = _activity_float(activity, "price", "fill_price")
        quantities.append(quantity)
        notionals.append(quantity * price if quantity is not None and price is not None else None)
        fees.append(_activity_float(activity, "commission", "fee", "fees", "transaction_fee"))

    total_quantity = _sum_optional(quantities)
    total_notional = _sum_optional(notionals)
    average_fill_price = (
        total_notional / total_quantity
        if total_quantity is not None and total_quantity > 0 and total_notional is not None
        else None
    )
    return {
        "activities": activities[:20],
        "activity_count": len(activities),
        "average_fill_price": average_fill_price,
        "filled_notional": total_notional,
        "broker_fee": _sum_optional(fees),
    }


def _alpaca_position_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    position_keys = {
        "asset_id",
        "avg_entry_price",
        "market_value",
        "cost_basis",
        "unrealized_pl",
        "unrealized_intraday_pl",
    }
    if not any(key in payload for key in position_keys):
        return {}
    return payload


def _alpaca_account_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    account_keys = {"cash", "equity", "buying_power", "portfolio_value", "status"}
    if not any(key in payload for key in account_keys):
        return {}
    return payload


class AlpacaUsEquityPaperBroker(MockUsEquityPaperBroker):
    contract = ALPACA_US_EQUITY_PAPER_CONTRACT

    def __init__(
        self,
        *,
        transport: AlpacaPaperTransport = _json_transport,
        get_transport: AlpacaPaperGetTransport = _json_get_transport,
        timeout_seconds: int = DEFAULT_ALPACA_PAPER_TIMEOUT_SECONDS,
    ):
        self.transport = transport
        self.get_transport = get_transport
        self.timeout_seconds = timeout_seconds

    def submit_order(self, intent: BrokerOrderIntent) -> BrokerSubmissionResult:
        validation = self.validate_order(intent)
        if validation.status != "accepted":
            return BrokerSubmissionResult(
                status="rejected",
                reason=validation.reason,
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
            )
        if intent.live_confirmation:
            return BrokerSubmissionResult(
                status="blocked",
                reason="Live US equity submission is disabled; use the Alpaca paper gate instead.",
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
            )
        if not intent.paper_submit_confirmation:
            return BrokerSubmissionResult(
                status="blocked",
                reason="Set paper_submit_confirmation=true before submitting to Alpaca paper.",
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
            )
        gate_failure = _alpaca_paper_gate_failure()
        if gate_failure is not None:
            return BrokerSubmissionResult(
                status="blocked",
                reason=gate_failure,
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
            )
        base_url = _alpaca_paper_base_url()
        payload = {
            "symbol": validation.normalized_symbol,
            "qty": f"{intent.quantity:g}",
            "side": intent.side,
            "type": intent.order_type,
            "time_in_force": intent.time_in_force or "day",
            "client_order_id": intent.client_order_id or f"quant-lab-{validation.normalized_symbol}",
        }
        if intent.order_type == "limit" and intent.limit_price is not None:
            payload["limit_price"] = f"{intent.limit_price:g}"
        try:
            status_code, response_body, response_headers = self.transport(
                f"{base_url}/v2/orders",
                _alpaca_paper_auth_headers(),
                payload,
                self.timeout_seconds,
            )
        except urllib.error.URLError as exc:
            return BrokerSubmissionResult(
                status="blocked",
                reason=f"Alpaca paper request failed before broker acceptance: {exc.reason}",
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
                external_submission_attempted=True,
            )
        except OSError as exc:
            return BrokerSubmissionResult(
                status="blocked",
                reason=f"Alpaca paper request failed before broker acceptance: {exc}",
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
                external_submission_attempted=True,
            )

        if 200 <= status_code < 300:
            broker_order_id = str(
                response_body.get("id")
                or response_body.get("client_order_id")
                or payload["client_order_id"]
            )
            request_id = response_headers.get("X-Request-ID") or response_headers.get("x-request-id")
            suffix = f" Request id: {request_id}." if request_id else ""
            return BrokerSubmissionResult(
                status="paper_recorded",
                reason=f"Alpaca paper order accepted by the paper Trading API.{suffix}",
                broker_order_id=broker_order_id,
                normalized_symbol=validation.normalized_symbol,
                estimated_notional=validation.estimated_notional,
                external_submission_attempted=True,
            )

        message = response_body.get("message") or response_body.get("error") or "Alpaca paper order rejected."
        return BrokerSubmissionResult(
            status="rejected",
            reason=f"Alpaca paper API returned {status_code}: {message}",
            normalized_symbol=validation.normalized_symbol,
            estimated_notional=validation.estimated_notional,
            external_submission_attempted=True,
        )

    def fetch_order_status(
        self,
        *,
        broker_order_id: Optional[str],
        client_order_id: Optional[str],
    ) -> BrokerOrderStatusResult:
        if not broker_order_id and not client_order_id:
            return BrokerOrderStatusResult(
                status="blocked",
                reason="Broker order id or client order id is required for Alpaca paper reconciliation.",
            )
        gate_failure = _alpaca_paper_gate_failure()
        if gate_failure is not None:
            return BrokerOrderStatusResult(status="blocked", reason=gate_failure)

        base_url = _alpaca_paper_base_url()
        if broker_order_id:
            lookup_id = urllib.parse.quote(broker_order_id, safe="")
            url = f"{base_url}/v2/orders/{lookup_id}"
        else:
            lookup_id = urllib.parse.quote(client_order_id or "", safe="")
            url = f"{base_url}/v2/orders:by_client_order_id?client_order_id={lookup_id}"

        try:
            status_code, response_body, _response_headers = self.get_transport(
                url,
                _alpaca_paper_auth_headers(),
                self.timeout_seconds,
            )
        except urllib.error.URLError as exc:
            return BrokerOrderStatusResult(
                status="error",
                reason=f"Alpaca paper order status lookup failed: {exc.reason}",
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                external_lookup_attempted=True,
            )
        except OSError as exc:
            return BrokerOrderStatusResult(
                status="error",
                reason=f"Alpaca paper order status lookup failed: {exc}",
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                external_lookup_attempted=True,
            )

        if status_code == 404:
            return BrokerOrderStatusResult(
                status="not_found",
                reason="Alpaca paper order was not found.",
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                external_lookup_attempted=True,
                raw_payload=response_body,
            )
        if not 200 <= status_code < 300:
            message = response_body.get("message") or response_body.get("error") or "Alpaca paper lookup failed."
            return BrokerOrderStatusResult(
                status="error",
                reason=f"Alpaca paper order status lookup returned {status_code}: {message}",
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                external_lookup_attempted=True,
                raw_payload=response_body,
            )

        order_id = str(response_body.get("id") or broker_order_id or "")
        resolved_client_order_id = str(response_body.get("client_order_id") or client_order_id or "")
        symbol = response_body.get("symbol")
        quantity = _optional_float(response_body.get("qty"))
        filled_quantity = _optional_float(response_body.get("filled_qty"))
        fill_activity_evidence = self._fetch_fill_activity_evidence(
            base_url=base_url,
            broker_order_id=order_id,
        )
        position_snapshot = self._fetch_position_snapshot(
            base_url=base_url,
            symbol=str(symbol or ""),
        )
        account_snapshot = self._fetch_account_snapshot(base_url=base_url)
        average_fill_price = (
            _optional_float(response_body.get("filled_avg_price"))
            or fill_activity_evidence["average_fill_price"]
        )
        filled_notional = fill_activity_evidence["filled_notional"]
        if filled_notional is None and filled_quantity is not None and average_fill_price is not None:
            filled_notional = filled_quantity * average_fill_price
        partial_fill = None
        if filled_quantity is not None and quantity is not None:
            partial_fill = 0 < filled_quantity < quantity

        return BrokerOrderStatusResult(
            status="found",
            reason="Alpaca paper order status was fetched.",
            broker_order_id=order_id,
            client_order_id=resolved_client_order_id,
            order_status=response_body.get("status"),
            symbol=symbol,
            side=response_body.get("side"),
            quantity=quantity,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price,
            filled_notional=filled_notional,
            broker_fee=fill_activity_evidence["broker_fee"],
            partial_fill=partial_fill,
            fill_activity_count=fill_activity_evidence["activity_count"],
            submitted_at=response_body.get("submitted_at"),
            filled_at=response_body.get("filled_at"),
            position_quantity=_optional_float(position_snapshot.get("qty")),
            position_market_value=_optional_float(position_snapshot.get("market_value")),
            position_cost_basis=_optional_float(position_snapshot.get("cost_basis")),
            position_unrealized_pl=_optional_float(position_snapshot.get("unrealized_pl")),
            position_snapshot=position_snapshot,
            account_cash=_optional_float(account_snapshot.get("cash")),
            account_equity=_optional_float(account_snapshot.get("equity")),
            account_buying_power=_optional_float(account_snapshot.get("buying_power")),
            account_snapshot=account_snapshot,
            fill_activities=fill_activity_evidence["activities"],
            external_lookup_attempted=True,
            raw_payload=response_body,
        )

    def _fetch_fill_activity_evidence(
        self,
        *,
        base_url: str,
        broker_order_id: str,
    ) -> dict[str, Any]:
        if not broker_order_id:
            return _alpaca_fill_activity_evidence(None)
        lookup_id = urllib.parse.quote(broker_order_id, safe="")
        try:
            status_code, response_body, _response_headers = self.get_transport(
                f"{base_url}/v2/account/activities/FILL?order_id={lookup_id}",
                _alpaca_paper_auth_headers(),
                self.timeout_seconds,
            )
        except (urllib.error.URLError, OSError):
            return _alpaca_fill_activity_evidence(None)
        if not 200 <= status_code < 300:
            return _alpaca_fill_activity_evidence(None)
        return _alpaca_fill_activity_evidence(response_body)

    def _fetch_position_snapshot(
        self,
        *,
        base_url: str,
        symbol: str,
    ) -> dict[str, Any]:
        if not symbol:
            return {}
        lookup_symbol = urllib.parse.quote(symbol, safe="")
        try:
            status_code, response_body, _response_headers = self.get_transport(
                f"{base_url}/v2/positions/{lookup_symbol}",
                _alpaca_paper_auth_headers(),
                self.timeout_seconds,
            )
        except (urllib.error.URLError, OSError):
            return {}
        if status_code == 404 or not 200 <= status_code < 300:
            return {}
        return _alpaca_position_snapshot(response_body)

    def _fetch_account_snapshot(
        self,
        *,
        base_url: str,
    ) -> dict[str, Any]:
        try:
            status_code, response_body, _response_headers = self.get_transport(
                f"{base_url}/v2/account",
                _alpaca_paper_auth_headers(),
                self.timeout_seconds,
            )
        except (urllib.error.URLError, OSError):
            return {}
        if not 200 <= status_code < 300:
            return {}
        return _alpaca_account_snapshot(response_body)


def us_equity_paper_broker() -> BrokerAdapter:
    return MockUsEquityPaperBroker()


def alpaca_us_equity_paper_preview_broker() -> BrokerAdapter:
    return MockUsEquityPaperBroker(contract=ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT)


def alpaca_us_equity_paper_broker() -> BrokerAdapter:
    return AlpacaUsEquityPaperBroker()


def stock_paper_broker_for_adapter(adapter_id: StockPaperBrokerAdapterId) -> BrokerAdapter:
    if adapter_id == "alpaca_us_equity_paper":
        return alpaca_us_equity_paper_broker()
    if adapter_id == "alpaca_us_equity_paper_preview":
        return alpaca_us_equity_paper_preview_broker()
    return us_equity_paper_broker()
