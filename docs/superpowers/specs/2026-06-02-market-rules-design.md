# PRD v3.0 Phase 1: 市场规则模块化 设计文档

> **目标：** 扩展已有 `market_calendar` 模块，补齐 7 项 A 股市场规则缺口，使其成为回测引擎的统一规则层。
>
> **范围：** 复权因子集成、涨跌停状态（含一字板）、停牌、ST 状态、退市日期、退市持仓自动处理、市场规则 YAML 配置。
>
> **技术栈：** Python 3.12 + Polars + DuckDB + Tushare/AkShare（数据获取）

---

## 1. 背景与动机

cQuant 已有 `market_calendar` 模块（780 行，13 文件），包含日历查询、交易规则（`TradingRules`）、复权因子（`AdjustmentFactor`）。但该模块**未被任何生产代码导入**（仅测试使用），且缺乏端到端集成：

| 功能 | 现状 | 缺口 |
|------|------|------|
| 复权因子 | `AdjustmentFactor` 类可应用 | 回测引擎未自动调用 |
| 涨跌停状态 | `CNTradingRules.price_limit` 可检测 | 未区分一字板，未集成到撮合 |
| 停牌 | `is_suspended` 字段存在 | 未在撮合流程中自动检查 |
| ST 状态 | `AssetStatus` 枚举 + `CNTradingRules` 用它算幅度 | 无历史 ST 状态追踪 |
| 退市日期 | 完全缺失 | 无 delist_date 字段或查询 |
| 一字涨跌停不可成交 | 完全缺失 | fill_simulator 不区分一字板 |
| 退市持仓自动处理 | 完全缺失 | 无强制平仓逻辑 |

**决策：扩展 `market_calendar`，不新建并行模块。** 理由：
- 已有良好结构（calendars/rules/adjustments 分层）
- 已有测试覆盖
- 无生产代码依赖，重构安全
- 避免重复造轮子

---

## 2. 模块架构

### 2.1 目录结构（扩展后）

```
python/cquant/market_calendar/
├── __init__.py                # 更新导出：新增 MarketRule, get_market_rule
├── service.py                 # MarketCalendarService（保持不变）
├── config_loader.py           # [新增] YAML 配置加载
├── registry.py                # [新增] 规则注册表
├── status_tracker.py          # [新增] ST/退市状态追踪 + 数据获取 + 缓存
├── delist_handler.py          # [新增] 退市持仓自动处理
├── limit_detector.py          # [新增] 涨跌停检测（含一字板）
├── adjustments/
│   └── factor.py              # 复权逻辑（保持不变）
├── calendars/
│   ├── base.py                # TradingCalendar（保持不变）
│   ├── cn.py                  # CNCalendar（保持不变）
│   ├── us.py                  # USCalendar（保持不变）
│   └── hk.py                  # HKCalendar（保持不变）
├── rules/
│   ├── base.py                # [扩展] TradingRules → 增加 check_tradable, detect_limit, handle_delist
│   ├── cn_rules.py            # [扩展] CNTradingRules → 实现全部 7 项市场规则
│   ├── us_rules.py            # [桩] US 扩展
│   └── hk_rules.py            # [桩] HK 扩展
configs/markets/
├── cn.yml                     # [新增] A 股配置
├── us.yml                     # [新增] 美股配置
└── hk.yml                     # [新增] 港股配置
```

### 2.2 核心接口

扩展现有 `rules/base.py` 的 `TradingRules` 基类，新增方法：

```python
# rules/base.py（扩展）
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import date
import polars as pl

# --- 新增枚举和数据类 ---

class LimitStatus(Enum):
    NONE = "none"
    UP = "up"
    DOWN = "down"
    YIZI_UP = "yizi_up"      # 一字涨停（开盘=收盘=最高=最低=涨停价）
    YIZI_DOWN = "yizi_down"  # 一字跌停

class TradabilityReason(Enum):
    TRADABLE = "tradable"
    SUSPENDED = "suspended"
    LIMIT_UP = "limit_up"
    LIMIT_DOWN = "limit_down"
    YIZI_LIMIT = "yizi_limit"
    DELISTED = "delisted"
    NOT_TRADING_DAY = "not_trading_day"

@dataclass
class TradabilityResult:
    tradable: bool
    reason: TradabilityReason
    message: str = ""

# --- TradingRules 扩展 ---

class TradingRules(ABC):
    """交易规则基类（扩展版）"""

    def __init__(self, config: dict):
        self.config = config  # 从 YAML 加载的配置

    # --- 保留现有方法 ---
    @abstractmethod
    def price_limit(self, asset_status, board) -> tuple[float, float]: ...
    @abstractmethod
    def is_suspended(self, asset_id, date) -> bool: ...
    @abstractmethod
    def lot_size(self) -> int: ...
    @abstractmethod
    def tick_size(self) -> float: ...
    @abstractmethod
    def settlement_lag(self) -> int: ...

    # --- 新增方法 ---
    @abstractmethod
    def check_tradable(self, asset_id: str, trade_date: date, bar: dict) -> TradabilityResult:
        """综合可交易性检查：停牌、涨跌停、退市等"""

    @abstractmethod
    def detect_limit(self, bar: dict, pre_close: float) -> LimitStatus:
        """检测涨跌停状态（含一字板）"""

    @abstractmethod
    def apply_adjustment(self, df: pl.DataFrame, adj_type: str) -> pl.DataFrame:
        """应用复权因子"""

    @abstractmethod
    def get_asset_status(self, asset_id: str, trade_date: date) -> str:
        """获取资产状态（'active'/'st'/'delisted'）"""

    @abstractmethod
    def get_delist_date(self, asset_id: str) -> date | None:
        """获取退市日期"""

    @abstractmethod
    def handle_delist(self, portfolio, asset_id: str, trade_date: date, price: float) -> list:
        """退市持仓自动处理，返回强制平仓交易列表"""
```

### 2.3 注册表

```python
# registry.py（新增）
_registry: dict[str, type[TradingRules]] = {}

def register_rules(market: str):
    """装饰器，注册市场规则类"""
    def decorator(cls):
        _registry[market] = cls
        return cls
    return decorator

def get_market_rules(market: str, config: dict) -> TradingRules:
    cls = _registry.get(market)
    if not cls:
        raise ValueError(f"No rules registered for market: {market}")
    return cls(config)

def load_market_config(market: str) -> dict:
    """从 configs/markets/{market}.yml 加载配置"""
    ...
```

---

## 3. 数据获取策略

### 3.1 三级降级

```
Tushare API (主)
  ├─ pro.st_basic()       → ST/退市基础信息
  ├─ pro.delist_date()    → 退市日期
  ├─ pro.limit_list()     → 涨跌停列表
  ├─ pro.adj_factor()     → 复权因子
  ├─ pro.suspend_d()      → 停牌信息
  │
  ├─ 频率控制: asyncio.Semaphore (QPS 从 cn.yml 读取)
  ├─ 大数据量: ThreadPoolExecutor 并行分页
  │
AkShare (备)
  ├─ ak.stock_st_info()           → ST 列表
  ├─ ak.stock_delisting_stock()   → 退市列表
  ├─ ak.stock_zt_pool_em()        → 涨停池
  ├─ ak.stock_dt_pool_em()        → 跌停池
  │
运行时推导 (兜底)
  ├─ detect_limit:  abs(close / pre_close - 1) >= limit_pct * 0.99
  ├─ detect_yizi:   open == close == high == low && limit_hit
  ├─ detect_st:     股票名称包含 "ST" 或 "*ST"
  └─ detect_delist: 连续 30 天停牌 + 无成交量
```

### 3.2 缓存层

DuckDB 表 `market_status_cache`：

```sql
CREATE TABLE IF NOT EXISTS market_status_cache (
    asset_id     VARCHAR NOT NULL,
    trade_date   DATE NOT NULL,
    status_type  VARCHAR NOT NULL,  -- 'st', 'delist', 'limit', 'suspend', 'adj'
    status_value VARCHAR NOT NULL,  -- JSON 值
    source       VARCHAR NOT NULL,  -- 'tushare', 'akshare', 'derived'
    fetched_at   TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (asset_id, trade_date, status_type)
);
```

- 查询时先查缓存，命中则直接返回
- 缓存未命中 → 调用数据源 → 写入缓存 → 返回
- 缓存过期策略：每日首次查询时刷新当天数据

### 3.3 频率控制

```python
# data_fetcher.py
class RateLimiter:
    """令牌桶限流器"""
    def __init__(self, qps: int, burst: int):
        self.qps = qps
        self.burst = burst
        self._semaphore = asyncio.Semaphore(burst)
        self._tokens = burst
        self._last_refill = time.monotonic()

    async def acquire(self):
        self._refill()
        await self._semaphore.acquire()

class MarketDataFetcher:
    """统一数据获取入口"""
    async def fetch_st_status(self, asset_ids: list[str]) -> pl.DataFrame:
        """获取 ST 状态，三级降级"""
        try:
            return await self._fetch_tushare_st(asset_ids)
        except (RateLimitError, APIError):
            try:
                return await self._fetch_akshare_st(asset_ids)
            except Exception:
                return self._derive_st_status(asset_ids)

    async def fetch_delist_dates(self, asset_ids: list[str]) -> pl.DataFrame:
        """获取退市日期，三级降级"""
        ...

    async def fetch_limit_list(self, trade_date: date) -> pl.DataFrame:
        """获取涨跌停列表，三级降级"""
        ...

    async def fetch_adj_factors(self, asset_ids: list[str], start: date, end: date) -> pl.DataFrame:
        """获取复权因子，三级降级"""
        ...
```

---

## 4. A 股规则实现（扩展 `cn_rules.py`）

扩展现有 `CNTradingRules` 类，新增 7 项方法：

```python
# rules/cn_rules.py（扩展）
@register_rules("CN")
class CNTradingRules(TradingRules):

    # --- 保留现有方法（price_limit, is_suspended, lot_size, tick_size, settlement_lag）---

    # --- 新增方法 ---

    def check_tradable(self, asset_id, trade_date, bar):
        if not self._is_trading_day(trade_date):
            return TradabilityResult(False, TradabilityReason.NOT_TRADING_DAY)
        if self.is_suspended(asset_id, trade_date):
            return TradabilityResult(False, TradabilityReason.SUSPENDED)
        status = self.get_asset_status(asset_id, trade_date)
        if status == "delisted":
            return TradabilityResult(False, TradabilityReason.DELISTED)
        pre_close = bar.get("pre_close", bar["close"])
        limit = self.detect_limit(bar, pre_close)
        if limit == LimitStatus.YIZI_UP:
            return TradabilityResult(False, TradabilityReason.YIZI_LIMIT, "一字涨停不可买入")
        if limit == LimitStatus.YIZI_DOWN:
            return TradabilityResult(False, TradabilityReason.YIZI_LIMIT, "一字跌停不可卖出")
        return TradabilityResult(True, TradabilityReason.TRADABLE)

    def detect_limit(self, bar, pre_close):
        if pre_close <= 0:
            return LimitStatus.NONE
        change_pct = (bar["close"] - pre_close) / pre_close
        asset_status = self.get_asset_status(bar["asset_id"], bar["trade_date"])
        _, up_limit = self.price_limit(asset_status, self._get_board(bar["asset_id"]))
        is_yizi = (bar["open"] == bar["close"] == bar["high"] == bar["low"])
        if change_pct >= up_limit * 0.99:
            return LimitStatus.YIZI_UP if is_yizi else LimitStatus.UP
        if change_pct <= -up_limit * 0.99:
            return LimitStatus.YIZI_DOWN if is_yizi else LimitStatus.DOWN
        return LimitStatus.NONE

    def apply_adjustment(self, df, adj_type):
        if adj_type == "none":
            return df
        return AdjustmentFactor.apply(df, adj_type)

    def get_asset_status(self, asset_id, trade_date):
        # 1. 查缓存 → 2. 查数据源 → 3. 运行时推导
        cached = self._tracker.get_status(asset_id, trade_date)
        if cached:
            return cached
        return self._tracker.derive_status(asset_id, trade_date)

    def get_delist_date(self, asset_id):
        return self._tracker.get_delist_date(asset_id)

    def handle_delist(self, portfolio, asset_id, trade_date, price):
        position = portfolio.get_position(asset_id)
        if not position or position.quantity <= 0:
            return []
        trade = Trade(asset_id=asset_id, date=trade_date, side="sell",
                      quantity=position.quantity, price=price,
                      reason="delist_forced_liquidation")
        portfolio.apply_trade(trade)
        return [trade]

    def _get_board(self, asset_id: str) -> str:
        code = asset_id.split(".")[0]
        if code.startswith("688"): return "star"
        if code.startswith("300") or code.startswith("301"): return "chinext"
        return "main_board"
```

---

## 5. 回测引擎集成

### 5.1 FillSimulator 改造

修改 `python/cquant/backtest_vector/fill_simulator.py`：

```python
from cquant.market_calendar import get_market_rules, load_market_config

class AShareFillSimulator:
    def __init__(self, market: str = "CN", adj_type: str = "forward"):
        config = load_market_config(market)
        self.rules = get_market_rules(market, config)
        self.adj_type = adj_type

    def simulate_fills(self, signals: list, portfolio, market_data: dict, trade_date) -> list:
        fills = []
        for signal in signals:
            bar = market_data.get(signal.asset_id, {}).get(trade_date)
            if not bar:
                continue

            # 1. 综合可交易性检查（停牌、涨跌停、退市）
            result = self.rules.check_tradable(signal.asset_id, trade_date, bar)
            if not result.tradable:
                # 退市持仓强制平仓
                if result.reason == TradabilityReason.DELISTED and signal.side == "sell":
                    forced = self.rules.handle_delist(portfolio, signal.asset_id, trade_date, bar["close"])
                    fills.extend(forced)
                continue

            # 2. 复权处理
            adj_close = self.rules.apply_adjustment(
                pl.DataFrame([bar]), self.adj_type
            ).row(0, named=True)["close"]

            # 3. 正常撮合（现有逻辑）
            fill = self._match_order(signal, bar, adj_close, portfolio)
            if fill:
                fills.append(fill)

        return fills
```

### 5.2 策略配置扩展

`PUT /strategies/{id}` 新增字段：

```json
{
  "market_rule": {
    "market": "CN",
    "adj_type": "forward",
    "config_override": null
  }
}
```

- `market`: 市场代码，决定使用哪个 MarketRule
- `adj_type`: 复权方式（forward/backward/none）
- `config_override`: 可选，覆盖 YAML 配置中的默认参数

---

## 6. 前端改动

### 6.1 策略配置页

在策略配置表单中新增「市场规则」区块：

- 复权方式下拉框：前复权 / 后复权 / 不复权
- 市场选择：A 股 / 美股 / 港股（影响涨跌停规则、T+N 结算等）

### 6.2 回测结果页

- 复权方式显示在回测参数摘要中
- 退市强制平仓事件在交易明细中标记（reason: "delist_forced_liquidation"）

---

## 7. 配置文件

### `configs/markets/cn.yml`

```yaml
market: CN
name: A股

price_limits:
  main_board: { up: 0.10, down: 0.10 }
  st: { up: 0.05, down: 0.05 }
  chinext: { up: 0.20, down: 0.20 }
  star: { up: 0.20, down: 0.20 }
  ipo_first_days: unlimited

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
  limit_tolerance: 0.99       # 涨跌停检测容差
  delist_suspend_days: 30     # 连续停牌 N 天推导为退市
```

### `configs/markets/us.yml`（桩）

```yaml
market: US
name: 美股

price_limits: {}               # 无涨跌停
settlement: T+2
lot_size: 1
tick_size: 0.01

adjustment:
  default: forward
  options: [forward, backward, none]

data_source:
  primary: tushare             # 暂用 Tushare 美股接口
  fallback: null
```

---

## 8. 测试策略

| 层级 | 框架 | 内容 |
|------|------|------|
| 单元测试 | pytest | LimitDetector（一字板、普通涨跌停、非涨跌停）、AdjustmentFactor（前/后复权）、StatusTracker（ST/退市推导） |
| 集成测试 | pytest | CNMarketRule 端到端：输入 bar → 输出 TradabilityResult + LimitStatus |
| 数据测试 | pytest | MarketDataFetcher：Tushare 获取 → 缓存写入 → 缓存命中；降级到 AkShare；降级到运行时推导 |
| 回测对比 | pytest | 同策略开启/关闭市场规则 → 验证差异（涨停不可买、退市平仓） |
| E2E | Playwright | 策略配置选择复权方式 → 回测 → 验证参数摘要显示 |

---

## 9. 验收标准

- [ ] TradingRules 基类扩展完整，CNTradingRules 实现全部 7 项市场规则
- [ ] YAML 配置加载正常，可覆盖默认参数
- [ ] Tushare 数据获取 + 频率控制 + 缓存工作正常
- [ ] AkShare 降级获取正常
- [ ] 运行时推导兜底正常（limit/yizi/st/delist）
- [ ] 复权因子在回测中自动应用（前/后/不复权可切换）
- [ ] 一字涨跌停检测正确，不可成交
- [ ] 退市持仓强制平仓逻辑正确
- [ ] ST 状态影响涨跌停幅度（±5%）
- [ ] 策略配置页支持选择市场和复权方式
- [ ] 回测结果页显示复权方式和退市事件
- [ ] 所有新模块有单元测试，回测对比测试通过
