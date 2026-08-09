# 快速开始

本篇面向新用户，带你从零跑通 cQuant：安装环境 → 摄入行情数据 → 物化因子 → 运行第一次回测。

cQuant 的完整研究闭环是：**数据摄入 → 因子物化 → 策略配置 → 回测 → 分析 → 实盘**。本篇覆盖前三步和首次回测。

---

## 1. 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.12 | 通过 conda 管理 |
| Conda | Miniconda / Anaconda / Mambaforge | 推荐用 mamba 加速 |
| Rust toolchain | stable | 通过 `rust/` git 子模块管理（pyo3/maturin） |
| Node.js | >= 18 | 前端开发（可选，仅 Web UI） |
| DuckDB | 随 conda 安装 | 默认数据库引擎，无需单独部署 |

操作系统：macOS / Linux（Windows 建议使用 WSL2）。

---

## 2. 安装步骤

### 2.1 克隆仓库并初始化子模块

```bash
git clone <repo-url> cQuant
cd cQuant

# 初始化 git 子模块（qlib、vibe-trading、cquant-rust）
git submodule update --init --recursive
```

### 2.2 创建 conda 环境

cQuant 的 conda 环境名为 **`cQuanty`**（注意大小写）：

```bash
# 一键引导：创建环境 + 构建 Rust wheel
./scripts/bootstrap_dev.sh

# 激活环境
conda activate cQuanty
```

`bootstrap_dev.sh` 会执行：
1. 用 `environment.yml` 创建 `cQuanty` 环境；
2. 用 `pyproject.toml`（hatchling 后端）安装 Python 包 `cquant`（可编辑模式）；
3. 通过 `scripts/build_rust.sh` 编译 Rust 子模块并生成 Python 绑定。

> 如果只做纯 Python 研究而不涉及事件驱动回测（Rust 引擎），可跳过 Rust 构建，但 conda 环境仍需创建。

### 2.3 验证安装

```bash
conda activate cQuanty
python -c "import cquant; print('cQuant OK')"
python -m cquant.cli.main status
```

`status` 命令会显示系统状态：数据库路径、已摄入数据版本、已物化因子集、已注册策略等。

![系统状态](placeholder-status.png)

---

## 3. 启动服务

cQuant 由两部分组成：**FastAPI 后端**（默认端口 8000）和 **React 前端**（默认端口 3000）。

### 3.1 启动后端 API

```bash
conda activate cQuanty
# 开发模式（热重载）
uvicorn cquant.api_server.app:app --host 0.0.0.0 --port 8000 --reload
```

API 文档（Swagger）位于 `http://localhost:8000/docs`。

### 3.2 启动前端

```bash
cd web
npm install        # 首次
npm run dev        # 启动 Vite 开发服务器，端口 3000
```

浏览器访问 `http://localhost:3000` 即可看到中文界面（支持 zh-CN / en-US 切换）。

![主界面](placeholder-home.png)

---

## 4. 数据摄入（Ingestion）

cQuant 数据仓库采用三层架构（Bronze → Silver → Gold），存储在 DuckDB 中。

### 4.1 引导元数据（Bootstrap）

从 TDX 数据库引导资产元数据与交易日历：

```bash
python -m cquant.cli.main bootstrap --target all --tdx-db tdx.db
```

`--target` 可选：`assets`（资产列表）、`calendar`（交易日历）、`all`（两者）。

### 4.2 摄入行情数据

cQuant 支持多数据源：

| 数据源 | 命令参数 | 适用场景 | 是否需要 Token |
|--------|----------|----------|----------------|
| **TDX** | `--source tdx` | A 股批量本地数据（6,675 股票） | 否 |
| **Tushare** | `--source tushare` | A 股专业数据（基本面/估值/分红） | 是（`TUSHARE_TOKEN`） |
| **AKShare** | `--source akshare` | A 股免费数据（公开接口） | 否 |
| **yfinance** | `--source yfinance` | 美股/港股 | 否 |

**示例 1：TDX 批量摄入（推荐首次使用）**

```bash
python -m cquant.cli.main ingest \
  --source tdx \
  --tdx-db tdx.db \
  --start 2024-01-01 \
  --end 2025-12-31
```

**示例 2：Tushare 摄入（需 Token）**

```bash
export TUSHARE_TOKEN="你的token"
python -m cquant.cli.main ingest \
  --source tushare \
  --symbols "SSE:600036,SSE:000001" \
  --start 2024-01-01 \
  --end 2025-12-31
```

摄入完成后会返回 `version_id`，后续因子物化和回测都基于这个数据集版本。

> **复权说明**：cQuant 默认使用前复权价（`adj_factor` 校验 + `adjusted_ohlc_sql` helper），回测与因子计算路径统一走复权价，避免幸存者偏差。详见 [FAQ](faq.md)。

### 4.3 PIT 正确性（基本面数据）

基本面数据（如 PE/PB/市值）严格遵循 **Point-in-Time（PIT）** 原则：使用 `announce_date`（公告日）而非报告期末日对齐，避免未来函数。`silver_fundamentals` 和 `silver_valuation_daily` 表均带 `announce_date` 字段。详见 [FAQ](faq.md)。

---

## 5. 物化因子

因子是策略的输入。cQuant 内置 500+ 因子（qlib Alpha158 + Alpha360 + Alpha101 + GTJA191 + 自定义）。

```bash
# 物化全部内置因子（首次推荐）
python -m cquant.cli.main factors \
  --dataset-version tdx_bulk_v1 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --all

# 或物化指定因子
python -m cquant.cli.main factors \
  --dataset-version tdx_bulk_v1 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --factor-names ret_20d rsi_14 momentum_60d
```

`--dataset-version` 对应第 4 步摄入返回的 `version_id`。物化结果存入 `silver_factor_values` 表。

> 因子增量物化：cQuant 会计算数据指纹，未变更的因子不会重复计算，大幅加速增量更新。

详细的因子研究流程（IC 分析、分层收益、因子 DSL）见 [因子研究指南](factor-research.md)。

---

## 6. 首次回测

最简单的回测：用 `StaticTopN` 策略，按 20 日动量（`ret_20d`）选前 10 只股票。

### 6.1 通过 CLI

```bash
python -m cquant.cli.main backtest \
  --dataset-version tdx_bulk_v1 \
  --strategy-id top10 \
  --start 2025-01-01 \
  --end 2025-06-30
```

关键参数（均有默认值，参见 `configs/defaults/backtest.toml`）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--initial-cash` | 1,000,000 | 初始资金（CNY） |
| `--benchmark` | `000300.SH` | 基准（沪深 300） |
| `--top-n` | 10 | 选股数量 |
| `--sort-factor` | `ret_20d` | 排序因子 |

### 6.2 通过 Web UI

1. 打开 `http://localhost:3000`；
2. 进入「策略」页面，点击「新建策略」，选择类型 `StaticTopN`，配置 `top_n=10`、`sort_factor=ret_20d`；
3. 进入「回测」页面，点击「新建回测」，选择策略、数据集版本、日期范围，点击「运行」；
4. 回测完成后进入详情页，查看 14 个分析 Tab。

![回测列表](placeholder-backtest-list.png)

回测结果分析的完整解读见 [回测分析指南](backtest-analysis.md)。

---

## 7. 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `TUSHARE_TOKEN` | 否 | Tushare Pro API Token（CN 专业数据） |
| `ANTHROPIC_API_KEY` | 否 | Claude API Key（AI Advisor） |
| `OPENAI_API_KEY` | 否 | OpenAI API Key（AI Advisor 备用） |

---

## 8. 下一步

- [因子研究指南](factor-research.md) — IC 分析、分层收益、因子 DSL
- [策略配置指南](strategy-config.md) — 8 种策略类型详解
- [回测配置指南](backtest.md) — 日期、资金、复权、净费模型
- [回测分析指南](backtest-analysis.md) — 14 个分析 Tab 解读
- [实盘交易指南](live-trading.md) — 部署、监控、Kill-Switch
- [常见问题](faq.md)
