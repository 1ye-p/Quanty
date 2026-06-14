# cQuant 前端产品评估报告（v3）

> 评估时间：2026-06-07
> 评估范围：web/src/ 全量代码（含 Phase 7 重构）
> 角色：产品经理（量化交易方向）

---

## 一、v2 → v3 变更摘要

v2 报告提出 6 个 P0 + 5 个 P1 改进项。本轮迭代**全部 P0 已解决 + 4 个 P1 已解决**：

| v2 问题 | 状态 | 解决方式 |
|---------|------|---------|
| **P0: BacktestsPage legacy 2,001 行** | ✅ 已删除 | Phase 7 直接删除文件，路由已切换到 List/Detail/Compare + 12 tabs |
| **P0: 工作流与页面深度集成** | ✅ 已解决 | FactorsPage / MLLabPage / OptimizePage / BacktestDetailPage 均调用 `updateContext`，新增 WorkflowSummary 组件 |
| **P0: 3 个 stub tab** | ✅ 已解决 | 委托给真实组件（ModelCompareTab 175 行 / FeatureImportanceTab 94 行 / ModelDiagnosticsTab 236 行）|
| **P1: KnowledgePage 骨架** | ✅ 已解决 | 4 个组件（Upload/Preview/Tags/List），232 行页面 + 480 行组件 |
| **P1: 图表集成到页面** | ✅ 已解决 | TradeScatter→FillsTab, PositionConcentration→LivePage, Attribution→AttributionTab |
| **P1: FactorsPage/MLLabPage 组件提取** | ✅ 已解决 | FactorsPage 889→265 行（-70%），MLLabPage 802→378 行（-53%）|
| **P2: DatasetsPage 数据浏览** | ✅ 已解决 | 4 个组件（DataPreview/FieldStats/QualityReport/AnomalyMarkers）|
| **P2: 实盘能力 LivePage** | ✅ 大幅改善 | 5 个组件（DeploymentCard/FundCurve/PositionPnL/ExecutionLog/RiskMonitor）|
| **P2: PipelinePage DAG 编辑器** | ✅ 已解决 | @xyflow/react DAG 编辑器 + NodeConfig + PipelineStatus |
| **P2: 告警通道配置** | ✅ 已解决 | 3 个组件（ChannelForm/ChannelList/SilenceRules），AlertsPage 改为 3-tab |

---

## 二、当前页面全景

### 页面代码量（最终状态）

| 页面 | v1 行数 | v3 行数 | 变化 | 评价 |
|------|---------|---------|------|------|
| ~~BacktestsPage~~ | 2,044 | **已删除** | -100% | ✅ 死代码清理完毕 |
| StrategiesPage | 1,412 | 1,412 | 不变 | ⚠️ 最大页面，已有组件提取 |
| OptimizePage | 760 | 778 | +2% | ⚠️ 仍较大，已有 3 个 tab 组件（481 行）|
| AdvisorPage | 522 | 522 | 不变 | OK |
| NewsPage | 431 | 431 | 不变 | OK |
| LivePage | 413 | 427 | +3% | ✅ 功能大幅增强 |
| ScoringPage | 403 | 403 | 不变 | OK |
| OverviewPage | 395 | 395 | 不变 | OK |
| AlertsPage | 433 | 379 | -12% | ✅ 改为 3-tab |
| MLLabPage | 802 | **378** | **-53%** | ✅ 组件提取 + 工作流集成 |
| BacktestsListPage | — | 356 | 新增 | ✅ 回测列表页 |
| FactorsPage | 889 | **265** | **-70%** | ✅ 组件提取 + 工作流集成 |
| TasksPage | 225 | 225 | 不变 | OK |
| RiskPage | 217 | 217 | 不变 | OK |
| PipelinePage | 145 | 199 | +37% | ✅ DAG 编辑器 |
| KnowledgePage | 140 | 232 | +66% | ✅ 功能大幅增强 |
| DatasetsPage | 278 | 279 | 不变 | ✅ 功能大幅增强（组件 390 行）|
| TradingPage | 162 | 162 | 不变 | OK |
| **合计** | **9,689** | **7,144** | **-26%** | 页面代码大幅瘦身 |

### 工作流集成详情（Phase 7）

| 页面 | 写入的 context 字段 | 触发时机 |
|------|-------------------|---------|
| **FactorsPage** | `selectedFactors`, `factorICResults` | IC 计算完成后 |
| **MLLabPage** | `experimentId`, `modelId`, `modelVersion` | 训练任务完成后 |
| **OptimizePage** | `optimizeConfig`, `optimizeResults` | 优化计算完成后 |
| **BacktestDetailPage** | `backtestId`, `backtestResults` | 回测详情加载后 |
| **WorkflowSummary** | — | 展示工作流全流程上下文汇总 |

### 新增组件汇总（31 个组件，4,248 行）

| 域 | 组件 | 行数 | 功能 |
|----|------|------|------|
| **knowledge/** | DocumentUpload | 193 | 文件上传（拖拽 + URL + 文本）|
| | DocumentPreview | 135 | 文档内容预览 |
| | DocumentTags | 56 | 标签管理 |
| | DocumentList | 96 | 文档列表 |
| **datasets/** | DataPreview | 91 | 数据表格预览 |
| | FieldStats | 104 | 字段级统计（min/max/mean/null率）|
| | QualityReport | 129 | 数据质量报告 |
| | AnomalyMarkers | 66 | 异常值标记 |
| **live/** | DeploymentCard | 90 | 策略部署卡片 |
| | FundCurve | 87 | 资金曲线图 |
| | PositionPnL | 87 | 持仓盈亏表 |
| | ExecutionLog | 111 | 执行日志 |
| | RiskMonitor | 125 | 风险监控面板 |
| **pipeline/** | PipelineDAG | 169 | DAG 编辑器（@xyflow/react）|
| | NodeConfig | 175 | 节点配置面板 |
| | PipelineStatus | 112 | 管道状态展示 |
| **alerts/** | ChannelForm | 178 | 通知渠道配置 |
| | ChannelList | 158 | 渠道列表管理 |
| | SilenceRules | 156 | 静默规则配置 |
| **factors/** | CreateFactorModal | 130 | 因子创建弹窗 |
| | FactorCard | 51 | 因子卡片 |
| | ICCalculator | 87 | IC 计算器 |
| | ICAlertModal | 68 | IC 阈值告警 |
| **ml/** | TrainForm | 191 | ML 训练表单 |
| | ModelCompareTab | 175 | 模型对比视图 |
| | FeatureImportanceTab | 94 | 特征重要性 |
| | ModelDiagnosticsTab | 236 | 模型诊断 |
| **strategies/** | StrategyEditor | 48 | 策略编辑器 |
| | StrategyHeader | 32 | 策略头部 |
| | StrategyPreview | 96 | 策略预览 |
| | VersionHistoryPanel | 88 | 版本历史 |
| **optimize/** | ConstraintsTab | 261 | 约束配置 |
| | ResultsTab | 118 | 优化结果 |
| | RiskBudgetTab | 102 | 风险预算 |
| **workflow/** | WorkflowSummary | 111 | 工作流上下文汇总展示 |

---

## 三、各页面功能评估

### 🟢 功能完整且有深度（10 个页面）

| 页面 | 核心能力 | 状态 |
|------|---------|------|
| **Backtests（体系）** | List + Detail + Compare + 12 tabs + 7 专业图表 + 工作流集成 | ✅ 功能完整 |
| **StrategiesPage** | CRUD + Monaco Editor + 版本管理 + 组件提取 | ✅ 功能完整 |
| **FactorsPage** | IC 分析 + 相关性矩阵 + 分层收益 + IC 衰减 + 因子创建 + DSL 编辑器 + 工作流集成 | ✅ 70% 瘦身 |
| **MLLabPage** | 实验对比 + 模型列表 + 预测 + 训练表单 + 工作流集成 | ✅ 53% 瘦身 |
| **OptimizePage** | 协方差 + 3 种优化器 + 约束 + 结果 + 风险预算 + 工作流集成 | ✅ 功能完整 |
| **AdvisorPage** | 多 Agent + SSE 流式 + 会话历史 | ✅ 功能完整 |
| **KnowledgePage** | 上传（拖拽/URL/文本）+ 预览 + 标签 + 搜索 + 删除 | ✅ 从骨架升级 |
| **DatasetsPage** | 数据预览 + 字段统计 + 质量报告 + 异常标记 | ✅ 从骨架升级 |
| **LivePage** | 部署卡片 + 资金曲线 + 持仓盈亏 + 执行日志 + 风险监控 + 持仓集中度 | ✅ 从骨架升级 |
| **AlertsPage** | 告警规则 + 历史 + 通知渠道配置 + 静默规则 | ✅ 从骨架升级 |

### 🟡 有改善但仍需加强

| 页面 | 当前状态 | 仍缺失 |
|------|---------|--------|
| **PipelinePage** | DAG 编辑器 + 节点配置 + 状态展示 | 缺手动触发、参数模板、执行历史 |
| **TradingPage** | OrderForm + OrderBook + PositionTable | 仍仅 Paper Broker，缺订单历史/成交回报 |
| **RiskPage** | 风控检查 + Sizer 试算 | 缺持仓级实时风控、历史风控事件 |
| **NewsPage** | 新闻时间线 + 情绪颜色点 | 无新闻对因子/策略的影响分析 |
| **ScoringPage** | 截面打分快照 | 打分结果无历史对比 |

### 🔴 需关注

| 问题 | 优先级 |
|------|--------|
| StrategiesPage 1,412 行 | P1 — 已有 4 个组件提取（264 行），页面本身仍较大 |
| OptimizePage 778 行 | P1 — 已有 3 个 tab 组件（481 行），页面本身仍较大 |

---

## 四、v1 → v3 三轮迭代全景对比

| 维度 | v1 起点 | v2 改善 | v3 最终 |
|------|---------|---------|---------|
| **页面总数** | 18 页 | 18 页 + 12 tabs + Compare | **17 页** + 12 tabs + Compare（BacktestsPage 已删除）|
| **页面代码量** | 9,689 行 | 11,950 行 | **7,144 行**（-26%）|
| **组件文件** | ~30 个 | ~50 个 | **~80 个**（+31 个新组件）|
| **API 模块** | 1 个文件 1,225 行 | 21 个域模块 | 同左 |
| **状态管理** | 无 | Zustand 5 stores | 同左 + workflow 深度集成 |
| **骨架页面** | 5 个 | 5 个 | **1 个**（仅 Tasks 仍较薄）|
| **图表组件** | 1 个（PnLChart）| 8 个 | **8 个**（已全部集成到页面）|
| **工作流** | 无 | 3 条预定义（UI 就绪）| **3 条 + 页面深度集成**（4 个页面写入 context）|
| **导出/分享** | 无 | PDF/PNG + 策略分享 | 同左 |
| **暗色模式** | 无 | CSS 变量体系 | 同左 |
| **页面测试** | 0 | 11 个 | **15 个** |

---

## 五、当前优先级建议

### P0 — 已全部完成 ✅

| 项目 | 状态 |
|------|------|
| BacktestsPage 死代码删除 | ✅ 已删除 |
| 3 个 stub tab 实现 | ✅ 已实现（ModelCompare/FeatureImportance/ModelDiagnostics）|
| 工作流页面深度集成 | ✅ 4 个页面写入 context + WorkflowSummary |

### P1

| 项目 | 原因 | 工作量 |
|------|------|--------|
| StrategiesPage 组件提取（1,412 行）| 最大的非 legacy 页面 | 中 |
| OptimizePage 组件提取（778 行）| 约束编辑 UX 仍复杂 | 中 |
| ScoringPage 打分历史对比 | 打分结果无法纵向对比 | 小 |
| RiskPage 持仓级实时风控 | 当前仅下单前检查 | 中 |

### P2

| 项目 | 原因 | 工作量 |
|------|------|--------|
| TradingPage 真实券商接入 | 从研究到实盘的关键一步 | 大 |
| PipelinePage 执行历史 + 手动触发 | DAG 编辑器已就绪，缺执行能力 | 小 |
| NewsPage 因子/策略影响分析 | 新闻与量化研究的连接点 | 中 |

---

## 六、总结

v3 迭代**彻底解决了所有 P0 问题**：

1. **BacktestsPage 2,001 行死代码已删除**，路由切换到 List/Detail/Compare + 12 tabs
2. **工作流深度集成**：FactorsPage / MLLabPage / OptimizePage / BacktestDetailPage 均自动写入 workflow context，WorkflowSummary 展示全流程汇总
3. **3 个 stub tab 全部实现**，委托给真实组件（ModelCompareTab / FeatureImportanceTab / ModelDiagnosticsTab）
4. **页面代码从 9,689 行瘦身到 7,144 行**（-26%），组件从 ~30 个增加到 ~80 个
5. **5 个骨架页面中的 4 个升级为完整功能**，仅 Tasks 仍较薄

**无 P0 遗留问题。** 下一步聚焦 P1：StrategiesPage 和 OptimizePage 组件继续提取，ScoringPage 历史对比，RiskPage 实时风控。
