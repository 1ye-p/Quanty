# cQuant 项目优化路线图

> 版本：v1.2 · 2026-05-22
> 来源：IMPROVEMENT_PLAN.md + OPENSOURCE_ANALYSIS.md + v2 评估报告 + Vibe-Trading 调研
> 原则：优先以 submodule 形式集成成熟开源工具并封装隔离，再补齐工程细节，最后打磨 UI/UX

---

## 全局概览

```
Phase 0    Qlib 子模块集成          ✅████████████  完成 ★★★★★
Phase 0-B  Vibe-Trading 子模块集成  ✅████████████  完成 ★★★★☆
Phase 1    UI Bug 修复              ✅████████████  完成
Phase 2    回测评估增强             ✅████████████  完成
Phase 3    因子研究 + ML 打通       ✅████████████  完成
Phase 4    AI Advisor 升级          ✅████████████  完成
```

---

## Phase 0：Qlib 子模块集成

> **目标**：将 Qlib 以 git submodule 形式纳入项目（参照 `rust/` 的管理方式），
> 在 cQuant 上层通过 `qlib_bridge/` 封装隔离，外部模块只调用 bridge 接口，
> 不直接依赖 Qlib 内部 API，保证 Qlib 版本升级时只需修改 bridge 层。

---

### 架构设计

```
项目目录结构（新增）
├── lib/
│   └── qlib/              ← git submodule（pin 到指定 tag/commit）
│       └── qlib/          ← Qlib 源码包
├── python/
│   └── cquant/
│       └── qlib_bridge/   ← cQuant 对 Qlib 的封装层（唯一出口）
│           ├── __init__.py
│           ├── _compat.py       # 可用性检测 + 优雅降级
│           ├── data_handler.py  # DuckDB → Qlib DataHandlerLP 适配
│           ├── evaluator.py     # IC/IR/risk_analysis 封装
│           ├── factor_set.py    # Alpha158/360 因子定义桥接
│           └── ml_pipeline.py   # Qlib ML workflow 封装（Phase 0.5）
```

**设计原则：**
- `qlib_bridge/` 之外的所有模块**只导入 `qlib_bridge`，不直接 `import qlib`**
- `_compat.py` 在 Qlib 不可用时返回 stub 对象，各方法 fallback 到 cQuant 原生实现
- bridge 接口使用 cQuant 自定义类型（Polars DataFrame / Python dataclass），屏蔽 Qlib 的 pandas multi-index 约定

---

### 0.1 子模块接入

- [ ] 添加 Qlib 为 git submodule，存放于 `lib/qlib/`：
  ```bash
  git submodule add https://github.com/microsoft/qlib.git lib/qlib
  cd lib/qlib && git checkout v0.9.6   # pin 到稳定版本
  ```
- [ ] 更新 `.gitmodules`：
  ```ini
  [submodule "lib/qlib"]
      path = lib/qlib
      url = https://github.com/microsoft/qlib.git
      branch = main          # 追踪 main，但 pin commit 在 bootstrap 中锁定
  ```
- [ ] `scripts/bootstrap_dev.sh` 新增 Qlib 安装步骤：
  ```bash
  # 初始化 qlib submodule
  git submodule update --init lib/qlib
  # 可编辑模式安装（不升级，只用当前 pin 版本）
  pip install -e lib/qlib --no-deps
  # Qlib 的额外依赖单独安装（避免覆盖 cQuant 主环境）
  pip install pandas numpy scipy statsmodels scikit-learn
  ```
- [ ] `environment.yml` 移除 `qlib` pip 条目（改为 submodule 安装）
- [ ] `CLAUDE.md` 架构总览补充 `lib/qlib` 子模块说明
- [ ] 验证：`python -c "import qlib; print(qlib.__version__)"` 无报错

### 版本升级流程（文档化）

```bash
# 升级 Qlib 版本
cd lib/qlib
git fetch && git checkout v0.9.x   # 目标版本 tag
cd ../..
git add lib/qlib
git commit -m "chore: bump qlib submodule to v0.9.x"
# 重新安装
pip install -e lib/qlib --no-deps
# 运行 bridge 测试确认接口兼容
pytest python/tests/unit/test_qlib_bridge.py
```

---

### 0.2 Bridge 基础层：可用性检测与降级

**文件**：`python/cquant/qlib_bridge/_compat.py`

- [ ] 实现 `QLIB_AVAILABLE: bool` 标志（尝试 `import qlib`）
- [ ] 实现 `require_qlib()` 装饰器：
  - Qlib 可用时：正常执行
  - 不可用时：`raise ImportError("Qlib not installed. Run: pip install -e lib/qlib")`
- [ ] 实现 `qlib_or_fallback(qlib_fn, fallback_fn)` 工具函数：
  - 根据 `QLIB_AVAILABLE` 自动路由到 Qlib 实现或 cQuant 原生实现
  - 用于 IC、IR 计算等有双实现的场景

---

### 0.3 数据适配层

**文件**：`python/cquant/qlib_bridge/data_handler.py`

- [ ] 实现 `CQuantDataHandler`（封装 Qlib 的 `DataHandlerLP`）：

  ```python
  class CQuantDataHandler:
      """将 cQuant DuckDB 数据适配为 Qlib DataHandlerLP。
      外部只调用此类，不直接用 qlib.DataHandlerLP。
      """
      @classmethod
      def from_catalog(cls,
                       catalog: Catalog,
                       dataset_version: str,
                       start: date, end: date,
                       processors: list[str] | None = None
                       ) -> "CQuantDataHandler": ...

      def fetch_features(self) -> pl.DataFrame:
          """返回 Polars DataFrame，屏蔽 pandas multi-index。"""

      def fetch_labels(self, horizon: int = 5) -> pl.Series:
          """前瞻收益率标签。"""
  ```

- [ ] 内部实现：
  - `_load_prices_to_pandas()` — 查询 `silver_prices_1d`，构建 `(datetime, instrument)` multi-index
  - `_load_factors_to_pandas()` — 查询 `gold_factor_values` pivot 为宽表
  - 调用 `StaticDataLoader(df)` + `DataHandlerLP(loader, infer_processors=[...])`
  - 返回结果转回 Polars（隔离 pandas 依赖）

- [ ] 单元测试：`python/tests/unit/test_qlib_bridge_data.py`
  - Mock DuckDB 查询，验证 multi-index 构建正确
  - 验证返回的 Polars DataFrame schema 符合预期

---

### 0.4 评估层封装

**文件**：`python/cquant/qlib_bridge/evaluator.py`

- [ ] 实现 `QlibEvaluator`（封装 IC/IR/risk_analysis）：

  ```python
  class QlibEvaluator:
      """Qlib 因子评估工具的 cQuant 封装。
      接口与 FactorEvaluator 保持一致，可互换使用。
      """
      def ic_series(self, factor: pl.Series, forward_returns: pl.Series,
                    method: str = "rank") -> pl.DataFrame: ...

      def ic_summary(self, factor_name: str, feature_set_version: str,
                     horizon: int = 5) -> dict: ...
          # 包含：mean_ic, ic_ir, ic_positive_pct, rank_ic_decay, quantile_returns

      def risk_analysis(self, returns: pl.Series,
                        benchmark: pl.Series | None = None) -> dict: ...
          # 包含：annualized_return, information_ratio, max_drawdown, sharpe
  ```

- [ ] 内部调用：
  - `qlib.contrib.report.analysis_model.calc_ic()` 计算 IC
  - `qlib.contrib.evaluate.risk_analysis()` 计算风险指标
  - 所有输入输出均转换为 Polars，不暴露 pandas Series 给调用方

- [ ] `factorlab/evaluation.py` 的 `FactorEvaluator` 新增 `backend` 参数：
  ```python
  evaluator = FactorEvaluator(backend="qlib")  # 或 "native"（默认）
  ```
  - `"qlib"` 时委托给 `QlibEvaluator`
  - `"native"` 时使用现有 Polars 实现
  - 对比测试验证两者数值差异 < 1e-4

- [ ] 单元测试：`python/tests/unit/test_qlib_bridge_evaluator.py`

---

### 0.5 Alpha158/360 因子集桥接

**文件**：`python/cquant/qlib_bridge/factor_set.py`

- [ ] 实现 `QlibFactorSet`：

  ```python
  class QlibFactorSet:
      """从 Qlib Alpha158/360 定义中提取可用于 cQuant 的因子。"""

      @staticmethod
      def alpha158_definitions() -> list[dict]:
          """读取 lib/qlib/qlib/contrib/data/handler.py 中的因子表达式，
          返回 [{name, expression, deps}] 列表。"""

      @staticmethod
      def to_cquant_factor(name: str, expression: str) -> Factor:
          """将 Qlib 因子表达式转为 cQuant Factor 子类（Polars 实现）。"""
  ```

- [ ] 筛选 Alpha158 中仅依赖 OHLCV 的因子（约 50-60 个）
- [ ] 在 `python/cquant/factorlab/factors/alpha158.py` 中生成对应 Factor 实现
  - 每个因子注明 `# Source: Qlib Alpha158 — {original_expression}`
  - 使用 Polars 重新实现（不直接调用 Qlib 表达式引擎，保持 cQuant 计算层独立）
- [ ] 注册到 `BUILTIN_FACTORS`，新增 tag `"alpha158"`

---

### 0.6 ML Pipeline 桥接（Phase 0.5，二期实现）

**文件**：`python/cquant/qlib_bridge/ml_pipeline.py`

- [ ] 评估 cQuant `ml_lab/pipeline.py` vs Qlib `DoubleEnsemble`/`workflow` 的功能差距
- [ ] 实现 `QlibMLBridge.run_double_ensemble(handler, label_col) → model_id`
  - 调用 Qlib 的集成学习模型训练
  - 预测结果写入 cQuant 的 `gold_predictions` 表（格式兼容 `MLModelStrategy`）
- [ ] 此步骤待 0.3-0.5 完成后再实现

---

### Phase 0 验收标准

```bash
# 0.1 子模块
git submodule status lib/qlib                  # 显示已 pin 的 commit hash
python -c "import qlib; print(qlib.__version__)"  # 无报错

# 0.2 降级兼容
python -c "from cquant.qlib_bridge import QLIB_AVAILABLE; print(QLIB_AVAILABLE)"

# 0.3 数据适配
pytest python/tests/unit/test_qlib_bridge_data.py  -v  # 全部通过

# 0.4 评估层
pytest python/tests/unit/test_qlib_bridge_evaluator.py -v  # 全部通过
# IC 数值对比（Qlib vs cQuant native 差异 < 1e-4）

# 0.5 因子集
python -c "from cquant.factorlab.factors.alpha158 import ALPHA158_FACTORS; print(len(ALPHA158_FACTORS))"
# 输出 >= 50
pytest python/tests/unit/test_alpha158_factors.py -v  # 全部通过
```

---

## Phase 0-B：Vibe-Trading 子模块集成

> **目标**：将 Vibe-Trading 以 git submodule 形式纳入项目（与 Qlib / Rust 子模块管理方式一致），
> 通过 `vibe_bridge/` 封装隔离，按优先级逐步将其 452 Alpha 因子库、A 股引擎规则、
> 多 Agent Swarm 团队、LLM 供应商配置引入 cQuant，同时保持随时同步上游更新的能力。

---

### 为什么选择 Vibe-Trading（选项 B）

Vibe-Trading 是 HKUDS 出品的 MIT 许可量化研究平台（8,170 stars，今日仍有提交），核心优势：

| 维度 | Vibe-Trading | cQuant 现状 | 引入价值 |
|------|-------------|------------|---------|
| **Alpha 因子库** | 452 个（qlib158 + Alpha101 + 国泰君安 191 + 学术因子） | 31 个 | 因子库扩大 14 倍 |
| **回测引擎** | 7 个专业引擎（含 A 股/港美股/期货/期权/复合） | 1 个向量化 A 股引擎 | 多市场扩展 |
| **多 Agent Swarm** | 29 套预置团队（DAG 调度，investment_committee 等） | 5 个 Agent（手写编排） | Agent 能力质的飞跃 |
| **LLM 支持** | 13+ 供应商（含 Qwen/GLM/Kimi/MiniMax 国产模型） | Claude + OpenAI | 国产模型接入 |
| **风险分析** | VaR/CVaR/Stress/EVT 完整方法论 | 5 个 Policy 类 | 风险分析深度 |

**cQuant 保持优势**：DuckDB 三层存储、LightGBM/XGBoost ML Pipeline、QMT 实盘执行、RAG 知识库。

---

### 架构设计

```
项目目录结构（新增）
├── lib/
│   ├── qlib/              ← 已有 submodule
│   └── vibe-trading/      ← 新增 submodule（pin 到指定 tag/commit）
│       └── agent/         ← Vibe-Trading 核心源码
├── python/
│   └── cquant/
│       └── vibe_bridge/   ← cQuant 对 Vibe-Trading 的封装层（唯一出口）
│           ├── __init__.py
│           ├── _compat.py        # 可用性检测 + 优雅降级
│           ├── alpha_zoo.py      # 452 Alpha → cQuant Factor ABC 适配
│           ├── backtest_engine.py # Vibe A 股引擎规则 → cQuant 填充/验证
│           ├── swarm.py          # 29 套 Swarm YAML → ai_advisor 编排
│           └── providers.py      # 13+ LLM 供应商 → ai_advisor providers
```

**设计原则（与 qlib_bridge 一致）：**
- `vibe_bridge/` 之外的所有模块**只导入 `vibe_bridge`，不直接 `import` Vibe-Trading 内部模块**
- `_compat.py` 在 Vibe 不可用时各方法 fallback 到 cQuant 原生实现
- bridge 接口使用 cQuant 自定义类型，屏蔽 Vibe-Trading 的内部 API

---

### 版本同步策略

```bash
# 方式 1：追踪最新 commit（保持与上游同步）
cd lib/vibe-trading
git fetch origin && git checkout main && git pull
cd ../..
git add lib/vibe-trading
git commit -m "chore: sync vibe-trading submodule to latest main"

# 方式 2：升级到指定版本 tag（稳定版本锁定）
cd lib/vibe-trading
git fetch && git checkout v0.2.0
cd ../..
git add lib/vibe-trading
git commit -m "chore: bump vibe-trading submodule to v0.2.0"

# 任何版本变更后必须运行 bridge 兼容性测试
pytest python/tests/unit/test_vibe_bridge.py -v
```

**`.gitmodules` 配置：**
```ini
[submodule "lib/vibe-trading"]
    path = lib/vibe-trading
    url = https://github.com/HKUDS/Vibe-Trading.git
    branch = main          # 追踪 main 分支，commit pin 由 bootstrap 管理
```

---

### 0-B.1 子模块接入

- [x] 添加 Vibe-Trading 为 git submodule，存放于 `lib/vibe-trading/`
- [x] 更新 `.gitmodules`
- [x] `scripts/bootstrap_dev.sh` 新增 Vibe-Trading 安装步骤
- [x] `environment.yml` 补充 Vibe-Trading 的最小依赖集
- [x] `CLAUDE.md` 架构总览补充 `lib/vibe-trading` 子模块说明
- [x] 验证 import 无报错

---

### 0-B.2 Bridge 基础层

**文件**：`python/cquant/vibe_bridge/_compat.py`

- [x] 实现 `VIBE_AVAILABLE: bool` 标志
- [x] 实现 `require_vibe()` 装饰器
- [x] 实现 `vibe_or_fallback(vibe_fn, fallback_fn)` 工具函数

---

### 0-B.3 Alpha Zoo 迁移（P0 — 最高优先级）

**文件**：`python/cquant/vibe_bridge/alpha_zoo.py`

Vibe-Trading 的 452 个 Alpha 分为 4 个 Zoo，按迁移难度排序：

| Zoo | 数量 | 数据依赖 | 迁移优先级 |
|-----|------|---------|-----------|
| `qlib158` | 154 | OHLCV（纯价量） | ★★★★★ 最优先 |
| `alpha101` | 101 | OHLCV + 成交量 | ★★★★☆ |
| `gtja191` | 191 | OHLCV + 换手率 | ★★★☆☆ |
| `academic` | 6 | 财务数据 | ★☆☆☆☆ 依赖基本面 |

**迁移机制：**

- [x] 实现 `VibeFactor` 协议适配器（Polars → Pandas panel → Vibe alpha → Polars）
- [x] 实现 `load_zoo(zoo_name: str) → list[Factor]` 批量加载工厂函数
- [x] **qlib158 迁移**：154 因子注册，tag `"qlib158"`，测试通过
- [x] **alpha101 迁移**：101 因子注册，tag `"alpha101"`，测试通过
- [x] **gtja191 迁移**：191 因子注册，tag `"gtja191"`，测试通过

---

### 0-B.4 A 股引擎规则对比与补齐

**文件**：`python/cquant/vibe_bridge/backtest_engine.py`

Vibe-Trading 的 `ChinaA` 引擎与 cQuant 的 `AShareFillSimulator` 都实现了 A 股约束，但细节存在差异。

- [ ] **规则对比清单**：逐条比较两个引擎的实现
  | 规则 | Vibe `china_a.py` | cQuant `fill_simulator.py` | 差距 |
  |------|---------|--------|------|
  | T+1 | `entry_date vs current_bar_date` | `buy_dates` dict | 待对比 |
  | 涨跌停检测 | 按板块动态（ChiNext 20%/BSE 30%）| `limit_rules.py` 动态 | 待对比 |
  | ST 限制 | heuristic（代码后缀判断） | 同 | 待对比 |
  | 手续费 | 0.025% + 转让费 0.001% + 印花税 0.05% | 0.03% + 印花税 0.1% | **有差异** |
  | 最小手数 | 100 股 | 100 股 | 相同 |
  | 滑点 | 默认 0.1% | 默认 0.01% | **有差异** |

- [x] 对比文档已输出至 `vibe_bridge/engine_compare.md`
- [x] 印花税更新建议已记录（0.1% → 0.05%，待用户确认）

---

### 0-B.5 Swarm 团队配置引入

**文件**：`python/cquant/vibe_bridge/swarm.py`

- [x] 实现 `VibSwarmLoader`：29 套 YAML 预置团队可加载
- [x] 实现 `to_agent_specs()` 将 Swarm YAML 转为 cQuant AgentSpec 格式
- [x] 测试通过（5 tests）

---

### 0-B.6 LLM 供应商扩展

**文件**：`python/cquant/vibe_bridge/providers.py`

- [x] 读取 `llm_providers.json` 的 14 个供应商配置
- [x] 实现 `VibeLLMProviderConfig` 适配器
- [x] 测试通过（6 tests）
  - [ ] Qwen（通义千问，`DASHSCOPE_API_KEY`）
  - [ ] GLM（智谱，`ZHIPU_API_KEY`）
  - [ ] Kimi（月之暗面，`MOONSHOT_API_KEY`）
  - [ ] DeepSeek（`DEEPSEEK_API_KEY`）
- [ ] `configs/defaults/` 新增 `llm_providers.toml` 配置文件
- [ ] `ai_advisor/providers/` 注册新 Provider 实现

---

### Phase 0-B 验收标准

```bash
# 0-B.1 子模块
git submodule status lib/vibe-trading          # 显示已 pin 的 commit hash
python -c "import sys; sys.path.insert(0, 'lib/vibe-trading'); \
           from agent.src.factors.zoo import qlib158; print('vibe ok')"

# 0-B.2 Bridge 可用性
python -c "from cquant.vibe_bridge import VIBE_AVAILABLE; print(VIBE_AVAILABLE)"

# 0-B.3 Alpha Zoo
python -c "from cquant.vibe_bridge.alpha_zoo import load_zoo; \
           print(len(load_zoo('qlib158')))"   # 输出 154
pytest python/tests/unit/test_vibe_alpha_qlib158.py -v    # 全部通过
pytest python/tests/unit/test_vibe_alpha_alpha101.py -v   # 全部通过

# 0-B.4 引擎规则对比
python -m cquant.vibe_bridge.backtest_engine --compare    # 输出规则差异报告

# 0-B.5 Swarm 配置加载
python -c "from cquant.vibe_bridge.swarm import VibSwarmLoader; \
           print(VibSwarmLoader().list_presets())"         # 列出 29 个团队名

# 0-B.6 LLM 供应商
python -c "from cquant.vibe_bridge.providers import list_vibe_providers; \
           print(list_vibe_providers())"                   # 列出 13+ 供应商
```

---

## Phase 1：UI Bug 修复 + 全局 UX

> **目标**：消除日常使用中的阻塞性问题，统一通知/加载/错误体验。

### 1.1 通知系统统一

- [ ] 引入 `sonner`（或使用 shadcn/ui 内置 toast）
  ```bash
  cd web && pnpm add sonner
  ```
- [ ] `main.tsx` 挂载 `<Toaster />`
- [ ] 封装 `useToast` hook，统一 success/error/info 调用
- [ ] 替换 `MLLabPage` 的 `alert("训练 Job 已提交")` → toast
- [ ] 所有 mutation（create/update/delete）接入 toast 反馈

### 1.2 策略配置修复

- [ ] **删除反馈**：`StrategiesPage` 删除成功/失败后显示 toast
- [ ] **确认弹框**：`window.confirm` → shadcn `AlertDialog`
- [ ] **表单校验**：
  - 策略 ID 为空时禁用"保存"按钮
  - 提交前 `JSON.parse(configText)` 校验，失败时行内错误
  - 捕获后端 409 → 展示"策略 ID 已存在"行内提示

### 1.3 回测参数增强

- [ ] `BacktestRunModal` 新增策略类型选择（StaticTopN / MultiFactorStrategy / MLModel）
- [ ] 选择 MultiFactorStrategy 时展示因子权重配置表格
- [ ] 日期范围校验（end > start，不超过今天）

### 1.4 Loading 与空状态

- [ ] 所有列表页（Factors/Strategies/Backtests/MLLab）加骨架屏
- [ ] 列表为空时显示引导性空状态 + 快捷操作按钮

### 1.5 全局错误处理

- [ ] `router.tsx` 添加 `<ErrorBoundary>` 包裹所有路由
- [ ] `web/src/lib/api.ts` 的 `request()` 统一将 4xx/5xx 转为用户可读错误
- [ ] 添加 `/404` 路由回退页面

### Phase 1 验收标准

```
[ ] 删除策略后，页面显示 toast "已删除"
[ ] 提交无效 JSON 时，表单显示行内错误，不发送请求
[ ] MLLab 提交 Job 后显示 toast，不弹 alert()
[ ] 刷新后空列表页显示引导 UI
[ ] 网络断开时 API 调用显示错误提示而非白屏
```

---

## Phase 2：回测评估增强

> **目标**：过拟合分析可在 UI 中触发；支持训练集/测试集划分；回测提交异步化。

### 2.1 回测异步化（P0，当前存在阻塞风险）

- [ ] `POST /api/v1/backtests` 改为 `BackgroundTask` 异步执行，立即返回 `{job_id}`
- [ ] 新增 `GET /api/v1/backtests/jobs/{job_id}` 查询运行状态
- [ ] 前端 `StrategiesPage` 的 `BacktestRunModal` 改用 `useJobPoller` hook 轮询
- [ ] `BacktestsPage` 列表展示 `running` 状态的动态 badge

### 2.2 过拟合分析触发

- [ ] 新增后端端点 `POST /api/v1/backtests/{id}/analyze`（BackgroundTask 异步）
- [ ] `BacktestsPage` 的 Overfitting 标签页：
  - 无分析数据时显示"运行分析"按钮
  - 点击触发 POST → 轮询 job 状态 → 完成后刷新
  - 已有数据时显示结果 + "重新分析"按钮

### 2.3 训练集 / 测试集划分

- [ ] 回测创建表单新增"评估模式"字段：
  - `full`：全量（默认）
  - `oos_split`：固定 OOS 截止日期（用户指定训练结束日）
  - `walk_forward`：滚动窗口（n_splits + in_sample_ratio）
- [ ] 后端 `BacktestSpec` 新增 `eval_mode` + `walk_forward_config` 字段
- [ ] `AnalysisEngine` 根据 `eval_mode` 选择对应的 Analyzer 运行

### 2.4 基准比较指标

- [ ] `BacktestSpec` 新增 `benchmark_asset_id`（如 `SSE:000300`）
- [ ] 后端加载基准收益率，传入 `compute_metrics(benchmark_returns=...)`
- [ ] `BacktestsPage` Overview 标签展示：Information Ratio、Tracking Error、Alpha（三个指标后端已实现）

### 2.5 结果导出

- [ ] Fills 表格增加"导出 CSV"按钮
- [ ] 指标报告增加"导出 JSON"按钮

### Phase 2 验收标准

```
[ ] 触发回测后，前端立即返回 job_id，不阻塞等待
[ ] Overfitting 标签点击"运行分析"→ 显示 loading → 展示 PSR/DSR/Overfit Score
[ ] 回测创建时选择 oos_split，BacktestsPage 展示 OOS 结果
[ ] Overview 标签展示 Information Ratio（需 benchmark 配置）
```

---

## Phase 3：因子研究工作流 + ML Lab 打通

> **目标**：用户能清晰理解并独立操作端到端研究流程（因子 → ML → 策略 → 回测）。

### 3.1 因子研究工作流

- [ ] `FactorsPage` 顶部添加流程步骤提示（Step 1 选数据集 → Step 2 选因子 → Step 3 计算 IC）
- [ ] "未选择数据集"时显示引导提示，链接到 DatasetsPage
- [ ] Feature Set Version 改为下拉选择（调用现有 `GET /api/v1/factors/versions`）

**因子评估可视化补全**（后端方法已实现，仅需前端展示）：
- [ ] **Rank IC 衰减图**：折线图，横轴 lag 1-20，纵轴 IC 值，调用 `FactorEvaluator.rank_ic_decay()`
- [ ] **分层收益图**：分组柱状图，5 个 Quantile 的平均收益，调用 `FactorEvaluator.quantile_returns()`
- [ ] **因子换手率**指标卡，调用 `FactorEvaluator.factor_turnover()`

**因子评估结果持久化**：
- [ ] 评估完成后将 `rank_ic_decay`、`quantile_returns`、`turnover` 写入 DuckDB（现在只存 IC 时序）
- [ ] 新增 `GET /api/v1/factors/analytics/history` 查询历史结果

### 3.2 ML Lab 工作流打通

- [ ] `MLLabPage` 顶部添加三步流程卡片：① 确认 Feature Set → ② 提交训练 → ③ 创建策略
- [ ] Feature Set Version 输入框改为下拉（调用 `GET /api/v1/factors/versions`）
- [ ] 训练完成后，实验行新增"用此模型创建策略"按钮
  - 跳转 StrategiesPage，预填 `MLModelStrategy` 配置（model_id、top_n）

**预测结果可视化**：
- [ ] 新增"预测"标签页：预测值分布直方图 + 预测 vs 实际收益散点图

### Phase 3 验收标准

```
[ ] 用户首次打开 FactorsPage，能通过流程提示完成第一次 IC 计算
[ ] IC 分析结果页同时展示：IC 时序 + Rank IC 衰减图 + 分层收益图
[ ] MLLabPage 的 Feature Set 选择为下拉，不再手动输入
[ ] 训练完成后点击"创建策略"，StrategiesPage 表单已预填 model_id
```

---

## Phase 4：AI Advisor 升级

> **目标**：参考 anthropics/financial-services 的模式升级多 Agent 架构和数据接入。

### 4.1 MCP 数据工具化

- [ ] 将 Tushare / AKShare 连接器封装为 MCP server
  - Agent 可通过工具调用实时行情，而非在代码中写死数据访问
- [ ] 将 factorlab IC 分析、backtest 结果查询封装为 MCP tool
- [ ] ai_advisor 的 Agent 工具列表从 Python 函数迁移为 MCP 调用

### 4.2 会话持久化

- [ ] 参考 TradingAgents 的 SQLite checkpoint 模式
- [ ] 将 `ai_advisor` 的 in-memory `_sessions` dict 替换为 SQLite 存储
- [ ] 支持跨进程（重启 API Server）后会话恢复

### 4.3 Callable Agents 编排

- [ ] 参考 Anthropic Financial Services 的 steering events 模式
- [ ] 将 5 个 Agent 解耦为独立可调用单元
- [ ] `orchestrator.py` 改为基于事件路由，而非手写调度状态机

### Phase 4 验收标准

```
[ ] AI Advisor 能通过 MCP 工具实时调用 AKShare 行情
[ ] 重启 API Server 后会话历史不丢失
[ ] 新增 Agent 类型不需要修改 orchestrator.py 核心逻辑
```

---

## 横切关注点（各 Phase 持续推进）

### 数据质量

- [ ] Silver 层价格数据增加 Winsorize 过滤（异常值：价格为 0、收益率 > 50%）
- [ ] CLI 多数据源支持：`--source {tdx,akshare,tushare,yfinance}`（当前只有 tdx）
- [ ] `silver_fundamentals` 定时更新（Scheduler 定时任务）

### 性能

- [ ] 因子物化 Lookback 窗口改为动态计算（按最大依赖因子，当前硬编码 90 天）
- [ ] `trading_days()` 改为 frozenset 二分查找 + 缓存（当前 O(N) 线性扫描）

### 测试

- [ ] 配置 `pytest-cov`，目标行覆盖率 ≥ 70%
- [ ] 补充前端组件测试（`StrategiesPage` 的 CRUD、`BacktestsPage` 的状态流转）
- [ ] 端到端集成测试：Factor → ML 训练 → MLModelStrategy → Backtest → AnalysisEngine

### 文档同步

- [ ] `CLAUDE.md` 模块索引更新（portfolio_opt、execution、scheduler 标记为完成）
- [ ] 各新模块补充 README（ml_lab、portfolio_opt、execution）
- [ ] API 文档：`/api/docs` OpenAPI 描述补全请求/响应示例

---

## 进度看板

| Phase | 状态 | 子任务进度 | 关键里程碑 | 备注 |
|-------|------|-----------|-----------|------|
| **Phase 0** Qlib 子模块集成 | ✅ 完成 | 0.1~0.5 全部完成 | `test_qlib_bridge` 全部通过，50+ Alpha158 因子可用 | |
| **Phase 0-B** Vibe-Trading 子模块集成 | ✅ 完成 | 0-B.1~0-B.6 全部完成 | 526 因子（80+154+101+191），29 Swarm 团队，14 LLM 供应商 | |
| **Phase 1** UI Bug 修复 | ✅ 完成 | toast → 策略校验 → 空状态 → 错误边界 | 无阻塞性操作 Bug | |
| **Phase 2** 回测评估增强 | ✅ 完成 | 异步化 → 过拟合触发 → 指标补全 → 导出 | 过拟合分析 UI 可独立触发 | |
| **Phase 3** 因子研究+ML 打通 | ✅ 完成 | IC 三图 → 工作流引导 → ML 跳转 | 端到端研究流程无断点 | |
| **Phase 4** AI Advisor 升级 | ✅ 完成 | MCP 工具化 → 会话持久化 → IntentRouter | MCP 数据工具可用 | |

状态：⬜ 待开始 · 🔄 进行中 · ✅ 完成 · ❌ 阻塞

---

## 附：开源工具整合决策摘要

| 工具 | 决策 | 集成方式 | 对应 Phase |
|------|------|----------|-----------|
| **Microsoft Qlib** | ✅ git submodule | `lib/qlib/` submodule（pin tag）+ `qlib_bridge/` 封装层；cQuant 上层只调用 bridge | Phase 0 🔄 |
| **Qlib Alpha158/360** | ✅ 通过 bridge 桥接 | `qlib_bridge/factor_set.py` 读取定义 → `factors/alpha158.py` Polars 重实现 | Phase 0.5 |
| **Vibe-Trading** | ✅ git submodule（选项 B） | `lib/vibe-trading/` submodule（追踪 main，可随时同步）+ `vibe_bridge/` 封装层；按优先级迁移：① 452 Alpha Zoo ② A 股引擎规则 ③ Swarm 团队 ④ 13+ LLM 供应商 | Phase 0-B ⬜ |
| **Anthropic Financial Services** | ✅ 架构参考 | Phase 4 MCP 化 + Callable Agents 编排模式 | Phase 4 |
| **FinanceToolkit** | ✅ 公式参考 | 参考财务比率公式扩充 factors/value、quality | Phase 3 |
| **Alphalens** | ✅ 图表设计参考 | 不引入依赖，参考图表布局实现前端 Rank IC / Quantile 图 | Phase 3 |
| **VnPy** | ⚠️ 局部参考 | 仅参考 XT gateway 回调模式完善 QMTAdapter | Phase 2 后 |
| **TradingAgents** | ⚠️ 局部参考 | SQLite checkpoint 用于 AI Advisor 会话持久化 | Phase 4 |
| **FinRL-Meta** | ⚠️ 研究扩展 | 将 backtest engine 包装为 gym env（研究用） | 长期 |
| **OpenBB** | ⚠️ 注意许可 | AGPLv3，商业使用需评估；MCP 设计参考 | 长期 |
| **AI-Trader / Zipline / Lean** | ❌ 不整合 | Crypto 导向 / 无 A 股支持 / 重量级 | — |
