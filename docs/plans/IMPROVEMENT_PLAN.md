# cQuant 改进计划

> 创建时间：2026-05-21
> 基于：QUANT_PLATFORM_REVIEW_v2.md + 代码审查 + 开源调研
> 状态追踪：使用 `[ ]` / `[x]` 勾选，完成后更新日期

---

## 总体范围拆解

用户提出的问题经代码审查后归纳为 **5 个独立子项目**，按优先级分三个批次推进：

| 批次 | 方向 | 核心价值 | 预估工作量 |
|------|------|----------|-----------|
| **批次 1** | B. 策略配置修复 + E. 全局 UX | 修复日常阻塞 Bug，低成本高收益 | 小（1-2 天）|
| **批次 2** | D. 回测评估增强 | 过拟合分析、训练集/测试集选择 | 大（3-5 天）|
| **批次 3** | A. 因子研究工作流 + C. ML Lab 打通 | 完善研究流程端到端 | 中（3-4 天）|

---

## 批次 1：策略配置修复 + 全局 UX

### B. 策略配置修复

#### B1. 删除操作无反馈
- [ ] `StrategiesPage.tsx`：删除成功后添加 toast 通知（替换 `alert()`）
- [ ] 删除前确认弹框（已有 window.confirm，改为 Modal 样式）
- [ ] 删除失败时展示错误原因

#### B2. 创建/编辑表单校验
- [ ] 策略 ID 为空时禁用"保存"按钮
- [ ] 提交前校验 config_text 是否为合法 JSON（前端 try-parse）
- [ ] 策略 ID 重复时展示行内错误（后端已返回 409，前端需捕获）

#### B3. 回测参数增强
- [ ] `BacktestRunModal` 中补充多因子权重配置入口（现只有 `sort_factor` 单因子）
- [ ] 支持选择策略类型（StaticTopN / MultiFactorStrategy / MLModel）

---

### E. 全局 UX 修复

#### E1. 通知系统统一
- [ ] 引入 toast 组件（推荐：`sonner` 或项目内现有 shadcn/ui toast）
- [ ] 替换所有 `alert()` 调用（MLLabPage 提交 Job 后）
- [ ] 所有 mutation 操作（create/update/delete）统一接入 toast 成功/失败

#### E2. Loading 状态与骨架屏
- [ ] `FactorsPage`：因子卡片加载时添加 skeleton
- [ ] `BacktestsPage`：列表和详情面板添加 loading indicator
- [ ] `MLLabPage`：feature importance 图表加载态

#### E3. 表单校验通用化
- [ ] `StrategiesPage` - 策略 ID / config 校验
- [ ] `MLLabPage` - Feature Set Version 格式校验（不能为空/含空格）
- [ ] `BacktestRunModal` - 日期范围校验（end > start）

#### E4. 全局错误边界
- [ ] `router.tsx` 添加 `ErrorBoundary` 组件
- [ ] API 请求失败统一展示友好错误提示（替换 console.log）
- [ ] 添加 404 路由回退页面

#### E5. 空状态设计
- [ ] 列表为空时（无策略/无回测/无实验）显示引导性空状态
- [ ] 空状态包含快捷操作入口（如"创建第一个策略"按钮）

---

## 批次 2：回测评估增强

### D. 回测评估页面

#### D1. 过拟合分析触发 UI
- [ ] `BacktestsPage.tsx` Overfitting 标签页添加"运行分析"按钮
- [ ] 按钮调用 `POST /api/v1/backtests/{id}/analyze`（需新增此端点）
- [ ] 后端 `backtests.py` 新增 `/analyze` 端点，异步运行 `AnalysisEngine`
- [ ] 分析 Job 状态轮询（类似 factors analytics 的 job polling 模式）
- [ ] 分析完成后刷新 Overfitting 标签数据

#### D2. 训练集 / 测试集划分选择
- [ ] 回测创建表单增加"评估模式"字段：
  - `full`：全量回测（当前默认）
  - `walk_forward`：滚动窗口（指定 n_splits、in_sample_ratio）
  - `oos_split`：固定训练/测试集（指定训练结束日期）
- [ ] 后端 `BacktestSpec` 接受 `eval_mode` + `walk_forward_config` 参数
- [ ] `WalkForwardAnalyzer` 对接 BacktestSpec 而非仅分析已有 returns

#### D3. 回测 POST 异步化
- [ ] `POST /api/v1/backtests` 改为异步提交（返回 job_id，改用 BackgroundTasks）
- [ ] 前端改为 job 轮询模式（已有 `useJobPoller` hook 可复用）
- [ ] 列表页实时显示 running 状态

#### D4. 指标增强
- [ ] `BacktestsPage` Overview 标签补充：Information Ratio、Tracking Error、Alpha
- [ ] 这三个指标已在 `metrics.py` 实现，但需要传入 benchmark_returns
- [ ] `BacktestSpec` 补充 `benchmark_asset_id` 字段，从 silver_prices_1d 加载基准收益

#### D5. 结果导出
- [ ] 添加"导出 CSV"按钮：Fills 表格、组合快照
- [ ] 添加"导出 JSON"按钮：完整回测配置 + 指标报告

---

## 批次 3：因子研究工作流 + ML Lab 打通

### A. 因子研究工作流

#### A1. 工作流引导
- [ ] `FactorsPage` 顶部添加流程说明（数据集选择 → 因子选择 → 计算 IC → 查看结果）
- [ ] "未选择数据集"时显示引导提示，直接跳转 DatasetsPage

#### A2. 因子评估可视化增强
- [ ] IC 时序图（已有）
- [ ] **Rank IC 衰减图**（横轴 lag 1-20，纵轴 IC 值 — `FactorEvaluator.rank_ic_decay()` 已实现，未展示）
- [ ] **因子分层收益图**（Quantile Returns — `FactorEvaluator.quantile_returns()` 已实现，未展示）
- [ ] **因子换手率**指标卡（`FactorEvaluator.factor_turnover()` 已实现，未展示）

#### A3. 因子评估结果持久化
- [ ] `POST /api/v1/factors/analytics/compute` 完成后将结果写入数据库（当前只存 job 状态）
- [ ] 新增 `GET /api/v1/factors/analytics/history` 端点，查询历史评估结果
- [ ] FactorsPage 支持查看历史评估记录

#### A4. 因子对比功能
- [ ] 支持同时选择多个因子，叠加展示 IC 时序对比

---

### C. ML Lab 工作流打通

#### C1. 工作流引导 UI
- [ ] `MLLabPage` 顶部添加三步流程说明：
  1. 先在"数据集"页面确认有 Feature Set Version
  2. 在此提交训练 Job（选择 trainer + feature set）
  3. 训练完成后，在"策略配置"页面创建 MLModel 策略并回测
- [ ] Feature Set Version 改为下拉选择（调用 `GET /api/v1/factors/versions`）

#### C2. 训练 Job 到策略的一键跳转
- [ ] 训练完成后，实验列表行展示"使用此模型创建策略"按钮
- [ ] 点击后跳转 StrategiesPage 并预填 `MLModelStrategy` 配置（model_id）

#### C3. 预测结果可视化
- [ ] 新增"预测分布"标签页：展示 gold_predictions 的预测值分布图
- [ ] 预测 vs 实际收益散点图（验证模型有效性）

#### C4. 实验对比
- [ ] 支持选中多个实验，对比 RMSE/Sharpe/方向准确率
- [ ] 实验列表增加分页

---

## 横切关注点（所有批次共用）

### 性能
- [ ] `POST /api/v1/backtests` 异步化（D3 已包含）
- [ ] 因子物化：Lookback 窗口改为按因子最大依赖动态计算
- [ ] 日历 `trading_days()` 改为二分查找 + 缓存

### 数据完整性
- [ ] CLI 开放多数据源（`--source {akshare,tushare,yfinance}`）
- [ ] Silver 层增加数据质量过滤（价格异常值 winsorize）
- [ ] `silver_fundamentals` 定期更新计划任务（Scheduler 集成）

### 测试
- [ ] 配置 `pytest-cov`，目标行覆盖率 ≥ 70%
- [ ] 补充 `BacktestsPage` / `StrategiesPage` 的前端组件测试
- [ ] 端到端测试：因子 → ML 训练 → 策略 → 回测 → 分析全链路

---

## 进度追踪看板

| 子项目 | 状态 | 开始日期 | 完成日期 | 备注 |
|--------|------|----------|----------|------|
| B. 策略配置修复 | ⬜ 待开始 | — | — | |
| E. 全局 UX 修复 | ⬜ 待开始 | — | — | |
| D. 回测评估增强 | ⬜ 待开始 | — | — | D3 异步化为 P0 |
| A. 因子研究工作流 | ⬜ 待开始 | — | — | |
| C. ML Lab 打通 | ⬜ 待开始 | — | — | |

状态图例：⬜ 待开始 / 🔄 进行中 / ✅ 完成 / ❌ 阻塞

---

## 与开源项目整合计划

> 详见 `docs/plans/OPENSOURCE_ANALYSIS.md`

| 组件 | 整合来源 | 整合方式 | 计划批次 |
|------|----------|----------|----------|
| IC 衰减分析 UI | Alphalens 设计参考 | 参考图表设计，复用 `FactorEvaluator.rank_ic_decay()` | 批次 3-A |
| 分层收益图 | Alphalens 设计参考 | 参考图表设计，复用 `FactorEvaluator.quantile_returns()` | 批次 3-A |
| LangGraph Agent 编排 | TradingAgents | 作为 AI Advisor 编排层的备选方案 | 评估中 |
| QMT 回调注册 | VnPy Gateway 参考 | 参考 vnpy 的 gateway 回调模式完善 QMTAdapter | 批次 2 后 |
| Factor Alpha158/360 | Qlib | 可选：将 Qlib 因子数据集导入 silver_fundamentals | 长期 |
| 向量化回测可视化 | VectorBT Plotly 参考 | 参考 Plotly 图表设计优化 PnL/DrawdownChart | 批次 2-D |
