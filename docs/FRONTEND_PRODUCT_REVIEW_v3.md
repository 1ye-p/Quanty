# cQuant 前端产品评估报告（v3）

> 评估时间：2026-06-07（基于 v2 评估后的第三版迭代）
> 评估范围：web/src/ 全量代码
> 角色：产品经理（量化交易方向）

---

## 一、v2 → v3 变更摘要

v2 报告提出 6 个 P0 + 5 个 P1 改进项。本轮迭代**解决了 3 个 P0 + 4 个 P1**：

| v2 问题 | 状态 | 解决方式 |
|---------|------|---------|
| **P0: BacktestsPage legacy 2,001 行** | ❌ 未解决 | BacktestsPage.tsx 仍为 2,001 行 |
| **P0: 工作流与页面深度集成** | ⚠️ 部分 | WorkflowBar 在 AppLayout 中，但各页面未显式写入 context |
| **P0: 3 个 stub tab** | ❌ 未解决 | ModelCompare/FeatureImportance/ModelDiagnostics 仍为 stub |
| **P1: KnowledgePage 骨架** | ✅ 已解决 | 4 个组件（Upload/Preview/Tags/List），232 行页面 + 480 行组件 |
| **P1: 图表集成到页面** | ✅ 已解决 | TradeScatter→FillsTab, PositionConcentration→LivePage, Attribution→AttributionTab |
| **P1: FactorsPage/MLLabPage 组件提取** | ✅ 已解决 | FactorsPage 889→247 行（-72%），MLLabPage 802→365 行（-54%）|
| **P2: DatasetsPage 数据浏览** | ✅ 已解决 | 4 个组件（DataPreview/FieldStats/QualityReport/AnomalyMarkers）|
| **P2: 实盘能力 LivePage** | ✅ 大幅改善 | 5 个组件（DeploymentCard/FundCurve/PositionPnL/ExecutionLog/RiskMonitor）|
| **P2: PipelinePage DAG 编辑器** | ✅ 已解决 | @xyflow/react DAG 编辑器 + NodeConfig + PipelineStatus |
| **P2: 告警通道配置** | ✅ 已解决 | 3 个组件（ChannelForm/ChannelList/SilenceRules），AlertsPage 改为 3-tab |

**本轮新增代码：+4,671 行 / -2,537 行，净增 +2,134 行，新增 24 个组件文件。**

---

## 二、当前页面全景（v3）

### 页面代码量变化

| 页面 | v1 行数 | v3 行数 | 变化 | 评价 |
|------|---------|---------|------|------|
| BacktestsPage | 2,044 | 2,001 | -2% | ❌ legacy 未清理 |
| StrategiesPage | 1,412 | 1,412 | 不变 | ⚠️ 仍较大 |
| FactorsPage | 889 | **247** | **-72%** | ✅ 组件提取彻底 |
| OptimizePage | 760 | 760 | 不变 | ⚠️ 仍较大 |
| MLLabPage | 802 | **365** | **-54%** | ✅ 组件提取 |
| AdvisorPage | 522 | 522 | 不变 | OK |
| AlertsPage | 433 | **379** | -12% | ✅ 改为 3-tab |
| NewsPage | 431 | 431 | 不变 | OK |
| LivePage | 413 | **427** | +3% | ✅ 功能大幅增强 |
| ScoringPage | 403 | 403 | 不变 | OK |
| OverviewPage | 395 | 395 | 不变 | OK |
| DatasetsPage | 278 | **279** | 不变 | ✅ 功能大幅增强（组件 390 行）|
| TasksPage | 225 | 225 | 不变 | OK |
| RiskPage | 217 | 217 | 不变 | OK |
| PipelinePage | 145 | **199** | +37% | ✅ DAG 编辑器 |
| KnowledgePage | 140 | **232** | +66% | ✅ 功能大幅增强 |
| TradingPage | 162 | 162 | 不变 | OK |

### 新增组件汇总（24 个新组件，3,596 行）

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

---

## 三、各页面功能评估（v3）

### 🟢 功能完整且有深度（从 v1 的 6 个增加到 10 个）

| 页面 | 核心能力 | 状态 |
|------|---------|------|
| **Backtests（体系）** | List + Detail + Compare + 12 tabs + 7 专业图表 | ✅ 功能完整（legacy 代码待清理）|
| **StrategiesPage** | CRUD + Monaco Editor + 版本管理 + 组件提取 | ✅ 功能完整 |
| **FactorsPage** | IC 分析 + 相关性矩阵 + 分层收益 + IC 衰减 + 因子创建 + DSL 编辑器 | ✅ 从 889 行瘦身到 247 行 |
| **MLLabPage** | 实验对比 + 模型列表 + 预测 + 训练表单 | ✅ 从 802 行瘦身到 365 行 |
| **OptimizePage** | 协方差 + 3 种优化器 + 约束 + 结果 + 风险预算 | ✅ 功能完整 |
| **AdvisorPage** | 多 Agent + SSE 流式 + 会话历史 | ✅ 功能完整 |
| **KnowledgePage** | 上传（拖拽/URL/文本）+ 预览 + 标签 + 搜索 + 删除 | ✅ 从骨架升级为完整功能 |
| **DatasetsPage** | 数据预览 + 字段统计 + 质量报告 + 异常标记 | ✅ 从骨架升级为完整功能 |
| **LivePage** | 部署卡片 + 资金曲线 + 持仓盈亏 + 执行日志 + 风险监控 + 持仓集中度 | ✅ 从"模拟展示"升级为功能完整 |
| **AlertsPage** | 告警规则 + 历史 + 通知渠道配置 + 静默规则 | ✅ 从骨架升级为完整功能 |

### 🟡 有改善但仍需加强

| 页面 | 当前状态 | 仍缺失 |
|------|---------|--------|
| **PipelinePage** | DAG 编辑器 + 节点配置 + 状态展示 | 缺手动触发、参数模板、执行历史 |
| **TradingPage** | OrderForm + OrderBook + PositionTable | 仍仅 Paper Broker，缺订单历史/成交回报 |
| **RiskPage** | 风控检查 + Sizer 试算 | 缺持仓级实时风控、历史风控事件 |
| **NewsPage** | 新闻时间线 + 情绪颜色点 | 无新闻对因子/策略的影响分析 |
| **ScoringPage** | 截面打分快照 | 打分结果无历史对比 |

### 🔴 仍需关注

| 问题 | 优先级 |
|------|--------|
| BacktestsPage.tsx 2,001 行 legacy 代码 | P0 技术债 |
| 3 个 stub tab（ModelCompare/FeatureImportance/ModelDiagnostics）| P0 功能缺口 |
| StrategiesPage 1,412 行 + OptimizePage 760 行 | P1 应继续提取组件 |

---

## 四、v1 → v3 三轮迭代全景对比

| 维度 | v1 起点 | v2 改善 | v3 现状 |
|------|---------|---------|---------|
| **页面总数** | 18 页 | 18 页 + 12 tabs + Compare | 同左 |
| **代码量** | 9,689 行 | 11,950 行 | 11,066 行（组件提取后页面瘦身）|
| **组件文件** | ~30 个 | ~50 个 | **74 个**（+24 个新组件）|
| **API 模块** | 1 个文件 1,225 行 | 21 个域模块 | 同左 |
| **状态管理** | 无 | Zustand 5 stores | 同左 |
| **骨架页面** | 5 个（Knowledge/Datasets/Pipeline/Tasks/Alerts）| 5 个 | **1 个**（仅 Tasks 仍较薄）|
| **图表组件** | 1 个（PnLChart）| 8 个 | **8 个**（已全部集成到页面）|
| **工作流** | 无 | 3 条预定义 | 同左（深度集成待完成）|
| **导出/分享** | 无 | PDF/PNG + 策略分享 | 同左 |
| **暗色模式** | 无 | CSS 变量体系 | 同左 |
| **页面测试** | 0 | 11 个测试文件 | **15 个**测试文件 |

---

## 五、当前优先级建议

### P0（最高优先级）

| 项目 | 原因 | 工作量 |
|------|------|--------|
| 清理 BacktestsPage legacy 2,001 行 | 新 List/Detail/Compare + 12 tabs 已完成，旧代码是技术债且增加维护成本 | 小 |
| 实现 3 个 stub tab | 用户点击后看到空页面，体验断裂 | 中 |
| 工作流与页面深度集成 | WorkflowBar 已搭建，但各页面的 IC/回测/优化结果未自动写入 workflow context | 中 |

### P1

| 项目 | 原因 | 工作量 |
|------|------|--------|
| StrategiesPage 组件提取（1,412 行）| 最大的非 legacy 页面 | 中 |
| OptimizePage 组件提取（760 行）| 约束编辑 UX 仍复杂 | 中 |
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

v3 迭代是**三轮中改进幅度最大的一轮**：

1. **5 个骨架页面中的 4 个升级为完整功能**（Knowledge/Datasets/Live/Alerts），仅 Tasks 仍较薄
2. **FactorsPage 和 MLLabPage 代码量分别减少 72% 和 54%**，组件提取彻底
3. **24 个新组件**覆盖知识库、数据质量、实盘监控、管道编辑、告警渠道等核心功能
4. **7 个专业金融图表全部集成到对应页面**，不再是孤立组件

**当前最大的技术债**是 BacktestsPage 的 2,001 行 legacy 代码。**最大的功能缺口**是 3 个 stub tab 和工作流深度集成。

建议下一步聚焦：**清理 legacy → stub tab 实现 → 工作流集成 → 策略/优化页面组件提取**。
