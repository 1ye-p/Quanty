"""Integration test: market rules end-to-end flow."""

from datetime import date

from cquant.core.enums import AssetStatus, TradabilityReason
from cquant.market_calendar import (
    LimitStatus,
    StatusTracker,
    TradabilityResult,
    get_market_rules,
    load_market_config,
)


class TestMarketRulesE2E:
    def setup_method(self):
        self.config = load_market_config("CN")
        self.rules = get_market_rules("CN", self.config)
        self.tracker = StatusTracker()
        self.rules.set_status_tracker(self.tracker)

    def test_full_tradability_check_normal(self):
        bar = {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2, "volume": 1000}
        result = self.rules.check_tradable("SH600000", date(2026, 1, 2), bar)
        assert result.tradable is True
        assert result.reason == TradabilityReason.TRADABLE

    def test_full_tradability_check_yizi_up(self):
        bar = {"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0, "volume": 0, "pre_close": 10.0}
        result = self.rules.check_tradable("SH600000", date(2026, 1, 2), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.YIZI_LIMIT

    def test_delist_flow(self):
        self.tracker.set_status("SH600000", date(2026, 6, 1), AssetStatus.DELISTED.value)
        bar = {"open": 5.0, "high": 5.0, "low": 5.0, "close": 5.0, "volume": 0}
        result = self.rules.check_tradable("SH600000", date(2026, 6, 1), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.DELISTED
        # Handle delist
        trades = self.rules.handle_delist({"SH600000": 1000}, "SH600000", date(2026, 6, 1), 5.0)
        assert len(trades) == 1
        assert trades[0].qty == 1000
        assert trades[0].reason == "delist_forced_liquidation"

    def test_st_limit_5pct(self):
        self.tracker.set_status("SZ000001", date(2026, 1, 2), AssetStatus.ST.value)
        bar = {"open": 10.5, "high": 10.5, "low": 10.5, "close": 10.5, "volume": 0, "pre_close": 10.0}
        result = self.rules.check_tradable("SZ000001", date(2026, 1, 2), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.YIZI_LIMIT

    def test_config_loaded_correctly(self):
        assert self.config["market"] == "CN"
        assert self.config["price_limits"]["main_board"]["up"] == 0.10
        assert self.config["price_limits"]["st"]["up"] == 0.05
        assert self.config["price_limits"]["chinext"]["up"] == 0.20
        assert self.config["price_limits"]["star"]["up"] == 0.20
        assert self.config["settlement"] == "T+1"
        assert self.config["lot_size"] == 100

    def test_detect_limit_via_rules(self):
        bar = {"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0, "volume": 0}
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.YIZI_UP

    def test_registry_returns_cn_rules(self):
        from cquant.market_calendar.rules.cn_rules import CNTradingRules
        assert isinstance(self.rules, CNTradingRules)

    def test_list_registered_markets(self):
        from cquant.market_calendar import list_registered_markets
        markets = list_registered_markets()
        assert "CN" in markets
