# cQuant 前端产品评估报告（v2）

> 评估时间：2026-06-07（基于 v1 评估后的第二版迭代）
> 评估范围：web/src/ 全量代码（页面 11,950 行 + 组件 1,701 行 + API 1,553 行 + stores 256 行 + types 513 行）
> 角色：产品经理（量化交易方向）

---

## 一、v1 → v2 变更摘要

v1 报告（`docs/FRONTEND_PRODUCT_REVIEW.md`）提出 4 个核心问题和 P0-P3 优先级建议。本轮迭代解决了其中 **2 个 P0 + 2 个 P1** 问题：

| v1 问题 | 状态 | 解决方式 |
|---------|------|---------|
| **P0 工作流断裂** | ✅ 已解决 | `workflowStore` + `WorkflowBar` 支持 3 条预定义工作流（因子→回测、ML Pipeline、组合优化） |
| **P0 回测对比缺失** | ✅ 已解决 | `BacktestComparePage` + `CompareMetricsTable` + `CompareNavChart` |
| **P1 可视化深度不足** | ✅ 大幅改善 | 新增 7 个专业金融图表组件（IC 热力图、月度收益热力图、因子相关性矩阵、交易散点图、持仓集中度、归因分解） |
| **P1 导出/协作缺失** | ✅ 已解决 | `ExportDialog`（PDF/PNG）+ `ShareDialog` + `SharePage`（策略分享链接） |
| 架构：API 单文件 1,225 行 | ✅ 已解决 | 拆分为 21 个域模块 + 统一错误处理 + AbortController |
| 架构：页面过于庞大 | ✅ 部分解决 | BacktestsPage 拆为 List/Detail/Compare + 12 个 tab 组件；Factors/ML/Optimize 组件提取 |

---

## 二、当前架构评价

### 架构层面（显著改善）

**代码组织：**
```
web/src/
├── pages/              # 18 个页面 + 12 个 backtest tab
├── components/         # 按域分组（backtests/charts/factors/ml/optimize/strategies/export/share/workflow/ui/layout）
├── stores/             # Zustand 状态管理（theme/sidebar/workflow/compare/factorExperiment）
├── lib/
│   ├── api/            # 21 个域模块（从 1 个 1,225 行文件拆分）
│   ├── types/          # Zod schema 定义（backtest/factor/ml/strategy）
│   └── utils.ts
└── hooks/
```

**亮点：**
- Zustand + persist 中间件用于工作流状态，刷新页面后不丢失进度
- API 域拆分 + backward compatibility layer，老代码零迁移成本
- Zod schema 定义核心实体，类型安全从 API 层贯穿到组件层
- 回测页面从 2,044 行单文件重构为 1 个列表页 + 1 个详情页 + 12 个 tab，每个 tab 独立可测试
- 暗色模式支持（CSS 变量体系：bg/text/border/brand/semantic/financial）

### 仍需改进

- `BacktestsPage.tsx` 仍有 2,001 行（legacy 代码未完全清理）
- `FactorsPage.tsx`（889 行）、`MLLabPage.tsx`（802 行）仍较大，组件提取不彻底
- `OptimizePage.tsx`（760 行）的约束编辑 UX 仍然复杂
- 3 个 stub tab（`BacktestModelCompareTab` 12 行、`BacktestFeatureImportanceTab` 10 行、`BacktestModelDiagnosticsTab` 10 行）仅有占位代码

---

## 三、各页面功能评估（更新版）

### 🟢 核心功能页面（功能完整，有深度）

| 页面 | 行数 | v2 新增能力 | 剩余问题 |
|------|------|------------|---------|
| **Backtests（体系）** | List(356) + Detail(78) + Compare(68) + 12 tabs(2,001) | 12 tab 详情（概览/Tearsheet/过拟合/Fills/WalkForward/TCA/归因/风控/高级/模型对比/特征重要性/模型诊断）| 3 个 stub tab 未实现；legacy BacktestsPage 未清理 |
| **StrategiesPage** | 1,412 | 组件提取（StrategyEditor/StrategyHeader/StrategyPreview/VersionHistoryPanel）| 版本 diff 视图缺失 |
| **FactorsPage** | 889 | IC 时序热力图 + 因子相关性矩阵 + IC 衰减图 + 分层收益图 + CorrelationTab | 页面仍较大，应继续提取 |
| **MLLabPage** | 802 | 组件提取（ExperimentsTab/ModelsTab/PredictionsTab）+ ModelDiagnosticsTab | 模型对比视图缺失 |
| **OptimizePage** | 760 | 组件提取（ConstraintsTab/ResultsTab/RiskBudgetTab）| 约束可视化仍弱 |

### 🟡 有改善但仍有差距的页面

| 页面 | 行数 | v2 变化 | 仍缺失 |
|------|------|--------|--------|
| **LivePage** | 413 | 无变化 | 仍标注"模拟展示"，无真实数据接入 |
| **TradingPage** | 162 | 无变化 | 仅 Paper Broker，缺订单历史/成交回报 |
| **RiskPage** | 217 | 无变化 | 缺持仓级实时风控、历史风控事件 |
| **NewsPage** | 431 | 无变化 | 无新闻对因子/策略的影响分析 |
| **ScoringPage** | 403 | 无变化 | 打分结果无历史对比 |

### 🔴 仍为骨架的页面

| 页面 | 行数 | 问题 |
|------|------|------|
| **KnowledgePage** | 140 | 仍仅搜索 + 列表，无上传/预览/标签 |
| **DatasetsPage** | 278 | 无数据浏览/字段统计 |
| **PipelinePage** | 145 | 无可视化 DAG/手动触发 |
| **TasksPage** | 225 | 无日志查看/重试 |
| **AlertsPage** | 433 | 无告警通道（Webhook/邮件） |

---

## 四、新增能力深度评估

### 1. 工作流引擎（workflowStore + WorkflowBar）

**已实现：**
- 3 条预定义工作流：因子→回测、ML Pipeline、组合优化
- 4 步骤进度条 + 上一步/下一步/重置
- Zustand persist 保持状态（刷新不丢失）
- context 对象在步骤间传递数据（selectedFactors、backtestResults 等）

**不足：**
- 工作流启动入口不明显（用户需要知道在哪里触发）
- 各页面尚未全部接入 workflow context（如 FactorsPage 的 IC 结果未自动写入 context）
- 缺工作流完成后的总结视图
- 只有 3 条硬编码工作流，无自定义能力

### 2. 专业金融图表（7 个新组件）

| 组件 | 行数 | 质量 |
|------|------|------|
| `ICTimeseriesHeatmap` | 189 | ✅ 支持周/月/季度粒度切换，颜色编码分 4 档，top 20 因子 |
| `FactorCorrelationMatrix` | 155 | ✅ 对称矩阵，颜色编码，点击查看详情 |
| `MonthlyReturnHeatmap` | 123 | ✅ 年×月热力图，正负收益颜色区分 |
| `TradeScatter` | 211 | ✅ 入场/出场散点图，支持盈亏颜色编码 |
| `PositionConcentration` | 213 | ✅ HHI 指数 + 前 N 大持仓占比 |
| `AttributionBreakdown` | 122 | ✅ 行业/因子归因分解柱状图 |
| `DeployWizard` | 155 | ✅ 从回测到实盘的部署向导 |

**评价：** 图表质量高，但部分图表尚未集成到对应页面（如 `TradeScatter` 需要接入 BacktestFillsTab，`PositionConcentration` 需要接入 LivePage）。

### 3. 导出与分享

- `ExportDialog`：支持 PDF/PNG 格式，可选范围（当前页/全报告），可选内容（图表/指标/表格）
- `ShareDialog` + `SharePage`：策略分享链接（`/share/:shareId`），可设置过期时间
- `download.ts` + `pdf.ts`：底层工具函数

### 4. API 基础设施重构

从 1 个 1,225 行文件拆分为 21 个域模块：

```
api/
├── client.ts       # 基础 HTTP 客户端 + AbortController
├── errors.ts       # 统一错误分类 + 重试策略
├── backtests.ts    # 回测 API（149 行）
├── factors.ts      # 因子 API（155 行）
├── ml.ts           # ML API（78 行）
├── strategies.ts   # 策略 API（47 行）
├── optimize.ts     # 优化 API（86 行）
├── ...             # 15 个其他域模块
└── index.ts        # 向后兼容 re-export（114 行）
```

---

## 五、更新后的优先级建议

### 已完成（本轮迭代）

- ✅ P0：工作流引擎（workflowStore + WorkflowBar）
- ✅ P0：回测对比视图（BacktestComparePage）
- ✅ P1：IC 时序热力图 + 因子相关性矩阵
- ✅ P1：月度收益热力图 + 交易散点图
- ✅ P1：PDF/PNG 导出 + 策略分享
- ✅ 架构：API 域拆分 + Zustand stores + Zod types

### 新的 P0（最高优先级）

| 优先级 | 改进项 | 原因 |
|--------|--------|------|
| **P0** | 清理 BacktestsPage legacy 代码（2,001 行→删除） | 新的 List/Detail/Compare + 12 tabs 已完成，旧代码是技术债 |
| **P0** | 工作流与页面深度集成 | WorkflowBar 已搭建，但各页面的 IC/回测/优化结果未自动写入 workflow context |
| **P0** | 3 个 stub tab 实现（ModelCompare/FeatureImportance/ModelDiagnostics） | 用户点击后看到空页面，体验断裂 |

### P1

| 优先级 | 改进项 | 原因 |
|--------|--------|------|
| **P1** | KnowledgePage 补齐（上传 + 预览 + 标签） | 知识库是核心功能但页面仍为骨架 |
| **P1** | 图表集成到页面 | TradeScatter→FillsTab, PositionConcentration→LivePage, Attribution→BacktestAttributionTab |
| **P1** | FactorsPage / MLLabPage 继续提取组件 | 两个页面仍在 800+ 行，应拆到 400 行以下 |

### P2

| 优先级 | 改进项 | 原因 |
|--------|--------|------|
| **P2** | DatasetsPage 数据浏览 + 字段统计 | 数据质量感知是量化研究基础 |
| **P2** | 实盘能力（LivePage 真实数据接入） | 从研究到实盘的关键一步 |
| **P2** | PipelinePage DAG 编辑器 | 自动化管道可视化管理 |
| **P2** | 告警通道（Webhook/邮件） | 生产可用性 |

---

## 六、总结

v2 迭代**解决了 v1 最关键的 2 个 P0 问题**（工作流断裂和回测对比），并在架构层面做了大幅改善（API 拆分、状态管理、组件提取、类型系统）。图表组件质量高，暗色模式和分享功能提升了用户体验。

**当前最大的技术债**是 BacktestsPage 的 legacy 代码（2,001 行）和 3 个 stub tab。**最大的功能缺口**是 KnowledgePage 仍为骨架，以及工作流引擎尚未与各页面深度集成。

建议下一步聚焦：**清理 legacy → 工作流集成 → KnowledgePage 补齐 → stub tab 实现**。
