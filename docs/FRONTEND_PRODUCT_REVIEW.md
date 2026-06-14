# cQuant 前端产品评估报告

> 评估时间：2026-06-02
> 评估范围：web/src/pages/ 全部 18 个页面（9,689 行代码）
> 角色：产品经理（量化交易方向）

---

## 一、整体架构评价

### 做得好的地方

- 导航分组清晰（研究工具 / 数据&监控 / 知识&AI / 系统），4 组 17 个页面覆盖量化研究全流程
- 全局任务状态栏（topbar 运行中任务数 + 详情下拉 + 取消/删除）非常实用
- 异步回测 + job 轮询 + 告警未读数的设计，符合实际量化工作流
- 侧边栏可折叠，支持移动端 drawer
- 任务运行中 badge 脉冲提示（ML 训练 / 回测 / 打分），信息密度高

### 架构层面问题

- `AppLayout.tsx`（290+ 行）承担了太多职责：任务轮询、告警轮询、侧边栏状态、移动端 drawer、topbar 下拉 — 应拆分
- 页面代码量差异极大（18 行 ~ 2,044 行），说明功能深度不均匀
- 缺少统一的 loading / empty / error 状态组件，各页面自行处理

---

## 二、各页面功能评估

### 🟢 核心功能页面（功能完整，有深度）

| 页面 | 行数 | 功能亮点 | 问题 |
|------|------|---------|------|
| **BacktestsPage** | 2,044 | 3-Tab 设计（概览/Tearsheet/过拟合分析）、NAV 图表、Walk-Forward OOS、CPCV 颜色格 | 过于庞大，应拆分组件 |
| **StrategiesPage** | 1,412 | 策略 CRUD、Monaco Editor JSON 编辑器、版本管理、回滚 | 编辑器体验好，但版本 diff 功能缺失 |
| **FactorsPage** | 889 | 因子定义卡片、IC/IR 异步计算、Rank IC 衰减图、分层收益图 | 因子筛选/排序能力弱 |
| **MLLabPage** | 802 | 实验对比、Job 提交、特征重要性柱状图 | 模型对比视图缺失 |
| **OptimizePage** | 760 | 协方差估计、3 种优化器（MVO/风险平价/成本感知）、约束编辑、ML 预测导入 | 约束编辑 UX 复杂，缺可视化 |
| **AdvisorPage** | 522 | 多 Agent 面板（Research/Risk/Debate）、SSE 流式输出、会话历史侧边栏 | Agent 输出无结构化展示 |

### 🟡 功能框架在但深度不足的页面

| 页面 | 行数 | 当前状态 | 缺失的关键体验 |
|------|------|---------|---------------|
| **LivePage** | 413 | 策略选择器 + 风险仪表盘 + 时序图 | ⚠️ 标注"模拟展示"，无真实数据接入，用户期望落差大 |
| **TradingPage** | 162 | OrderForm + OrderBook + PositionTable | 仅 Paper Broker，缺订单历史、成交回报、持仓盈亏 |
| **RiskPage** | 217 | 风控检查（下单前验证）+ Sizer 试算 | 缺持仓级实时风控监控、历史风控事件记录 |
| **ScoringPage** | 403 | 截面打分快照 | 打分结果无历史对比、无回测联动 |
| **NewsPage** | 431 | 新闻时间线 + 情绪颜色点 | 无新闻对因子/策略的影响分析 |

### 🔴 功能薄弱或仅有框架的页面

| 页面 | 行数 | 问题 |
|------|------|------|
| **KnowledgePage** | 140 | 仅搜索框 + 文档列表，无上传 UI、文档预览、标签管理 |
| **DatasetsPage** | 278 | 数据集列表 + 质量报告，但无数据浏览、字段级统计、异常标记 |
| **PipelinePage** | 145 | 仅展示管道状态，无可视化 DAG 编辑、手动触发、参数配置 |
| **TasksPage** | 225 | 任务列表，但无任务日志查看、重试、依赖关系 |
| **AlertsPage** | 433 | 告警历史 + 规则配置，但无告警通道（邮件/Webhook）、静默规则 |

---

## 三、核心产品问题

### 1. 量化工作流断裂

用户的真实流程是：

```
因子研究 → 策略构建 → 回测验证 → 组合优化 → 风控检查 → 实盘执行
```

但当前各页面是**独立孤岛**：

- FactorsPage 计算完 IC 后，无法一键"将 IC 显著的因子加入策略"
- BacktestsPage 回测完成后，无法一键"用此策略创建 ML 训练任务"或"提交到实盘监控"
- MLLabPage 训练完模型后，无法一键"用此模型创建回测"
- ScoringPage 打分后，无法一键"将 Top N 股票提交到组合优化"

**缺少的关键体验：页面间的跳转预填 + 端到端流程引导。**

### 2. 实盘能力薄弱

- LivePage 明确标注"模拟展示"，TradingPage 仅 Paper Broker
- 缺少券商接入的真实状态、资金曲线、持仓盈亏追踪
- 对量化交易员来说，"看到真实的钱"是最核心的需求

### 3. 可视化深度不足

- 回测图表依赖 lightweight-charts（NAV 折线 + 回撤面积），但缺：
  - 月度收益热力图
  - 行业/因子归因分解图
  - 持仓集中度变化图
  - 交易明细散点图（入场/出场时机可视化）
- 因子研究缺：IC 时序热力图、因子相关性矩阵图

### 4. 协作与导出能力缺失

- 无导出报告功能（PDF/PNG）
- 无策略分享/协作
- 无回测结果对比视图（多个策略 side-by-side）

---

## 四、优先级建议

| 优先级 | 改进项 | 预期价值 | 工作量估计 |
|--------|--------|---------|-----------|
| **P0** | 页面间跳转预填（因子→策略→回测→优化） | 打通工作流，核心体验质变 | 中 |
| **P0** | 回测结果对比视图（多策略并排） | 量化研究最常用功能 | 中 |
| **P1** | 因子 IC 热力图 + 因子相关性矩阵 | 因子研究深度 | 中 |
| **P1** | KnowledgePage 文档上传 + 预览 | 知识库可用性 | 小 |
| **P1** | 月度收益热力图 + 交易散点图 | 回测分析深度 | 中 |
| **P2** | ML 模型对比视图 | 模型选择效率 | 小 |
| **P2** | 组合优化约束可视化（饼图/柱状图） | 优化结果理解 | 小 |
| **P2** | 告警通道配置（Webhook/邮件） | 生产可用性 | 中 |
| **P3** | 真实券商接入（QMT 适配器 UI） | 从研究到实盘 | 大 |

---

## 五、页面间跳转预填方案（P0 详细设计）

### 核心思路

在每个页面的"完成态"增加"下一步操作"入口，通过 URL query params 传递上下文：

```
/factors?computed=ret_20d,vol_20d       →  /strategies?prefill_factors=ret_20d,vol_20d
/backtests?run_id=abc123               →  /optimize?source_backtest=abc123
/ml?experiment_id=xyz                  →  /backtests?model_id=xyz
/scoring?snapshot_id=snap1             →  /optimize?assets_from=snap1
```

### 关键跳转路径

| 源页面 | 触发条件 | 目标页面 | 预填内容 |
|--------|---------|---------|---------|
| FactorsPage | IC 计算完成 | StrategiesPage | 将 IC 显著因子名称填入策略 JSON |
| FactorsPage | 因子选择 | MLLabPage | 将因子列表填入特征集 |
| BacktestsPage | 回测完成 | OptimizePage | 用回测持仓作为优化初始权重 |
| BacktestsPage | 回测完成 | AdvisorPage | 自动发起"分析此回测"对话 |
| MLLabPage | 训练完成 | BacktestsPage | 将 model_id 填入 MLModelStrategy |
| MLLabPage | 训练完成 | StrategiesPage | 将 model_id 填入策略配置 |
| ScoringPage | 打分完成 | OptimizePage | 将 Top N 股票填入优化标的 |
| ScoringPage | 打分完成 | BacktestsPage | 将打分结果作为策略选股来源 |
| AdvisorPage | 分析结论 | StrategiesPage | 将建议参数填入策略 |

### 实现方式

1. 创建 `usePrefill` hook，读取 URL query params 并映射到页面状态
2. 各页面在初始化时检查 prefill 参数并自动填充
3. "下一步"按钮使用 `<Link>` 带 query params 跳转
4. 在 AppLayout 中增加面包屑导航显示当前工作流位置
