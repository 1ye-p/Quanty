# 执行 Agent 测试用例 1：策略组合实现

> 测试时间：2026-07-13
> 测试目标：验证执行提示词对策略组合 Plan 的实现能力

---

## 输入 Plan

[er_test_1_strategy_review.md 的输出]

---

## 预期输出（实现报告）

# 实现报告：策略组合增强

## 变更摘要

增强 CompositeStrategy 支持阶段式策略协调，实现全局止盈止损功能。

## 代码变更

### 文件 1：`python/cquant/backtest_vector/strategies/combo.py`

**变更类型**：修改

**变更内容**：
```python
"""Strategy combination framework: run multiple strategies and merge signals."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame

logger = logging.getLogger(__name__)


class CoordinationMode(str, Enum):
    """策略协调模式。"""
    SEQUENTIAL = "sequential"  # 阶段式：策略 A → 策略 B
    PARALLEL = "parallel"      # 并行式：同时执行
    CONDITIONAL = "conditional"  # 条件式：按优先级执行


class StrategyRole(str, Enum):
    """策略角色。"""
    ENTRY = "entry"              # 建仓
    ADD_POSITION = "add_position"  # 加仓
    EXIT = "exit"                # 退出


@dataclass
class StrategySlot:
    """策略槽位配置。"""
    strategy: Strategy
    role: StrategyRole
    stop_loss: float | None = None
    take_profit: float | None = None


class CompositeStrategy(Strategy):
    """Combine signals from multiple sub-strategies.

    Parameters:
        strategy_id: Identifier for this composite.
        strategies: List of strategy slots with role and risk config.
        coordination_mode: How strategies coordinate:
            - "sequential": strategies run in order (entry → add_position)
            - "parallel": all strategies run simultaneously
            - "conditional": strategies run based on priority
        global_stop_loss: Global stop loss percentage for all positions.
        global_take_profit: Global take profit percentage for all positions.
    """

    def __init__(
        self,
        strategy_id: str,
        strategies: list[StrategySlot],
        coordination_mode: CoordinationMode = CoordinationMode.SEQUENTIAL,
        global_stop_loss: float | None = None,
        global_take_profit: float | None = None,
    ) -> None:
        self._strategy_id = strategy_id
        self._strategies = strategies
        self._coordination_mode = coordination_mode
        self._global_stop_loss = global_stop_loss
        self._global_take_profit = global_take_profit

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        if not self._strategies:
            return _empty_frame()

        if self._coordination_mode == CoordinationMode.SEQUENTIAL:
            return self._sequential_generate(ctx)
        elif self._coordination_mode == CoordinationMode.PARALLEL:
            return self._parallel_generate(ctx)
        else:
            return self._conditional_generate(ctx)

    def _sequential_generate(self, ctx: StrategyContext) -> SignalFrame:
        """阶段式生成信号：entry → add_position。"""
        entry_signals: list[SignalFrame] = []
        add_signals: list[SignalFrame] = []
        exit_signals: list[SignalFrame] = []

        for slot in self._strategies:
            sig = slot.strategy.generate_signals(ctx)
            if sig.is_empty():
                continue

            # 添加来源标记
            sig = sig.with_columns(
                pl.lit(slot.strategy.strategy_id).alias("_source"),
                pl.lit(slot.role.value).alias("_role"),
            )

            if slot.role == StrategyRole.ENTRY:
                entry_signals.append(sig)
            elif slot.role == StrategyRole.ADD_POSITION:
                add_signals.append(sig)
            else:
                exit_signals.append(sig)

        # 合并信号
        all_signals = entry_signals + add_signals + exit_signals
        if not all_signals:
            return _empty_frame()

        return pl.concat(all_signals)

    def _parallel_generate(self, ctx: StrategyContext) -> SignalFrame:
        """并行生成信号。"""
        all_signals: list[SignalFrame] = []

        for slot in self._strategies:
            sig = slot.strategy.generate_signals(ctx)
            if not sig.is_empty():
                sig = sig.with_columns(
                    pl.lit(slot.strategy.strategy_id).alias("_source"),
                    pl.lit(slot.role.value).alias("_role"),
                )
                all_signals.append(sig)

        if not all_signals:
            return _empty_frame()

        return pl.concat(all_signals)

    def _conditional_generate(self, ctx: StrategyContext) -> SignalFrame:
        """条件式生成信号（按优先级）。"""
        for slot in self._strategies:
            sig = slot.strategy.generate_signals(ctx)
            if not sig.is_empty():
                sig = sig.with_columns(
                    pl.lit(slot.strategy.strategy_id).alias("_source"),
                    pl.lit(slot.role.value).alias("_role"),
                )
                return sig

        return _empty_frame()

    def get_global_stop_loss(self) -> float | None:
        """获取全局止损比例。"""
        return self._global_stop_loss

    def get_global_take_profit(self) -> float | None:
        """获取全局止盈比例。"""
        return self._global_take_profit


def _empty_frame() -> SignalFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "signal_date": pl.Date,
            "direction": pl.Utf8,
            "strength": pl.Float64,
            "confidence": pl.Float64,
        }
    )
```

**变更原因**：扩展 CompositeStrategy 支持阶段式协调和全局止盈止损。

---

### 文件 2：`python/cquant/backtest_vector/strategies/attribution.py`

**变更类型**：新增

**变更内容**：
```python
"""Trade attribution tracking for composite strategies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class TradeAttribution:
    """每笔交易的来源归因。"""
    strategy_id: str          # 来源策略
    signal_type: str          # buy / sell / stop_loss / take_profit
    entry_price: float        # 入场价格
    current_price: float      # 当前价格
    pnl: float               # 盈亏
    entry_date: date          # 入场日期
    exit_date: date | None    # 退出日期


class AttributionTracker:
    """交易归因追踪器。"""

    def __init__(self) -> None:
        self._attributions: dict[str, TradeAttribution] = {}

    def record_entry(
        self,
        trade_id: str,
        strategy_id: str,
        signal_type: str,
        entry_price: float,
        entry_date: date,
    ) -> None:
        """记录入场归因。"""
        self._attributions[trade_id] = TradeAttribution(
            strategy_id=strategy_id,
            signal_type=signal_type,
            entry_price=entry_price,
            current_price=entry_price,
            pnl=0.0,
            entry_date=entry_date,
            exit_date=None,
        )

    def record_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_date: date,
        signal_type: str,
    ) -> None:
        """记录出场归因。"""
        if trade_id in self._attributions:
            attr = self._attributions[trade_id]
            attr.current_price = exit_price
            attr.pnl = (exit_price - attr.entry_price) / attr.entry_price
            attr.exit_date = exit_date
            attr.signal_type = signal_type

    def get_attribution(self, trade_id: str) -> TradeAttribution | None:
        """获取交易归因。"""
        return self._attributions.get(trade_id)

    def get_all_attributions(self) -> list[TradeAttribution]:
        """获取所有交易归因。"""
        return list(self._attributions.values())
```

**变更原因**：实现交易归因追踪功能。

---

## 测试用例

### 测试 1：`test_composite_strategy_sequential`

```python
def test_composite_strategy_sequential():
    """测试阶段式策略组合。"""
    # Arrange
    entry_strategy = MockStrategy("entry_strategy")
    add_strategy = MockStrategy("add_strategy")

    slots = [
        StrategySlot(strategy=entry_strategy, role=StrategyRole.ENTRY),
        StrategySlot(strategy=add_strategy, role=StrategyRole.ADD_POSITION),
    ]

    composite = CompositeStrategy(
        strategy_id="test_composite",
        strategies=slots,
        coordination_mode=CoordinationMode.SEQUENTIAL,
        global_stop_loss=0.05,
        global_take_profit=0.20,
    )

    ctx = StrategyContext(as_of_date=date(2025, 1, 15))

    # Act
    signals = composite.generate_signals(ctx)

    # Assert
    assert not signals.is_empty()
    assert "_source" in signals.columns
    assert "_role" in signals.columns
    assert composite.get_global_stop_loss() == 0.05
    assert composite.get_global_take_profit() == 0.20
```

### 测试 2：`test_attribution_tracker`

```python
def test_attribution_tracker():
    """测试交易归因追踪。"""
    # Arrange
    tracker = AttributionTracker()

    # Act
    tracker.record_entry(
        trade_id="trade_1",
        strategy_id="entry_strategy",
        signal_type="buy",
        entry_price=100.0,
        entry_date=date(2025, 1, 15),
    )

    tracker.record_exit(
        trade_id="trade_1",
        exit_price=120.0,
        exit_date=date(2025, 2, 15),
        signal_type="take_profit",
    )

    # Assert
    attr = tracker.get_attribution("trade_1")
    assert attr is not None
    assert attr.strategy_id == "entry_strategy"
    assert attr.pnl == 0.20
    assert attr.exit_date == date(2025, 2, 15)
```

---

## 文档更新

### 更新 1：`docs/superpowers/specs/2026-07-13-three-stage-prompt-architecture-design.md`

**更新内容**：添加策略组合实现的链接和说明。

---

## 未实现项

| 序号 | 项目 | 原因 | 后续计划 |
|------|------|------|----------|
| 1 | 前端配置界面 | 时间限制 | Phase 4 实现 |
| 2 | 全局止盈止损执行逻辑 | 需要与回测引擎集成 | Phase 4 实现 |

---

## 质量检查结果

- [x] Lint 通过（ruff check）
- [x] Type Check 通过（mypy）
- [x] Test 通过（pytest）
- [x] Build 通过

---

## 测试结果

**评估维度**：
- ✅ 代码质量：遵循 PEP 8，type hints 完整
- ✅ 测试覆盖：核心功能有测试用例
- ✅ 文档更新：相关文档已更新
- ⚠️ 改进建议：可补充更多边界条件测试
