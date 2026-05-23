"""测试 Paper Broker 量价参与率约束。"""
from __future__ import annotations

import pytest

from cquant.execution.broker import Order, OrderStatus
from cquant.execution.paper_broker import PaperBroker


class TestVolumeParticipationLimit:
    def test_no_volume_limit_by_default(self) -> None:
        """默认情况下无量价约束，大单可全量成交。"""
        broker = PaperBroker(initial_cash=10_000_000)
        broker.update_prices({"SSE:600036": 50.0})
        order = Order(order_id="t1", asset_id="SSE:600036", side="buy", qty=100_000)
        result = broker.submit_order(order)
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 100_000

    def test_max_volume_pct_limits_fill(self) -> None:
        """max_volume_pct=0.1 时，最多成交日成交量的 10%。"""
        broker = PaperBroker(initial_cash=10_000_000, max_volume_pct=0.1)
        broker.update_prices({"SSE:600036": 50.0})
        broker.update_volumes({"SSE:600036": 1_000_000})
        # 下单 200,000 股，但只允许最多 100,000（10% × 1,000,000）
        order = Order(order_id="t1", asset_id="SSE:600036", side="buy", qty=200_000)
        result = broker.submit_order(order)
        assert result.filled_qty <= 100_000
        assert result.filled_qty > 0

    def test_small_order_not_affected_by_volume_limit(self) -> None:
        """小单不受量价约束影响，仍可全量成交。"""
        broker = PaperBroker(initial_cash=1_000_000, max_volume_pct=0.1)
        broker.update_prices({"SSE:600036": 50.0})
        broker.update_volumes({"SSE:600036": 1_000_000})
        order = Order(order_id="t1", asset_id="SSE:600036", side="buy", qty=5_000)
        result = broker.submit_order(order)
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 5_000

    def test_volume_limit_disabled_when_zero(self) -> None:
        """max_volume_pct=0 时，不受量价约束。"""
        broker = PaperBroker(initial_cash=10_000_000, max_volume_pct=0.0)
        broker.update_prices({"SSE:600036": 50.0})
        broker.update_volumes({"SSE:600036": 100_000})
        order = Order(order_id="t1", asset_id="SSE:600036", side="buy", qty=50_000)
        result = broker.submit_order(order)
        assert result.status == OrderStatus.FILLED
