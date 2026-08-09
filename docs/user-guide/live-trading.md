# 实盘交易指南

本篇介绍 cQuant 实盘交易的部署、监控、Kill-Switch（紧急停止）与 Paper Broker（模拟券商）。

> **重要约束**：根据项目 AI 使用指引，禁止 AI 自动执行真实交易指令，所有策略须经人工审核后方可上线。本篇所述功能均需人工确认。

cQuant 的实盘执行链路位于 `execution/` 模块，核心组件：
- **LiveExecutor** — 实盘执行引擎，按调度加载策略 → 生成信号 → 转换订单 → 执行 → 持久化；
- **PaperBroker** — 模拟券商（默认），用 `CostModel` 撮合，用于纸面交易；
- **BrokerAdapter** — 真实券商适配器抽象（如 QMT），需自行实现。

---

## 1. 部署

### 1.1 通过 Web UI 部署向导

进入「实盘」页面，使用 **Deploy Wizard**（`DeployWizard`）引导部署：

1. **选择策略**：从已验证的回测策略中选择（建议先在回测中确认 Overfitting / Risk Tab 达标）；
2. **选择券商**：默认 `PaperBroker`（模拟），生产可选已对接的真实券商适配器；
3. **配置资金**：初始资金、账户；
4. **设置调度**：每日调仓时间、频率；
5. **确认部署**：策略进入 `active` 状态。

![实盘部署向导](placeholder-deploy-wizard.png)

### 1.2 通过 CLI

```bash
# 启动实盘执行
python -m cquant.cli.main live start --strategy-id <strategy_id> [--broker paper]

# 交易操作
python -m cquant.cli.main trade account          # 查看账户状态
python -m cquant.cli.main trade positions        # 查看持仓
python -m cquant.cli.main trade orders           # 查看订单
python -m cquant.cli.main trade buy --symbol SSE:600036 --qty 1000
python -m cquant.cli.main trade sell --symbol SSE:600036 --qty 1000
```

---

## 2. 执行流程（LiveExecutor）

每个交易日，LiveExecutor 按以下步骤运行：

1. **加载策略**（`StrategyLoader`）：从数据库加载 `active` 策略配置；
2. **生成信号**：策略基于最新数据生成买卖信号（`SignalFrame`）；
3. **信号过滤**：过滤不可交易标的（停牌、涨跌停、退市）；
4. **转换订单**（`SignalConverter`）：信号 + 风控/仓位Sizer → 具体订单；
5. **执行订单**：通过 Broker（PaperBroker 或真实券商）撮合；
6. **持久化**（`ExecutionPersister`）：成交记录、持仓快照写入数据库；
7. **更新账户**：刷新资金、持仓、盈亏。

整个过程在「实盘」页面实时监控。

---

## 3. 监控

### 3.1 实盘页面（LivePage）

「实盘」页面展示：

| 模块 | 内容 |
|------|------|
| 账户信息（`AccountInfo`） | 资金、可用、冻结、总资产、盈亏 |
| 持仓（`PositionRiskDashboard`） | 持仓明细、权重、盈亏、集中度 |
| 订单历史（`OrderHistory`） | 订单状态（pending/filled/cancelled） |
| 成交历史（`TradeHistory`） | 逐笔成交 |
| 执行监控 | 当日执行进度、错误日志 |

![实盘监控](placeholder-live-monitor.png)

### 3.2 算法订单（TWAP/VWAP）

支持 TWAP（时间加权）和 VWAP（成交量加权）算法订单，降低大单的市场冲击：

在「交易」页面的 `AlgoOrderForm` 配置算法类型、订单总量、执行时段，提交后在 `AlgoOrderMonitor` 监控执行进度。

### 3.3 持仓集中度

`PositionConcentration` 组件展示 HHI 和单仓位权重，预警持仓过度集中。

---

## 4. Kill-Switch（紧急停止）

**Kill-Switch 是 cQuant 的紧急制动开关**，一键 halt 所有活跃策略。

### 4.1 触发 Kill-Switch

- **Web UI**：「实盘」页面顶部红色 Kill-Switch 按钮；
- **API**：`POST /live/kill-switch`；
- **触发后**：所有 `active` 策略立即转为 `halted` 状态，停止生成新信号和下单。

```bash
curl -X POST http://localhost:8000/live/kill-switch
```

### 4.2 查看 Kill-Switch 状态

```bash
curl http://localhost:8000/live/kill-switch/status
# 或在 Web UI 查看
```

返回当前 Kill-Switch 是否激活、激活时间、受影响的策略数。

### 4.3 恢复（Resume）

```bash
curl -X POST http://localhost:8000/live/resume
```

`/live/resume` 仅恢复被 Kill-Switch halt 的策略（按激活时间戳识别），将它们转回 `active`，并清除 Kill-Switch 标志。

> **建议**：恢复前务必先排查触发 Kill-Switch 的原因（异常亏损、数据问题、策略 bug），确认修复后再 resume。

---

## 5. Paper Broker（模拟券商）

`PaperBroker`（`execution/paper_broker.py`）是默认的模拟券商，特点：

- 用与回测相同的 `CostModel` 撮合（佣金/印花税/滑点），保证回测与纸面交易一致；
- 支持涨跌停限制（CN 规则）；
- 模拟成交，不产生真实交易；
- **用途**：策略上线前的纸面验证、回测逻辑的真实数据复现。

```python
from cquant.execution import PaperBroker

broker = PaperBroker(initial_cash=1_000_000)
# 配合 LiveExecutor 使用
```

### 接入真实券商

真实券商通过 `BrokerAdapter` 抽象接入（`execution/adapter.py` / `execution/adapters/`）：

1. 继承 `BrokerAdapter`，实现所有抽象方法（下单、撤单、查持仓、查资金等）；
2. 在配置中注册适配器；
3. 部署时选择该券商。

> 目前内置 QMT 等适配器的对接框架。接入真实券商需严格遵守券商 API 规范，并在纸面交易充分验证后再切实盘。

---

## 6. 调度与数据更新

实盘依赖每日数据更新，通过 **DataScheduler**（`scheduler/`）自动化：

```bash
# 启动调度守护进程
python -m cquant.cli.main scheduler start

# 查看调度状态
python -m cquant.cli.main scheduler status

# 手动触发调度任务
python -m cquant.cli.main scheduler run --task <task_name>
```

调度任务包括：每日行情摄入、基本面更新（valuation_daily）、ML 模型预测、Gold 表清理等。配置见 `scheduler/` 的配置文件。

---

## 7. 告警

实盘运行中的异常（风险 breaches、IC 衰减、数据缺失）会触发告警：

- 在「告警」页面配置告警规则（严重级别：Critical / High / Medium / Low）；
- 配置通知渠道（邮件 / Webhook），支持测试渠道和静默规则（Silence Rules）；
- 风控 breaches（如回撤超限、杠杆超限）会触发 `risk_breach` 类型告警。

详见 [FAQ - 告警配置](faq.md)。

---

## 8. 实盘上线检查清单

上线前请逐项确认：

- [ ] 回测 Overfitting Tab：DSR/PSR/CPCV 达标，无过拟合；
- [ ] 回测 Risk Tab：VaR/CVaR、最大回撤、持仓集中度可接受；
- [ ] 回测 TCA Tab：成本结构合理，换手率不过高；
- [ ] 参数敏感性分析：参数微调结果稳定（非过拟合）；
- [ ] Paper Broker 纸面交易运行 ≥ 2 周，表现与回测一致；
- [ ] Kill-Switch 已测试可用；
- [ ] 告警渠道已配置并测试；
- [ ] 数据调度（scheduler）稳定运行；
- [ ] **人工审核通过**（CLAUDE.md 要求：所有策略须经人工审核后方可上线）。

---

## 9. 相关文档

- [回测分析指南](backtest-analysis.md) — 上线前的回测验证
- [策略配置指南](strategy-config.md) — 风控参数
- [常见问题](faq.md)
