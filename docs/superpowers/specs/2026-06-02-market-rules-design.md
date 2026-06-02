# PRD v3.0 Phase 1: 市场规则模块化 设计文档

> **目标：** 将 A 股市场规则从散落的 building blocks 整合为可配置、可扩展的独立模块，覆盖 7 项缺口。
>
> **范围：** 复权因子集成、涨跌停状态（含一字板）、停牌、ST 状态、退市日期、退市持仓自动处理、市场规则 YAML 配置。
>
> **技术栈：** Python 3.12 + Polars + DuckDB + Tushare/AkShare（数据获取）

---

## 1. 背景与动机

cQuant 已有市场规则的 building blocks（`market_calendar`、`backtest_vector/fill_simulator`），但缺乏端到端集成：

| 功能 | 现状 | 缺口 |
|------|------|------|
| 复权因子 | silver 层存储 adj_factor，AdjustmentFactor 类可应用 | 回测引擎未自动调用 |
| 涨跌停状态 | limit_rules.py 可检测，但无持久化状态标记 | 未区分一字板，未集成到撮合 |
| 停牌 | is_suspended 字段存在，hook 注入机制存在 | 未在撮合流程中自动检查 |
| ST 状态 | AssetStatus 枚举存在，CNTradingRules 用它算涨跌停幅度 | 无历史 ST 状态追踪 |
| 退市日期 | 完全缺失 | 无 delist_date 字段或查询 |
| 一字涨跌停不可成交 | 完全缺失 | fill_simulator 不区分一字板 |
| 退市持仓自动处理 | 完全缺失 | 无强制平仓逻辑 |

---

## 2. 模块架构

### 2.1 目录结构

```
python/cquant/market_rules/
├── __init__.py              # 导出 MarketRule, MarketRegistry, get_market_rule
├── base.py                  # MarketRule 抽象基类 + 数据类
├── registry.py              # 规则注册表
├── adjustments.py           # 复权逻辑（前/后/不复权）
├── limit_detector.py        # 涨跌停检测（含一字板）
├── status_tracker.py        # ST/退市状态追踪（数据获取 + 运行时推导）
├── delist_handler.py        # 退市持仓自动处理
├── data_fetcher.py          # Tushare/AkShare 数据获取 + 频率控制 + 缓存
├── rules/
│   ├── __init__.py
│   ├── cn_rules.py          # A 股规则实现
│   ├── us_rules.py          # 美股规则（桩）
│   └── hk_rules.py          # 港股规则（桩）
configs/markets/
├── cn.yml                   # A 股配置
├── us.yml                   # 美股配置
└── hk.yml                   # 港股配置
```

### 2.2 核心接口

```python
# base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import date
import polars as pl

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

class AssetStatus(Enum):
    ACTIVE = "active"
    ST = "st"
    STAR_ST = "star_st"
    DELISTED = "delisted"

@dataclass
class MarketConfig:
    market: str                    # "CN", "US", "HK"
    name: str                      # "A股"
    price_limits: dict             # {"main_board": {"up": 0.10, "down": 0.10}, ...}
    settlement: str                # "T+1"
    lot_size: int                  # 100
    tick_size: float               # 0.01
    adjustment_default: str        # "forward"
    data_source_primary: str       # "tushare"
    data_source_fallback: str      # "akshare"
    rate_limit: dict               # {"tushare": {"qps": 200, "burst": 50}}

class MarketRule(ABC):
    """市场规则抽象基类。每个市场实现一个子类。"""

    def __init__(self, config: MarketConfig):
        self.config = config

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
    def get_asset_status(self, asset_id: str, trade_date: date) -> AssetStatus:
        """获取资产状态（ACTIVE/ST/DELISTED）"""

    @abstractmethod
    def get_delist_date(self, asset_id: str) -> date | None:
        """获取退市日期"""

    @abstractmethod
    def handle_delist(self, portfolio, asset_id: str, trade_date: date, price: float) -> list:
        """退市持仓自动处理，返回强制平仓交易列表"""

    def get_price_limit(self, asset_status: AssetStatus, board: str) -> tuple[float, float]:
        """根据资产状态和板块获取涨跌停幅度"""
        limits = self.config.price_limits
        if asset_status in (AssetStatus.ST, AssetStatus.STAR_ST):
            cfg = limits.get("st", limits.get("main_board"))
        else:
            cfg = limits.get(board, limits.get("main_board"))
        return (-cfg["down"], cfg["up"])
```

### 2.3 注册表

```python
# registry.py
_registry: dict[str, type[MarketRule]] = {}

def register_market_rule(market: str):
    """装饰器，注册市场规则类"""
    def decorator(cls):
        _registry[market] = cls
        return cls
    return decorator

def get_market_rule(market: str, config: MarketConfig) -> MarketRule:
    cls = _registry.get(market)
    if not cls:
        raise ValueError(f"No market rule registered for {market}")
    return cls(config)

def load_market_config(market: str) -> MarketConfig:
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

## 4. A 股规则实现 (`cn_rules.py`)

### 4.1 CNMarketRule

```python
@register_market_rule("CN")
class CNMarketRule(MarketRule):

    def check_tradable(self, asset_id, trade_date, bar):
        # 1. 交易日检查
        if not self._is_trading_day(trade_date):
            return TradabilityResult(False, TradabilityReason.NOT_TRADING_DAY)

        # 2. 停牌检查
        if self._is_suspended(asset_id, trade_date, bar):
            return TradabilityResult(False, TradabilityReason.SUSPENDED)

        # 3. 退市检查
        status = self.get_asset_status(asset_id, trade_date)
        if status == AssetStatus.DELISTED:
            return TradabilityResult(False, TradabilityReason.DELISTED)

        # 4. 涨跌停检查（含一字板）
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
        _, up_limit = self.get_price_limit(asset_status, self._get_board(bar["asset_id"]))

        # 一字板检测：开盘=收盘=最高=最低 且 触及涨跌停
        is_yizi = (bar["open"] == bar["close"] == bar["high"] == bar["low"])
        if change_pct >= up_limit * 0.99:
            return LimitStatus.YIZI_UP if is_yizi else LimitStatus.UP
        if change_pct <= -up_limit * 0.99:  # A 股涨跌停对称
            return LimitStatus.YIZI_DOWN if is_yizi else LimitStatus.DOWN
        return LimitStatus.NONE

    def apply_adjustment(self, df, adj_type):
        if adj_type == "none":
            return df
        return AdjustmentFactor.apply(df, adj_type, self.config)

    def get_asset_status(self, asset_id, trade_date):
        # 1. 查缓存
        cached = self._cache_get(asset_id, trade_date, "st")
        if cached:
            return AssetStatus(cached)
        # 2. 查数据源
        status = self._fetcher.get_asset_status(asset_id, trade_date)
        if status:
            self._cache_set(asset_id, trade_date, "st", status.value)
            return status
        # 3. 运行时推导
        return self._derive_asset_status(asset_id, trade_date)

    def handle_delist(self, portfolio, asset_id, trade_date, price):
        """退市持仓强制平仓"""
        position = portfolio.get_position(asset_id)
        if not position or position.quantity <= 0:
            return []
        # 强制以最后可交易价格平仓
        trade = Trade(
            asset_id=asset_id,
            date=trade_date,
            side="sell",
            quantity=position.quantity,
            price=price,
            reason="delist_forced_liquidation"
        )
        portfolio.apply_trade(trade)
        return [trade]

    def _get_board(self, asset_id: str) -> str:
        """根据股票代码判断板块"""
        code = asset_id.split(".")[0]
        if code.startswith("688"):
            return "star"       # 科创板
        if code.startswith("300") or code.startswith("301"):
            return "chinext"    # 创业板
        return "main_board"     # 主板
```

---

## 5. 回测引擎集成

### 5.1 FillSimulator 改造

修改 `python/cquant/backtest_vector/fill_simulator.py`：

```python
class AShareFillSimulator:
    def __init__(self, market_rule: MarketRule | None = None, adj_type: str = "forward"):
        self.rule = market_rule or get_market_rule("CN", load_market_config("CN"))
        self.adj_type = adj_type

    def simulate_fills(self, signals: list, portfolio, market_data: dict, trade_date) -> list:
        fills = []
        for signal in signals:
            bar = market_data.get(signal.asset_id, {}).get(trade_date)
            if not bar:
                continue

            # 1. 复权处理
            adj_close = self.rule.apply_adjustment(
                pl.DataFrame([bar]), self.adj_type
            ).row(0, named=True)["close"]

            # 2. 综合可交易性检查
            result = self.rule.check_tradable(signal.asset_id, trade_date, bar)
            if not result.tradable:
                continue

            # 3. 退市处理（卖出信号）
            if signal.side == "sell":
                status = self.rule.get_asset_status(signal.asset_id, trade_date)
                if status == AssetStatus.DELISTED:
                    forced = self.rule.handle_delist(portfolio, signal.asset_id, trade_date, adj_close)
                    fills.extend(forced)
                    continue

            # 4. 正常撮合（现有逻辑）
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

- [ ] MarketRule 基类定义完整，CNMarketRule 实现全部 7 项市场规则
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
