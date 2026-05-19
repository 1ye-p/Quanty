# cQuant 快速上手指南

> 版本：0.1.0 · 更新：2026-05-14

---

## 环境要求

| 依赖 | 说明 |
|------|------|
| conda + cQuanty 环境 | `conda activate cQuanty` |
| Python 3.12 | 已包含在 cQuanty 环境中 |
| Node.js ≥ 18 | 用于前端（`brew install node` 或官网下载） |

---

## 一、配置敏感信息

在项目根目录创建 `.env`（已被 `.gitignore` 排除，不会提交到 Git）：

```bash
cp .env.example .env
```

编辑 `.env`，按需填入：

```env
# 数据源（至少填一个）
TUSHARE_TOKEN=你的Token      # https://tushare.pro/register

# AI 助手（至少填一个，用于 AI Advisor 功能）
ANTHROPIC_API_KEY=sk-ant-xx  # https://console.anthropic.com/
OPENAI_API_KEY=sk-xx         # 备用，可不填

# 其余保持默认即可
```

---

## 二、启动服务

需要**同时开两个终端**：

### 终端 1 — 后端 API（FastAPI）

```bash
conda activate cQuanty
cd /path/to/cQuant
uvicorn cquant.api_server.app:app --port 8000 --reload
```

启动成功后可访问：
- API 文档（Swagger）：[http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### 终端 2 — 前端 Dashboard（React）

```bash
cd /path/to/cQuant/web
npm install     # 首次需要，后续跳过
npm run dev
```

启动成功后访问：
- Web Dashboard：[http://localhost:3000](http://localhost:3000)

---

## 三、功能导览

### 3.1 知识库（研报/策略文档管理）

**适用场景**：导入机构研报、策略说明书、个人笔记，然后用关键词或语义搜索快速检索。

#### 导入文档

**方式 A：通过 Web UI**

进入 Dashboard → **Knowledge Base** 页面 → 使用搜索框检索已有文档。
（当前版本 Web 暂无上传界面，请使用方式 B）

**方式 B：通过 API**

```bash
# 导入本地 PDF 研报
curl -X POST http://localhost:8000/api/v1/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "uri": "/绝对路径/研报.pdf",
    "source_name": "华泰证券",
    "logical_type": "research",
    "title": "2025年A股量化策略展望"
  }'

# 导入 Markdown 笔记
curl -X POST http://localhost:8000/api/v1/knowledge/ingest \
  -d '{"uri": "/路径/strategy.md", "logical_type": "strategy"}'

# 导入网页
curl -X POST http://localhost:8000/api/v1/knowledge/ingest \
  -d '{"uri": "https://example.com/article", "logical_type": "research"}'
```

`logical_type` 可选值：`research`（研报）、`strategy`（策略）、`notes`（笔记）、`data`（数据说明）

**方式 C：通过 Python**

```python
import sys; sys.path.insert(0, 'python')
from cquant.knowledge_base import KnowledgeBaseService, IngestRequest

kb = KnowledgeBaseService.create()
result = kb.ingest(IngestRequest(
    uri="/路径/report.pdf",
    source_name="中信证券",
    logical_type="research",
    title="动量因子深度研究"
))
print(result.status, result.chunk_count)  # ok, 42
```

#### 搜索文档

**Web UI**：Knowledge Base 页面 → 搜索框输入关键词 → 回车

**API**：
```bash
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"text": "A股动量因子", "top_k": 5}'
```

**Python**：
```python
from cquant.knowledge_base import KnowledgeBaseService, SearchQuery

kb = KnowledgeBaseService.create()
resp = kb.search(SearchQuery(text="A股动量因子", top_k=5))
for hit in resp.hits:
    print(f"[{hit.score:.3f}] {hit.title} — {hit.source_name}")
```

---

### 3.2 数据接入

**适用场景**：从 Tushare、AKShare 等数据源获取A股/美股行情数据。

```python
import sys; sys.path.insert(0, 'python')
from cquant.datahub.connectors.tushare_connector import TushareConnector
from cquant.datahub.connectors.base import DataSpec
from cquant.core.enums import Market
from datetime import date

# Tushare（需在 .env 设置 TUSHARE_TOKEN）
connector = TushareConnector()
spec = DataSpec(
    symbols=["SSE:600036", "SZSE:000858"],
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
    market=Market.CN,
)
for batch in connector.fetch(spec):
    print(f"来源: {batch.source}, 行数: {batch.data.height}")
    print(batch.data.head(3))
```

Web UI：Dashboard → **Datasets** 页面，查看已注册的数据集版本。

---

### 3.3 因子计算

**适用场景**：在 Jupyter Notebook 中计算内置因子（动量、波动率等）。

```python
import sys; sys.path.insert(0, 'python')
import polars as pl
from cquant.factorlab import FactorRegistry, FeaturePipeline, PipelineSpec
from cquant.factorlab.factors import BUILTIN_FACTORS
from datetime import date

# 加载内置因子（8个）
registry = FactorRegistry()
for f in BUILTIN_FACTORS:
    registry.register(f)

print("可用因子:", registry.all_names())
# ['ma_20d_ratio', 'ret_1d', 'ret_20d', 'ret_5d', 'ret_60d',
#  'vol_20d', 'vol_60d', 'zscore_close_60d']

# 准备价格数据（polars DataFrame）
prices = pl.DataFrame({...})  # 需要列: asset_id, trade_date, close, volume, amount, is_suspended

# 运行因子管道
pipeline = FeaturePipeline(registry)
spec = PipelineSpec(
    factor_names=["ret_20d", "vol_20d", "zscore_close_60d"],
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
)
result = pipeline.run(prices, spec)
print(result.data.head())
```

---

### 3.4 回测

**适用场景**：对量化策略做向量化回测，评估历史表现。

```python
import sys; sys.path.insert(0, 'python')
import polars as pl
from decimal import Decimal
from datetime import date
from cquant.backtest_vector import VectorBacktestEngine, BacktestSpec, Strategy, StrategyContext
from cquant.backtest_vector.costs import CostModel
from cquant.core.enums import SignalDirection

# 定义策略（示例：买入第一个资产）
class SimpleStrategy(Strategy):
    @property
    def strategy_id(self): return "demo"

    def generate_signals(self, ctx: StrategyContext):
        return pl.DataFrame([{
            "asset_id": "SSE:600036",
            "signal_date": ctx.as_of_date,
            "direction": SignalDirection.LONG.value,
            "strength": 1.0,
            "confidence": 1.0,
            "strategy_id": "demo",
        }])

# 运行回测
engine = VectorBacktestEngine()
spec = BacktestSpec(
    strategy=SimpleStrategy(),
    prices=prices_df,           # Silver 格式价格 DataFrame
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
    initial_cash=Decimal("1000000"),
    cost_model=CostModel.for_cn(),  # A股费用模型（含印花税）
)
result = engine.run(spec)
print(f"总收益: {result.metrics.total_return:.2%}")
print(f"夏普比率: {result.metrics.sharpe_ratio:.3f}")
print(f"最大回撤: {result.metrics.max_drawdown:.2%}")
```

Web UI：Dashboard → **Backtests** 页面，查看已完成的回测运行记录。

---

### 3.5 回测质量分析（过拟合检测）

**适用场景**：对回测结果做统计显著性检验，判断策略是否过拟合。

```python
from cquant.bt_analyzer import AnalysisEngine, AnalysisSpec

engine = AnalysisEngine(AnalysisSpec(
    n_oos_windows=5,     # 滚动样本外窗口数
    n_trials=1,          # 测试策略数量（用于 DSR 修正）
    benchmark_sharpe=0.0,
))
report = engine.run(backtest_result)

print(f"过拟合评分: {report.overall_overfit_score.score:.2f} ({report.overall_overfit_score.confidence})")
print(f"PSR: {report.psr:.3f}")   # 接近1=显著；接近0=不显著
print(f"DSR: {report.dsr:.3f}")
print(report.summary)
```

---

### 3.6 AI 研究助手

**前提**：在 `.env` 设置 `ANTHROPIC_API_KEY`。

**Web UI**：Dashboard → **AI Advisor** → 在聊天框输入问题。

示例问题：
- `"这份动量因子研报的核心结论是什么？"`
- `"分析一下回测 run_id=xxx 的过拟合风险"`
- `"A股量化策略有哪些常见失效场景？"`

**Python**：
```python
from cquant.ai_advisor import AdvisorOrchestrator, AdvisorSession, ClaudeProvider
from cquant.ai_advisor import SafetyPolicy, KnowledgeSearchTool, BacktestResultTool
from cquant.knowledge_base import KnowledgeBaseService

kb = KnowledgeBaseService.create()
provider = ClaudeProvider()  # 读取 .env 中的 ANTHROPIC_API_KEY
orchestrator = AdvisorOrchestrator(
    provider=provider,
    agents=None,
    tools=[KnowledgeSearchTool(), BacktestResultTool()],
    kb_service=kb,
    safety=SafetyPolicy(),
)
session = AdvisorSession()
response = orchestrator.chat_sync("A股动量策略的主要风险是什么？", session)
print(response)
```

> **安全限制**：AI Advisor 只能做离线研究分析，无法访问券商接口或执行真实交易。

---

## 四、常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `No module named 'cquant'` | 包未安装到 conda 环境 | `pip install -e .`（项目根目录）|
| AI 助手回复"API key not configured" | `.env` 未设置 | 在 `.env` 填入 `ANTHROPIC_API_KEY` |
| 知识库搜索无结果 | 未导入文档 | 先通过 `/ingest` 或 Python 导入文档 |
| 前端请求报错 404/CORS | 后端未启动 | 确认 `uvicorn` 在 `:8000` 运行 |
| 向量检索不可用（降级为关键词） | lancedb 未安装 | `pip install lancedb`（可选） |
| PDF 解析失败 | 解析库未安装 | `pip install pdfplumber` |
| `TUSHARE_TOKEN` 无效 | Token 错误或未填写 | 在 [tushare.pro](https://tushare.pro) 获取 Token |

---

## 五、目录结构速查

```
cQuant/
├── python/cquant/       # Python 核心包
│   ├── core/            # 类型、枚举、事件总线
│   ├── market_calendar/ # 交易日历（A/US/HK）
│   ├── datahub/         # 数据接入（Tushare/AKShare）
│   ├── factorlab/       # 因子计算
│   ├── backtest_vector/ # 向量化回测
│   ├── bt_analyzer/     # 过拟合检测
│   ├── ml_lab/          # ML 训练（XGBoost/LightGBM）
│   ├── newsflow/        # 新闻数据接入
│   ├── knowledge_base/  # 研报知识库（RAG）
│   ├── ai_advisor/      # 多Agent研究助手
│   ├── riskguard/       # 风控策略
│   └── api_server/      # FastAPI 服务
├── web/                 # React 前端
├── knowledge/           # 知识库数据（本地文件+DuckDB）
├── notebooks/           # Jupyter 笔记本
├── .env.example         # 配置模板（复制为 .env 后填写）
├── QUICKSTART.md        # 本文档
└── CHANGELOG.md         # 版本变更记录
```

---

## 六、典型工作流

```
1. 导入研报/数据
   ↓
2. 计算因子（factorlab）
   ↓
3. 运行回测（backtest_vector）
   ↓
4. 过拟合检测（bt_analyzer）
   ↓
5. 用 AI Advisor 解读结果
   ↓
6. 在 Web Dashboard 可视化查看
```
