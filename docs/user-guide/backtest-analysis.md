# 回测分析指南

本篇逐个解读回测详情页的分析 Tab。cQuant 提供多个 Tab，从不同角度审视回测结果。

回测详情页路径：`http://localhost:3000/backtests/{run_id}`。Tab 导航位于顶部，其中 **WalkForward Tab 仅在 `engine=walk_forward` 时显示**。

---

## Tab 总览

| Tab | 路径 | 用途 |
|-----|------|------|
| [Overview](#1-overview总览) | `` | 核心指标 + NAV 曲线 + 基准对比 |
| [Tearsheet](#2-tearsheet收益报告) | `tearsheet` | 经典 tearsheet（月度热力图等） |
| [Overfitting](#3-overfitting过拟合检测) | `overfitting` | 过拟合检测（DSR/PSR/CPCV） |
| [Fills](#4-fills成交明细) | `fills` | 逐笔成交 + K 线标注 |
| [WalkForward](#5-walkforward滚动重训) | `walkforward` | 滚动重训结果（条件显示） |
| [TCA](#6-tca交易成本分析) | `tca` | 交易成本归因（含 Brinson 归因） |
| [Risk](#7-risk风险分析) | `risk` | 风险指标 + 持仓集中度 + 因子分解 |
| [Calendar](#8-calendar日历分析) | `calendar` | 日历效应 + 假日效应 |
| [Advanced](#9-advanced高级分析) | `advanced` | 收益分布 + 滚动指标 + 压力测试 |
| [ModelCompare](#10-modelcompare模型对比) | `model-compare` | ML 模型横向对比 |
| [FeatureImportance](#11-featureimportance特征重要性) | `feature-importance` | ML 特征重要性 |
| [ModelDiagnostics](#12-modeldiagnostics模型诊断) | `model-diagnostics` | ML 模型诊断 |
| [TradeAnalysis](#13-tradeanalysis交易分析) | `trade-analysis` | 单笔交易盈亏 + MFE/MAE |

> ModelCompare / FeatureImportance / ModelDiagnostics 三个 Tab 主要用于 ML 策略（`MLModelStrategy`）。

---

## 1. Overview（总览）

**用途**：一屏看清回测整体表现。

**关键指标**：
| 指标 | 含义 | 解读 |
|------|------|------|
| Total Return | 累计收益率 | 区间总收益 |
| Annualized Return | 年化收益率 | 折算年化 |
| Sharpe Ratio | 夏普比率 | > 1 合格，> 2 优秀 |
| Sortino Ratio | 索提诺比率 | 仅用下行波动，> 1 合格 |
| Max Drawdown | 最大回撤 | 越小越好，< 20% 较稳 |
| Calmar Ratio | 年化收益 / 最大回撤 | > 1 合格 |
| Win Rate | 胜率 | 单笔交易盈利占比 |
| Profit Factor | 盈亏比 | 总盈利 / 总亏损，> 1.5 合格 |
| Information Ratio (IR) | 信息比率 | 相对基准的超额收益 / 跟踪误差 |
| Tracking Error (TE) | 跟踪误差 | 相对基准的波动 |
| Alpha / Beta | 超额收益 / 市场敏感度 | Alpha 越高越好，Beta 反映系统性风险 |
| Turnover | 换手率 | 日均换手，影响成本 |
| HHI | 赫芬达尔指数 | 持仓集中度，越低越分散 |

**图表**：
- **NAV 曲线**：策略净值 vs 基准净值，带调仓标记；
- **回撤时序**：逐日回撤，直观显示回撤持续时间和深度；
- **滚动 Sharpe / 波动率**：随时间变化的滚动指标，判断策略稳定性；
- **Benchmark Compare**：相对基准的 Alpha/Beta 滚动、捕获比、相关性。

![Overview 总览](placeholder-overview.png)

**如何解读**：先看 Sharpe 和 Max Drawdown 是否达标，再看 NAV 曲线是否平稳跑赢基准，最后看回撤时序确认最大回撤发生在什么市场环境。

---

## 2. Tearsheet（收益报告）

**用途**：经典 tearsheet 报告，类似 pyfolio / Quantopian 风格。

**关键内容**：
- 累计收益曲线；
- **月度收益热力图**（`MonthlyHeatmap`）：每格是一个月的收益率，红绿直观显示月度表现；
- 月度/年度收益分布；
- 滚动夏普、滚动波动率。

**如何解读**：月度热力图若大面积飘绿（亏损），说明策略在某些月份系统性失效，需检查是否与特定市场环境（如熊市、震荡市）相关。

---

## 3. Overfitting（过拟合检测）

**用途**：检测策略是否过拟合（in-sample 表现好但 out-of-sample 失效）。

**关键指标**：
| 指标 | 含义 |
|------|------|
| DSR（Deflated Sharpe Ratio） | 通胀调整后的夏普比率，考虑了"试错次数"的影响 |
| PSR（Probabilistic Sharpe Ratio） | 夏普比率超过基准的概率 |
| CPCV（Combinatorial Purged Cross-Validation） | 组合交叉验证，评估样本外稳健性 |
| 过拟合评分（`OverfitScore`） | 综合评分，分数越高越可能过拟合 |

**如何解读**：
- DSR < 1 或 PSR < 0.95 → 可能过拟合，谨慎上线；
- CPCV 各折的 OOS 表现方差大 → 策略不稳定；
- 过拟合评分高 → 需简化策略或增加样本。

> 若启用了 Walk-Forward 重训，过拟合评分会纳入 refit 的 OOS 指标，更可靠。

---

## 4. Fills（成交明细）

**用途**：逐笔成交记录，核对策略实际执行情况。

**关键内容**：
- 成交表（分页）：日期、标的、方向、价格、数量、成本、成交原因；
- 成交原因（`reason`）：如 `signal`（信号）、`stop_loss`（止损）、`forced_exit`（强制退出）、`rebalance`（调仓），高亮显示；
- **成交散点图**（`TradeScatter`）：收益 vs 持有时长散点；
- **K 线标注**（`TradeKlineChart`）：在 K 线图上标注买卖点，折叠标注避免密集。

**如何解读**：检查成交原因分布是否合理（止损过多？强制退出频繁？）；K 线标注核对买卖点是否符合策略逻辑。

![Fills 成交明细](placeholder-fills.png)

---

## 5. WalkForward（滚动重训）

**用途**：展示滚动重训（walk-forward）回测的逐折结果。**仅当 `engine=walk_forward` 时显示。**

**关键内容**：
- 各折（fold）的时间窗口、训练/测试样本量；
- 各折 OOS（out-of-sample）指标：夏普、收益、回撤；
- `FoldMetricsCard`：汇总各折指标对比；
- IS（in-sample）vs OOS（out-of-sample）对比面板。

**如何解读**：OOS 指标稳定（各折方差小）说明策略稳健；OOS 远低于 IS 说明过拟合。

---

## 6. TCA（交易成本分析）

**用途**：交易成本归因分析（Transaction Cost Analysis）+ Brinson 归因。

**关键内容**：
- 成本分解：佣金、印花税、滑点、市场冲击各项占比；
- **Brinson 归因**：将超额收益分解为**配置效应**（行业/资产配置）和**选股效应**（个股选择）；
- 总成本占收益的比例。

**如何解读**：若滑点/市场冲击占比过高，说明策略换手过频或流动性不足；Brinson 归因告诉你超额收益来自"选对行业"还是"选对个股"。

---

## 7. Risk（风险分析）

**用途**：多维度风险分析。

**关键内容**：
- **风险指标**：VaR 95%、CVaR 95%、组合 VaR、下行风险；
- **持仓集中度**（`PositionConcentration`）：HHI、单仓位权重分布；
- **滚动风险指标**：滚动波动率、滚动 VaR；
- **回撤分析**：Top N 回撤的深度、持续时间、恢复时间；
- **因子风险分解**（`factor_decomposition`）：组合收益分解到各风险因子。

**如何解读**：VaR/CVaR 反映尾部风险；持仓集中度过高（HHI > 0.3）说明风险集中；因子分解揭示组合暴露于哪些系统性因子。

---

## 8. Calendar（日历分析）

**用途**：分析策略表现的日历效应。

**关键内容**：
- **月度/星期效应**：哪些月份/星期收益更高；
- **假日效应**（`holiday effects`）：节假日前后的收益特征（如 A 股"春节效应"）；
- 月度胜率统计。

**如何解读**：若收益高度集中在某几个月，说明策略依赖特定季节性，需评估其可持续性；假日效应可辅助择时。

---

## 9. Advanced（高级分析）

**用途**：进阶统计分析与压力测试。

**关键内容**：
- **收益分布**：直方图、偏度、峰度、正态性检验；
- **滚动指标**：滚动 Alpha/Beta/Sharpe/Volatility；
- **统计检验面板**（`StatisticalTestPanel`）：检验收益是否显著异于 0；
- **历史压力测试**：用历史极端场景（如 2015 股灾、2020 疫情）回放策略；
- **参数敏感性分析**（`SensitivityPanel`）：关键参数微调对结果的影响（热力图）。

**如何解读**：收益分布若右偏且厚尾为佳；压力测试中策略最大回撤可接受则稳健；参数敏感性热力图若大面积剧烈变化 → 参数过拟合。

---

## 10. ModelCompare（模型对比）

**用途**：横向对比多个 ML 模型（LightGBM / XGBoost / qlib 各模型）。主要针对 ML 策略。

**关键内容**：各模型的训练指标（IC、Rank IC、准确率）、预测分布、训练耗时对比表。

**如何解读**：选 IC 高且训练稳定的模型；警惕训练指标虚高但预测分布异常的模型。

---

## 11. FeatureImportance（特征重要性）

**用途**：展示 ML 模型的特征重要性。主要针对 ML 策略。

**关键内容**：LightGBM/XGBoost 的 gain / split 重要性排序条形图。

**如何解读**：检查重要特征是否符合金融逻辑；若一个无关特征重要性异常高，可能是数据泄露。

---

## 12. ModelDiagnostics（模型诊断）

**用途**：ML 模型诊断。主要针对 ML 策略。

**关键内容**：预测值分布、残差分析、IC 衰减、过拟合检测（训练 vs 验证）。

**如何解读**：预测分布应合理（无明显偏斜）；IC 衰减应平滑；训练 IC 远高于验证 IC → 过拟合。

---

## 13. TradeAnalysis（交易分析）

**用途**：单笔交易（round-trip）层面的盈亏分析。

**关键内容**：
- **round-trip 匹配**：将买卖配对成完整交易；
- **MFE / MAE**：Maximum Favorable Excursion（最大浮盈）/ Maximum Adverse Excursion（最大浮亏）；
- **多空拆分**：做多/做空交易分别统计；
- 持有时长分布、单笔盈亏分布。

**如何解读**：MFE 远大于 MAE 说明能拿住盈利单；MAE 过大说明止损过晚；持有时长分布应与策略周期匹配。

---

## 分析流程建议

1. **Overview** 看整体是否达标；
2. **Tearsheet** 看月度表现模式；
3. **Overfitting** 排除过拟合；
4. **Risk** 评估尾部风险与集中度；
5. **Fills / TradeAnalysis** 核对执行细节；
6. **TCA** 分析成本结构；
7. **Advanced** 做压力测试与敏感性分析；
8. （ML 策略）**ModelCompare / FeatureImportance / ModelDiagnostics** 审查模型。

---

## 相关文档

- [回测配置指南](backtest.md)
- [策略配置指南](strategy-config.md)
- [实盘交易指南](live-trading.md)
