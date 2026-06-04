"""Tests for alert enhancement: severity, risk_breach type, notification channels."""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ── Test _save_alert with severity ─────────────────────────────────────────────

class TestSaveAlertSeverity:
    """Verify _save_alert correctly passes severity parameter."""

    def test_save_alert_default_severity(self):
        from cquant.api_server.alert_checker import _save_alert

        catalog = MagicMock()
        _save_alert(catalog, "ar_test", "data_stale", "test message")

        call_args = catalog.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "severity" in sql
        assert params[3] == "warning"  # default severity

    def test_save_alert_critical_severity(self):
        from cquant.api_server.alert_checker import _save_alert

        catalog = MagicMock()
        _save_alert(catalog, "ar_test", "pnl_drawdown", "critical drawdown", severity="critical")

        call_args = catalog.execute.call_args
        params = call_args[0][1]
        assert params[3] == "critical"

    def test_save_alert_info_severity(self):
        from cquant.api_server.alert_checker import _save_alert

        catalog = MagicMock()
        _save_alert(catalog, "ar_test", "data_stale", "info message", severity="info")

        call_args = catalog.execute.call_args
        params = call_args[0][1]
        assert params[3] == "info"


# ── Test RULE_TYPES includes risk_breach ──────────────────────────────────────

class TestRuleTypes:
    def test_risk_breach_in_rule_types(self):
        from cquant.api_server.alert_checker import RULE_TYPES
        assert "risk_breach" in RULE_TYPES
        assert RULE_TYPES["risk_breach"] == "风控策略拦截交易"

    def test_all_expected_types_present(self):
        from cquant.api_server.alert_checker import RULE_TYPES
        expected = {"data_stale", "factor_ic_low", "pnl_drawdown", "risk_breach"}
        assert set(RULE_TYPES.keys()) == expected


# ── Test DDL includes severity column ─────────────────────────────────────────

class TestEnsureTables:
    def test_meta_alert_history_ddl_includes_severity(self):
        from cquant.api_server.alert_checker import _ensure_tables, _alert_tables_ensured

        # Reset the global flag to force re-execution
        import cquant.api_server.alert_checker as mod
        original = mod._alert_tables_ensured
        mod._alert_tables_ensured = False

        catalog = MagicMock()
        _ensure_tables(catalog)

        # Find the CREATE TABLE call for meta_alert_history
        calls = [c[0][0] for c in catalog.execute.call_args_list]
        history_ddl = [c for c in calls if "meta_alert_history" in c and "CREATE" in c]
        assert len(history_ddl) >= 1
        assert "severity" in history_ddl[0]

        # Restore
        mod._alert_tables_ensured = original


# ── Test check_pnl_drawdown severity logic ────────────────────────────────────

class TestPnlDrawdownSeverity:
    def test_critical_when_dd_above_10pct(self):
        from cquant.api_server.alert_checker import check_pnl_drawdown

        catalog = MagicMock()
        df_mock = MagicMock()
        df_mock.is_empty.return_value = False
        df_mock.__getitem__ = lambda self, key: [0.15] if key == "max_dd" else [None]
        catalog.query.return_value = df_mock

        check_pnl_drawdown(catalog, "ar_test", {"strategy_id": "s1", "threshold_pct": "5"})

        call_args = catalog.execute.call_args
        params = call_args[0][1]
        assert params[3] == "critical"

    def test_warning_when_dd_below_10pct(self):
        from cquant.api_server.alert_checker import check_pnl_drawdown

        catalog = MagicMock()
        df_mock = MagicMock()
        df_mock.is_empty.return_value = False
        df_mock.__getitem__ = lambda self, key: [0.08] if key == "max_dd" else [None]
        catalog.query.return_value = df_mock

        check_pnl_drawdown(catalog, "ar_test", {"strategy_id": "s1", "threshold_pct": "5"})

        call_args = catalog.execute.call_args
        params = call_args[0][1]
        assert params[3] == "warning"


# ── Test notification_channel module ──────────────────────────────────────────

class TestNotificationChannel:
    def test_channel_registry(self):
        from cquant.api_server.notification_channel import CHANNELS
        assert "webhook" in CHANNELS
        assert "email" in CHANNELS
        assert "dingtalk" in CHANNELS

    def test_get_channel_webhook(self):
        from cquant.api_server.notification_channel import get_channel, WebhookChannel
        ch = get_channel("webhook", {"url": "https://example.com/hook"})
        assert isinstance(ch, WebhookChannel)
        assert ch.url == "https://example.com/hook"

    def test_get_channel_unknown_type(self):
        from cquant.api_server.notification_channel import get_channel
        ch = get_channel("unknown_type", {})
        assert ch is None

    def test_webhook_channel_type(self):
        from cquant.api_server.notification_channel import WebhookChannel
        ch = WebhookChannel(url="https://example.com")
        assert ch.channel_type == "webhook"

    def test_email_channel_type(self):
        from cquant.api_server.notification_channel import EmailChannel
        ch = EmailChannel(smtp_host="smtp.example.com")
        assert ch.channel_type == "email"

    def test_dingtalk_channel_type(self):
        from cquant.api_server.notification_channel import DingTalkChannel
        ch = DingTalkChannel(webhook_url="https://oapi.dingtalk.com/robot/send")
        assert ch.channel_type == "dingtalk"

    @patch("urllib.request.urlopen")
    def test_webhook_send_success(self, mock_urlopen):
        from cquant.api_server.notification_channel import WebhookChannel

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ch = WebhookChannel(url="https://example.com/hook")
        result = ch.send("Test", "Hello", severity="warning")
        assert result is True

    @patch("urllib.request.urlopen")
    def test_webhook_send_failure(self, mock_urlopen):
        from cquant.api_server.notification_channel import WebhookChannel

        mock_urlopen.side_effect = Exception("Network error")

        ch = WebhookChannel(url="https://example.com/hook")
        result = ch.send("Test", "Hello")
        assert result is False


# ── Test fill_simulator _emit_risk_alert ──────────────────────────────────────

class TestFillSimulatorRiskAlert:
    def test_emit_risk_alert_with_catalog(self):
        from cquant.backtest_vector.fill_simulator import AShareFillSimulator
        from datetime import date

        mock_catalog = MagicMock()

        sim = AShareFillSimulator(catalog=mock_catalog)
        sim._emit_risk_alert("T+1", "REJECTED", "T+1 限制", "000001.SZ", date(2025, 1, 1))

        mock_catalog.execute.assert_called_once()
        call_args = mock_catalog.execute.call_args[0]
        params = call_args[1]
        assert params[2] == "risk_breach"
        assert params[3] == "critical"  # REJECTED -> critical
        assert "T+1" in params[4]

    def test_emit_risk_alert_clipped_warning(self):
        from cquant.backtest_vector.fill_simulator import AShareFillSimulator
        from datetime import date

        mock_catalog = MagicMock()

        sim = AShareFillSimulator(catalog=mock_catalog)
        sim._emit_risk_alert("max_position", "CLIPPED", "仓位限制", "000001.SZ", date(2025, 1, 1))

        params = mock_catalog.execute.call_args[0][1]
        assert params[3] == "warning"  # CLIPPED -> warning

    def test_emit_risk_alert_no_catalog(self):
        from cquant.backtest_vector.fill_simulator import AShareFillSimulator
        from datetime import date

        sim = AShareFillSimulator()
        # Should not raise
        sim._emit_risk_alert("T+1", "REJECTED", "T+1 限制", "000001.SZ", date(2025, 1, 1))

    def test_emit_risk_alert_catalog_exception_handled(self):
        from cquant.backtest_vector.fill_simulator import AShareFillSimulator
        from datetime import date

        mock_catalog = MagicMock()
        mock_catalog.execute.side_effect = Exception("DB error")

        sim = AShareFillSimulator(catalog=mock_catalog)
        # Should not raise
        sim._emit_risk_alert("T+1", "REJECTED", "T+1 限制", "000001.SZ", date(2025, 1, 1))


# ── Test alert API routes ─────────────────────────────────────────────────────

class TestAlertRoutes:
    def test_update_rule_body_model(self):
        from cquant.api_server.routes.alerts import AlertRuleUpdateBody
        body = AlertRuleUpdateBody(params={"max_days": 5}, enabled=False)
        assert body.params == {"max_days": 5}
        assert body.enabled is False

    def test_update_rule_body_partial(self):
        from cquant.api_server.routes.alerts import AlertRuleUpdateBody
        body = AlertRuleUpdateBody(enabled=False)
        assert body.params is None
        assert body.enabled is False

    def test_channel_body_model(self):
        from cquant.api_server.routes.alerts import ChannelBody
        body = ChannelBody(
            channel_type="webhook",
            name="Test",
            config={"url": "https://example.com"},
            enabled=True,
        )
        assert body.channel_type == "webhook"
        assert body.name == "Test"
