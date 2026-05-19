# cQuant 量化平台深度评估报告

> 评估日期：2026-05-18
> 评估视角：专业量化交易员（端到端量化工作流）
> 评估范围：数据管道 → 因子挖掘 → 策略制定 → 机器学习 → 回测评估 → 仓位控制 → 风险控制 → 执行交易

---

## 目录

- [一、总体评价](#一总体评价)
- [二、数据管道 (Data Pipeline)](#二数据管道-data-pipeline)
- [三、因子挖掘 (Factor Mining)](#三因子挖掘-factor-mining)
- [四、策略制定 (Strategy Development)](#四策略制定-strategy-development)
- [五、机器学习 (Machine Learning)](#五机器学习-machine-learning)
- [六、回测评估 (Backtesting & Evaluation)](#六回测评估-backtesting--evaluation)
- [七、仓位控制 (Position Sizing)](#七仓位控制-position-sizing)
- [八、风险控制 (Risk Control)](#八风险控制-risk-control)
- [九、执行与交易 (Execution & Trading)](#九执行与交易-execution--trading)
- [十、基础设施与工程](#十基础设施与工程)
- [十一、优先级排序与路线图建议](#十一优先级排序与路线图建议)

---

## 一、总体评价

### 已完成的工作（值得肯定）

cQuant 在 Phase 1 阶段搭建了一个**架构清晰、设计合理**的量化平台骨架：

| 模块 | 完成度 | 亮点 |
|------|--------|------|
| 数据层 (datahub) | ★★★★☆ | 三层存储 (Bronze/Silver/Gold)、多数据源适配、标准化管道 |
| 因子层 (factorlab) | ★★★☆☆ | 20 个内置因子、Factor ABC + Registry、物化管道 |
| 回测引擎 (backtest_vector) | ★★★★☆ | 完整的 A 股约束模拟（涨跌停/T+1/手数）、成本模型、TCA |
| 过拟合检测 (bt_analyzer) | ★★★★☆ | PSR/DSR/CPCV/Walk-Forward，Lopez de Prado 方法论落地 |
| 风控层 (riskguard) | ★★☆☆☆ | 4 种 Sizer、Policy 架构就绪，但仅 1 个 Policy 实现 |
| CLI | ★★★☆☆ | 命令齐全、交易/行情/回测一站式 |

### 核心短板

从量化交易员的视角看，当前平台最大的问题不是单个模块的深度，而是**端到端工作流的断裂**：

1. **策略层极度薄弱** — 只有 1 个 `StaticTopNStrategy`（截面动量 Top-N），无法支撑任何实战策略
2. **机器学习层完全缺失** — `ml_lab` 模块未开始，无从数据到预测的 ML 管道
3. **风控层名存实亡** — 数据模型定义了 4 种 limit_type，但只有 `position_pct` 有 Policy 实现
4. **因子库偏科** — 20 个因子全部是价量因子，缺乏基本面/价值/质量/成长类因子
5. **回测与风控的集成是假的** — RiskContext 传空 DataFrame，RiskSnapshot 字段全 None

---

## 二、数据管道 (Data Pipeline)

### 2.1 现状

| 能力 | 状态 | 说明 |
|------|------|------|
| 多数据源接入 | ✅ 已实现 | TDX / Tushare / AKShare / YFinance / CSV |
| 实时行情 | ✅ 已实现 | 东方财富接口，轮询模式 |
| 三层存储 | ✅ 架构就绪 | Bronze(审计) → Silver(标准化) → Gold(分析) |
| 数据标准化 | ✅ 已实现 | 列名映射、Asset ID 统一、类型强制 |
| 增量更新 | ⚠️ 部分 | dataset_versions 有版本管理，但无增量 diff 逻辑 |
| 数据质量校验 | ❌ 缺失 | 无异常值检测、无缺失数据插补、无交叉验证 |

### 2.2 关键问题

**P0 - 缺失数据处理**
- Silver 层没有 null/NaN 清洗逻辑，异常值（如价格为 0、成交量为负）会直接进入因子计算
- 停牌股复牌后首日的价格跳空没有特殊处理（adj_factor 不连续）
- 缺少"脏数据隔离"机制 — 一条异常数据可能污染整个因子序列

**P0 - Bronze 层是空壳**
- `bronze_ingestions` 表只记录元数据，`storage_uri` 指向的 Parquet 文件从未被写入
- 意味着**无法重放原始数据**，数据溯源能力为零
- 建议：将原始数据写入 `data/lake/bronze/{source}/{dataset}/{date}.parquet`

**P1 - 无分钟级存储**
- AKShare 和 YFinance 支持 M1/M5/M15 等分钟频率，但 Silver 层只有 `silver_prices_1d`
- 对日内策略（如 T+0 ETF 套利、高频动量）完全无法支撑
- 建议：增加 `silver_prices_intraday` 表，按频率分表或分区

**P1 - 行业/板块数据缺失**
- `silver_assets` 有 `industry` 和 `sector` 字段，但 bootstrap 时全填 NULL
- 导致 Brinson 归因、行业轮动策略、行业中性策略均无法使用
- 建议：从 AKShare 或 Tushare 获取申万行业分类并写入

**P2 - US/HK 数据覆盖不足**
- YFinance connector 存在但 US/HK 的交易所路由逻辑弱（无法区分 NYSE/NASDAQ/AMEX）
- HK 市场的 adj_factor 计算逻辑未实现（港股有碎股、供股等复杂 corporate action）

### 2.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 实现 Bronze 层实际数据写入 | 数据可追溯、可重放 |
| P0 | Silver 层增加数据质量校验（价格/成交量异常值过滤） | 因子计算可靠性 |
| P1 | 增加 `silver_prices_intraday` 表 | 支撑日内策略 |
| P1 | 补充行业/板块数据到 `silver_assets` | 行业归因、中性策略 |
| P2 | US/HK 交易所精确路由 | 多市场扩展 |

---

## 三、因子挖掘 (Factor Mining)

### 3.1 现状

当前 20 个因子按类别分布：

| 类别 | 数量 | 代表因子 | 覆盖度 |
|------|------|----------|--------|
| 动量 | 7 | ret_1d~ret_240d, momentum_12_1 | ★★★★☆ |
| 波动率 | 5 | vol_20d/60d/120d, downside_vol, max_dd | ★★★★☆ |
| 流动性 | 3 | turnover_rate, volume_ratio, amount_ratio | ★★★☆☆ |
| 技术 | 5 | zscore, MA ratio, RSI, Bollinger, high_ratio | ★★★☆☆ |
| **价值** | **0** | PE/PB/股息率/EV/EBITDA | ❌ |
| **质量** | **0** | ROE/ROA/毛利率/应计 | ❌ |
| **成长** | **0** | 营收增速/利润增速/SUE | ❌ |
| **规模** | **0** | 市值/对数市值 | ❌ |
| **情绪** | **0** | 分析师预期/舆情得分 | ❌ |
| **微观结构** | **0** | Amihud/买卖价差/订单不平衡 | ❌ |

### 3.2 关键问题

**P0 - 因子库严重偏科**
- 全部 20 个因子都是**价量技术因子**，没有任何基本面因子
- 在 A 股市场，纯价量因子的有效性逐年衰减（因子拥挤），基本面因子是超额收益的重要来源
- `FactorContext.extra` 字段已预留了基本面数据接口，但没有任何因子使用它

**P0 - 因子 DAG 是假的**
- 文档声称"DAG 执行"，但实际是**顺序 for 循环**
- 因子之间无法声明依赖关系（如 `pe_ttm` 依赖 `close` 和 `eps`）
- 复合因子（如 Fama-French SMB/HML）无法在管道内构建
- 建议：实现真正的 DAG — 因子声明 `dependencies`，Pipeline 做拓扑排序

**P1 - Lookback 窗口不足**
- `materialize.py` 硬编码 90 天回看，但 `ret_240d` 需要 240 个交易日、`momentum_12_1` 需要 ~252 个交易日
- 结果：数据范围前段会产生大量 null 值
- 建议：根据因子实际需要的最大 lookback 动态计算

**P1 - DownsideVol 实现有误**
- 当前实现：对负收益取 `rolling_std`（正收益置零后求标准差）
- 正确公式：`sqrt(mean(min(ret, 0)^2))` — 使用全部样本计算下行偏差
- 当前实现会低估波动率（分母被零值膨胀）

**P2 - 无因子评估框架**
- 缺少 IC/IR/Rank IC/ICIR 等标准因子评价指标
- 无法判断因子的有效性、衰减速度、换手率
- 建议：增加 `factor_evaluation` 模块，计算 IC 时间序列、分层回测

### 3.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 新增价值/质量/成长/规模因子（至少各 3-5 个） | 因子多样性、策略丰富度 |
| P0 | 修复 DownsideVol 计算公式 | 因子正确性 |
| P1 | 实现真正的 DAG 引擎（因子依赖声明 + 拓扑排序） | 复合因子构建 |
| P1 | 动态 lookback 窗口 | 消除前端 null |
| P1 | 增加因子评估框架 (IC/IR/分层回测) | 因子筛选科学化 |
| P2 | 增加情绪因子（分析师预期、新闻情感） | 另类数据 alpha |

---

## 四、策略制定 (Strategy Development)

### 4.1 现状

**仅有 1 个策略**：`StaticTopNStrategy`（截面动量 Top-N 选股）

```python
# 伪代码
signals = factors.rank("sort_factor").head(top_n)
weights = equal_weight(signals)
```

这是最简单的截面多头策略，不涉及任何：
- 市场状态判断（牛熊切换）
- 行业轮动
- 多空对冲
- 均值回归
- 事件驱动
- 配对交易

### 4.2 关键问题

**P0 - 策略框架只有骨架**
- `Strategy` ABC 定义了 `generate_signals(ctx) -> SignalFrame`，但没有任何策略组合、策略选择、策略评估的机制
- 无法进行策略间的比较、组合、或动态切换

**P0 - 无策略模板库**
- 缺少常见的量化策略模板：
  - 多因子打分策略（加权/机器学习权重）
  - 行业轮动策略
  - 动量 + 均值回归混合策略
  - 事件驱动策略（财报、定增、解禁）
  - 统计套利 / 配对交易
  - 市场中性策略（多空对冲）

**P1 - 无策略参数管理**
- 策略参数通过 CLI 参数传递，没有配置文件管理
- 无法进行参数搜索、参数稳定性分析
- `AnalysisSpec.param_grid` 字段已存在但未使用

**P1 - 无策略组合框架**
- 缺少多策略组合能力（等权/风险平价/动态权重）
- 缺少策略间相关性分析
- 缺少策略分配（allocation）逻辑

### 4.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 实现多因子加权策略模板 | 从单因子到多因子 |
| P0 | 实现行业中性/市场中性策略 | 对冲能力 |
| P1 | 策略参数配置化（TOML/YAML） | 可复现性、参数搜索 |
| P1 | 多策略组合框架 | 策略多元化 |
| P2 | 事件驱动策略框架 | 另类 alpha 来源 |

---

## 五、机器学习 (Machine Learning)

### 5.1 现状

**`ml_lab` 模块完全未开始**（Phase 2 规划）。

`gold_predictions` 表已定义（`model_id`, `horizon`, `label_name`, `prediction`, `confidence`），但无任何代码写入。

`meta_ml_jobs` 表已定义用于 MLflow 跟踪，但无集成代码。

### 5.2 建议的 ML 管道架构

从量化实战角度，ML 管道应包含：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  特征工程     │ ──→ │  模型训练     │ ──→ │  预测生成     │ ──→ │  信号转换     │
│  (factorlab)  │     │  (ml_lab)    │     │  (ml_lab)    │     │  (strategy)  │
│              │     │              │     │              │     │              │
│ - 因子值      │     │ - LightGBM   │     │ - 滚动预测    │     │ - 预测→权重   │
│ - 行业哑变量  │     │ - XGBoost    │     │ - Purged K-Fold│    │ - 置信度过滤  │
│ - 宏观变量    │     │ - Ridge      │     │ - MLflow 跟踪 │     │              │
│ - 标签构建    │     │ - MLP/TabNet │     │              │     │              │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 5.3 关键缺失能力

| 能力 | 优先级 | 说明 |
|------|--------|------|
| 标签构建 (labeling) | P0 | 收益率标签、Triple Barrier 标签、趋势标签 |
| 特征工程管道 | P0 | 因子标准化 (cross-sectional z-score)、缺失值处理、特征选择 |
| 模型训练框架 | P0 | sklearn/lightgbm/xgboost 封装、超参搜索 |
| Purged Cross-Validation | P0 | 防止信息泄露的交叉验证（与 bt_analyzer 的 CPCV 对接） |
| 滚动训练 + 预测 | P1 | Walk-forward 训练、避免 look-ahead |
| MLflow 集成 | P1 | 实验跟踪、模型版本管理、可复现性 |
| 模型解释性 | P2 | SHAP 值、特征重要性、部分依赖图 |
| 深度学习 | P3 | LSTM/Transformer 用于时序预测 |

### 5.4 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 实现标签构建模块（前瞻收益率、Triple Barrier） | ML 的 Y 变量 |
| P0 | 实现特征标准化管道（截面 z-score、winsorize） | 模型输入质量 |
| P0 | 实现 LightGBM/XGBoost 训练封装 | 核心 ML 能力 |
| P1 | Purged Walk-Forward 训练管道 | 防过拟合 |
| P1 | MLflow 集成 | 实验管理 |

---

## 六、回测评估 (Backtesting & Evaluation)

### 6.1 现状

回测引擎是当前平台**完成度最高**的模块。

**引擎能力矩阵：**

| 能力 | 状态 | 说明 |
|------|------|------|
| 向量化回测 | ✅ | 每日信号 → 次日执行，防止前视偏差 |
| A 股约束 | ✅ | 涨跌停/T+1/手数/停牌/现金缓冲 |
| 成本模型 | ✅ | 佣金/印花税/滑点，CN/US/HK 预设 |
| TCA | ✅ | 交易成本分析报告 |
| 基础指标 | ✅ | Sharpe/Calmar/MaxDD/WinRate/ProfitFactor |
| 过拟合检测 | ✅ | PSR/DSR/CPCV/Walk-Forward/Multiple Testing |
| 归因分析 | ⚠️ | Brinson/Factor 归因代码存在但未接入 |
| Sortino | ❌ | 未计算 |
| VaR/CVaR | ❌ | 字段存在但永远为 None |
| Beta | ❌ | 字段存在但永远为 None |
| 事件驱动引擎 | ❌ | Phase 2 未开始 |
| vectorbt 适配 | ❌ | 文档提到但未实现 |

### 6.2 关键问题

**P0 - 回测指标不完整**

缺失的关键指标及其量化意义：

| 缺失指标 | 重要性 | 说明 |
|----------|--------|------|
| **Sortino Ratio** | 高 | 只惩罚下行波动，比 Sharpe 更符合交易员直觉 |
| **VaR / CVaR (95%)** | 高 | 尾部风险度量，风控决策的核心输入 |
| **Beta** | 高 | 市场暴露度量，对冲策略的必要参数 |
| **Information Ratio** | 中 | 相对基准的超额收益/跟踪误差 |
| **Tail Ratio** | 中 | 右尾/左尾收益比，衡量收益分布偏度 |
| **Omega Ratio** | 中 | 考虑所有矩的收益/损失比 |
| **持仓集中度 (HHI)** | 中 | Herfindahl 指数，衡量分散化程度 |

**P0 - RiskSnapshot 字段全空**

`_persist_risk_snapshots` 写入的 `beta`, `var_95`, `cvar_95`, `sector_exposure`, `factor_exposure` 全部为 None。这意味着：
- 无法追踪策略的时序风险暴露
- 无法做风险归因
- 无法验证风控 Policy 是否生效

**P1 - 执行价格过于简化**
- 所有 fill 使用收盘价，没有 VWAP/TWAP 模拟
- 大单冲击未建模（无成交量参与率约束）
- 滑点是固定百分比，不随流动性变化

**P1 - 涨跌停检测硬编码**
- 使用 `prev_close * 1.095` 和 `0.905` 硬编码 9.5% 阈值
- 无法区分主板 10%、创业板/科创板 20%、北交所 30% 的不同限制
- `_is_price_valid` 会错误拒绝创业板的合法 20% 涨跌幅

**P2 - `total_trades` 字段误导**
- `BacktestMetrics.total_trades` 实际是 `len(returns)`（交易日数），不是实际成交笔数
- 会导致 Profit Factor 等依赖交易次数的分析产生误解

**P2 - 无基准比较**
- `backtest.toml` 配置了 `benchmark = "CSI300"` 但代码中未使用
- 无法计算超额收益、跟踪误差、信息比率

### 6.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 补充 Sortino/VaR/CVaR/Beta 计算 | 风险度量完整性 |
| P0 | 让 RiskSnapshot 填入真实值 | 风险追踪能力 |
| P0 | 涨跌停检测改为按板块动态计算 | A 股回测准确性 |
| P1 | 引入 VWAP/TWAP 执行价格模拟 | 大资金回测真实性 |
| P1 | 基准比较 + 超额收益计算 | 策略评价标准 |
| P2 | 修复 total_trades 语义 | 指标准确性 |
| P2 | vectorbt 适配器 | 性能优化（大规模回测） |

---

## 七、仓位控制 (Position Sizing)

### 7.1 现状

4 种 Sizer 实现：

| Sizer | 算法 | 数据依赖 | 实际可用性 |
|-------|------|----------|-----------|
| EqualWeight | 1/N 等权 | 无 | ✅ 可用 |
| Kelly | Kelly Criterion | 信号置信度（代理值） | ⚠️ 粗糙 |
| TargetVol | 目标波动率 | 信号强度（代理值） | ⚠️ 粗糙 |
| VolParity | 风险平价 | 真实波动率数据 | ✅ 可用（需外部输入） |

### 7.2 关键问题

**P0 - Kelly 和 TargetVol 使用代理值而非真实数据**

```python
# Kelly Sizer 当前实现
win_prob = signal.confidence  # 用信号置信度代替胜率
odds = signal.strength * 2    # 用信号强度代替赔率

# TargetVol Sizer 当前实现
vol_estimate = 0.20 + (1 - abs(signal.strength)) * 0.10  # 硬编码 20% 基准波动率
```

这在实盘中是**不可接受的**：
- Kelly 公式对输入极其敏感，代理值会导致仓位剧烈波动
- TargetVol 的波动率估计完全脱离实际（贵州茅台 30% 波动率和 ST 股 80% 波动率被同等对待）

**P1 - 未使用协方差矩阵**
- `SizingContext` 有 `return_covariance` 字段，但没有任何 Sizer 使用它
- 意味着**组合层面的分散化效应被完全忽略**
- 建议：实现 Mean-Variance Optimization (MVO) 和 Black-Litterman Sizer

**P1 - VolParity 不支持做空**
- 当 `allow_short=True` 时，空头仓位被静默忽略
- 无法支撑多空策略

### 7.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | Kelly 使用历史收益分布计算真实胜率/赔率 | 仓位合理性 |
| P0 | TargetVol 使用真实历史波动率 | 仓位合理性 |
| P1 | 实现 MVO Sizer（均值-方差优化） | 组合优化 |
| P1 | 实现 Black-Litterman Sizer | 主观观点融合 |
| P2 | VolParity 支持做空 | 多空策略 |

---

## 八、风险控制 (Risk Control)

### 8.1 现状

| 能力 | 状态 | 说明 |
|------|------|------|
| 仓位比例限制 | ✅ | `PositionLimitPolicy` — 单票最大 10% |
| 名义金额限制 | ✅ | `PositionLimitPolicy` — 单票最大金额 |
| 杠杆限制 | ❌ | 模型已定义，无 Policy 实现 |
| 行业暴露限制 | ❌ | 模型已定义，无 Policy 实现 |
| 因子暴露限制 | ❌ | 模型已定义，无 Policy 实现 |
| 回撤熔断 | ❌ | 未实现 |
| 换手率限制 | ❌ | RiskBudget 数据结构存在，无消费方 |
| 止损/止盈 | ❌ | 完全未实现 |
| 高水位追踪 | ❌ | `get_drawdown()` 是一次性计算，无状态维护 |
| Policy 链式组合 | ❌ | 无编排器串联多个 Policy |

### 8.2 关键问题

**P0 - 止损机制完全缺失**

这是**最危险的缺失**。一个没有止损的量化系统在实盘中意味着：
- 单票可能亏损 50%+ 而系统不会触发任何保护
- 组合回撤可能突破所有预设阈值而无人干预
- 建议实现：
  - 固定百分比止损（如 -5%）
  - 移动止损（trailing stop，如从最高点回撤 8%）
  - 时间止损（持仓超过 N 天且未盈利则退出）
  - 波动率止损（ATR 倍数）

**P0 - 回撤熔断缺失**
- 当组合回撤超过阈值（如 -10%）时，应自动减仓或停止交易
- `RiskBudget` 数据结构已定义 `risk_budget` 字段，但从未被检查

**P0 - 风控与回测的集成是假的**

```python
# engine.py 中的 RiskContext 构造
ctx = RiskContext(
    current_positions=pl.DataFrame(),  # 空的！
    nav=nav,
    cash=cash,
)
```

- `current_positions` 传空 DataFrame，意味着仓位集中度、行业暴露等检查**全部失效**
- Policy 的 `evaluate()` 返回 `APPROVED` 不是因为检查通过，而是因为**没有数据可以检查**

**P1 - Sizer 使用代理值而非真实波动率（已在第七节详述）**

**P1 - Python 回退过于宽松**
- 当 Rust wheel 不存在时，`_py_pre_trade_check` 批准所有正数量的订单
- 等于**没有风控**

### 8.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 实现止损机制（固定/移动/ATR） | 生存底线 |
| P0 | 实现回撤熔断 Policy | 组合保护 |
| P0 | 修复回测引擎的 RiskContext 集成 | 风控真正生效 |
| P0 | 实现杠杆限制 Policy | 防止过度暴露 |
| P1 | 实现行业暴露限制 Policy | 分散化控制 |
| P1 | 实现 Policy 链式编排 | 多策略风控 |
| P1 | 实现高水位追踪（HWM） | 回撤计算准确性 |
| P2 | 实现因子暴露限制 | 因子风险管理 |

---

## 九、执行与交易 (Execution & Trading)

### 9.1 现状

| 能力 | 状态 | 说明 |
|------|------|------|
| Paper Broker | ✅ | 模拟交易，完整的订单/成交管理 |
| 实时行情 | ✅ | 东方财富接口，轮询模式 |
| CLI 交易命令 | ✅ | buy/sell/positions/orders/account |
| QMT Broker | ❌ | 帮助文本提到但未实现 |
| 回测→实盘一致性 | ❌ | 回测用 Close 价格，实盘用真实成交价 |
| 订单类型 | ⚠️ | 只有 market/limit，无 stop/stop_limit |
| 风控前置检查 | ❌ | Paper broker 不经过 RiskPolicy |

### 9.2 关键问题

**P1 - 无真实 Broker 接入**
- QMT（迅投）是 A 股最常用的量化交易接口之一，但只有占位符
- 建议优先实现 QMT adapter，其次是恒生/华锐等机构级接口

**P1 - Paper Broker 不经过风控**
- Paper broker 直接执行订单，没有经过 `RiskPolicy` 检查
- 意味着模拟交易的结果**高估了策略的真实表现**（没有被风控拒绝/裁剪的订单）

**P2 - 无订单状态机**
- `OrderStatus` 定义了完整的状态（pending → submitted → partially_filled → filled），但 Paper broker 直接跳到 filled
- 无法模拟真实的订单生命周期（撤单、部分成交、拒绝）

### 9.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P1 | 实现 QMT Broker Adapter | 实盘交易能力 |
| P1 | Paper Broker 接入 RiskPolicy | 模拟交易真实性 |
| P2 | 订单状态机完善 | 生命周期管理 |
| P2 | 实现回测→实盘一致性验证 | 策略可信度 |

---

## 十、基础设施与工程

### 10.1 关键工程问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| 无 `[project.dependencies]` | 高 | `pip install cquant` 无法安装依赖，只能 conda |
| 插件系统是空壳 | 中 | Schema 定义了 20 种能力类型，但无加载器、无插件清单 |
| Config 文件未被消费 | 高 | 4 个 TOML 配置文件存在但 CLI 不加载它们 |
| Rust submodule 是占位符 | 中 | `.gitmodules` 中 URL 为 PLACEHOLDER |
| 测试覆盖不足 | 高 | 无 factorlab 单元测试、无 riskguard 测试、仅 1 个 smoke test |
| 日历线性扫描性能差 | 低 | `trading_days()` 是 O(N) 逐日扫描 |
| `seed_sample_data.sh` 是空壳 | 中 | 无法生成测试数据 |

### 10.2 建议

1. **在 `pyproject.toml` 添加 `[project.dependencies]`** — 当前 conda-only 的分发方式限制了可移植性
2. **实现 Config 加载层** — CLI 应读取 `configs/defaults/*.toml`，命令行参数覆盖配置文件
3. **补充单元测试** — 至少覆盖：每个因子的计算正确性、每个 Sizer 的权重归一化、每个 Policy 的边界条件
4. **实现插件加载器** — `registry.toml` 定义了发现路径，需要 `importlib` 动态加载 + manifest 校验

---

## 十一、优先级排序与路线图建议

### Phase 1.5（立即修复，1-2 周）

| # | 任务 | 模块 | 理由 |
|---|------|------|------|
| 1 | 实现止损机制（固定% / trailing / ATR） | riskguard | 生存底线，无止损不实盘 |
| 2 | 修复回测引擎 RiskContext 集成 | backtest_vector | 风控不生效等于没有风控 |
| 3 | 补充 Sortino/VaR/CVaR/Beta 计算 | backtest_vector | 风险度量基本功 |
| 4 | 涨跌停检测改为按板块动态计算 | backtest_vector | A 股回测准确性 |
| 5 | Kelly/TargetVol 使用真实历史数据 | riskguard | 仓位控制合理性 |
| 6 | 修复 DownsideVol 计算公式 | factorlab | 因子正确性 |
| 7 | 实现回撤熔断 Policy | riskguard | 组合保护 |

### Phase 2.0（核心能力补齐，4-6 周）

| # | 任务 | 模块 | 理由 |
|---|------|------|------|
| 8 | 新增价值/质量/成长/规模因子（~20 个） | factorlab | 因子库完整性 |
| 9 | 实现因子评估框架 (IC/IR/分层回测) | factorlab | 因子筛选科学化 |
| 10 | 实现多因子加权策略模板 | backtest_vector | 策略多样性 |
| 11 | 实现 ML 标签构建 + 特征标准化 | ml_lab | ML 管道起点 |
| 12 | 实现 LightGBM 训练封装 | ml_lab | 核心 ML 能力 |
| 13 | 实现杠杆/行业暴露限制 Policy | riskguard | 风控体系完善 |
| 14 | 增加行业/板块数据到 silver_assets | datahub | 行业归因基础 |
| 15 | Bronze 层实际数据写入 | datahub | 数据可追溯 |

### Phase 2.5（高级能力，6-10 周）

| # | 任务 | 模块 | 理由 |
|---|------|------|------|
| 16 | Purged Walk-Forward ML 训练管道 | ml_lab | 防过拟合 |
| 17 | 实现 MVO / Black-Litterman Sizer | riskguard | 组合优化 |
| 18 | 实现 QMT Broker Adapter | cli/broker | 实盘能力 |
| 19 | 事件驱动回测引擎 (Rust pyo3) | backtest_event | 高频策略支撑 |
| 20 | 分钟级数据存储 | datahub | 日内策略 |
| 21 | 真正的 DAG 因子引擎 | factorlab | 复合因子构建 |
| 22 | 策略组合框架 | backtest_vector | 多策略管理 |

### Phase 3.0（平台成熟，10-16 周）

| # | 任务 | 模块 | 理由 |
|---|------|------|------|
| 23 | 多 Agent 研究助手 | ai_advisor | AI 辅助研究 |
| 24 | 知识库 RAG 系统 | knowledge_base | 研报/策略知识管理 |
| 25 | React 前端仪表盘 | web | 可视化 |
| 26 | FastAPI 服务 | api_server | 服务化 |
| 27 | 插件系统完整实现 | registry | 生态扩展 |

---

## 附录：量化流程完整性自评

| 流程阶段 | 完成度 | 关键缺失 |
|----------|--------|----------|
| 数据采集 | 70% | Bronze 层空壳、无分钟数据、行业数据缺失 |
| 数据清洗 | 50% | 无异常值检测、无缺失插补 |
| 因子挖掘 | 40% | 全是价量因子、无基本面、无评估框架 |
| 策略制定 | 15% | 仅 1 个策略、无组合框架 |
| 机器学习 | 0% | 模块未开始 |
| 回测评估 | 65% | 指标不完整、执行模型简化、风控集成假 |
| 仓位控制 | 35% | 4 种 Sizer 但 2 个用代理值、无协方差优化 |
| 风险控制 | 20% | 无止损、无熔断、仅 1 个 Policy、集成是假的 |
| 执行交易 | 25% | 仅 Paper broker、无真实接入、不经过风控 |
| 监控报告 | 30% | TCA 有、但无实时 PnL 仪表盘、无告警 |

**总体评估：平台架构设计优秀（8/10），但量化实战能力不足（3/10）。当前适合用于学习和研究，距离实盘交易还需要大量工作。**

---

*本文档将随项目迭代持续更新。*
