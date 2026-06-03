# PRD v3.0 Phase 3: TCA + Brinson 归因 设计文档

> **目标：** 将已实现但未接入的 TCA 和 Brinson 归因模块串联到回测流水线，新增前端展示 Tab。
>
> **范围：** 后端集成 `TransactionCostAnalyzer` + 增强 `BrinsonAttribution`；前端新增「成本分析」和「归因分析」Tab；API 新增端点。
>
> **技术栈：** Python 3.12 + Polars + FastAPI + React 18 + TypeScript + TanStack Query

---

## 1. 背景与动机

### 现状

| 组件 | 文件 | 状态 |
|------|------|------|
| `TransactionCostAnalyzer` | `backtest_vector/tca.py` | **已实现，未接入** |
| `BrinsonAttribution` | `bt_analyzer/attribution.py` | **已实现，弱集成** |
| `FactorAttribution` | `bt_analyzer/attribution.py` | 已定义，从未调用 |
| `AnalysisEngine` | `bt_analyzer/engine.py` | 调用 Brinson 但有严重局限 |
| 前端 BacktestsPage | `web/src/pages/BacktestsPage.tsx` | 无 TCA/归因 Tab |

### 问题

1. **TCA 完全断连**：`TransactionCostAnalyzer` 写好了 4 个方法（`analyze`/`analyze_by_asset`/`analyze_by_date`/`generate_report`），但 `AnalysisEngine.run()` 从未调用，`BacktestResult` 没有 `tca_summary` 字段，API 无端点，前端无展示。

2. **Brinson 归因质量差**：
   - 只有单期汇总（全期间平均权重 × 全期间收益），无逐日归因
   - 基准权重用等权 fallback（`{a: 1/n for a in assets}`），不是真实基准
   - `benchmark_returns` 直接用 `asset_returns`（即 portfolio 和 benchmark 完全相同），归因结果无意义
   - `sector_map` 未传入，每个资产被当作独立"行业"

3. **前端零展示**：用户跑完回测看不到成本分解，也看不到收益归因。

---

## 2. 设计方案

### 2.1 后端：串联 TCA

**改动文件：** `bt_analyzer/engine.py`、`bt_analyzer/models.py`

在 `AnalysisEngine.run()` 中，Brinson 归因之前，调用 `TransactionCostAnalyzer`：

```python
from cquant.backtest_vector.tca import TransactionCostAnalyzer

tca_analyzer = TransactionCostAnalyzer()
tca_summary = tca_analyzer.analyze(result.fills)
tca_by_asset = tca_analyzer.analyze_by_asset(result.fills)
tca_by_date = tca_analyzer.analyze_by_date(result.fills)
```

将结果写入 `AnalysisReport` 新增字段：

```python
@dataclass
class AnalysisReport:
    # ... existing fields ...
    tca_summary: "TCASummary | None" = None
    tca_by_asset: "list[TCADetail] | None" = None
    tca_by_date: "list[TCADetail] | None" = None
```

**无需改动 `tca.py`** — 代码已完备，只需串联。

### 2.2 后端：增强 Brinson 归因

**改动文件：** `bt_analyzer/engine.py`

当前 `AnalysisEngine.run()` 的 Brinson 逻辑（第 78-117 行）有三个问题需要修复：

#### 问题 1：基准权重是等权 fallback

**修复：** 支持从 `BacktestSpec.benchmark_asset_id` 获取真实基准。如果用户指定了基准（如沪深300 ETF），从价格数据计算基准成分权重；否则降级为等权。

```python
def _compute_benchmark_weights(
    self,
    assets: list[str],
    prices: pl.DataFrame,
    benchmark_asset_id: str,
) -> dict[str, float]:
    """Compute benchmark weights. If benchmark_asset_id is a single asset (ETF),
    use equal weights for the universe. If it's a universe, compute from market cap."""
    # For single benchmark asset (e.g. 000300.SH ETF), use equal weights
    # This is a pragmatic simplification — real index weights require external data
    return {a: 1.0 / len(assets) for a in assets}
```

> **注意：** 真正的指数成分权重需要外部数据（如 Wind/Tushare 的 index_weight 接口）。当前阶段使用等权是合理的降级策略，后续可通过 `extra["benchmark_weights"]` 注入真实权重。

#### 问题 2：benchmark_returns = portfolio_returns

**修复：** 从 `spec.prices` 中基准资产的价格计算 benchmark returns。如果 `benchmark_asset_id` 为空，使用 universe 内资产的等权收益作为基准。

```python
# 计算每个资产在回测期间的收益
asset_returns = {}
for a in assets:
    apx = prices_df.filter(pl.col("asset_id") == a).sort("trade_date")
    if len(apx) >= 2:
        asset_returns[a] = float(apx["close"][-1]) / float(apx["close"][0]) - 1

# 基准收益 = 等权组合收益（如果不是单资产基准）
bench_returns = {a: sum(asset_returns.values()) / len(asset_returns) for a in assets}
```

#### 问题 3：只有单期汇总

**修复：** 新增逐日归因逻辑。将回测期间按调仓日分段，每个区间做一次 Brinson 归因，生成时间序列。

```python
def _compute_daily_brinson(
    self,
    positions: pl.DataFrame,
    prices: pl.DataFrame,
    benchmark_weights: dict[str, float],
) -> list[dict]:
    """Compute Brinson attribution for each rebalance period."""
    dates = sorted(positions["trade_date"].unique().to_list())
    results = []
    for i in range(len(dates) - 1):
        td = dates[i]
        next_td = dates[i + 1]
        # Get portfolio weights at td
        pos = positions.filter(pl.col("trade_date") == td)
        port_weights = dict(zip(pos["asset_id"], pos["target_weight"]))
        # Compute returns between td and next_td
        ...
        results.append({
            "date": next_td,
            "allocation": alloc,
            "selection": selec,
            "interaction": inter,
        })
    return results
```

### 2.3 API 端点

**改动文件：** `api_server/routes/backtests.py`

新增两个端点：

```python
@router.get("/{run_id}/tca")
async def get_tca(run_id: str):
    """Return TCA summary for a backtest run."""
    # 从 AnalysisReport 中获取 TCA 数据
    # 如果 AnalysisReport 不存在，实时计算


@router.get("/{run_id}/attribution")
async def get_attribution(run_id: str):
    """Return Brinson attribution for a backtest run."""
    # 从 AnalysisReport 中获取归因数据
```

**响应格式：**

```json
// GET /backtests/{run_id}/tca
{
  "summary": {
    "total_turnover": 5000000,
    "total_commission": 1500,
    "total_stamp_duty": 2500,
    "total_slippage": 500,
    "total_cost": 4500,
    "cost_per_trade": 45,
    "cost_as_pct_turnover": 0.09,
    "num_trades": 100,
    "avg_trade_size": 50000
  },
  "by_asset": [
    {"asset_id": "SSE:600036", "turnover": 500000, "commission": 150, "stamp_duty": 250, "slippage": 50, "total_cost": 450, "cost_pct": 0.09, "num_trades": 10}
  ],
  "by_date": [
    {"trade_date": "2025-06-01", "turnover": 100000, "commission": 30, "stamp_duty": 50, "slippage": 10, "total_cost": 90, "cost_pct": 0.09, "num_trades": 2}
  ]
}

// GET /backtests/{run_id}/attribution
{
  "summary": {
    "total_return": 0.15,
    "benchmark_return": 0.10,
    "active_return": 0.05,
    "allocation_effect": 0.02,
    "selection_effect": 0.025,
    "interaction_effect": 0.005
  },
  "daily": [
    {"date": "2025-06-02", "allocation": 0.001, "selection": 0.002, "interaction": 0.0005}
  ],
  "sector_details": {
    "Finance": {"port_weight": 0.3, "bench_weight": 0.25, "port_return": 0.05, "bench_return": 0.04}
  }
}
```

### 2.4 前端：新增 Tab

**改动文件：** `web/src/pages/BacktestsPage.tsx`

#### Tab 类型扩展

```tsx
type Tab = 'overview' | 'tearsheet' | 'overfitting' | 'fills' | 'walkforward' | 'tca' | 'attribution'
```

#### 「成本分析」Tab 内容

1. **成本概览卡片**（4 格 grid）：
   - 总成本（元）
   - 成本率（% of turnover）
   - 交易笔数
   - 平均每笔成本

2. **成本分解饼图**：佣金 / 印花税 / 滑点 三部分

3. **按资产成本排名表**：DataTable，列 = 资产、成交额、佣金、印花税、滑点、总成本、成本率

4. **成本趋势折线图**：每日总成本折线

#### 「归因分析」Tab 内容

1. **归因概览卡片**（4 格 grid）：
   - 累计超额收益
   - Allocation Effect
   - Selection Effect
   - Interaction Effect

2. **归因堆叠面积图**：逐日三效应累计曲线

3. **行业归因明细表**：DataTable，列 = 行业、组合权重、基准权重、组合收益、基准收益、Allocation、Selection、Interaction

### 2.5 数据流

```
BacktestResult.fills
    └── TransactionCostAnalyzer.analyze() ──→ TCASummary
    └── .analyze_by_asset() ──→ list[TCADetail]
    └── .analyze_by_date() ──→ list[TCADetail]
                │
                ▼
    AnalysisReport.tca_summary / tca_by_asset / tca_by_date
                │
                ▼
    API: GET /backtests/{run_id}/tca
                │
                ▼
    Frontend: TCA Tab (cards + chart + table)


BacktestResult.positions + prices
    └── BrinsonAttribution.analyze() ──→ BrinsonResult (summary)
    └── _compute_daily_brinson() ──→ list[dict] (daily time series)
                │
                ▼
    AnalysisReport.brinson_attribution + brinson_daily
                │
                ▼
    API: GET /backtests/{run_id}/attribution
                │
                ▼
    Frontend: Attribution Tab (cards + area chart + table)
```

---

## 3. 边界情况处理

| 场景 | 处理 |
|------|------|
| 无交易（fills 为空） | TCA Tab 显示空状态，不报错 |
| 无 benchmark | 归因 Tab 显示"未设置基准，无法归因"提示 |
| 单资产 | Brinson 归因无意义，Tab 显示"单资产组合无需归因" |
| 数据不足（< 2 个交易日） | 降级为汇总归因，不生成逐日序列 |
| AnalysisReport 不存在 | API 端点实时计算 TCA/归因（不依赖预计算） |
| benchmark_asset_id 为 ETF | 当前阶段用等权降级，后续可通过 extra 注入真实权重 |

---

## 4. 测试策略

| 层级 | 内容 |
|------|------|
| 单元测试 | `TransactionCostAnalyzer` 已有测试（如有），新增 `AnalysisEngine` TCA 集成测试 |
| 单元测试 | Brinson 逐日归因：mock positions + prices，验证时间序列长度和值 |
| 单元测试 | 边界情况：空 fills、无 benchmark、单资产 |
| 集成测试 | 端到端：BacktestSpec → BacktestResult → AnalysisEngine → API → 前端渲染 |
| 前端测试 | TCA Tab 渲染、归因 Tab 渲染、空状态、无基准状态 |

---

## 5. 验收标准

- [ ] `AnalysisReport` 包含 `tca_summary`、`tca_by_asset`、`tca_by_date` 字段
- [ ] `AnalysisReport.brinson_attribution` 使用正确的 benchmark returns（非 portfolio returns）
- [ ] 新增 `brinson_daily` 字段包含逐日归因时间序列
- [ ] API `GET /backtests/{run_id}/tca` 返回完整 TCA 数据
- [ ] API `GET /backtests/{run_id}/attribution` 返回 summary + daily + sector_details
- [ ] 前端「成本分析」Tab 显示概览卡片 + 成本分解 + 按资产排名 + 趋势图
- [ ] 前端「归因分析」Tab 显示概览卡片 + 堆叠面积图 + 行业明细表
- [ ] 空状态和边界情况正确处理
- [ ] 现有测试无回归
