# 市场规则模块化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 `market_calendar` 模块，补齐 7 项 A 股市场规则缺口（复权集成、涨跌停含一字板、停牌、ST 状态、退市日期、退市持仓处理、YAML 配置）

**Architecture:** 扩展已有 `TradingRules` 基类新增 6 个抽象方法，在 `market_calendar/` 内新增 `config_loader.py`、`limit_detector.py`、`status_tracker.py`、`delist_handler.py`、`registry.py`。数据获取采用 Tushare→AkShare→运行时推导三级降级。回测引擎 `fill_simulator.py` 接入新规则层。

**Tech Stack:** Python 3.12 + Polars + DuckDB + PyYAML + Tushare + AkShare

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `python/cquant/market_calendar/rules/base.py` | Modify | 扩展 TradingRules 基类，新增 6 个抽象方法 + 枚举/数据类 |
| `python/cquant/market_calendar/rules/cn_rules.py` | Modify | 实现新增的 6 个方法 |
| `python/cquant/market_calendar/config_loader.py` | Create | YAML 配置加载 |
| `python/cquant/market_calendar/limit_detector.py` | Create | 涨跌停检测（含一字板） |
| `python/cquant/market_calendar/status_tracker.py` | Create | ST/退市状态追踪 + 数据获取 + 缓存 |
| `python/cquant/market_calendar/delist_handler.py` | Create | 退市持仓自动处理 |
| `python/cquant/market_calendar/registry.py` | Create | 规则注册表 |
| `python/cquant/market_calendar/__init__.py` | Modify | 更新导出 |
| `configs/markets/cn.yml` | Create | A 股配置 |
| `configs/markets/us.yml` | Create | 美股配置（桩） |
| `configs/markets/hk.yml` | Create | 港股配置（桩） |
| `python/cquant/backtest_vector/fill_simulator.py` | Modify | 接入新规则层 |
| `python/cquant/backtest_vector/limit_rules.py` | Modify | 标记 deprecated，委托给 limit_detector |
| `python/tests/unit/test_limit_detector.py` | Create | 涨跌停检测测试 |
| `python/tests/unit/test_status_tracker.py` | Create | 状态追踪测试 |
| `python/tests/unit/test_cn_trading_rules_v2.py` | Create | CNTradingRules 扩展方法测试 |
| `python/tests/unit/test_config_loader.py` | Create | 配置加载测试 |
| `python/tests/unit/test_delist_handler.py` | Create | 退市处理测试 |

---

### Task 1: 枚举与数据类型

**Files:**
- Modify: `python/cquant/market_calendar/rules/base.py`
- Modify: `python/cquant/core/enums.py`

- [ ] **Step 1: 在 enums.py 新增 LimitStatus 枚举**

```python
# python/cquant/core/enums.py — 在 AssetStatus 之后添加
class LimitStatus(str, Enum):
    """涨跌停状态"""
    NONE = "none"
    UP = "up"
    DOWN = "down"
    YIZI_UP = "yizi_up"      # 一字涨停
    YIZI_DOWN = "yizi_down"  # 一字跌停


class TradabilityReason(str, Enum):
    """不可交易原因"""
    TRADABLE = "tradable"
    SUSPENDED = "suspended"
    LIMIT_UP = "limit_up"
    LIMIT_DOWN = "limit_down"
    YIZI_LIMIT = "yizi_limit"
    DELISTED = "delisted"
    NOT_TRADING_DAY = "not_trading_day"
```

- [ ] **Step 2: 在 base.py 添加 TradabilityResult 数据类**

```python
# python/cquant/market_calendar/rules/base.py — 在 import 之后、TradingRules 之前添加
from dataclasses import dataclass
from cquant.core.enums import LimitStatus, TradabilityReason

@dataclass
class TradabilityResult:
    """综合可交易性检查结果"""
    tradable: bool
    reason: TradabilityReason
    message: str = ""
```

- [ ] **Step 3: 运行测试确认无导入错误**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -c "from cquant.core.enums import LimitStatus, TradabilityReason; from cquant.market_calendar.rules.base import TradabilityResult; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add python/cquant/core/enums.py python/cquant/market_calendar/rules/base.py
git commit -m "feat(market_calendar): add LimitStatus, TradabilityReason enums and TradabilityResult"
```

---

### Task 2: YAML 配置加载器

**Files:**
- Create: `python/cquant/market_calendar/config_loader.py`
- Create: `configs/markets/cn.yml`
- Create: `configs/markets/us.yml`
- Create: `configs/markets/hk.yml`
- Test: `python/tests/unit/test_config_loader.py`

- [ ] **Step 1: 编写配置加载测试**

```python
# python/tests/unit/test_config_loader.py
from pathlib import Path
import pytest
from cquant.market_calendar.config_loader import load_market_config

def test_load_cn_config():
    config = load_market_config("CN")
    assert config["market"] == "CN"
    assert config["price_limits"]["main_board"]["up"] == 0.10
    assert config["price_limits"]["st"]["up"] == 0.05
    assert config["settlement"] == "T+1"
    assert config["lot_size"] == 100
    assert config["adjustment"]["default"] == "forward"

def test_load_us_config():
    config = load_market_config("US")
    assert config["market"] == "US"
    assert config["price_limits"] == {}
    assert config["settlement"] == "T+2"

def test_load_unknown_market_raises():
    with pytest.raises(FileNotFoundError):
        load_market_config("XX")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest python/tests/unit/test_config_loader.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建 YAML 配置文件**

```yaml
# configs/markets/cn.yml
market: CN
name: A股

price_limits:
  main_board: { up: 0.10, down: 0.10 }
  st: { up: 0.05, down: 0.05 }
  chinext: { up: 0.20, down: 0.20 }
  star: { up: 0.20, down: 0.20 }
  ipo_first_days: 5

settlement: T+1
lot_size: 100
tick_size: 0.01

adjustment:
  default: forward
  options: [forward, backward, none]

data_source:
  primary: tushare
  fallback: akshare
  cache_table: market_status_cache
  rate_limit:
    tushare: { qps: 200, burst: 50 }
    akshare: { qps: 10, burst: 5 }

derivation:
  limit_tolerance: 0.99
  delist_suspend_days: 30
```

```yaml
# configs/markets/us.yml
market: US
name: 美股
price_limits: {}
settlement: T+2
lot_size: 1
tick_size: 0.01
adjustment:
  default: forward
  options: [forward, backward, none]
data_source:
  primary: tushare
  fallback: null
```

```yaml
# configs/markets/hk.yml
market: HK
name: 港股
price_limits: {}
settlement: T+2
lot_size: 100
tick_size: 0.01
adjustment:
  default: forward
  options: [forward, backward, none]
data_source:
  primary: tushare
  fallback: null
```

- [ ] **Step 4: 实现配置加载器**

```python
# python/cquant/market_calendar/config_loader.py
"""YAML market config loader."""
from __future__ import annotations
from pathlib import Path
import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "markets"

_cache: dict[str, dict] = {}


def load_market_config(market: str) -> dict:
    """Load market config from configs/markets/{market}.yml."""
    market = market.upper()
    if market in _cache:
        return _cache[market]
    path = _CONFIG_DIR / f"{market.lower()}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Market config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    _cache[market] = config
    return config


def clear_config_cache() -> None:
    """Clear the config cache (for testing)."""
    _cache.clear()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest python/tests/unit/test_config_loader.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add python/cquant/market_calendar/config_loader.py configs/markets/ python/tests/unit/test_config_loader.py
git commit -m "feat(market_calendar): add YAML config loader with CN/US/HK configs"
```

---

### Task 3: 涨跌停检测器（含一字板）

**Files:**
- Create: `python/cquant/market_calendar/limit_detector.py`
- Test: `python/tests/unit/test_limit_detector.py`

- [ ] **Step 1: 编写涨跌停检测测试**

```python
# python/tests/unit/test_limit_detector.py
import pytest
from cquant.market_calendar.limit_detector import detect_limit, LimitStatus

def _bar(open_, high, low, close, volume=1000):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

class TestDetectLimit:
    def test_no_limit(self):
        bar = _bar(10.0, 10.5, 9.5, 10.2)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.NONE

    def test_limit_up(self):
        bar = _bar(10.5, 11.0, 10.5, 11.0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.UP

    def test_limit_down(self):
        bar = _bar(9.5, 9.5, 9.0, 9.0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.DOWN

    def test_yizi_limit_up(self):
        # 一字涨停: open == close == high == low == limit price
        bar = _bar(11.0, 11.0, 11.0, 11.0, volume=0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.YIZI_UP

    def test_yizi_limit_down(self):
        bar = _bar(9.0, 9.0, 9.0, 9.0, volume=0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.YIZI_DOWN

    def test_st_limit_up(self):
        bar = _bar(10.5, 10.5, 10.5, 10.5)
        assert detect_limit(bar, 10.0, 0.05) == LimitStatus.YIZI_UP

    def test_normal_price_not_limit(self):
        bar = _bar(10.0, 10.3, 9.8, 10.1)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.NONE

    def test_zero_prev_close_returns_none(self):
        bar = _bar(10.0, 10.0, 10.0, 10.0)
        assert detect_limit(bar, 0.0, 0.10) == LimitStatus.NONE
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest python/tests/unit/test_limit_detector.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现涨跌停检测器**

```python
# python/cquant/market_calendar/limit_detector.py
"""Limit up/down detection including yizi-board (一字板)."""
from __future__ import annotations
from cquant.core.enums import LimitStatus


def detect_limit(bar: dict, pre_close: float, limit_pct: float, tolerance: float = 0.99) -> LimitStatus:
    """Detect limit status from bar data.

    Args:
        bar: dict with keys open, high, low, close, volume
        pre_close: previous close price
        limit_pct: limit percentage (e.g. 0.10 for ±10%)
        tolerance: detection tolerance (default 0.99 to handle rounding)

    Returns:
        LimitStatus enum value
    """
    if pre_close <= 0 or limit_pct <= 0:
        return LimitStatus.NONE

    change_pct = (bar["close"] - pre_close) / pre_close
    threshold = limit_pct * tolerance

    is_yizi = (bar["open"] == bar["close"] == bar["high"] == bar["low"])

    if change_pct >= threshold:
        return LimitStatus.YIZI_UP if is_yizi else LimitStatus.UP
    if change_pct <= -threshold:
        return LimitStatus.YIZI_DOWN if is_yizi else LimitStatus.DOWN
    return LimitStatus.NONE
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest python/tests/unit/test_limit_detector.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add python/cquant/market_calendar/limit_detector.py python/tests/unit/test_limit_detector.py
git commit -m "feat(market_calendar): add limit detector with yizi-board detection"
```

---

### Task 4: 状态追踪器（ST/退市 + 数据获取 + 缓存）

**Files:**
- Create: `python/cquant/market_calendar/status_tracker.py`
- Test: `python/tests/unit/test_status_tracker.py`

- [ ] **Step 1: 编写状态追踪测试**

```python
# python/tests/unit/test_status_tracker.py
from datetime import date
from unittest.mock import MagicMock
import pytest
from cquant.market_calendar.status_tracker import StatusTracker
from cquant.core.enums import AssetStatus

class TestStatusTracker:
    def setup_method(self):
        self.tracker = StatusTracker.__new__(StatusTracker)
        self.tracker._cache = {}
        self.tracker._fetcher = None

    def test_derive_st_from_name(self):
        result = self.tracker._derive_st_from_name("ST 万科A")
        assert result == AssetStatus.ST

    def test_derive_star_st_from_name(self):
        result = self.tracker._derive_st_from_name("*ST 新海")
        assert result == AssetStatus.STAR_ST

    def test_derive_active_from_name(self):
        result = self.tracker._derive_st_from_name("贵州茅台")
        assert result == AssetStatus.ACTIVE

    def test_cache_hit(self):
        self.tracker._cache[("SH600000", date(2026, 1, 1), "st")] = AssetStatus.ST.value
        result = self.tracker.get_status("SH600000", date(2026, 1, 1))
        assert result == "st"

    def test_cache_miss_returns_none(self):
        result = self.tracker.get_status("SH600000", date(2026, 1, 1))
        assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest python/tests/unit/test_status_tracker.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现状态追踪器**

```python
# python/cquant/market_calendar/status_tracker.py
"""ST/delist status tracking with data source + runtime derivation."""
from __future__ import annotations
import logging
from datetime import date
from cquant.core.enums import AssetStatus

logger = logging.getLogger(__name__)


class StatusTracker:
    """Tracks asset status (ST, delisted, etc.) with three-tier data strategy."""

    def __init__(self, fetcher=None, cache_table: str = "market_status_cache"):
        self._cache: dict[tuple, str] = {}
        self._fetcher = fetcher
        self._cache_table = cache_table

    def get_status(self, asset_id: str, trade_date: date) -> str | None:
        """Get cached status. Returns None if not cached."""
        key = (asset_id, trade_date, "st")
        return self._cache.get(key)

    def set_status(self, asset_id: str, trade_date: date, status: str, source: str = "derived") -> None:
        """Cache a status value."""
        key = (asset_id, trade_date, "st")
        self._cache[key] = status

    def get_delist_date(self, asset_id: str) -> date | None:
        """Get delist date from cache or data source."""
        key = (asset_id, "delist_date")
        cached = self._cache.get(key)
        if cached:
            return date.fromisoformat(cached) if cached != "none" else None
        if self._fetcher:
            try:
                result = self._fetcher.get_delist_date(asset_id)
                self._cache[key] = result.isoformat() if result else "none"
                return result
            except Exception as e:
                logger.warning("Failed to fetch delist date for %s: %s", asset_id, e)
        self._cache[key] = "none"
        return None

    def fetch_and_cache_status(self, asset_ids: list[str], trade_date: date) -> dict[str, str]:
        """Batch fetch status for multiple assets. Returns {asset_id: status}."""
        results = {}
        uncached = []
        for aid in asset_ids:
            cached = self.get_status(aid, trade_date)
            if cached:
                results[aid] = cached
            else:
                uncached.append(aid)

        if uncached and self._fetcher:
            try:
                fetched = self._fetcher.fetch_st_status(uncached, trade_date)
                for aid, status in fetched.items():
                    self.set_status(aid, trade_date, status, "tushare")
                    results[aid] = status
            except Exception as e:
                logger.warning("Data fetch failed, falling back to derivation: %s", e)
                for aid in uncached:
                    derived = self._derive_status(aid)
                    self.set_status(aid, trade_date, derived, "derived")
                    results[aid] = derived

        return results

    def _derive_status(self, asset_id: str) -> str:
        """Runtime derivation fallback."""
        return AssetStatus.ACTIVE.value

    @staticmethod
    def _derive_st_from_name(name: str) -> AssetStatus:
        """Derive ST status from stock name."""
        if "*" in name and "ST" in name:
            return AssetStatus.STAR_ST
        if "ST" in name:
            return AssetStatus.ST
        return AssetStatus.ACTIVE
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest python/tests/unit/test_status_tracker.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add python/cquant/market_calendar/status_tracker.py python/tests/unit/test_status_tracker.py
git commit -m "feat(market_calendar): add status tracker with cache + data fetch + derivation"
```

---

### Task 5: 退市持仓处理器

**Files:**
- Create: `python/cquant/market_calendar/delist_handler.py`
- Test: `python/tests/unit/test_delist_handler.py`

- [ ] **Step 1: 编写退市处理测试**

```python
# python/tests/unit/test_delist_handler.py
from datetime import date
from cquant.market_calendar.delist_handler import DelistHandler, ForcedLiquidationTrade

class TestDelistHandler:
    def test_handle_delist_with_position(self):
        handler = DelistHandler()
        trades = handler.handle_delist(
            positions={"SH600000": 1000},
            asset_id="SH600000",
            trade_date=date(2026, 6, 1),
            price=5.0,
        )
        assert len(trades) == 1
        assert trades[0].side == "sell"
        assert trades[0].qty == 1000
        assert trades[0].price == 5.0
        assert trades[0].reason == "delist_forced_liquidation"

    def test_handle_delist_no_position(self):
        handler = DelistHandler()
        trades = handler.handle_delist(
            positions={},
            asset_id="SH600000",
            trade_date=date(2026, 6, 1),
            price=5.0,
        )
        assert len(trades) == 0

    def test_handle_delist_zero_quantity(self):
        handler = DelistHandler()
        trades = handler.handle_delist(
            positions={"SH600000": 0},
            asset_id="SH600000",
            trade_date=date(2026, 6, 1),
            price=5.0,
        )
        assert len(trades) == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest python/tests/unit/test_delist_handler.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现退市处理器**

```python
# python/cquant/market_calendar/delist_handler.py
"""Delist position handler — forced liquidation."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date


@dataclass
class ForcedLiquidationTrade:
    """A forced liquidation trade due to delisting."""
    asset_id: str
    trade_date: date
    side: str  # always "sell"
    qty: int
    price: float
    reason: str = "delist_forced_liquidation"


class DelistHandler:
    """Handles forced liquidation when a stock is delisted."""

    def handle_delist(
        self,
        positions: dict[str, int],
        asset_id: str,
        trade_date: date,
        price: float,
    ) -> list[ForcedLiquidationTrade]:
        """Generate forced sell trade for delisted stock.

        Args:
            positions: current portfolio positions {asset_id: quantity}
            asset_id: the delisted stock
            trade_date: date of delisting
            price: last available price for liquidation

        Returns:
            List of forced liquidation trades (empty if no position)
        """
        qty = positions.get(asset_id, 0)
        if qty <= 0:
            return []
        return [ForcedLiquidationTrade(
            asset_id=asset_id,
            trade_date=trade_date,
            side="sell",
            qty=qty,
            price=price,
            reason="delist_forced_liquidation",
        )]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest python/tests/unit/test_delist_handler.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add python/cquant/market_calendar/delist_handler.py python/tests/unit/test_delist_handler.py
git commit -m "feat(market_calendar): add delist handler for forced liquidation"
```

---

### Task 6: 扩展 TradingRules 基类 + 注册表

**Files:**
- Modify: `python/cquant/market_calendar/rules/base.py`
- Create: `python/cquant/market_calendar/registry.py`

- [ ] **Step 1: 扩展 TradingRules 基类**

在 `python/cquant/market_calendar/rules/base.py` 的 `TradingRules` 类中添加新方法：

```python
# 在现有方法之后添加
from cquant.market_calendar.limit_detector import detect_limit as _detect_limit, LimitStatus as _LimitStatus
from cquant.market_calendar.status_tracker import StatusTracker
from cquant.market_calendar.delist_handler import DelistHandler, ForcedLiquidationTrade

class TradingRules(ABC):
    # ... 现有 5 个方法保持不变 ...

    def __init__(self) -> None:
        self._status_tracker: StatusTracker | None = None
        self._delist_handler: DelistHandler = DelistHandler()

    def set_status_tracker(self, tracker: StatusTracker) -> None:
        """注入状态追踪器"""
        self._status_tracker = tracker

    def check_tradable(self, asset_id: str, trade_date, bar: dict) -> TradabilityResult:
        """综合可交易性检查。子类可覆盖。"""
        if self._status_tracker:
            status = self._status_tracker.get_status(asset_id, trade_date)
            if status == AssetStatus.DELISTED.value:
                return TradabilityResult(False, TradabilityReason.DELISTED)
        return TradabilityResult(True, TradabilityReason.TRADABLE)

    def detect_limit(self, bar: dict, pre_close: float, limit_pct: float) -> _LimitStatus:
        """检测涨跌停状态。委托给 limit_detector。"""
        return _detect_limit(bar, pre_close, limit_pct)

    def get_asset_status(self, asset_id: str, trade_date) -> str:
        """获取资产状态。子类应覆盖以接入数据源。"""
        if self._status_tracker:
            return self._status_tracker.get_status(asset_id, trade_date) or AssetStatus.ACTIVE.value
        return AssetStatus.ACTIVE.value

    def get_delist_date(self, asset_id: str):
        """获取退市日期。"""
        if self._status_tracker:
            return self._status_tracker.get_delist_date(asset_id)
        return None

    def handle_delist(self, positions: dict, asset_id: str, trade_date, price: float) -> list[ForcedLiquidationTrade]:
        """退市持仓强制平仓。"""
        return self._delist_handler.handle_delist(positions, asset_id, trade_date, price)
```

- [ ] **Step 2: 创建注册表**

```python
# python/cquant/market_calendar/registry.py
"""Market rules registry."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cquant.market_calendar.rules.base import TradingRules

_registry: dict[str, type[TradingRules]] = {}


def register_rules(market: str):
    """Decorator to register a TradingRules class for a market."""
    def decorator(cls):
        _registry[market.upper()] = cls
        return cls
    return decorator


def get_market_rules(market: str, config: dict) -> TradingRules:
    """Get a TradingRules instance for the given market."""
    market = market.upper()
    cls = _registry.get(market)
    if not cls:
        raise ValueError(f"No rules registered for market: {market}")
    return cls(config=config)


def list_registered_markets() -> list[str]:
    """List all registered market codes."""
    return list(_registry.keys())
```

- [ ] **Step 3: 运行测试确认无回归**

Run: `pytest python/tests/unit/test_market_calendar.py -v`
Expected: All existing tests still pass

- [ ] **Step 4: Commit**

```bash
git add python/cquant/market_calendar/rules/base.py python/cquant/market_calendar/registry.py
git commit -m "feat(market_calendar): extend TradingRules base + add registry"
```

---

### Task 7: 实现 CNTradingRules 扩展方法

**Files:**
- Modify: `python/cquant/market_calendar/rules/cn_rules.py`
- Test: `python/tests/unit/test_cn_trading_rules_v2.py`

- [ ] **Step 1: 编写 CNTradingRules 扩展测试**

```python
# python/tests/unit/test_cn_trading_rules_v2.py
from datetime import date
from decimal import Decimal
import pytest
from cquant.market_calendar.rules.cn_rules import CNTradingRules
from cquant.market_calendar.limit_detector import LimitStatus
from cquant.market_calendar.rules.base import TradabilityResult
from cquant.core.enums import AssetStatus, TradabilityReason

def _make_asset(asset_id="SH600000", status=AssetStatus.ACTIVE):
    """Create a minimal Asset-like object."""
    class A:
        pass
    a = A()
    a.asset_id = asset_id
    a.status = status
    a.lot_size = 100
    a.tick_size = Decimal("0.01")
    return a

def _bar(open_=10.0, high=10.5, low=9.5, close=10.2, volume=1000):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

class TestCNTradingRulesExtended:
    def setup_method(self):
        self.rules = CNTradingRules()

    def test_detect_limit_normal(self):
        bar = _bar(10.0, 10.3, 9.8, 10.1)
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.NONE

    def test_detect_limit_up(self):
        bar = _bar(10.5, 11.0, 10.5, 11.0)
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.UP

    def test_detect_yizi_up(self):
        bar = _bar(11.0, 11.0, 11.0, 11.0, volume=0)
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.YIZI_UP

    def test_check_tradable_active(self):
        bar = _bar()
        result = self.rules.check_tradable("SH600000", date(2026, 1, 2), bar)
        assert result.tradable is True
        assert result.reason == TradabilityReason.TRADABLE

    def test_get_asset_status_default(self):
        result = self.rules.get_asset_status("SH600000", date(2026, 1, 2))
        assert result == AssetStatus.ACTIVE.value

    def test_get_delist_date_default(self):
        result = self.rules.get_delist_date("SH600000")
        assert result is None

    def test_handle_delist(self):
        trades = self.rules.handle_delist({"SH600000": 1000}, "SH600000", date(2026, 1, 2), 5.0)
        assert len(trades) == 1
        assert trades[0].side == "sell"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest python/tests/unit/test_cn_trading_rules_v2.py -v`
Expected: FAIL (methods not implemented)

- [ ] **Step 3: 扩展 CNTradingRules**

在 `python/cquant/market_calendar/rules/cn_rules.py` 中：

1. 修改 `__init__` 接受 `config` 参数
2. 添加 `detect_limit`、`check_tradable`、`get_asset_status`、`get_delist_date`、`handle_delist` 方法
3. 添加 `_get_board` 和 `_get_limit_pct` 辅助方法

```python
# 在 CNTradingRules 类中添加

def __init__(self, suspension_lookup=None, ipo_dates=None, config=None):
    self._suspension_lookup = suspension_lookup
    self._ipo_dates = ipo_dates or {}
    self._config = config or {}
    super().__init__()

def _get_board(self, asset_id: str) -> str:
    code = asset_id.split(":")[-1] if ":" in asset_id else asset_id[2:]
    if code.startswith("688"): return "star"
    if code.startswith("300") or code.startswith("301"): return "chinext"
    return "main_board"

def _get_limit_pct(self, asset_id: str, is_st: bool = False) -> float:
    if is_st:
        return self._config.get("price_limits", {}).get("st", {}).get("up", 0.05)
    board = self._get_board(asset_id)
    defaults = {"main_board": 0.10, "chinext": 0.20, "star": 0.20}
    return self._config.get("price_limits", {}).get(board, {}).get("up", defaults.get(board, 0.10))

def detect_limit(self, bar, pre_close, limit_pct=None):
    if limit_pct is None:
        limit_pct = 0.10
    from cquant.market_calendar.limit_detector import detect_limit
    tolerance = self._config.get("derivation", {}).get("limit_tolerance", 0.99)
    return detect_limit(bar, pre_close, limit_pct, tolerance)

def check_tradable(self, asset_id, trade_date, bar):
    # Delegate to base for delist check
    base_result = super().check_tradable(asset_id, trade_date, bar)
    if not base_result.tradable:
        return base_result
    # Check suspension
    asset = _make_asset(asset_id)
    if self.is_suspended(asset, trade_date):
        return TradabilityResult(False, TradabilityReason.SUSPENDED)
    # Check limit
    pre_close = bar.get("pre_close", bar["close"])
    is_st = False
    if self._status_tracker:
        status = self._status_tracker.get_status(asset_id, trade_date)
        is_st = status in (AssetStatus.ST.value, AssetStatus.STAR_ST.value)
    limit_pct = self._get_limit_pct(asset_id, is_st)
    limit = self.detect_limit(bar, pre_close, limit_pct)
    if limit == LimitStatus.YIZI_UP:
        return TradabilityResult(False, TradabilityReason.YIZI_LIMIT, "一字涨停不可买入")
    if limit == LimitStatus.YIZI_DOWN:
        return TradabilityResult(False, TradabilityReason.YIZI_LIMIT, "一字跌停不可卖出")
    if limit == LimitStatus.UP:
        return TradabilityResult(False, TradabilityReason.LIMIT_UP)
    if limit == LimitStatus.DOWN:
        return TradabilityResult(False, TradabilityReason.LIMIT_DOWN)
    return TradabilityResult(True, TradabilityReason.TRADABLE)

def get_asset_status(self, asset_id, trade_date):
    if self._status_tracker:
        cached = self._status_tracker.get_status(asset_id, trade_date)
        if cached:
            return cached
    return AssetStatus.ACTIVE.value

def get_delist_date(self, asset_id):
    if self._status_tracker:
        return self._status_tracker.get_delist_date(asset_id)
    return None

def handle_delist(self, positions, asset_id, trade_date, price):
    return self._delist_handler.handle_delist(positions, asset_id, trade_date, price)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest python/tests/unit/test_cn_trading_rules_v2.py -v`
Expected: 7 passed

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `pytest python/tests/unit/test_market_calendar.py python/tests/unit/test_cn_trading_rules_v2.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add python/cquant/market_calendar/rules/cn_rules.py python/tests/unit/test_cn_trading_rules_v2.py
git commit -m "feat(market_calendar): implement CNTradingRules extended methods"
```

---

### Task 8: 更新导出 + 注册 CN 规则

**Files:**
- Modify: `python/cquant/market_calendar/__init__.py`
- Modify: `python/cquant/market_calendar/rules/cn_rules.py`（添加 @register_rules 装饰器）

- [ ] **Step 1: 在 cn_rules.py 添加注册装饰器**

```python
# 在文件顶部 import 之后添加
from cquant.market_calendar.registry import register_rules

# 修改类定义
@register_rules("CN")
class CNTradingRules(TradingRules):
    ...
```

- [ ] **Step 2: 更新 __init__.py 导出**

```python
# python/cquant/market_calendar/__init__.py
from cquant.market_calendar.service import MarketCalendarService
from cquant.market_calendar.rules.base import TradingRules, TradabilityResult
from cquant.market_calendar.adjustments.factor import AdjustmentFactor
from cquant.market_calendar.registry import get_market_rules, register_rules, list_registered_markets
from cquant.market_calendar.config_loader import load_market_config
from cquant.market_calendar.status_tracker import StatusTracker
from cquant.market_calendar.limit_detector import LimitStatus, detect_limit
from cquant.market_calendar.delist_handler import DelistHandler

__all__ = [
    "MarketCalendarService", "TradingRules", "TradabilityResult",
    "AdjustmentFactor", "get_market_rules", "register_rules",
    "list_registered_markets", "load_market_config", "StatusTracker",
    "LimitStatus", "detect_limit", "DelistHandler",
]
```

- [ ] **Step 3: 验证注册表工作**

Run: `python -c "from cquant.market_calendar import get_market_rules, load_market_config; r = get_market_rules('CN', load_market_config('CN')); print(type(r).__name__)"`
Expected: `CNTradingRules`

- [ ] **Step 4: Commit**

```bash
git add python/cquant/market_calendar/__init__.py python/cquant/market_calendar/rules/cn_rules.py
git commit -m "feat(market_calendar): register CN rules + update exports"
```

---

### Task 9: 回测引擎集成

**Files:**
- Modify: `python/cquant/backtest_vector/fill_simulator.py`
- Modify: `python/cquant/backtest_vector/limit_rules.py`

- [ ] **Step 1: 在 fill_simulator.py 导入新规则层**

在文件顶部添加导入：

```python
from cquant.market_calendar import get_market_rules, load_market_config, StatusTracker
from cquant.market_calendar.rules.base import TradabilityResult
from cquant.core.enums import TradabilityReason
```

- [ ] **Step 2: 修改 AShareFillSimulator.__init__ 接受 market 参数**

```python
def __init__(self, cost_model: CostModel | None = None, market: str = "CN", adj_type: str = "forward") -> None:
    self._cost_model = cost_model or CostModel.for_cn()
    config = load_market_config(market)
    self._rules = get_market_rules(market, config)
    self._adj_type = adj_type
    self._status_tracker = StatusTracker()
    self._rules.set_status_tracker(self._status_tracker)
```

- [ ] **Step 3: 修改 _calculate_sell_qty 和 _calculate_buy_qty 使用新规则**

在 `_calculate_sell_qty` 中，将现有的 `_is_suspended` 和 `_is_at_limit_down` 检查替换为：

```python
# 替换现有的 suspension + limit 检查
bar = {
    "open": self._get_price(td, asset_id, lookup, "open"),
    "high": self._get_price(td, asset_id, lookup, "high"),
    "low": self._get_price(td, asset_id, lookup, "low"),
    "close": self._get_price(td, asset_id, lookup, "close"),
    "volume": self._get_price(td, asset_id, lookup, "volume"),
}
result = self._rules.check_tradable(asset_id, td, bar)
if not result.tradable:
    if result.reason == TradabilityReason.DELISTED:
        # Handle delist
        forced = self._rules.handle_delist(positions, asset_id, td, bar["close"])
        # ... process forced trades
    return 0
```

在 `_calculate_buy_qty` 中做类似替换。

- [ ] **Step 4: 在 limit_rules.py 添加 deprecation 注释**

```python
# python/cquant/backtest_vector/limit_rules.py — 文件顶部添加
"""A-share daily price limit rules by board type.

.. deprecated::
    This module is superseded by cquant.market_calendar.limit_detector.
    New code should use the market_calendar module directly.
"""
```

- [ ] **Step 5: 运行现有回测测试确认无回归**

Run: `pytest python/tests/unit/ -k "backtest or fill" -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add python/cquant/backtest_vector/fill_simulator.py python/cquant/backtest_vector/limit_rules.py
git commit -m "feat(backtest): integrate market_calendar rules into fill simulator"
```

---

### Task 10: 端到端集成测试

**Files:**
- Test: `python/tests/integration/test_market_rules_e2e.py`

- [ ] **Step 1: 编写端到端集成测试**

```python
# python/tests/integration/test_market_rules_e2e.py
"""Integration test: market rules end-to-end flow."""
from datetime import date
from decimal import Decimal
from cquant.market_calendar import (
    get_market_rules, load_market_config, StatusTracker,
    LimitStatus, TradabilityResult,
)
from cquant.core.enums import AssetStatus, TradabilityReason

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

    def test_full_tradability_check_yizi_up(self):
        bar = {"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0, "volume": 0}
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

    def test_st_limit_5pct(self):
        self.tracker.set_status("SZ000001", date(2026, 1, 2), AssetStatus.ST.value)
        bar = {"open": 10.5, "high": 10.5, "low": 10.5, "close": 10.5, "volume": 0}
        result = self.rules.check_tradable("SZ000001", date(2026, 1, 2), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.YIZI_LIMIT

    def test_config_loaded_correctly(self):
        assert self.config["market"] == "CN"
        assert self.config["price_limits"]["main_board"]["up"] == 0.10
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest python/tests/integration/test_market_rules_e2e.py -v`
Expected: 5 passed

- [ ] **Step 3: 运行全量测试**

Run: `pytest python/tests/ -v --timeout=60`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add python/tests/integration/test_market_rules_e2e.py
git commit -m "test(market_calendar): add end-to-end integration tests"
```

---

## 验证清单

- [ ] `LimitStatus` / `TradabilityReason` / `TradabilityResult` 类型定义完整
- [ ] YAML 配置加载正常（CN/US/HK）
- [ ] 一字涨跌停检测正确
- [ ] ST/退市状态追踪 + 缓存 + 三级降级工作正常
- [ ] 退市持仓强制平仓逻辑正确
- [ ] TradingRules 基类扩展完整，CNTradingRules 实现全部方法
- [ ] 注册表工作正常
- [ ] fill_simulator 集成新规则层
- [ ] 端到端测试通过
- [ ] 所有现有测试无回归
