import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import execution
from app.models import OrderApprovalRequest, OrderAuditRecord
from app.storage import OrderAuditStore


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self._env = {
            key: os.environ.get(key)
            for key in [
                "UPBIT_ACCESS_KEY",
                "UPBIT_SECRET_KEY",
                "QUANT_LAB_LIVE_TRADING_ENABLED",
                "QUANT_LAB_LIVE_TRADING_ACK",
                "QUANT_LAB_MIN_ORDER_NOTIONAL_KRW",
                "QUANT_LAB_APPROVAL_FEE_BPS",
                "QUANT_LAB_MAX_APPROVAL_EXPOSURE_PCT",
            ]
        }
        for key in self._env:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_query_string_preserves_array_brackets_for_upbit_hash(self):
        query = execution.build_query_string(
            [
                ("market", "KRW-BTC"),
                ("states[]", "wait"),
                ("states[]", "watch"),
                ("limit", 50),
            ]
        )

        self.assertEqual(
            query,
            "market=KRW-BTC&states[]=wait&states[]=watch&limit=50",
        )

    def test_private_snapshot_is_disabled_without_credentials(self):
        snapshot = execution.get_private_snapshot()

        self.assertFalse(snapshot.credential_ready)
        self.assertEqual(snapshot.balances, [])
        self.assertEqual(snapshot.open_orders, [])

    def test_execution_status_requires_ack_even_with_credentials(self):
        os.environ["QUANT_LAB_LIVE_TRADING_ENABLED"] = "true"
        os.environ["UPBIT_ACCESS_KEY"] = "access"
        os.environ["UPBIT_SECRET_KEY"] = "secret"

        status = execution.get_execution_status()

        self.assertFalse(status.adapter_ready)
        self.assertIn("REAL_ORDERS_OK", status.reason)

    def test_execution_settings_expose_guard_thresholds_without_secrets(self):
        os.environ["UPBIT_ACCESS_KEY"] = "access"
        os.environ["UPBIT_SECRET_KEY"] = "secret"
        os.environ["QUANT_LAB_MIN_ORDER_NOTIONAL_KRW"] = "7000"
        os.environ["QUANT_LAB_APPROVAL_FEE_BPS"] = "7.5"
        os.environ["QUANT_LAB_MAX_APPROVAL_EXPOSURE_PCT"] = "45"

        settings = execution.get_execution_settings()

        self.assertTrue(settings.credential_configured)
        self.assertIsNotNone(settings.checked_at)
        self.assertTrue(settings.private_reads_enabled)
        self.assertFalse(settings.adapter_ready)
        self.assertFalse(settings.live_ack_configured)
        self.assertEqual(settings.live_ack_required_value, execution.LIVE_TRADING_ACK_VALUE)
        self.assertEqual(settings.order_info_source, "upbit_orders_chance")
        self.assertEqual(settings.min_order_notional_krw, 7000)
        self.assertEqual(settings.approval_fee_bps, 7.5)
        self.assertEqual(settings.approval_fee_rate, 0.00075)
        self.assertEqual(settings.max_approval_exposure_pct, 45)

    def test_precheck_uses_upbit_order_chance_when_credentials_exist(self):
        os.environ["UPBIT_ACCESS_KEY"] = "access"
        os.environ["UPBIT_SECRET_KEY"] = "secret"
        record = OrderAuditRecord(
            id="dry-run-1",
            created_at="2026-05-18T00:00:00+00:00",
            exchange="upbit",
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            status="dry_run",
            reason="test",
            request_payload={
                "market": "KRW-BTC",
                "side": "bid",
                "ord_type": "limit",
                "volume": "1",
                "price": "10000",
                "identifier": "dry-run-1",
            },
        )
        chance = {
            "bid_fee": "0.0005",
            "ask_fee": "0.0005",
            "market": {
                "id": "KRW-BTC",
                "bid": {"currency": "KRW", "price_unit": "1", "min_total": 5000},
                "ask": {"currency": "BTC", "price_unit": "1", "min_total": 5000},
                "max_total": "1000000",
            },
            "bid_account": {"currency": "KRW", "balance": "20000", "locked": "0"},
            "ask_account": {"currency": "BTC", "balance": "0.1", "locked": "0"},
        }

        with patch.object(execution, "fetch_upbit_order_chance", return_value=chance):
            precheck = execution.build_order_precheck(record)

        self.assertEqual(precheck.status, "pass")
        self.assertIsNotNone(precheck.checked_at)
        self.assertEqual(precheck.order_info_source, "upbit_orders_chance")
        self.assertIsNotNone(precheck.order_info_checked_at)
        self.assertGreaterEqual(precheck.order_info_age_seconds, 0)
        self.assertTrue(precheck.credential_ready)
        self.assertEqual(precheck.min_order_notional, 5000)
        self.assertEqual(precheck.max_order_notional, 1000000)
        self.assertEqual(precheck.price_unit, 1)
        self.assertEqual(precheck.fee_rate, 0.0005)
        self.assertEqual(precheck.available_quote_balance, 20000)
        self.assertEqual(precheck.available_base_balance, 0.1)
        self.assertGreater(precheck.post_order_exposure_pct, 52)
        self.assertTrue(all(check.status == "pass" for check in precheck.checks))

    def test_approval_does_not_place_order_when_precheck_fails(self):
        os.environ["UPBIT_ACCESS_KEY"] = "access"
        os.environ["UPBIT_SECRET_KEY"] = "secret"
        os.environ["QUANT_LAB_LIVE_TRADING_ENABLED"] = "true"
        os.environ["QUANT_LAB_LIVE_TRADING_ACK"] = execution.LIVE_TRADING_ACK_VALUE
        store = OrderAuditStore(
            Path(tempfile.gettempdir()) / f"quant_lab_execution_tests_{os.getpid()}.sqlite3"
        )
        store.clear()
        source = OrderAuditRecord(
            id="dry-run-low-notional",
            created_at="2026-05-18T00:00:00+00:00",
            exchange="upbit",
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            status="dry_run",
            reason="test",
            request_payload={
                "market": "KRW-BTC",
                "side": "bid",
                "ord_type": "limit",
                "volume": "0.001",
                "price": "1000",
                "identifier": "dry-run-low-notional",
            },
        )
        store.save_record(source)
        chance = {
            "bid_fee": "0.0005",
            "ask_fee": "0.0005",
            "market": {
                "id": "KRW-BTC",
                "bid": {"currency": "KRW", "price_unit": "1", "min_total": 5000},
                "ask": {"currency": "BTC", "price_unit": "1", "min_total": 5000},
                "max_total": "1000000",
            },
            "bid_account": {"currency": "KRW", "balance": "100000", "locked": "0"},
            "ask_account": {"currency": "BTC", "balance": "1", "locked": "0"},
        }

        with patch.object(execution, "fetch_upbit_order_chance", return_value=chance):
            with patch.object(execution, "place_upbit_order") as place_order:
                result = execution.approve_dry_run_order_intent(
                    record_id=source.id,
                    request=OrderApprovalRequest(live_confirmation=True),
                    audit_store=store,
                )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason, "Pre-approval checks failed before live submission.")
        self.assertEqual(result.response_payload["precheck"]["status"], "fail")
        place_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
