# cQuant 量化平台评估报告 v2

> 评估日期：2026-05-19
> 评估基准：v1 报告（2026-05-18）→ 当前版本（重命名为 quant）
> 评估视角：专业量化交易员（端到端量化工作流）

---

## 目录

- [一、版本概览：与 v1 的对比](#一版本概览与-v1-的对比)
- [二、已解决问题清单](#二已解决问题清单)
- [三、数据管道](#三数据管道)
- [四、因子挖掘](#四因子挖掘)
- [五、策略制定](#五策略制定)
- [六、机器学习](#六机器学习)
- [七、回测评估](#七回测评估)
- [八、仓位控制与组合优化](#八仓位控制与组合优化)
- [九、风险控制](#九风险控制)
- [十、执行与交易](#十执行与交易)
- [十一、AI 研究助手与知识库](#十一ai-研究助手与知识库)
- [十二、基础设施与工程质量](#十二基础设施与工程质量)
- [十三、优先级路线图](#十三优先级路线图)
- [附录：量化流程完整性自评](#附录量化流程完整性自评)

---

## 一、版本概览：与 v1 的对比

### 模块数量对比

| 维度 | v1 | v2 | 变化 |
|------|----|----|------|
| Python 源文件数 | ~60 | ~200 | +240% |
| 已实现模块数 | 8 | 17 | +9 个新模块 |
| 因子总数 | 20 | 31 | +11 个基本面因子 |
| 风控 Policy 数 | 1 | 5 | +4 个 |
| 仓位 Sizer 数 | 4 | 6 | +MVO/BL |
| 单元测试文件数 | ~5 | ~46 | +820% |

### 新增模块一览

| 模块 | 功能 | 完成度 |
|------|------|--------|
| `ml_lab` | ML 训练流水线（标签/特征/LightGBM/XGBoost/Walk-Forward） | ★★★★☆ |
| `portfolio_opt` | 组合优化（MVO/风险平价/成本感知） | ★★★★☆ |
| `execution` | 执行层（QMT 适配器/Paper Broker） | ★★★☆☆ |
| `backtest_event` | 事件驱动回测引擎 | ★★★☆☆ |
| `knowledge_base` | RAG 知识库（LanceDB/混合检索） | ★★★★☆ |
| `ai_advisor` | 多 Agent 研究助手 | ★★★★☆ |
| `newsflow` | 新闻摄取（东方财富/Sina/RSS）+ PIT 控制 | ★★★★☆ |
| `api_server` | FastAPI 服务（REST + SSE） | ★★★☆☆ |
| `scheduler` | 策略调度 + 健康检查 | ★★★☆☆ |

**总体结论：v2 是一次质的飞跃，已从"研究框架骨架"进化为"功能基本完整的量化平台"。架构设计成熟，代码质量较高，但仍有若干关键细节未被打磨到位。**

---

## 二、已解决问题清单

以下是 v1 报告指出的问题在 v2 中的解决情况：

### ✅ 完全解决

| v1 问题 | 解决方案 |
|---------|----------|
| Bronze 层不写实际文件 | `bronze_writer.py` 实现 Parquet 写入 + SHA-256 内容哈希 |
| 止损机制缺失 | `FixedStopLossPolicy` + `TrailingStopLossPolicy` |
| 回撤熔断缺失 | `DrawdownBreakerPolicy`（默认 -10% 阈值） |
| 杠杆限制仅有模型定义 | `LeverageLimitPolicy` 实现软裁剪 + 硬拒绝 |
| 行业暴露限制缺失 | `SectorLimitPolicy` 实现 |
| Sortino Ratio 缺失 | `metrics.py` 完整计算 |
| VaR/CVaR 永远为 None | 现已计算并写入指标 |
| Beta 永远为 None | 支持基准收益输入，完整计算 |
| 涨跌停硬编码 9.5% | `limit_rules.py` 按板块动态：主板 10%/创业板+科创板 20%/北交所 30%/ST 5% |
| 仅 1 个策略模板 | `MultiFactorStrategy` + `CompositeStrategy` |
| ML 模块完全缺失 | `ml_lab` 全面实现：标签、特征、LightGBM、XGBoost、Purged K-Fold、Walk-Forward、MLflow |
| 无 MVO/BL 仓位 Sizer | `MvoSizer`（SLSQP）+ `BlackLittermanSizer`（贝叶斯更新）完整实现 |
| 无独立组合优化模块 | `portfolio_opt`：MVO/风险平价/成本感知三种优化器 |
| QMT 仅占位符 | `QMTAdapter` 实现连接/下单/撤单/查仓（xtquant SDK） |
| 插件系统空壳 | `registry.py` 完整实现：manifest 验证/动态加载/26 种能力类型 |
| 行业数据未入库 | `bootstrap_assets_from_tdx()` 写入 `silver_assets.industry/sector` |
| 无测试覆盖 | 46 个单元测试 + 2 个集成测试 + parity 测试 |

### ⚠️ 部分解决（已有实现但存在缺陷）

| v1 问题 | 当前状态 | 残留问题 |
|---------|----------|----------|
| Kelly 使用代理值 | 使用真实 vol 辅助估算 | 胜率仍从 confidence 信号估算，非历史数据 |
| TargetVol 使用代理值 | 使用真实 vol（有输入时） | 协方差矩阵未参与计算 |
| RiskContext 传空 DataFrame | 现从目标权重构建仓位 | 从目标权重而非实际 fill 历史构建，有偏差 |
| DAG 引擎是假的 | `dag.py` 实现了真正的 Kahn 拓扑排序 | `pipeline.py` **未接入** DAG 引擎，仍是顺序循环 |

---

## 三、数据管道

### 3.1 现状评估

| 能力 | 状态 | 说明 |
|------|------|------|
| Bronze 层 Parquet 写入 | ✅ | 内容哈希、provenance 完整 |
| 多数据源 | ✅ | TDX/Tushare/AKShare/YFinance/CSV |
| Silver 层标准化 | ✅ | 源感知列映射、类型强制、去重 |
| 实时行情 | ✅ | 东方财富，轮询模式 |
| 行业数据 | ✅ | 从 TDX 自动分类（主板/创业板/科创板/北交所） |
| 新闻摄取 + PIT | ✅ | Eastmoney/Sina/RSS + 延迟感知 PIT 过滤 |
| 数据质量校验 | ❌ | 仅 schema 验证，无异常值检测 |
| 分钟级数据存储 | ❌ | AKShare 支持 M1 但 Silver 层只有 `silver_prices_1d` |
| 其他数据源接入 CLI | ⚠️ | AKShare/Tushare/YFinance 有实现但 CLI `--source` 只支持 `tdx` |

### 3.2 关键残留问题

**P1 - CLI 多数据源封闭**
- `cmd_ingest` 仅接受 `--source tdx`
- AKShare、Tushare、YFinance 已完全实现但无 CLI 入口
- 建议：统一 `--source {tdx,tushare,akshare,yfinance}` 路由

**P1 - 数据质量管道缺失**
- 价格为 0、成交量为负、收益率 >100% 等异常值未过滤
- 复牌后首日价格跳空的 adj_factor 不连续处理缺失
- 建议：在 `SilverNormalizer` 中加入 Winsorize 阶段

**P2 - 无分钟级存储**
- AKShare M1/M5 数据有采集能力但无存储路径
- 对日内回测/T+0 策略完全不支持

**P2 - 日历 O(N) 线性扫描**
- `trading_days()` 仍是逐日循环，无索引/缓存
- 对长周期批量计算有性能瓶颈

---

## 四、因子挖掘

### 4.1 因子库全貌（v2）

**总计 31 个内置因子：**

| 类别 | 数量 | 代表因子 |
|------|------|----------|
| 动量 | 7 | ret_1d~ret_240d, momentum_12_1 |
| 波动率 | 5 | vol_20d/60d/120d, downside_vol, max_dd |
| 流动性 | 3 | turnover_rate, volume_ratio, amount_ratio |
| 技术 | 5 | zscore, ma_ratio, rsi, bollinger, high_ratio |
| 价值 | 3 | **pe_ttm, pb, dividend_yield** ← 新增 |
| 质量 | 3 | **roe, roa, gross_margin** ← 新增 |
| 成长 | 2 | **revenue_growth_yoy, earnings_growth_yoy** ← 新增 |
| 规模 | 2 | **market_cap, ln_market_cap** ← 新增 |

### 4.2 关键发现

**重大进展：DAG 引擎已实现但未接入**

`dag.py` 实现了完整的 Kahn 拓扑排序 + 循环检测，这是专业因子框架的核心能力。然而：

```python
# pipeline.py 当前实现（仍是顺序循环）
for factor_name in spec.factor_names:
    series = factor.safe_compute(windowed, ctx)
    result = result.with_columns(series.alias(factor_name))

# dag.py 已实现但未被调用
engine = DAGPipeline(registry)
engine.run(...)  # ← 这行代码从未出现在 pipeline.py 中
```

这意味着复合因子（如 `pe_ttm / vol_20d` 归一化估值）无法在管道内构建。

**P0 - 基本面因子数据依赖未打通**

11 个基本面因子（value/quality/growth/size）依赖 `ctx.extra['fundamentals']` DataFrame，但：
- 没有任何数据管道将基本面数据写入 `ctx.extra`
- `FactorMaterializer` 不加载基本面数据
- 实际运行时，这 11 个因子会静默返回全 NULL

**P0 - Lookback 窗口仍硬编码 90 天**

`materialize.py` 仍使用 `timedelta(days=90)`：
- `ret_240d` 需要 240 个交易日（约 340 日历天）
- `momentum_12_1` 需要 ~270 个交易日
- 结果：所有需要超过 90 天历史的因子，在回测期初端会产生大量 NULL

**P1 - 因子评估框架不完整**

`evaluation.py` 计算了 IC/ICIR/IC 胜率，但缺失：
- **Rank IC 衰减分析**（IC(k) 随 lag k 衰减，判断因子预测周期）
- **因子换手率**（每期排名变化剧烈度，影响交易成本）
- **分层回测**（Quantile Backtest — 将因子分 5/10 层，验证单调性）
- 这三者是学术和工业界判断因子有效性的标准方法

**P2 - DownsideVol 公式存疑**

`downside_vol_20d` 仍对负收益序列取 `rolling_std`，标准公式应为：
```python
# 标准下行标准差
sqrt(mean(min(ret, 0)^2))  # 全样本，非仅负值
```

### 4.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 实现基本面数据加载到 `ctx.extra`（Tushare 财务数据） | 11 个因子从 NULL 变可用 |
| P0 | 将 `pipeline.py` 改用 `DAGPipeline` 引擎 | 支持复合因子 |
| P0 | 动态 lookback 窗口（按因子最大依赖计算） | 消除前端 NULL |
| P1 | 补充 Rank IC 衰减 + 换手率 + 分层回测 | 因子筛选科学化 |
| P2 | 修复 DownsideVol 公式 | 因子准确性 |

---

## 五、策略制定

### 5.1 现状

| 策略类型 | 状态 | 说明 |
|----------|------|------|
| StaticTopNStrategy | ✅ | 截面动量 Top-N |
| MultiFactorStrategy | ✅ | 多因子加权打分，支持配置权重 |
| CompositeStrategy | ✅ | 多策略等权/自定义权重组合 |
| 行业轮动策略 | ❌ | 未实现 |
| 市场中性/多空对冲 | ❌ | 未实现 |
| 事件驱动策略 | ❌ | 未实现 |
| 均值回归策略 | ❌ | 未实现 |
| 统计套利 | ❌ | 未实现 |

### 5.2 关键问题

**P1 - portfolio_opt 模块与策略层未打通**

`portfolio_opt` 实现了完整的 MVO/风险平价/成本感知优化器，但：
- `backtest_vector/engine.py` 中并未调用 `portfolio_opt`
- 策略仍只支持 Sizer（仓位比例），而非真正的组合优化
- MVO 需要 `expected_returns` 和 `covariance`，但无数据传递路径

**P1 - 无策略参数网格搜索**

`AnalysisSpec.param_grid` 字段存在但从未被使用：
- `SensitivityAnalyzer` 只做滚动 Sharpe 的 CV，不重跑策略
- 无法自动寻找最优参数组合

**P2 - 短仓支持不完整**

多处声明 `allow_short=True` 但实际 AShareFillSimulator 未实现做空：
- 无融券成本模型
- 无 T+0 短仓结算

---

## 六、机器学习

### 6.1 现状（v2 全新模块）

| 能力 | 状态 | 说明 |
|------|------|------|
| 标签构建 | ✅ | 前瞻收益率 + Triple Barrier（1/-1/0） |
| 特征标准化 | ✅ | 截面 z-score + Winsorize + 截面中位数填充 |
| Purged K-Fold | ✅ | 时间序列感知分割，支持 purge_window + embargo_days |
| LightGBM 训练 | ✅ | 回归器，RMSE/MAE/R²/方向准确率 |
| XGBoost 训练 | ✅ | 回归器 + 分类器（含精确率/召回率/F1） |
| Walk-Forward 验证 | ✅ | 滚动训练窗口，无前视偏差 |
| MLflow 集成 | ✅ | 实验跟踪（可降级为 no-op） |
| 线性模型 | ❌ | Ridge/Lasso 未实现 |
| 神经网络 | ❌ | LSTM/Transformer 未实现 |
| 模型解释性 | ❌ | SHAP 值未实现 |
| 特征重要性管道 | ❌ | 无自动特征筛选 |
| 模型集成 | ❌ | 无 Stacking/Blending |
| 预测→信号转换 | ❌ | ML 预测未接入策略信号生成 |

### 6.2 关键问题

**P0 - ML 预测与策略信号未打通**

`ml_lab` 能训练模型，但：
- `gold_predictions` 表已定义，但 `LGBMTrainer` / `XGBTrainer` 不写入该表
- 没有任何 `Strategy` 子类能读取 ML 模型的预测结果并生成信号
- 端到端流程断裂：训练完的模型无法直接驱动回测

**P1 - 无自动特征筛选**

量化 ML 中，因子/特征的有效性随市场环境变化。缺少：
- 基于 IC 的特征过滤（低 IC 因子应被剔除）
- 多重共线性检测（因子间高相关）
- 递归特征消除（RFE）

**P2 - Triple Barrier 参数固定**

标签构建中 `upper_pct=0.05, lower_pct=-0.05, max_periods=10` 为函数参数，但：
- 不同波动率环境应有不同阈值（如高波时应扩大 barrier）
- 建议使用 ATR 动态设置 barrier 宽度

### 6.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 实现 `MLModelStrategy`（读取 gold_predictions → 信号） | ML 端到端打通 |
| P0 | LGBMTrainer 写入 `gold_predictions` | 预测持久化 |
| P1 | 特征选择管道（IC 过滤 + 相关性剔除） | 模型泛化性 |
| P2 | ATR 动态 Triple Barrier | 标签质量 |
| P3 | SHAP 解释性 | 模型可解释 |

---

## 七、回测评估

### 7.1 指标完整性（v2）

| 指标 | v1 状态 | v2 状态 |
|------|---------|---------|
| Sharpe | ✅ | ✅ |
| Sortino | ❌ | ✅ 已实现 |
| Calmar | ✅ | ✅ |
| Max Drawdown | ✅ | ✅ |
| VaR 95% | ❌ NULL | ✅ 已计算 |
| CVaR 95% | ❌ NULL | ✅ 已计算 |
| Beta | ❌ NULL | ✅ 支持基准输入 |
| Win Rate | ✅ | ✅ |
| Profit Factor | ✅ | ✅ |
| Information Ratio | ❌ | ❌ 仍未实现 |
| Tracking Error | ❌ | ❌ 仍未实现 |
| Alpha (Jensen's α) | ❌ | ❌ 仍未实现 |
| Tail Ratio | ❌ | ❌ |
| Omega Ratio | ❌ | ❌ |
| Turnover % | ❌ | ❌ |

### 7.2 关键残留问题

**P1 - 主动管理核心指标缺失**

Information Ratio = 超额收益 / 跟踪误差，是主动管理的核心评价指标：
- 基准 (`CSI300`) 在 `backtest.toml` 中配置，但 `compute_metrics` 中未使用
- 无法回答"这个策略相对基准的信息含量"这一核心问题

**P1 - RiskContext 仍基于目标权重**

`_build_risk_context()` 从目标权重构建仓位，而非实际 fill 历史：
- 当有订单被风控 CLIPPED 或 REJECTED 时，实际仓位与目标仓位不同
- 导致后续 step 的风控检查依据是错误的仓位状态
- 建议：RiskContext 应从 `PortfolioLedger` 的实时仓位构建

**P1 - 组合快照数据仍不准确**

`_persist_portfolio_snapshots` 中仍使用硬编码估算：
```python
cash = nav * 0.1      # 硬编码假设 10% 现金
gross_exposure = nav * 0.9  # 应来自 fill simulator 实际数据
```

**P2 - Attribution 模块未接入**

`BrinsonAttribution` 和 `FactorAttribution` 代码完整，但 `AnalysisEngine.run()` 未调用，需要手动调用。

### 7.3 建议优先级

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P1 | 实现 Information Ratio + Tracking Error + Alpha | 主动管理评价 |
| P1 | RiskContext 从 PortfolioLedger 实时仓位构建 | 风控数据准确性 |
| P1 | 修复 portfolio snapshots 硬编码估算 | 报告准确性 |
| P2 | Attribution 接入 AnalysisEngine | 自动化归因分析 |

---

## 八、仓位控制与组合优化

### 8.1 现状（v2 重大升级）

| 组件 | v1 | v2 |
|------|----|----|
| EqualWeight | ✅ | ✅ |
| Kelly | ⚠️ 代理值 | ⚠️ 部分真实（vol 真实，胜率仍代理） |
| TargetVol | ⚠️ 代理值 | ⚠️ 部分真实（vol 真实，协方差未用） |
| VolParity | ✅ | ✅ |
| **MvoSizer** | ❌ | ✅ SLSQP 真实 MVO |
| **BlackLittermanSizer** | ❌ | ✅ 贝叶斯更新，真实 BL |
| **MeanVarianceOptimizer** | ❌ | ✅ 最大化 Sharpe，多约束 |
| **RiskParityOptimizer** | ❌ | ✅ 等风险贡献（ERC） |
| **CostAwareOptimizer** | ❌ | ✅ 换手惩罚项 |

### 8.2 关键问题

**P1 - portfolio_opt 与回测引擎未集成**

`portfolio_opt` 是独立模块，回测引擎只调用 `riskguard/sizers/`：
- `MeanVarianceOptimizer` 无法在回测中被策略调用
- 建议：在 `BacktestSpec` 中增加 `optimizer` 字段，引擎在信号生成后调用优化器

**P1 - MVO/BL 需要外部 expected_returns 和 covariance**

两个优化器的输入数据没有自动计算来源：
- `expected_returns` 应来自 ML 模型预测或因子线性回归估算
- `covariance` 应来自历史收益率的滚动协方差矩阵
- 建议：实现 `CovarianceEstimator`（历史/EWMA/Ledoit-Wolf 收缩）

**P2 - Kelly 胜率仍是代理值**

```python
# 当前实现
p = clamp(signal.confidence, 0.1, 0.9)  # 胜率 = 信号置信度（主观）
```
真正的 Kelly 应从历史交易记录中统计实际胜率/赔率。

---

## 九、风险控制

### 9.1 现状（v2 大幅改善）

| 能力 | v1 | v2 |
|------|----|----|
| 仓位比例限制 | ✅ | ✅ |
| 杠杆限制 | ❌ | ✅ |
| 行业暴露限制 | ❌ | ✅ |
| 固定止损 | ❌ | ✅ |
| 移动止损 | ❌ | ✅ |
| 回撤熔断 | ❌ | ✅ |
| ATR 止损 | ❌ | ❌ 仍未实现 |
| 时间止损 | ❌ | ❌ 仍未实现 |
| 分级熔断 | ❌ | ❌ 单阈值，非分级 |
| 高水位自动追踪 | ❌ | ❌ 需调用方手动维护 |
| Policy 链编排器（独立类） | ❌ | ⚠️ 内嵌在 engine.py |

### 9.2 关键残留问题

**P1 - 无高水位自动追踪**

`portfolio_ledger.py` 的 `get_drawdown(peak_nav, current_nav)` 需要调用方传入 `peak_nav`：
- 回测引擎未维护高水位 NAV 的状态变量
- 导致每步计算的 drawdown 不准确
- 建议：在 `PortfolioLedger` 内部自动维护 `_peak_nav` 状态

**P1 - DrawdownBreakerPolicy 无恢复机制**

当前实现一旦触发 -10% 阈值，将永久拒绝买单：
- 没有恢复条件（如回升 2% 以上才解除）
- 没有分级机制（-5% 减仓 50%，-10% 全停）
- 实盘中可能导致策略永久关闭

**P1 - SectorLimitPolicy 无内置数据源**

`SectorLimitPolicy` 接受外部 `sector_map` dict，但：
- 无法从 `silver_assets` 自动加载行业映射
- 回测引擎在构建 `RiskContext` 时未传递行业信息
- 实际上该 policy 在回测中形同虚设

**P2 - 无因子暴露限制**

`RiskLimit.limit_type == 'factor_exposure'` 在数据模型中定义，但无对应 Policy 实现。对于量化多因子策略，控制因子暴露（如 beta 中性、size 中性）是标准操作。

---

## 十、执行与交易

### 10.1 现状（v2 新增 execution 模块）

| 能力 | v1 | v2 |
|------|----|----|
| Paper Broker | ✅ | ✅（含成本模型）|
| QMT Broker | ❌ 占位符 | ✅ 部分实现（连接/下单/撤单/查仓）|
| Broker 抽象层 | ❌ | ✅ Broker ABC + BrokerAdapter |
| Paper Broker 经过风控 | ❌ | ❌ 仍未接入 RiskPolicy |
| 订单状态机 | ❌ | ⚠️ 定义完整但 Paper 直接跳 FILLED |
| VWAP/TWAP 执行 | ❌ | ❌ 仍未实现 |

### 10.2 关键残留问题

**P1 - Paper Broker 绕过风控**

`paper_broker.py` 直接调用 `CostModel` 计算成本后立即成交，未经过任何 `RiskPolicy` 检查：
- 等于模拟交易没有风控保护
- 与回测引擎的风控逻辑不一致
- 建议：Paper Broker 在 `submit_order()` 前调用策略绑定的 Policy 链

**P1 - QMT 适配器回调机制不完整**

当前 QMT 适配器在 `submit_order()` 后立即返回，但 QMT 的成交回报是异步推送的：
- 未实现 QMT 回调注册（`xtquant` 的 `on_order_stock_async_response`）
- 成交状态不会自动更新
- 建议：实现 `XtQuantTraderCallback` 子类并注册回调

**P2 - 无滑点/市场冲击高级模型**

所有成交仍使用收盘价 + 固定比例滑点：
- 大单（占当日成交量 >1%）的市场冲击被低估
- 建议实现简单的 Almgren-Chriss 或 Kyle's lambda 冲击模型

---

## 十一、AI 研究助手与知识库

### 11.1 现状（v2 全新，Phase 3 超前完成）

| 能力 | 状态 | 亮点 |
|------|------|------|
| 多 Agent 编排 | ✅ | 5 专业 Agent（研究/风险/辩论/报告/执行） |
| RAG 知识检索 | ✅ | LanceDB + DuckDB 混合检索（RRF 融合） |
| LLM 多提供商 | ✅ | Claude + OpenAI + 故障转移 |
| 安全策略 | ✅ | 工具调用授权 + 响应验证，执行 Agent 只读 |
| 新闻 PIT 控制 | ✅ | 按数据源延迟模型过滤 |
| 文档摄取 | ✅ | PDF/URL/Markdown/CSV 四种格式 |
| 向量检索 | ✅ | LanceDB Arrow-native 本地存储 |
| 语义相似文档 | ✅ | 基于 doc 质心的相似搜索 |
| SSE 流式推送 | ✅ | Agent 进度流 + 实时行情流 |
| 身份认证 | ❌ | API Server 无 Auth |
| 情感分析 | ❌ | newsflow 情感得分永远 NULL |
| 会话持久化 | ❌ | 内存 dict，重启丢失 |
| 嵌入模型本地化 | ⚠️ | 默认 NullEmbeddingProvider，只有关键词检索 |

### 11.2 关键问题

**P1 - API Server 无认证**

所有 `/advisor`、`/live`、`/knowledge` 端点无任何认证机制：
- 任何人可以访问实时行情和知识库
- 建议：至少添加 Bearer Token 认证（API Key 即可）

**P1 - 情感分析为 NULL**

`newsflow/normalize.py` 的 `sentiment_score` 字段始终为 NULL：
- `newsflow` 有 PIT 控制、去重、分类，但没有情感模型
- 建议：集成 FinBERT 或 Claude API 实现中文财经新闻情感分析

**P2 - 嵌入模型默认为 NullProvider**

默认 `NullEmbeddingProvider` 返回零向量，知识库只能做关键词检索：
- 语义相似度搜索完全失效
- 建议：为本地部署提供 `sentence-transformers` 作为默认嵌入，避免强依赖 OpenAI

---

## 十二、基础设施与工程质量

### 12.1 整体质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | 9/10 | 模块边界清晰、接口抽象合理、依赖方向正确 |
| 代码质量 | 8/10 | 类型标注完整、Pydantic 验证、错误处理规范 |
| 测试覆盖 | 6/10 | 46 个单元测试，但质量未知，无覆盖率报告 |
| 文档同步 | 5/10 | CLAUDE.md 部分过时，模块 README 缺失 |
| 可观测性 | 4/10 | 无 metrics/tracing，只有 logging |
| 生产就绪 | 4/10 | 无 Auth/Rate Limit/熔断，无容器化 |

### 12.2 关键工程问题

**P1 - 无 [project.dependencies]**

`pyproject.toml` 仍无依赖声明，`pip install cquant` 会安装一个空壳：
- 阻断了 Docker 化部署路径
- 建议：将 `environment.yml` 的核心依赖迁移到 `pyproject.toml`

**P1 - configs/defaults/*.toml 未被 CLI 读取**

`backtest.toml`、`datahub.toml` 等配置文件存在但 CLI 不加载：
- 用户改了配置文件但 CLI 不生效
- 建议：添加 `config.py` 层，支持 TOML → 命令行参数覆盖

**P2 - 测试质量未知**

有 46 个测试文件，但：
- 无 pytest coverage report（`pytest --cov` 未配置）
- 部分测试可能是空测试或纯 import 测试
- 建议：配置 `pytest-cov`，目标行覆盖率 ≥ 70%

**P2 - CLAUDE.md 部分过时**

`CLAUDE.md` 仍显示 `api_server`、`ml_lab`、`knowledge_base` 为"未开始"：
- 新模块未更新模块索引表
- 建议：同步更新 Phase 状态和模块索引

---

## 十三、优先级路线图

### P0：端到端流程断裂修复（1-2 周）

| # | 任务 | 模块 | 影响 |
|---|------|------|------|
| 1 | 基本面数据加载到 `ctx.extra`（Tushare 财务 API） | datahub + factorlab | 11 个基本面因子从 NULL 变可用 |
| 2 | Pipeline 接入 DAG 引擎 | factorlab | 复合因子构建能力 |
| 3 | Lookback 窗口改为动态计算 | factorlab | 消除前端 NULL |
| 4 | ML 预测写入 `gold_predictions` | ml_lab | ML 训练结果可持久化 |
| 5 | 实现 `MLModelStrategy`（预测→信号） | backtest_vector | ML 端到端打通 |

### P1：核心质量提升（2-4 周）

| # | 任务 | 模块 | 影响 |
|---|------|------|------|
| 6 | CLI 支持多数据源（akshare/tushare/yfinance） | datahub | 数据采集完整 |
| 7 | 实现 Information Ratio + Tracking Error + Alpha | backtest_vector | 主动管理指标 |
| 8 | RiskContext 从 PortfolioLedger 实时仓位构建 | backtest_vector | 风控数据准确 |
| 9 | portfolio_opt 与回测引擎集成 | portfolio_opt | MVO/RP 进入回测 |
| 10 | 高水位追踪内置于 PortfolioLedger | riskguard | DrawdownBreaker 准确 |
| 11 | DrawdownBreaker 分级机制 + 恢复条件 | riskguard | 实盘可用性 |
| 12 | SectorLimitPolicy 从 silver_assets 自动加载行业 | riskguard | 行业风控生效 |
| 13 | Paper Broker 接入 RiskPolicy | execution | 模拟交易风控 |
| 14 | 因子评估补充 Rank IC 衰减 + 换手率 + 分层回测 | factorlab | 因子选择科学化 |
| 15 | API Server 添加 Bearer Token 认证 | api_server | 安全性 |

### P2：功能完善（4-8 周）

| # | 任务 | 模块 | 影响 |
|---|------|------|------|
| 16 | 协方差矩阵估计器（历史/EWMA/Ledoit-Wolf） | portfolio_opt | MVO/BL 输入数据 |
| 17 | 情感分析模型集成（FinBERT/Claude） | newsflow | 新闻因子可用 |
| 18 | 分钟级数据存储（silver_prices_intraday） | datahub | 日内策略支持 |
| 19 | QMT 适配器回调机制 | execution | 实盘成交回报 |
| 20 | 数据质量管道（异常值检测/填充） | datahub | 因子计算稳定性 |
| 21 | 会话持久化（SQLite/Redis） | ai_advisor | AI 助手可靠性 |
| 22 | ATR 止损 + 时间止损 Policy | riskguard | 风控多样化 |
| 23 | 特征重要性 + SHAP 分析 | ml_lab | 模型可解释性 |
| 24 | pyproject.toml 补充依赖声明 | 基础设施 | 容器化支持 |

### P3：高级能力（8-16 周）

| # | 任务 | 模块 | 影响 |
|---|------|------|------|
| 25 | 事件驱动回测与向量化回测 parity 验证 | backtest_event | 引擎可信度 |
| 26 | 行业轮动策略 + 市场中性策略 | backtest_vector | 策略多元化 |
| 27 | Almgren-Chriss 市场冲击模型 | backtest_vector | 大资金回测真实性 |
| 28 | LSTM/Transformer 时序模型 | ml_lab | 深度学习 alpha |
| 29 | React 前端仪表盘 | web | 可视化 |
| 30 | Docker/K8s 部署方案 | 基础设施 | 生产环境 |

---

## 附录：量化流程完整性自评

| 流程阶段 | v1 完成度 | v2 完成度 | 变化 |
|----------|-----------|-----------|------|
| 数据采集 | 70% | 80% | +10% |
| 数据清洗 | 50% | 55% | +5% |
| 因子挖掘 | 40% | 65% | +25% |
| 策略制定 | 15% | 50% | +35% |
| 机器学习 | 0% | 60% | +60% |
| 回测评估 | 65% | 78% | +13% |
| 仓位控制 | 35% | 70% | +35% |
| 风险控制 | 20% | 65% | +45% |
| 执行交易 | 25% | 45% | +20% |
| 监控报告 | 30% | 55% | +25% |
| **综合** | **35%** | **62%** | **+27%** |

### 综合结论

**v2 是一次全面性的升级，平台已具备量化研究的基本完整性。**

- **架构评分：9/10** — 设计优秀，扩展性强，代码风格统一
- **量化实战能力：6/10** — 主要流程已贯通，但端到端仍有断裂点（基本面数据、ML→信号、portfolio_opt→引擎）
- **生产就绪度：4/10** — 核心功能完备，但缺乏认证、监控、容器化等工程保障

**最关键的 3 个断点（优先解决）：**
1. **基本面数据未打通** → 11 个因子为 NULL，ML 特征缺失基本面维度
2. **ML 预测未接入策略** → 训练的模型不能驱动回测，整个 ml_lab 是孤岛
3. **portfolio_opt 未接入引擎** → MVO/风险平价优化器无法在回测中使用

---

*本报告基于代码静态分析，测试验证以实际运行结果为准。*
*下一次评估建议在 P0/P1 任务完成后进行。*
