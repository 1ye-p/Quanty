# 策略配置指南

本篇介绍 cQuant 的 8 种策略类型、因子权重、风控参数与市场规则配置。

策略是"如何从因子/信号生成买卖决策"的逻辑。cQuant 通过 `BacktestRunSpec.strategy_type` 字段选择策略，前端在「策略」页面用 `StrategyBuilder` 可视化配置。

---

## 1. 策略类型总览

| 策略类型 | `strategy_type` 值 | 适用场景 | 是否需要因子 |
|----------|-------------------|----------|--------------|
| 静态 TopN | `StaticTopN` | 单因子排序选股（最简单） | 单因子 |
| 多因子 | `MultiFactor` | 多因子加权合成打分 | 多因子 |
| ML 模型 | `MLModelStrategy` | 机器学习预测信号 | ML 模型 |
| 市场中性 | `MarketNeutral` | 多空对冲（做多 top、做空 bottom） | 多因子/ML |
| 行业轮动 | `SectorRotation` | 先选行业、再选个股 | 多因子 |
| 组合策略 | `Combo` | 多个子策略组合 | 子策略 |
| 指标信号 | `IndicatorSignal` | 技术指标条件触发（突破/金叉等） | 指标条件 |
| 规则条件 | `BreakoutPullback` | 突破回踩等规则化选股 | 规则参数 |

> 注：`IndicatorSignal` 与 `BreakoutPullback` 都基于规则条件 DSL，前者由用户自定义指标条件，后者内置突破回踩逻辑。

---

## 2. 各策略类型详解

### 2.1 StaticTopN（静态 TopN）

最简单的横截面动量策略：每个调仓日按 `sort_factor` 降序排名，取前 `top_n` 只，等权配置。

| 参数 | 说明 | 示例 |
|------|------|------|
| `top_n` | 选股数量 | 10 |
| `sort_factor` | 排序因子名 | `ret_20d` |

适合：单因子验证、快速原型。

### 2.2 MultiFactor（多因子）

多因子加权合成打分，是实战中最常用的类型。

| 参数 | 说明 |
|------|------|
| 因子列表 | 选择多个因子 |
| 因子权重 | 每个因子的权重（如 `ret_20d: 0.4, rsi_14: 0.3, ...`） |
| `top_n` | 选股数量 |
| 缺失因子处理 | `fill_0`（填 0）/ `drop`（剔除）/ `risk_penalty`（风险惩罚） |
| `penalty_per_missing` | 缺失因子风险惩罚系数（配合 `risk_penalty`） |

**缺失因子处理策略**：
- `fill_0`：缺失值填 0（默认，简单但可能引入偏差）；
- `drop`：剔除有缺失的股票（严格，可能样本过少）；
- `risk_penalty`：缺失越多打分越低（折中，按 `penalty_per_missing` 扣分）。

> 因子权重可保存为模板（`factor_templates.py`），支持预设模板的加载/保存。前端提供「因子模板管理器」。

### 2.3 MLModelStrategy（ML 模型）

使用机器学习模型（LightGBM / XGBoost / qlib 模型）的预测值作为信号。

| 参数 | 说明 |
|------|------|
| `model_version` | 已训练的 ML 模型版本 |
| `label_name` | 预测标签（如 `ret_5d`） |
| `top_n` | 选股数量 |

模型在「ML 实验室」页面训练，训练完成后获得 `model_version`。详见 ML 相关文档。

### 2.4 MarketNeutral（市场中性）

做多高分组、做空低分组，对冲市场风险。

| 参数 | 说明 |
|------|------|
| `top_n` | 做多股票数 |
| `short_n` | 做空股票数 |

> A 股默认 `allow_short = false`（无裸卖空），启用市场中性需在市场规则中放开做空限制，或通过股指期货对冲。

### 2.5 SectorRotation（行业轮动）

先按行业动量选 top 行业，再在各行业内选 top 个股。

| 参数 | 说明 |
|------|------|
| `sector_map` | 资产 → 行业映射 |
| `top_sectors` | 选择的行业数（如 3） |
| `top_n_per_sector` | 每个行业选的个股数（如 3） |

行业映射可从 `SectorLimit` 风控策略自动加载。

### 2.6 Combo（组合策略）

将多个子策略按指定方法组合。

| 参数 | 说明 |
|------|------|
| `sub_strategy_configs` | 子策略配置列表 |
| `combo_method` | 组合方法：`equal_weight`（等权）等 |

每个子策略是一个完整的策略配置（含自己的 `strategy_type` 和参数）。

### 2.7 IndicatorSignal（指标信号）

基于技术指标的条件触发。通过**规则条件 DSL** 定义入场/出场条件。

| 参数 | 说明 |
|------|------|
| `indicator_specs` | 指标规格列表（指标名 + 参数） |
| `entry_conditions` | 入场条件（DSL 表达式列表） |
| `exit_conditions` | 出场条件（DSL 表达式列表） |

**指标支持**（`cquant/indicator/` 模块）：
- OHLCV 类、移动平均类、趋势类（MACD 等）、震荡类（RSI/KDJ）、波动率类（布林带/ATR）、成交量类。

**条件 DSL 示例**：
```
# 入场：MACD 金叉且 RSI < 70
macd_diff > 0 and macd_diff_prev <= 0 and rsi_14 < 70

# 出场：跌破 20 日均线
close < ma(close, 20)
```

> 条件 DSL 支持 `let` 绑定（定义中间变量），方便复杂逻辑。前端 Monaco 编辑器提供指标参考面板和自动补全。

引擎会自动过滤不可交易的标的（停牌、涨跌停），避免信号无法执行。

### 2.8 BreakoutPullback（突破回踩）

内置的规则化选股策略：捕捉突破前期高点后回踩的买点。配置通过 `breakout_pullback.toml`（参数含突破窗口、回踩幅度、止损等）。

---

## 3. 因子权重配置

`MultiFactor` 策略的核心是因子权重。配置方式：

1. 在 `StrategyBuilder` 的「因子」区域，用 `FactorSelector` 选择因子；
2. 在 `FactorWeightTable` 中设置每个因子的权重（数值或百分比）；
3. 可点击「因子相关性提示」查看因子间相关性，避免高相关因子重复计权；
4. 用「因子模板管理器」保存当前权重组合为模板，供下次复用。

**权重优化回路**：回测后可在回测详情页点击「优化因子权重」，跳转回策略配置，迭代优化。

---

## 4. 仓位 Sizer（资金分配）

选定股票后，如何分配资金由 **Sizer** 决定。cQuant 内置多种 Sizer（`riskguard/sizers/`）：

| Sizer | 说明 | 适用 |
|-------|------|------|
| `equal_weight` | 等权分配 | 默认，简单稳健 |
| `target_vol` | 目标波动率（按波动反比配权） | 风险平价思路 |
| `vol_parity` | 波动率平价 | 各标的贡献等量风险 |
| `kelly` | 凯利公式（按胜率/赔率配权） | 激进，需谨慎（通常用半 Kelly） |
| `mvo` | 均值-方差优化（MVO） | 经典马科维茨，含约束 |
| `black_litterman` | Black-Litterman | 结合因子观点的市场均衡 |

MVO / Black-Litterman 支持高级约束：单资产上下限、行业上限、换手率惩罚、协方差估计器选择等。

---

## 5. 风控参数

风控策略（`riskguard/policies/`）在持仓层面施加约束，cQuant 内置以下策略：

| 策略 | 说明 | 关键参数 |
|------|------|----------|
| `stop_loss` | 固定止损 | `stop_loss_pct` |
| `atr_stop_loss` | ATR 动态止损 | `atr_period`、`atr_multiplier` |
| `trailing_stop` | 移动止损 | `trail_pct` |
| `max_holding_days` | 最大持有天数 | `max_days` |
| `drawdown_breaker` | 回撤熔断（分级） | `dd_threshold`、级别 |
| `global_stop` | 全局止损 | 全局亏损阈值 |
| `leverage_limit` | 杠杆上限 | `max_gross_leverage` |
| `position_limits` | 单仓位限制 | `max_position_pct`、`max_positions` |
| `sector_limit` | 行业集中度限制 | `max_sector_pct` |
| `factor_exposure_limit` | 因子暴露限制 | 因子暴露上下限 |
| `forced_exit` | 强制退出 | 触发条件 |

**全局风控配置**（`GlobalRiskConfig`）：可一键启用「快速止损」和「快速回撤熔断」，无需逐项配置。

在 `StrategyBuilder` 中可多选风控策略，并为每个策略配置参数。

---

## 6. 市场规则

不同市场的交易规则不同，cQuant 通过 **TradingRules** 适配（`market_calendar/`）：

| 规则 | CN（A 股） | US（美股） | HK（港股） |
|------|-----------|-----------|-----------|
| 涨跌停 | ±10%（ST ±5%，创业板/科创板 ±20%） | 无 | 无 |
| T+N | T+1 | T+0 | T+0 |
| 做空 | 不允许（默认） | 允许 | 允许 |
| 最小手数 | 100 股 | 1 股 | 按手 |
| 印花税 | 卖出 0.1% | 无 | 双边 0.13% |

在 `StrategyBuilder` 顶部选择市场（`market`），系统自动加载对应规则：
- **涨跌停检测**：自动过滤涨停（无法买入）和跌停（无法卖出）标的；
- **退市处理**：退市股票自动剔除，避免脏数据；
- **停牌过滤**：停牌标的信号被过滤；
- **ST/涨跌停过滤开关**：`filterST`、`filterSuspended`、`filterLimitUpDown`。

**复权类型**（`adjType`）：默认前复权。回测与因子计算统一走复权价。详见 [回测配置指南](backtest.md)。

**调仓频率**（`rebalance_frequency`）：`1d`（日）/ `1w`（周）/ `1mo`（月）。引擎会按频率过滤调仓日，非调仓日不产生信号。

---

## 7. 策略版本管理

cQuant 支持策略版本管理：每次保存策略会生成一个新版本（最多 50 个），可查看版本差异（`VersionDiff`）并回滚到历史版本。在策略详情页的「版本历史」面板操作。

---

## 8. 完整配置示例

一个典型的多因子策略配置（JSON 片段）：

```json
{
  "strategy_type": "MultiFactor",
  "factors": [
    {"name": "ret_20d", "weight": 0.4},
    {"name": "rsi_14", "weight": 0.3},
    {"name": "mom_60d", "weight": 0.3}
  ],
  "top_n": 15,
  "missing_factor_strategy": "risk_penalty",
  "penalty_per_missing": 0.5,
  "sizer": "target_vol",
  "rebalance_frequency": "1w",
  "market": "CN",
  "adjType": "pre",
  "policies": ["drawdown_breaker", "stop_loss"],
  "policy_params": {
    "drawdown_breaker": {"dd_threshold": 0.15},
    "stop_loss": {"stop_loss_pct": 0.08}
  },
  "max_position_pct": 0.1,
  "max_positions": 15,
  "filterST": true,
  "filterSuspended": true,
  "filterLimitUpDown": true
}
```

---

## 9. 相关文档

- [快速开始](getting-started.md)
- [因子研究指南](factor-research.md) — 因子评估与选择
- [回测配置指南](backtest.md)
- [回测分析指南](backtest-analysis.md)
