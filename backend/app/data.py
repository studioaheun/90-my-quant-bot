import json
import math
import os
import threading
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .models import (
    Candle,
    MarketDataColumnarExport,
    MarketDataColumnarStatus,
    MarketDataProviderStatus,
    MarketTicker,
)
from .storage import (
    DEFAULT_CANDLE_CACHE_TTL_SECONDS,
    MarketDataStore,
)


class MarketDataError(RuntimeError):
    pass


_market_data_store: Optional[MarketDataStore] = None
_market_data_store_lock = threading.Lock()
_provider_runtime_status: Dict[str, Dict[str, Any]] = {}


def get_candles(symbol: str, timeframe: str, source: str, limit: int) -> List[Candle]:
    try:
        candles = _get_candles_for_source(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            limit=limit,
        )
    except MarketDataError as exc:
        _record_provider_error(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            error=str(exc),
        )
        raise

    _record_provider_success(
        source=source,
        symbol=symbol,
        timeframe=timeframe,
        rows=len(candles),
    )
    return candles


def _get_candles_for_source(
    symbol: str,
    timeframe: str,
    source: str,
    limit: int,
) -> List[Candle]:
    if source == "sample":
        return generate_sample_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    if source == "sample_us":
        return generate_sample_us_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    if source == "alpha_vantage":
        return get_alpha_vantage_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    if source == "upbit":
        return get_upbit_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    raise MarketDataError(f"Unsupported market data source: {source}")


def get_market_ticker(symbol: str, source: str) -> MarketTicker:
    try:
        ticker = _get_market_ticker_for_source(symbol=symbol, source=source)
    except MarketDataError as exc:
        _record_provider_error(
            source=source,
            symbol=symbol,
            timeframe="ticker",
            error=str(exc),
        )
        raise

    _record_provider_success(
        source=source,
        symbol=symbol,
        timeframe="ticker",
        rows=1,
    )
    return ticker


def _get_market_ticker_for_source(symbol: str, source: str) -> MarketTicker:
    if source == "sample":
        return sample_market_ticker(symbol=symbol)
    if source == "sample_us":
        return sample_us_market_ticker(symbol=symbol)
    if source == "alpha_vantage":
        return alpha_vantage_market_ticker(symbol=symbol)
    if source == "upbit":
        return fetch_upbit_ticker(symbol=symbol)
    raise MarketDataError(f"Unsupported market data source: {source}")


def get_market_data_provider_statuses() -> List[MarketDataProviderStatus]:
    status_checked_at = datetime.now(timezone.utc).isoformat()
    try:
        cache_ttl = _candle_cache_ttl_seconds()
        cache_note = ""
    except MarketDataError as exc:
        cache_ttl = None
        cache_note = f" Cache TTL configuration error: {exc}"

    alpha_configured = bool(os.environ.get("ALPHA_VANTAGE_API_KEY"))
    providers = [
        {
            "source": "sample",
            "label": "Sample crypto",
            "configured": True,
            "available": True,
            "credential_name": None,
            "base_url": None,
            "note": "Deterministic local crypto candles for offline development.",
        },
        {
            "source": "sample_us",
            "label": "Sample US stocks/ETFs",
            "configured": True,
            "available": True,
            "credential_name": None,
            "base_url": None,
            "note": "Deterministic local US stock/ETF candles for paper trading.",
        },
        {
            "source": "alpha_vantage",
            "label": "Alpha Vantage daily",
            "configured": alpha_configured,
            "available": alpha_configured,
            "credential_name": "ALPHA_VANTAGE_API_KEY",
            "base_url": _alpha_vantage_base_url(),
            "note": (
                "Compact daily OHLCV is available."
                if alpha_configured
                else "Set ALPHA_VANTAGE_API_KEY to enable real stock/ETF daily data."
            ),
        },
        {
            "source": "upbit",
            "label": "Upbit public",
            "configured": True,
            "available": True,
            "credential_name": None,
            "base_url": "https://api.upbit.com",
            "note": "Public KRW crypto candles and ticker; private execution is guarded separately.",
        },
    ]

    statuses: List[MarketDataProviderStatus] = []
    for provider in providers:
        source = str(provider["source"])
        runtime = _provider_runtime_status.get(source, {})
        statuses.append(
            MarketDataProviderStatus(
                source=source,
                label=str(provider["label"]),
                status_checked_at=status_checked_at,
                configured=bool(provider["configured"]),
                available=bool(provider["available"]),
                credential_name=provider["credential_name"],
                base_url=provider["base_url"],
                cache_ttl_seconds=cache_ttl,
                last_success_at=_optional_string(runtime.get("last_success_at")),
                last_error_at=_optional_string(runtime.get("last_error_at")),
                last_error=_optional_string(runtime.get("last_error")),
                last_symbol=_optional_string(runtime.get("last_symbol")),
                last_timeframe=_optional_string(runtime.get("last_timeframe")),
                last_rows=_optional_int(runtime.get("last_rows")),
                note=str(provider["note"]) + cache_note,
            )
        )

    return statuses


def get_market_data_columnar_status() -> MarketDataColumnarStatus:
    return _get_market_data_store().columnar_status()


def export_market_data_columnar_parquet(
    source: Optional[str] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> MarketDataColumnarExport:
    normalized_symbol = symbol.strip().upper() if symbol else None
    normalized_source = source.strip() if source else None
    normalized_timeframe = timeframe.strip() if timeframe else None
    return _get_market_data_store().export_columnar_parquet(
        source=normalized_source or None,
        symbol=normalized_symbol or None,
        timeframe=normalized_timeframe or None,
    )


def generate_sample_candles(symbol: str, timeframe: str, limit: int) -> List[Candle]:
    end_day = date(2026, 5, 18)
    base_price = _base_price_for_symbol(symbol)
    candles: List[Candle] = []

    for index in range(limit):
        day = end_day - timedelta(days=limit - index - 1)
        trend = 1 + index * 0.0022
        cycle = math.sin(index / 7.0) * 0.035 + math.sin(index / 19.0) * 0.055
        shock = -0.14 if 92 <= index <= 103 else 0.0
        recovery = max(0, index - 110) * 0.0014
        close = base_price * (trend + cycle + shock + recovery)
        previous_close = candles[-1].close if candles else close * 0.992
        open_price = previous_close * (1 + math.sin(index / 5.0) * 0.006)
        high = max(open_price, close) * (1 + 0.006 + abs(math.sin(index)) * 0.006)
        low = min(open_price, close) * (1 - 0.006 - abs(math.cos(index)) * 0.005)
        volume = 1000 + index * 4 + abs(math.sin(index / 3.0)) * 420

        candles.append(
            Candle(
                timestamp=_timestamp_for(day, timeframe),
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=round(volume, 6),
            )
        )

    return candles


def generate_sample_us_candles(symbol: str, timeframe: str, limit: int) -> List[Candle]:
    if timeframe != "day":
        raise MarketDataError("Sample US stock/ETF data currently supports day timeframe.")

    end_day = date(2026, 5, 18)
    base_price = _base_price_for_us_symbol(symbol)
    beta = _beta_for_us_symbol(symbol)
    business_days: List[date] = []
    candles: List[Candle] = []

    day = end_day
    while len(business_days) < limit:
        if day.weekday() >= 5:
            day -= timedelta(days=1)
            continue
        business_days.append(day)
        day -= timedelta(days=1)
    business_days.reverse()

    for business_day_index, day in enumerate(business_days):
        trend = 1 + business_day_index * (0.00085 + beta * 0.00015)
        cycle = math.sin(business_day_index / 9.0) * (0.018 + beta * 0.004)
        rotation = math.sin(business_day_index / 27.0) * 0.035
        drawdown = -0.09 * beta if 78 <= business_day_index <= 91 else 0.0
        rebound = max(0, business_day_index - 96) * 0.0007
        close = base_price * (trend + cycle + rotation + drawdown + rebound)
        previous_close = candles[-1].close if candles else close * 0.997
        open_price = previous_close * (1 + math.sin(business_day_index / 6.0) * 0.003)
        high = max(open_price, close) * (1 + 0.004 + abs(math.sin(business_day_index)) * 0.004)
        low = min(open_price, close) * (1 - 0.004 - abs(math.cos(business_day_index)) * 0.003)
        volume = _base_volume_for_us_symbol(symbol) * (
            0.82 + abs(math.sin(business_day_index / 5.0)) * 0.34
        )

        candles.append(
            Candle(
                timestamp=_timestamp_for(day, timeframe),
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=round(volume, 2),
            )
        )

    return candles


def get_upbit_candles(symbol: str, timeframe: str, limit: int) -> List[Candle]:
    expected_count = min(limit, 200)
    cache_ttl = _candle_cache_ttl_seconds()
    store = _get_market_data_store()
    cached = store.get_candles(
        source="upbit",
        symbol=symbol,
        timeframe=timeframe,
        limit=expected_count,
        max_age_seconds=cache_ttl,
    )
    if len(cached) >= expected_count:
        return cached

    candles = fetch_upbit_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    store.save_candles(
        source="upbit",
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
    )
    return candles


def get_alpha_vantage_candles(symbol: str, timeframe: str, limit: int) -> List[Candle]:
    if timeframe != "day":
        raise MarketDataError("Alpha Vantage source currently supports day timeframe.")

    expected_count = min(limit, 100)
    cache_ttl = _candle_cache_ttl_seconds()
    store = _get_market_data_store()
    cached = store.get_candles(
        source="alpha_vantage",
        symbol=symbol.upper(),
        timeframe=timeframe,
        limit=expected_count,
        max_age_seconds=cache_ttl,
    )
    if len(cached) >= expected_count:
        return cached

    candles = fetch_alpha_vantage_daily(symbol=symbol)
    store.save_candles(
        source="alpha_vantage",
        symbol=symbol.upper(),
        timeframe=timeframe,
        candles=candles,
    )
    return candles[-expected_count:]


def set_market_data_store_for_tests(store: Optional[MarketDataStore]) -> None:
    global _market_data_store
    with _market_data_store_lock:
        _market_data_store = store


def reset_market_data_provider_status_for_tests() -> None:
    _provider_runtime_status.clear()


def _record_provider_success(
    source: str,
    symbol: str,
    timeframe: str,
    rows: int,
) -> None:
    status = _provider_runtime_status.setdefault(source, {})
    status["last_success_at"] = datetime.now(timezone.utc).isoformat()
    status["last_symbol"] = symbol
    status["last_timeframe"] = timeframe
    status["last_rows"] = rows
    status.pop("last_error", None)


def _record_provider_error(
    source: str,
    symbol: str,
    timeframe: str,
    error: str,
) -> None:
    status = _provider_runtime_status.setdefault(source, {})
    status["last_error_at"] = datetime.now(timezone.utc).isoformat()
    status["last_error"] = error
    status["last_symbol"] = symbol
    status["last_timeframe"] = timeframe


def sample_market_ticker(symbol: str) -> MarketTicker:
    candles = generate_sample_candles(symbol=symbol, timeframe="day", limit=180)
    previous = candles[-2]
    latest = candles[-1]
    change_pct = (latest.close / previous.close - 1) * 100 if previous.close else 0.0
    return MarketTicker(
        symbol=symbol,
        source="sample",
        timestamp=datetime.now(timezone.utc).isoformat(),
        price=latest.close,
        change_pct=round(change_pct, 4),
        volume_24h=latest.volume,
        quote_volume_24h=round(latest.volume * latest.close, 2),
    )


def sample_us_market_ticker(symbol: str) -> MarketTicker:
    candles = generate_sample_us_candles(symbol=symbol, timeframe="day", limit=180)
    previous = candles[-2]
    latest = candles[-1]
    change_pct = (latest.close / previous.close - 1) * 100 if previous.close else 0.0
    return MarketTicker(
        symbol=symbol,
        source="sample_us",
        timestamp=datetime.now(timezone.utc).isoformat(),
        price=latest.close,
        change_pct=round(change_pct, 4),
        volume_24h=latest.volume,
        quote_volume_24h=round(latest.volume * latest.close, 2),
    )


def alpha_vantage_market_ticker(symbol: str) -> MarketTicker:
    candles = get_alpha_vantage_candles(symbol=symbol, timeframe="day", limit=2)
    if len(candles) < 2:
        raise MarketDataError(f"Alpha Vantage returned too few candles for {symbol}.")
    previous = candles[-2]
    latest = candles[-1]
    change_pct = (latest.close / previous.close - 1) * 100 if previous.close else 0.0
    return MarketTicker(
        symbol=symbol.upper(),
        source="alpha_vantage",
        timestamp=latest.timestamp,
        price=latest.close,
        change_pct=round(change_pct, 4),
        volume_24h=latest.volume,
        quote_volume_24h=round(latest.volume * latest.close, 2),
    )


def fetch_alpha_vantage_daily(symbol: str) -> List[Candle]:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise MarketDataError(
            "ALPHA_VANTAGE_API_KEY is required for the alpha_vantage source. "
            "Use sample_us for offline stock/ETF paper trading."
        )

    query = urllib.parse.urlencode(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol.upper(),
            "outputsize": "compact",
            "apikey": api_key,
        }
    )
    url = f"{_alpha_vantage_base_url().rstrip('/')}/query?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise MarketDataError(f"Could not fetch Alpha Vantage daily candles: {exc}") from exc

    if not isinstance(payload, dict):
        raise MarketDataError("Alpha Vantage response was not an object.")
    for key in ("Error Message", "Note", "Information"):
        if key in payload:
            raise MarketDataError(f"Alpha Vantage returned {key}: {payload[key]}")

    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise MarketDataError(f"Alpha Vantage returned no daily data for {symbol}.")

    candles: List[Candle] = []
    for day_text, item in sorted(series.items()):
        if not isinstance(item, dict):
            continue
        day = datetime.strptime(day_text, "%Y-%m-%d").date()
        candles.append(
            Candle(
                timestamp=_timestamp_for(day, "day"),
                open=float(item["1. open"]),
                high=float(item["2. high"]),
                low=float(item["3. low"]),
                close=float(item["4. close"]),
                volume=float(item["5. volume"]),
            )
        )

    if not candles:
        raise MarketDataError(f"Alpha Vantage returned no parseable daily data for {symbol}.")
    return candles


def fetch_upbit_candles(symbol: str, timeframe: str, limit: int) -> List[Candle]:
    if not symbol.startswith("KRW-"):
        raise MarketDataError("Upbit source expects symbols like KRW-BTC or KRW-ETH")

    count = min(limit, 200)
    path = "days"
    if timeframe.startswith("minute"):
        unit = timeframe.replace("minute", "") or "60"
        path = f"minutes/{int(unit)}"
    elif timeframe != "day":
        raise MarketDataError("Upbit source currently supports day and minuteN timeframes")

    query = urllib.parse.urlencode({"market": symbol, "count": count})
    url = f"https://api.upbit.com/v1/candles/{path}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise MarketDataError(f"Could not fetch Upbit candles: {exc}") from exc

    candles = [
        Candle(
            timestamp=item["candle_date_time_utc"] + "Z",
            open=float(item["opening_price"]),
            high=float(item["high_price"]),
            low=float(item["low_price"]),
            close=float(item["trade_price"]),
            volume=float(item["candle_acc_trade_volume"]),
        )
        for item in payload
    ]
    candles.reverse()
    return candles


def fetch_upbit_ticker(symbol: str) -> MarketTicker:
    if not symbol.startswith("KRW-"):
        raise MarketDataError("Upbit source expects symbols like KRW-BTC or KRW-ETH")

    query = urllib.parse.urlencode({"markets": symbol})
    url = f"https://api.upbit.com/v1/ticker?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise MarketDataError(f"Could not fetch Upbit ticker: {exc}") from exc

    if not payload:
        raise MarketDataError(f"Upbit returned no ticker for {symbol}")

    item = payload[0]
    timestamp = datetime.fromtimestamp(
        float(item["timestamp"]) / 1000,
        tz=timezone.utc,
    ).isoformat()
    return MarketTicker(
        symbol=symbol,
        source="upbit",
        timestamp=timestamp,
        price=float(item["trade_price"]),
        change_pct=round(float(item.get("signed_change_rate", 0.0)) * 100, 4),
        volume_24h=float(item.get("acc_trade_volume_24h", 0.0)),
        quote_volume_24h=float(item.get("acc_trade_price_24h", 0.0)),
    )


def _get_market_data_store() -> MarketDataStore:
    global _market_data_store
    if _market_data_store is None:
        with _market_data_store_lock:
            if _market_data_store is None:
                _market_data_store = MarketDataStore()
    return _market_data_store


def _candle_cache_ttl_seconds() -> Optional[int]:
    configured = os.environ.get("QUANT_LAB_CANDLE_CACHE_TTL_SECONDS")
    if configured is None:
        return DEFAULT_CANDLE_CACHE_TTL_SECONDS
    normalized = configured.lower()
    if normalized == "none":
        return None
    if normalized in {"off", "disabled"}:
        return 0
    try:
        return max(0, int(configured))
    except ValueError as exc:
        raise MarketDataError(
            "QUANT_LAB_CANDLE_CACHE_TTL_SECONDS must be an integer, none, off, or disabled."
        ) from exc


def _alpha_vantage_base_url() -> str:
    return os.environ.get("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co")


def _optional_string(value: object) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


def _optional_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def _base_price_for_symbol(symbol: str) -> float:
    if "BTC" in symbol:
        return 92_000_000
    if "ETH" in symbol:
        return 4_300_000
    if "SOL" in symbol:
        return 210_000
    return 100_000


def _base_price_for_us_symbol(symbol: str) -> float:
    normalized = symbol.upper()
    if normalized == "SPY":
        return 520.0
    if normalized == "QQQ":
        return 445.0
    if normalized == "AAPL":
        return 190.0
    if normalized == "MSFT":
        return 430.0
    if normalized == "NVDA":
        return 920.0
    if normalized == "TSLA":
        return 185.0
    return 100.0


def _beta_for_us_symbol(symbol: str) -> float:
    normalized = symbol.upper()
    if normalized in {"NVDA", "TSLA"}:
        return 1.7
    if normalized in {"QQQ", "AAPL", "MSFT"}:
        return 1.25
    return 0.9


def _base_volume_for_us_symbol(symbol: str) -> float:
    normalized = symbol.upper()
    if normalized in {"SPY", "QQQ"}:
        return 58_000_000
    if normalized in {"AAPL", "NVDA", "TSLA"}:
        return 72_000_000
    if normalized == "MSFT":
        return 25_000_000
    return 5_000_000


def _timestamp_for(day: date, timeframe: str) -> str:
    if timeframe == "day":
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc).isoformat()
    return datetime(day.year, day.month, day.day, 9, tzinfo=timezone.utc).isoformat()
