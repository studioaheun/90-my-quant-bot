import unittest
from unittest.mock import patch

from app.brokers import (
    ALPACA_PAPER_TRADING_ACK_VALUE,
    ALPACA_US_EQUITY_PAPER_CONTRACT,
    ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT,
    AlpacaUsEquityPaperBroker,
    BrokerOrderIntent,
    BrokerOrderStatusResult,
    US_EQUITY_PAPER_BROKER_CONTRACT,
    alpaca_us_equity_paper_preview_broker,
    us_equity_paper_broker,
)
from app.execution import evaluate_broker_order_intent, reconcile_broker_order_evaluation
from app.models import BrokerOrderIntentEvaluation, BrokerOrderIntentRequest


class BrokerAdapterContractTests(unittest.TestCase):
    def _alpaca_paper_evaluation(self) -> BrokerOrderIntentEvaluation:
        return BrokerOrderIntentEvaluation(
            id="eval-alpaca-paper-1",
            checked_at="2026-05-23T00:00:00+00:00",
            adapter_id="alpaca_us_equity_paper",
            broker_contract=ALPACA_US_EQUITY_PAPER_CONTRACT,
            request=BrokerOrderIntentRequest(
                adapter_id="alpaca_us_equity_paper",
                symbol="SPY",
                side="buy",
                quantity=1,
                order_type="market",
                client_order_id="client-alpaca-paper-1",
            ),
            validation_status="accepted",
            submission_status="paper_recorded",
            reason="Alpaca paper order accepted.",
            normalized_symbol="SPY",
            broker_order_id="alpaca-order-1",
            external_submission_attempted=True,
            live_submission_supported=False,
        )

    def test_us_equity_paper_contract_is_not_live_order_capable(self):
        contract = US_EQUITY_PAPER_BROKER_CONTRACT

        self.assertEqual(contract.id, "mock_us_equity_paper")
        self.assertEqual(contract.provider_type, "paper_broker")
        self.assertEqual(contract.submission_mode, "paper_record_only")
        self.assertFalse(contract.live_order_supported)
        self.assertFalse(contract.required_credentials)
        self.assertIn("market", contract.supported_order_types)
        self.assertIn("limit", contract.supported_order_types)

    def test_alpaca_paper_preview_contract_lists_future_credentials_without_live_submission(self):
        contract = ALPACA_US_EQUITY_PAPER_PREVIEW_CONTRACT

        self.assertEqual(contract.id, "alpaca_us_equity_paper_preview")
        self.assertEqual(contract.provider_type, "paper_broker")
        self.assertEqual(contract.submission_mode, "paper_record_only")
        self.assertFalse(contract.live_order_supported)
        self.assertIn("ALPACA_API_KEY_ID", contract.required_credentials)
        self.assertIn("ALPACA_API_SECRET_KEY", contract.required_credentials)

    def test_alpaca_paper_contract_requires_external_paper_gates(self):
        contract = ALPACA_US_EQUITY_PAPER_CONTRACT

        self.assertEqual(contract.id, "alpaca_us_equity_paper")
        self.assertEqual(contract.provider_type, "paper_broker")
        self.assertEqual(contract.submission_mode, "external_paper")
        self.assertFalse(contract.live_order_supported)
        self.assertIn("ALPACA_PAPER_TRADING_ENABLED", contract.required_credentials)
        self.assertIn("ALPACA_PAPER_TRADING_ACK", contract.required_credentials)

    def test_mock_us_equity_paper_broker_records_paper_order_only(self):
        broker = us_equity_paper_broker()
        intent = BrokerOrderIntent(
            symbol="spy",
            side="buy",
            quantity=3,
            order_type="limit",
            limit_price=512.25,
            client_order_id="paper-test-1",
        )

        validation = broker.validate_order(intent)
        self.assertEqual(validation.status, "accepted")
        self.assertEqual(validation.normalized_symbol, "SPY")
        self.assertAlmostEqual(validation.estimated_notional or 0, 1536.75)

        result = broker.submit_order(intent)
        self.assertEqual(result.status, "paper_recorded")
        self.assertEqual(result.broker_order_id, "paper-test-1")
        self.assertEqual(result.normalized_symbol, "SPY")

    def test_alpaca_paper_preview_records_without_external_submission(self):
        broker = alpaca_us_equity_paper_preview_broker()
        intent = BrokerOrderIntent(
            symbol="qqq",
            side="buy",
            quantity=1,
            order_type="limit",
            limit_price=440,
            client_order_id="alpaca-preview-1",
        )

        validation = broker.validate_order(intent)
        self.assertEqual(validation.status, "accepted")
        self.assertEqual(validation.normalized_symbol, "QQQ")

        result = broker.submit_order(intent)
        self.assertEqual(result.status, "paper_recorded")
        self.assertEqual(result.broker_order_id, "alpaca-preview-1")
        self.assertIn("no external broker", result.reason)

    def test_alpaca_paper_broker_blocks_without_per_request_confirmation(self):
        broker = AlpacaUsEquityPaperBroker(transport=lambda *args: self.fail("should not call Alpaca"))

        result = broker.submit_order(
            BrokerOrderIntent(
                symbol="SPY",
                side="buy",
                quantity=1,
                order_type="market",
                client_order_id="alpaca-paper-1",
            )
        )

        self.assertEqual(result.status, "blocked")
        self.assertIn("paper_submit_confirmation", result.reason)
        self.assertFalse(result.external_submission_attempted)

    def test_alpaca_paper_broker_submits_to_paper_endpoint_when_all_gates_pass(self):
        calls = []

        def fake_transport(url, headers, payload, timeout_seconds):
            calls.append((url, headers, payload, timeout_seconds))
            return (
                201,
                {"id": "alpaca-order-123", "client_order_id": payload["client_order_id"]},
                {"X-Request-ID": "req-abc"},
            )

        broker = AlpacaUsEquityPaperBroker(transport=fake_transport)
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "paper-key",
                "ALPACA_API_SECRET_KEY": "paper-secret",
                "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                "ALPACA_PAPER_TRADING_ENABLED": "true",
                "ALPACA_PAPER_TRADING_ACK": ALPACA_PAPER_TRADING_ACK_VALUE,
            },
            clear=False,
        ):
            result = broker.submit_order(
                BrokerOrderIntent(
                    symbol="qqq",
                    side="buy",
                    quantity=1.5,
                    order_type="limit",
                    limit_price=440.25,
                    time_in_force="day",
                    client_order_id="alpaca-paper-2",
                    paper_submit_confirmation=True,
                )
            )

        self.assertEqual(result.status, "paper_recorded")
        self.assertEqual(result.broker_order_id, "alpaca-order-123")
        self.assertTrue(result.external_submission_attempted)
        self.assertEqual(len(calls), 1)
        url, headers, payload, _timeout = calls[0]
        self.assertEqual(url, "https://paper-api.alpaca.markets/v2/orders")
        self.assertEqual(headers["APCA-API-KEY-ID"], "paper-key")
        self.assertEqual(payload["symbol"], "QQQ")
        self.assertEqual(payload["qty"], "1.5")
        self.assertEqual(payload["type"], "limit")
        self.assertEqual(payload["limit_price"], "440.25")
        self.assertEqual(payload["time_in_force"], "day")

    def test_alpaca_paper_broker_reconciles_accepted_order_status(self):
        calls = []

        def fake_get_transport(url, headers, timeout_seconds):
            calls.append((url, headers, timeout_seconds))
            return (
                200,
                {
                    "id": "alpaca-order-123",
                    "client_order_id": "alpaca-paper-2",
                    "status": "accepted",
                    "symbol": "QQQ",
                    "side": "buy",
                    "qty": "1.5",
                    "filled_qty": "0",
                    "submitted_at": "2026-05-23T00:00:00Z",
                },
                {},
            )

        broker = AlpacaUsEquityPaperBroker(get_transport=fake_get_transport)
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "paper-key",
                "ALPACA_API_SECRET_KEY": "paper-secret",
                "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                "ALPACA_PAPER_TRADING_ENABLED": "true",
                "ALPACA_PAPER_TRADING_ACK": ALPACA_PAPER_TRADING_ACK_VALUE,
            },
            clear=False,
        ):
            result = broker.fetch_order_status(
                broker_order_id="alpaca-order-123",
                client_order_id="alpaca-paper-2",
            )

        self.assertEqual(result.status, "found")
        self.assertEqual(result.order_status, "accepted")
        self.assertEqual(result.symbol, "QQQ")
        self.assertEqual(result.quantity, 1.5)
        self.assertTrue(result.external_lookup_attempted)
        self.assertEqual(calls[0][0], "https://paper-api.alpaca.markets/v2/orders/alpaca-order-123")

    def test_alpaca_paper_broker_reconciles_fill_and_position_evidence(self):
        calls = []

        def fake_get_transport(url, _headers, _timeout_seconds):
            calls.append(url)
            if "/v2/account/activities/FILL" in url:
                return (
                    200,
                    [
                        {
                            "id": "fill-1",
                            "order_id": "alpaca-order-partial",
                            "qty": "1.5",
                            "price": "101.25",
                            "commission": "0.01",
                        },
                        {
                            "id": "fill-2",
                            "order_id": "alpaca-order-partial",
                            "qty": "2.5",
                            "price": "101.5",
                            "commission": "0.02",
                        },
                    ],
                    {},
                )
            if "/v2/positions/" in url:
                return (
                    200,
                    {
                        "symbol": "SPY",
                        "qty": "4",
                        "market_value": "406.2",
                        "cost_basis": "405.625",
                        "unrealized_pl": "0.575",
                        "avg_entry_price": "101.40625",
                    },
                    {},
                )
            if "/v2/account" in url:
                return (
                    200,
                    {
                        "cash": "9994.37",
                        "equity": "10400.57",
                        "buying_power": "19988.74",
                        "status": "ACTIVE",
                    },
                    {},
                )
            return (
                200,
                {
                    "id": "alpaca-order-partial",
                    "client_order_id": "alpaca-paper-partial",
                    "status": "partially_filled",
                    "symbol": "SPY",
                    "side": "buy",
                    "qty": "10",
                    "filled_qty": "4",
                    "filled_avg_price": "101.4",
                },
                {},
            )

        broker = AlpacaUsEquityPaperBroker(get_transport=fake_get_transport)
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "paper-key",
                "ALPACA_API_SECRET_KEY": "paper-secret",
                "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                "ALPACA_PAPER_TRADING_ENABLED": "true",
                "ALPACA_PAPER_TRADING_ACK": ALPACA_PAPER_TRADING_ACK_VALUE,
            },
            clear=False,
        ):
            result = broker.fetch_order_status(
                broker_order_id="alpaca-order-partial",
                client_order_id="alpaca-paper-partial",
            )

        self.assertEqual(result.status, "found")
        self.assertTrue(result.partial_fill)
        self.assertEqual(result.filled_quantity, 4)
        self.assertAlmostEqual(result.average_fill_price or 0, 101.4)
        self.assertAlmostEqual(result.filled_notional or 0, 405.625)
        self.assertAlmostEqual(result.broker_fee or 0, 0.03)
        self.assertEqual(result.fill_activity_count, 2)
        self.assertEqual(result.position_quantity, 4)
        self.assertAlmostEqual(result.position_market_value or 0, 406.2)
        self.assertAlmostEqual(result.account_cash or 0, 9994.37)
        self.assertAlmostEqual(result.account_equity or 0, 10400.57)
        self.assertEqual(len(result.fill_activities or []), 2)
        self.assertIn("/v2/account/activities/FILL", calls[1])
        self.assertIn("/v2/positions/SPY", calls[2])
        self.assertIn("/v2/account", calls[3])

    def test_alpaca_paper_broker_reconciles_rejected_order_status(self):
        def fake_get_transport(_url, _headers, _timeout_seconds):
            return (
                200,
                {
                    "id": "alpaca-order-rejected",
                    "client_order_id": "alpaca-paper-rejected",
                    "status": "rejected",
                    "symbol": "SPY",
                    "side": "buy",
                    "qty": "1",
                    "filled_qty": "0",
                },
                {},
            )

        broker = AlpacaUsEquityPaperBroker(get_transport=fake_get_transport)
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "paper-key",
                "ALPACA_API_SECRET_KEY": "paper-secret",
                "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                "ALPACA_PAPER_TRADING_ENABLED": "true",
                "ALPACA_PAPER_TRADING_ACK": ALPACA_PAPER_TRADING_ACK_VALUE,
            },
            clear=False,
        ):
            result = broker.fetch_order_status(
                broker_order_id="alpaca-order-rejected",
                client_order_id="alpaca-paper-rejected",
            )

        self.assertEqual(result.status, "found")
        self.assertEqual(result.order_status, "rejected")
        self.assertTrue(result.external_lookup_attempted)

    def test_alpaca_paper_broker_reports_missing_order_status(self):
        def fake_get_transport(_url, _headers, _timeout_seconds):
            return (404, {"message": "order not found"}, {})

        broker = AlpacaUsEquityPaperBroker(get_transport=fake_get_transport)
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "paper-key",
                "ALPACA_API_SECRET_KEY": "paper-secret",
                "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                "ALPACA_PAPER_TRADING_ENABLED": "true",
                "ALPACA_PAPER_TRADING_ACK": ALPACA_PAPER_TRADING_ACK_VALUE,
            },
            clear=False,
        ):
            result = broker.fetch_order_status(
                broker_order_id="missing-order",
                client_order_id="missing-client-order",
            )

        self.assertEqual(result.status, "not_found")
        self.assertTrue(result.external_lookup_attempted)

    def test_alpaca_paper_broker_blocks_reconciliation_without_credentials(self):
        broker = AlpacaUsEquityPaperBroker(get_transport=lambda *args: self.fail("should not call Alpaca"))

        with patch.dict("os.environ", {}, clear=True):
            result = broker.fetch_order_status(
                broker_order_id="alpaca-order-123",
                client_order_id="alpaca-paper-2",
            )

        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.external_lookup_attempted)

    def test_mock_us_equity_paper_broker_blocks_live_confirmation(self):
        broker = us_equity_paper_broker()
        result = broker.submit_order(
            BrokerOrderIntent(
                symbol="QQQ",
                side="sell",
                quantity=1,
                live_confirmation=True,
            )
        )

        self.assertEqual(result.status, "blocked")
        self.assertIn("disabled", result.reason)

    def test_mock_us_equity_paper_broker_rejects_invalid_limit_order(self):
        broker = us_equity_paper_broker()
        result = broker.submit_order(
            BrokerOrderIntent(
                symbol="MSFT",
                side="buy",
                quantity=1,
                order_type="limit",
            )
        )

        self.assertEqual(result.status, "rejected")
        self.assertIn("limit_price", result.reason)

    def test_broker_intent_evaluation_never_attempts_external_submission(self):
        result = evaluate_broker_order_intent(
            BrokerOrderIntentRequest(
                symbol="aapl",
                side="buy",
                quantity=2,
                order_type="limit",
                limit_price=180.25,
                reference_price=180,
                cash_available=1_000,
                current_position_quantity=0,
                portfolio_equity=1_000,
                paper_fee_bps=1,
                paper_slippage_bps=1,
                client_order_id="eval-test-1",
            )
        )

        self.assertEqual(result.validation_status, "accepted")
        self.assertEqual(result.submission_status, "paper_recorded")
        self.assertTrue(result.id)
        self.assertEqual(result.normalized_symbol, "AAPL")
        self.assertFalse(result.external_submission_attempted)
        self.assertFalse(result.live_submission_supported)
        self.assertIsNotNone(result.paper_fill_estimate)
        self.assertEqual(result.paper_fill_estimate.status, "estimated_fill")
        self.assertAlmostEqual(result.paper_fill_estimate.estimated_notional or 0, 360.036)
        self.assertLess(result.paper_fill_estimate.cash_after or 0, 1_000)

    def test_broker_intent_evaluation_blocks_live_confirmation(self):
        result = evaluate_broker_order_intent(
            BrokerOrderIntentRequest(
                symbol="NVDA",
                side="sell",
                quantity=1,
                live_confirmation=True,
            )
        )

        self.assertEqual(result.validation_status, "accepted")
        self.assertEqual(result.submission_status, "blocked")
        self.assertTrue(result.id)
        self.assertIn("disabled", result.reason)
        self.assertFalse(result.external_submission_attempted)

    def test_broker_intent_evaluation_reports_paper_fill_shortfalls(self):
        cash_shortfall = evaluate_broker_order_intent(
            BrokerOrderIntentRequest(
                symbol="SPY",
                side="buy",
                quantity=10,
                order_type="market",
                reference_price=500,
                cash_available=1_000,
            )
        )
        self.assertIsNotNone(cash_shortfall.paper_fill_estimate)
        self.assertEqual(cash_shortfall.paper_fill_estimate.status, "cash_shortfall")
        self.assertFalse(cash_shortfall.paper_fill_estimate.cash_sufficient)

        not_fillable = evaluate_broker_order_intent(
            BrokerOrderIntentRequest(
                symbol="QQQ",
                side="buy",
                quantity=1,
                order_type="limit",
                limit_price=100,
                reference_price=110,
            )
        )
        self.assertIsNotNone(not_fillable.paper_fill_estimate)
        self.assertEqual(not_fillable.paper_fill_estimate.status, "not_fillable")
        self.assertFalse(not_fillable.paper_fill_estimate.fillable)

    def test_broker_intent_evaluation_supports_alpaca_paper_preview(self):
        result = evaluate_broker_order_intent(
            BrokerOrderIntentRequest(
                adapter_id="alpaca_us_equity_paper_preview",
                symbol="spy",
                side="buy",
                quantity=1,
                order_type="market",
                reference_price=500,
                cash_available=1_000,
                client_order_id="alpaca-eval-1",
            )
        )

        self.assertEqual(result.adapter_id, "alpaca_us_equity_paper_preview")
        self.assertEqual(result.broker_contract.id, "alpaca_us_equity_paper_preview")
        self.assertEqual(result.submission_status, "paper_recorded")
        self.assertFalse(result.external_submission_attempted)
        self.assertFalse(result.live_submission_supported)

    def test_broker_intent_evaluation_blocks_alpaca_paper_until_gated(self):
        result = evaluate_broker_order_intent(
            BrokerOrderIntentRequest(
                adapter_id="alpaca_us_equity_paper",
                symbol="spy",
                side="buy",
                quantity=1,
                order_type="market",
                reference_price=500,
                cash_available=1_000,
                client_order_id="alpaca-paper-eval-1",
            )
        )

        self.assertEqual(result.adapter_id, "alpaca_us_equity_paper")
        self.assertEqual(result.broker_contract.id, "alpaca_us_equity_paper")
        self.assertEqual(result.validation_status, "accepted")
        self.assertEqual(result.submission_status, "blocked")
        self.assertFalse(result.external_submission_attempted)
        self.assertIn("paper_submit_confirmation", result.reason)

    def test_reconcile_alpaca_paper_evaluation_matches_accepted_status(self):
        class FakeBroker:
            def fetch_order_status(self, **_kwargs):
                return BrokerOrderStatusResult(
                    status="found",
                    reason="found",
                    broker_order_id="alpaca-order-1",
                    client_order_id="client-alpaca-paper-1",
                    order_status="accepted",
                    symbol="SPY",
                    side="buy",
                    quantity=1,
                    filled_quantity=0,
                    external_lookup_attempted=True,
                    raw_payload={"status": "accepted"},
                )

        with patch("app.execution.alpaca_us_equity_paper_broker", return_value=FakeBroker()):
            reconciliation = reconcile_broker_order_evaluation(self._alpaca_paper_evaluation())

        self.assertEqual(reconciliation.status, "matched")
        self.assertEqual(reconciliation.broker_status, "accepted")
        self.assertTrue(reconciliation.external_lookup_attempted)

    def test_reconcile_alpaca_paper_evaluation_preserves_fill_and_position_evidence(self):
        class FakeBroker:
            def fetch_order_status(self, **_kwargs):
                return BrokerOrderStatusResult(
                    status="found",
                    reason="found",
                    broker_order_id="alpaca-order-1",
                    client_order_id="client-alpaca-paper-1",
                    order_status="partially_filled",
                    symbol="SPY",
                    side="buy",
                    quantity=1,
                    filled_quantity=0.4,
                    average_fill_price=501.25,
                    filled_notional=200.5,
                    broker_fee=0.01,
                    partial_fill=True,
                    fill_activity_count=1,
                    position_quantity=0.4,
                    position_market_value=201.0,
                    position_cost_basis=200.5,
                    position_unrealized_pl=0.5,
                    position_snapshot={"symbol": "SPY", "qty": "0.4"},
                    account_cash=999.5,
                    account_equity=1200.5,
                    account_buying_power=1999.0,
                    account_snapshot={"cash": "999.5", "equity": "1200.5"},
                    fill_activities=[{"id": "fill-1", "qty": "0.4"}],
                    external_lookup_attempted=True,
                    raw_payload={"status": "partially_filled"},
                )

        with patch("app.execution.alpaca_us_equity_paper_broker", return_value=FakeBroker()):
            reconciliation = reconcile_broker_order_evaluation(self._alpaca_paper_evaluation())

        self.assertEqual(reconciliation.status, "matched")
        self.assertTrue(reconciliation.broker_partial_fill)
        self.assertAlmostEqual(reconciliation.broker_avg_fill_price or 0, 501.25)
        self.assertAlmostEqual(reconciliation.broker_filled_notional or 0, 200.5)
        self.assertAlmostEqual(reconciliation.broker_fee or 0, 0.01)
        self.assertEqual(reconciliation.broker_fill_activity_count, 1)
        self.assertEqual(reconciliation.broker_position_quantity, 0.4)
        self.assertEqual(reconciliation.broker_account_cash, 999.5)
        self.assertEqual(len(reconciliation.broker_fill_activities), 1)
        self.assertIn("partial fill", reconciliation.reason)

    def test_reconcile_alpaca_paper_evaluation_flags_rejected_status(self):
        class FakeBroker:
            def fetch_order_status(self, **_kwargs):
                return BrokerOrderStatusResult(
                    status="found",
                    reason="found",
                    broker_order_id="alpaca-order-1",
                    client_order_id="client-alpaca-paper-1",
                    order_status="rejected",
                    symbol="SPY",
                    side="buy",
                    quantity=1,
                    filled_quantity=0,
                    external_lookup_attempted=True,
                    raw_payload={"status": "rejected"},
                )

        with patch("app.execution.alpaca_us_equity_paper_broker", return_value=FakeBroker()):
            reconciliation = reconcile_broker_order_evaluation(self._alpaca_paper_evaluation())

        self.assertEqual(reconciliation.status, "mismatch")
        self.assertEqual(reconciliation.broker_status, "rejected")
        self.assertIn("rejected", reconciliation.reason)

    def test_reconcile_alpaca_paper_evaluation_reports_missing_order(self):
        class FakeBroker:
            def fetch_order_status(self, **_kwargs):
                return BrokerOrderStatusResult(
                    status="not_found",
                    reason="Alpaca paper order was not found.",
                    broker_order_id="alpaca-order-1",
                    client_order_id="client-alpaca-paper-1",
                    external_lookup_attempted=True,
                )

        with patch("app.execution.alpaca_us_equity_paper_broker", return_value=FakeBroker()):
            reconciliation = reconcile_broker_order_evaluation(self._alpaca_paper_evaluation())

        self.assertEqual(reconciliation.status, "not_found")
        self.assertTrue(reconciliation.external_lookup_attempted)

    def test_reconcile_alpaca_paper_evaluation_reports_credential_block(self):
        class FakeBroker:
            def fetch_order_status(self, **_kwargs):
                return BrokerOrderStatusResult(
                    status="blocked",
                    reason="Alpaca paper API credentials are missing.",
                    broker_order_id="alpaca-order-1",
                    client_order_id="client-alpaca-paper-1",
                    external_lookup_attempted=False,
                )

        with patch("app.execution.alpaca_us_equity_paper_broker", return_value=FakeBroker()):
            reconciliation = reconcile_broker_order_evaluation(self._alpaca_paper_evaluation())

        self.assertEqual(reconciliation.status, "blocked")
        self.assertFalse(reconciliation.external_lookup_attempted)


if __name__ == "__main__":
    unittest.main()
