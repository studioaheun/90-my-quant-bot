import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import data
from app.models import Candle
from app.storage import MarketDataStore


class MarketDataCacheTests(unittest.TestCase):
    def setUp(self):
        self._alpha_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        self._columnar_enabled = os.environ.get("QUANT_LAB_COLUMNAR_CACHE_ENABLED")
        self._duckdb_path = os.environ.get("QUANT_LAB_DUCKDB_PATH")
        self._parquet_path = os.environ.get("QUANT_LAB_CANDLE_PARQUET_PATH")
        self._cache_ttl = os.environ.get("QUANT_LAB_CANDLE_CACHE_TTL_SECONDS")
        os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
        os.environ["QUANT_LAB_COLUMNAR_CACHE_ENABLED"] = "true"
        os.environ["QUANT_LAB_CANDLE_CACHE_TTL_SECONDS"] = "none"
        os.environ.pop("QUANT_LAB_DUCKDB_PATH", None)
        os.environ.pop("QUANT_LAB_CANDLE_PARQUET_PATH", None)
        self.db_path = Path(tempfile.gettempdir()) / "quant_lab_data_cache_tests.sqlite3"
        self.duckdb_path = self.db_path.with_suffix(".duckdb")
        self.parquet_path = (
            self.duckdb_path.parent
            / f"{self.duckdb_path.stem}_market_candles.parquet"
        )
        for path in (self.db_path, self.duckdb_path, self.parquet_path):
            if path.exists():
                path.unlink()
        self.store = MarketDataStore(self.db_path)
        data.set_market_data_store_for_tests(self.store)
        data.reset_market_data_provider_status_for_tests()

    def tearDown(self):
        data.set_market_data_store_for_tests(None)
        data.reset_market_data_provider_status_for_tests()
        if self._alpha_key is None:
            os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
        else:
            os.environ["ALPHA_VANTAGE_API_KEY"] = self._alpha_key
        self._restore_env("QUANT_LAB_COLUMNAR_CACHE_ENABLED", self._columnar_enabled)
        self._restore_env("QUANT_LAB_DUCKDB_PATH", self._duckdb_path)
        self._restore_env("QUANT_LAB_CANDLE_PARQUET_PATH", self._parquet_path)
        self._restore_env("QUANT_LAB_CANDLE_CACHE_TTL_SECONDS", self._cache_ttl)
        for path in (self.db_path, self.duckdb_path, self.parquet_path):
            if path.exists():
                path.unlink()

    def test_market_data_store_round_trips_latest_candles(self):
        candles = _candles(4)
        self.store.save_candles(
            source="upbit",
            symbol="KRW-BTC",
            timeframe="day",
            candles=candles,
        )

        cached = self.store.get_candles(
            source="upbit",
            symbol="KRW-BTC",
            timeframe="day",
            limit=2,
        )

        self.assertEqual(
            [candle.timestamp for candle in cached],
            ["2026-05-03T00:00:00Z", "2026-05-04T00:00:00Z"],
        )
        self.assertEqual(cached[-1].close, 103)

    def test_market_data_store_mirrors_to_duckdb_and_exports_parquet(self):
        self.store.save_candles(
            source="alpha_vantage",
            symbol="SPY",
            timeframe="day",
            candles=_candles(4),
        )

        status = self.store.columnar_status()
        self.assertTrue(status.enabled)
        self.assertEqual(status.rows, 4)
        self.assertEqual(status.sources, ["alpha_vantage"])
        self.assertEqual(status.symbols, ["SPY"])
        self.assertEqual(status.timeframes, ["day"])
        self.assertTrue(self.duckdb_path.exists())

        export = self.store.export_columnar_parquet(
            source="alpha_vantage",
            symbol="SPY",
            timeframe="day",
        )

        self.assertEqual(export.rows, 4)
        self.assertEqual(export.source, "alpha_vantage")
        self.assertEqual(export.symbol, "SPY")
        self.assertTrue(Path(export.parquet_path).exists())

        import duckdb

        conn = duckdb.connect()
        try:
            parquet_rows = conn.execute(
                "SELECT COUNT(*) FROM read_parquet(?)",
                [export.parquet_path],
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(parquet_rows, 4)

    def test_upbit_candles_use_cache_after_first_fetch(self):
        calls = []
        original_fetch = data.fetch_upbit_candles

        def fake_fetch(symbol: str, timeframe: str, limit: int):
            calls.append((symbol, timeframe, limit))
            return _candles(limit)

        data.fetch_upbit_candles = fake_fetch
        try:
            first = data.get_candles(
                symbol="KRW-BTC",
                timeframe="day",
                source="upbit",
                limit=3,
            )
            second = data.get_candles(
                symbol="KRW-BTC",
                timeframe="day",
                source="upbit",
                limit=3,
            )
        finally:
            data.fetch_upbit_candles = original_fetch

        self.assertEqual(len(calls), 1)
        self.assertEqual([candle.close for candle in first], [100, 101, 102])
        self.assertEqual([candle.close for candle in second], [100, 101, 102])

    def test_alpha_vantage_candles_use_cache_after_first_fetch(self):
        calls = []
        original_fetch = data.fetch_alpha_vantage_daily

        def fake_fetch(symbol: str):
            calls.append(symbol)
            return _candles(100)

        data.fetch_alpha_vantage_daily = fake_fetch
        try:
            first = data.get_candles(
                symbol="SPY",
                timeframe="day",
                source="alpha_vantage",
                limit=50,
            )
            second = data.get_candles(
                symbol="SPY",
                timeframe="day",
                source="alpha_vantage",
                limit=50,
            )
        finally:
            data.fetch_alpha_vantage_daily = original_fetch

        self.assertEqual(calls, ["SPY"])
        self.assertEqual(len(first), 50)
        self.assertEqual([candle.close for candle in first[-3:]], [197, 198, 199])
        self.assertEqual([candle.close for candle in second[-3:]], [197, 198, 199])

    def test_alpha_vantage_requires_api_key(self):
        with self.assertRaises(data.MarketDataError) as context:
            data.fetch_alpha_vantage_daily("SPY")

        self.assertIn("ALPHA_VANTAGE_API_KEY", str(context.exception))

    def test_provider_status_tracks_success_and_error(self):
        data.get_market_ticker(symbol="SPY", source="sample_us")

        with self.assertRaises(data.MarketDataError):
            data.get_market_ticker(symbol="SPY", source="alpha_vantage")

        statuses = {
            status.source: status
            for status in data.get_market_data_provider_statuses()
        }

        self.assertEqual(statuses["sample_us"].last_symbol, "SPY")
        self.assertEqual(statuses["sample_us"].last_rows, 1)
        self.assertIsNotNone(statuses["sample_us"].last_success_at)
        self.assertEqual(statuses["alpha_vantage"].last_symbol, "SPY")
        self.assertIsNotNone(statuses["alpha_vantage"].last_error_at)
        self.assertIn("ALPHA_VANTAGE_API_KEY", statuses["alpha_vantage"].last_error)

    def _restore_env(self, key, value):
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _candles(count: int):
    start = date(2026, 5, 1)
    return [
        Candle(
            timestamp=f"{(start + timedelta(days=index)).isoformat()}T00:00:00Z",
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=10 + index,
        )
        for index in range(count)
    ]


if __name__ == "__main__":
    unittest.main()
