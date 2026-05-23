# 开源项目调研报告 v2

> 调研日期：2026-05-21（更新）
> 目标：识别可复用的成熟开源组件，避免重复造轮子

---

## 结论摘要

| 项目 | 定位 | 建议 | 优先级 |
|------|------|------|--------|
| **Microsoft Qlib** | 研究型量化框架 | ✅ 可通过 DuckDB→DataFrame 适配层无缝集成；用于因子评估、IC 分析、ML Pipeline | 高 |
| **Anthropic Financial Services** | Claude AI 金融服务参考模板 | ✅ Agent 编排模式、MCP 数据连接器、Skill 库设计直接可用 | 高 |
| **FinanceToolkit** | 150+ 财务指标计算库 | ✅ 低成本扩充因子库（基本面财务比率） | 中 |
| **VnPy** | 实盘交易执行平台 | ⚠️ 参考 QMT 回调模式，不引入为依赖 | 低 |
| **TradingAgents** | LangGraph 多 Agent | ⚠️ LangGraph 编排参考，SQLite 会话持久化可直接借鉴 | 低 |
| **AI-Trader (HKUDS)** | 加密货币 Agent | ❌ 定位 Crypto，与 A 股无关 | 无 |
| **Alphalens** | 因子评估分析库 | ✅ 参考可视化设计（功能已在 cQuant 实现） | 参考 |
| **FinRL-Meta** | RL 交易环境 | ⚠️ 可将 backtest engine 包装为 gym env（研究用途） | 低 |
| **OpenBB** | 数据聚合平台 | ⚠️ MCP 设计有参考价值，但 AGPLv3 许可证受限 | 参考 |

---

## 问题解答

### Q1：Qlib 与 DuckDB 是否冲突？

**结论：不冲突，用户的判断正确。**

之前的分析低估了 Qlib 的数据适配能力。核心事实：

**Qlib 有三种数据接入方式，其中两种不需要转换到专有格式：**

1. **`StaticDataLoader`**（无需转换）：
   - 直接接受 Pandas DataFrame、Parquet 文件路径、或文件路径字典
   - `DataHandlerLP.from_df(df)` 一行代码包装外部 DataFrame
   - 适配成本：**~50 行代码**

2. **`DataHandlerLP`**（标准接口）：
   - 接受任意 `DataLoader` 子类
   - 包含 Processor 流水线（ZscoreNorm、CSRankNorm、DropnaProcessor 等）
   - DuckDB → Pandas → `StaticDataLoader` → `DataHandlerLP` → Qlib 分析工具

3. **Qlib 专有二进制格式**（可选）：
   - 只有在需要极致查询性能时才必要（7.4s vs 147s）
   - 有官方 `dump_bin.py` 脚本可从 CSV 转换

**实际适配代码（示意）：**
```python
import duckdb, pandas as pd
from qlib.data.dataset.loader import StaticDataLoader
from qlib.data.dataset.handler import DataHandlerLP
from qlib.contrib.evaluate import risk_analysis

# 1. 从 DuckDB 加载数据（tdx2db 格式）
con = duckdb.connect("tdx.db")
df = con.execute("""
    SELECT trade_date AS datetime, asset_id AS instrument,
           open, high, low, close, volume
    FROM silver_prices_1d
""").df()
df = df.set_index(["datetime", "instrument"])  # Qlib 要求的多重索引

# 2. 适配到 Qlib
loader = StaticDataLoader(df)
handler = DataHandlerLP(data_loader=loader,
                        infer_processors=["ZscoreNorm"])

# 3. 使用 Qlib 的 IC/IR 评估工具（不依赖专有格式）
from qlib.contrib.report import analysis_model
ic_df = analysis_model.calc_ic(pred_label=predictions, label=actual_returns)
```

**全量迁移可行性评估：**

| 使用场景 | 迁移复杂度 | 价值 |
|----------|-----------|------|
| IC/IR 评估工具 | 低（DataFrame 输入） | 立即可用 |
| Alpha158/360 因子集 | 中（需 DataHandlerLP 适配） | 高（158 个预计算因子） |
| ML Pipeline（LightGBM 等） | 中（需对接 Qlib dataset） | 中（cQuant 已有实现） |
| 回测评估指标 | 低（返回序列直接输入） | 中（补充现有指标） |
| Qlib 专有数据格式 | 高（需 dump_bin 转换） | 可选（性能优化时才需要）|

**建议策略：封装式集成，不全量替换**
- 在 `factorlab/evaluation.py` 外层适配 Qlib 的 IC 计算（增加准确性验证）
- 将 Alpha158 的因子定义作为参考，逐步补充到 cQuant 因子库
- 保持 cQuant 现有 DuckDB 架构不变，Qlib 作为"分析工具层"调用

---

### Q2：VnPy MainEngine "太重"具体指什么？

**结论：主要是架构耦合问题，不是性能问题。**

| 维度 | 实际情况 |
|------|----------|
| **内存占用** | 闲置 ~100-200MB，不算大 |
| **CPU 占用** | EventEngine 空转时近零 |
| **启动时间** | 1-2 秒，可接受 |
| **架构耦合** | **高**——这才是核心问题 |

**什么叫"架构耦合太重"：**

```python
# 使用 VnPy 的 paper_account，你被迫初始化整个堆栈：
event_engine = EventEngine()
main_engine = MainEngine(event_engine)   # 启动 EventEngine + OmsEngine + LogEngine + EmailEngine
main_engine.add_gateway(XtpGateway)     # 还需要至少一个 gateway
main_engine.add_app(PaperAccountApp)    # 才能用 paper account
# → 你只想要 PaperBroker，却拿了整个交易系统

# vs cQuant 的现有设计（干净）：
broker = PaperBroker(cost_model=CostModel.for_cn())
order = broker.submit_order(order_intent)  # 独立可用，无依赖
```

**对 cQuant 的影响评估：**
你的 `PaperBroker + QMTAdapter` 的设计比 VnPy **更优**：
- 继承 `Broker` ABC，可随时切换实现
- 不依赖任何事件总线
- 单元测试友好

**唯一有参考价值的地方**：VnPy XT/QMT gateway 的异步回调注册模式，用于完善 `QMTAdapter` 当前缺失的成交回报。

---

### Q3：anthropics/financial-services 分析

**结论：高度相关，特别是 ai_advisor 和知识库的架构改进。**

这是 Anthropic 发布的**金融服务领域 Claude 部署参考模板**，不是 demo，是为金融机构设计的可 fork 生产模板。

**核心架构：**
```
Claude Cowork 插件   ←→   同一套 Agent 定义   ←→   Managed Agents API
（用户界面）                                          （后端无头调用）
                              ↓
                  Agent 层（pitch-agent, gl-reconciler...）
                              ↓
                  Skill 层（markdown 技能文件）
                              ↓
                  MCP 连接器层（FactSet, Bloomberg, S&P...）
```

**关键设计模式与 cQuant 的映射：**

| Financial Services 特性 | cQuant 对应模块 | 改进机会 |
|-------------------------|----------------|---------|
| Agent-as-Plugin（每个 Agent 自带 skill 文件） | `ai_advisor/agents/` | 将 agent 的工具描述从 Python 代码提取为 markdown skill |
| MCP 数据连接器（11 个金融数据源） | `datahub/connectors/` | 将 Tushare/AKShare 封装为 MCP 工具，供 Agent 直接调用 |
| Steering Events（Agent 间结构化交接） | `ai_advisor/orchestrator.py` | 用 steering events 替换手写的 agent 调度状态机 |
| 可调用 Agent（callable_agents） | `ai_advisor/orchestrator.py` | 将 5 个 agent 改为独立可调用单元 |
| SQLite checkpoint 断点续传 | session 存储（in-memory） | 参考实现会话持久化 |
| Slash Command 层（`/backtest`, `/ic-analysis`） | CLI `main.py` | 增加面向 AI 使用的命令层 |

**最高价值的借鉴点：**

1. **MCP 化 cQuant 的数据工具**：
   ```
   # 当前：Agent 通过 Python 工具调用数据
   result = await KnowledgeSearchTool.execute(query)
   
   # 改进：暴露为 MCP server，可被任何 Claude 实例调用
   # → 实现 ai_advisor 的"数据源即工具"架构
   ```

2. **Managed Agent 双端部署**：
   - 同一套 agent 定义，既能在 cQuant Web UI 中使用，也能通过 API 调用
   - 未来可将 cQuant AI Advisor 部署为 Claude Managed Agent

---

### Q4：其他推荐项目

**新发现的高价值项目：**

#### FinanceToolkit（强烈推荐）

**GitHub：** https://github.com/JerBouma/FinanceToolkit

```python
pip install financetoolkit
```

**为什么对 cQuant 有价值：**
- 150+ 财务比率（盈利能力、效率、流动性、估值、偿债能力）
- 30+ 技术指标
- 风险指标（VaR、协方差）
- **极低依赖**：pandas + numpy + scipy
- **可单独 import 模块**，不需要使用完整框架

**具体可复用的因子类别：**
```python
from financetoolkit.ratios import ProfitabilityModel  # ROE, ROA, 毛利率等
from financetoolkit.ratios import ValuationModel       # PE, PB, EV/EBITDA
from financetoolkit.ratios import EfficiencyModel      # 资产周转率, 库存周转
from financetoolkit.risk import RiskModel              # VaR, Beta, 夏普比率
```

**集成方式：** 用 `FinanceToolkit` 的公式实现扩充 cQuant 的 `factors/value.py`、`factors/quality.py`，不需要引入整个框架，只参考公式。

**CN 市场支持：** 核心计算与市场无关，只需提供财务数据 DataFrame 即可。

---

#### FinRL-Meta（研究用途）

**GitHub：** https://github.com/AI4Finance-Foundation/FinRL-Meta

可将 cQuant 的 backtest engine 包装为 OpenAI Gym 环境：
```python
# 未来扩展方向：用 RL 优化组合权重
from finrl_meta.env_stock_trading.env_stocktrading_np import StockTradingEnv
# → 替换为 cQuant 的 AShareFillSimulator + PortfolioLedger
```

适合作为**研究性扩展**，不建议引入生产流程。

---

#### OpenBB（MCP 方向有参考价值）

**GitHub：** https://github.com/OpenBB-finance/OpenBB

⚠️ **AGPLv3 许可证**（商业使用需注意）

但其 MCP Server 设计值得参考：
- OpenBB 将金融数据访问封装为 MCP server
- 可参考这个模式将 cQuant 的 Tushare/AKShare 连接器 MCP 化
- 使 AI Advisor 能直接通过工具调用实时数据

---

## 完整整合优先级矩阵（更新版）

### 立即可用（低风险，高收益）

| 组件 | 来源 | 集成方式 | 工作量 |
|------|------|----------|--------|
| Qlib IC/IR 评估工具 | Microsoft Qlib | DuckDB→DataFrame→StaticDataLoader | 50-100 行适配代码 |
| FinanceToolkit 财务比率公式 | FinanceToolkit | 参考公式实现，扩充 factors/ | 小（按需选取） |
| Rank IC 衰减图、分层收益图 | Alphalens 设计参考 | 使用现有 `rank_ic_decay()` + 前端图表 | 小 |
| SQLite 会话持久化 | TradingAgents 参考 | 替换 ai_advisor 内存 session | 小 |

### 中期评估

| 组件 | 来源 | 工作量 | 条件 |
|------|------|--------|------|
| MCP 化数据工具 | Anthropic Financial Services 模式 | 中 | AI Advisor 迭代时 |
| Qlib Alpha158/360 因子集 | Microsoft Qlib | 中（需数据适配层） | 基本面数据就绪后 |
| QMT 回调注册 | VnPy XT gateway 参考 | 小 | 实盘接入时 |
| Callable Agents 编排 | Anthropic Financial Services | 中 | AI Advisor 重构时 |

### 不建议整合

| 项目 | 原因 |
|------|------|
| VnPy（全量） | 架构耦合过重，cQuant 现有 execution 层更优 |
| AI-Trader | 定位 Crypto，不适用于 A 股 |
| Alphalens | 功能已实现，依赖已停止维护 |
| Zipline-Reloaded | 无 A 股支持，回测引擎重叠 |
| Lean Engine (QuantConnect) | .NET 依赖，重量级，A 股支持未知 |
| Nautilus Trader | Rust 复杂度高于必要，A 股无 HFT 需求 |
| Coinbase AgentKit | 仅 Crypto/Blockchain |
