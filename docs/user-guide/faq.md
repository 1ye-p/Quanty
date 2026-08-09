# 常见问题（FAQ）

本篇汇总 cQuant 使用中的常见问题：数据缺失、PIT 正确性、复权、性能、告警等。

---

## 数据

### Q1：回测时提示某只股票数据缺失怎么办？

cQuant 采用**行情缺失前向填充 + 退市剔除**机制（HARD-1）：
- **停牌/缺失**：缺失行情会前向填充（用上一交易日数据），避免因单日缺失导致信号断裂；
- **退市**：退市股票自动从 universe 剔除，避免脏数据进入回测；
- **数据质量评分**：可在「数据集」页面查看质量报告（`QualityReport`），定位缺失集中区域。

若大面积缺失，请检查数据摄入是否完整：
```bash
python -m cquant.cli.main status   # 查看数据覆盖率
```

### Q2：多数据源合并时有重复数据怎么处理？

摄入时自动**源合并去重**（`source merge dedup`），按优先级保留数据。可在 `datahub.toml` 配置数据源优先级。

### Q3：如何检测幸存者偏差？

cQuant 内置**幸存者偏差校正**（Task 12）和**复权因子校验**（Task 13）。在「数据集」页面查看质量评分，确保 universe 包含已退市股票的历史数据。

---

## PIT 正确性（基本面）

### Q4：什么是 PIT（Point-in-Time）正确性？为什么重要？

PIT 意为"时点正确"：在使用基本面数据（如 PE/PB/净利润/市值）时，必须用**公告日（announce_date）**对齐，而非报告期末日。

**反例**：用 2024Q3 报告（2025-01 发布）的数据参与 2024-10 的回测 → 用了未来信息（未来函数），回测结果虚高。

cQuant 的 `silver_fundamentals` 和 `silver_valuation_daily` 表均带 `announce_date` 字段，因子物化时严格按 announce_date 对齐（PIT3-1/2/3）。有 5 个专门测试覆盖 PIT 正确性。

### Q5：市值因子用哪个表？

市值因子（value/size）从 `silver_valuation_daily` 读取（按 announce_date 对齐），而非用报告期末的股本×价格近似。`cross_section_scorer` 的市值也改用 valuation_daily（PIT3-3）。

### Q6：AKShare 的财务数据怎么保证 PIT 正确？

AKShare 回退路径会**解析实际财务值**（PIT4），而非用估算值，确保即便走免费数据源也保持 PIT 正确。

---

## 复权

### Q7：cQuant 默认用什么复权方式？

**前复权**（`pre`）。所有回测和因子计算路径统一通过 `adjusted_ohlc_sql` helper 生成复权 SQL，避免分红/送股造成的价格跳空。

### Q8：如何确认复权正确？

- 启动时自动检查 `adj_factor`（复权因子）覆盖率，覆盖率不足会告警；
- fills 表保留 `raw_close`（原始价）列，可核对；
- 有 8 个复权正确性测试覆盖（ADJ-5）；
- 若复权因子更新，可用 `scripts/rematerialize_factors.py` 重新物化因子。

### Q9：复权方式可以切换吗？

在策略配置的「市场规则」区域选择 `adjType`。但**强烈建议保持前复权**，切换可能导致回测与因子口径不一致。

---

## 性能

### Q10：全市场（6000+ 股票）回测很慢怎么办？

- **向量化引擎**：cQuant 默认用向量化引擎（Polars + 矩阵化价格），已针对大股票池优化（Task 704 价格矩阵向量化）；
- **增量物化**：因子增量物化用数据指纹，避免重复计算；
- **并发控制**：全局 job 信号量限制并发，避免资源争抢；
- **数据规模**：若仍慢，可先用子集 universe（如沪深 300 成分股）验证逻辑，再扩展到全市场。

> cQuant 有专门的**大股票池性能基准**（HARD-5，仅测量）用于评估。

### Q11：因子物化很慢？

- 确认是否触发了增量物化（数据指纹命中则跳过）；
- 检查是否物化了过多因子（按需 `--factor-names` 指定）；
- DuckDB 内存不足时调大 `memory_limit`。

### Q12：回测结果不可复现？

cQuant 用**局部 RNG 透传**（`random_seed` 传入 `BacktestSpec`，HARD-2），消除全局 seed 污染。同一 `random_seed` + 同一数据版本 → 结果可精确复现。若不可复现，检查：
- 数据版本是否变化；
- 是否有未提交的代码改动；
- `random_seed` 是否固定。

---

## 告警

### Q13：如何配置告警通知渠道？

在「告警」页面 → 「通知渠道」Tab：
1. 点击新增渠道（`ChannelForm`）：选择类型（邮件 / Webhook）、填入配置；
2. 「测试渠道」（`testChannel`）：发送测试通知验证连通性；
3. 配置「静默规则」（`SilenceRules`）：在指定时段抑制告警（如非交易时段）。

### Q14：因子 IC 衰减了如何告警？

在「因子」页面，因子卡片上的 IC 告警徽标（`FactorCard`）会自动反映 IC 状态。告警规则（如 Mean IC < 0.02 或不显著）在「告警」页面配置，触发后通过已配置渠道通知。

### Q15：风控 breaches 如何告警？

风控策略（止损/回撤熔断/杠杆限制）触发时会生成 `risk_breach` 类型告警（Task 335-342）。严重级别（Critical/High/Medium/Low）决定通知优先级。在「风险」页面的 `RiskEventHistory` 可查看历史 breach 记录。

---

## 策略与回测

### Q16：多因子策略，某些股票缺部分因子怎么处理？

在策略配置的「缺失因子处理」选择：
- `fill_0`（默认）：缺失填 0；
- `drop`：剔除有缺失的股票；
- `risk_penalty`：缺失越多打分越低（配合 `penalty_per_missing` 系数）。

详见 [策略配置指南 - 缺失因子处理](strategy-config.md#22-multifactor多因子)。

### Q17：基准（benchmark）数据缺失会怎样？

UI 会显示 **benchmark 空值警告**（UX-1），相对指标（Alpha/Beta/IR/TE）无法计算。请确保基准在回测区间内有完整数据，或更换基准。

### Q18：A 股回测，为什么有的股票买不进？

A 股有涨跌停限制：涨停（无法买入）、跌停（无法卖出）会被自动过滤。引擎的 `filterLimitUpDown` 开关默认开启。若回测中大量信号被过滤，说明策略倾向追涨杀跌，需调整。

### Q19：Walk-Forward 和普通回测有什么区别？

- **普通回测**（`vector`）：全区间一次性回测，快但可能有未来函数风险；
- **Walk-Forward**（`walk_forward`）：按窗口滚动训练（ML）+ 预测 + 回测，严格避免未来函数，结果更接近实盘。ML 策略建议用 Walk-Forward。

回测详情页的 WalkForward Tab 仅在 `engine=walk_forward` 时显示。

### Q20：如何导出回测报告？

回测详情页支持导出：
- **PDF tearsheet**：完整分析报告（含 SVG 图表）；
- **CSV/JSON**：指标、fills、收益序列；
- 通过 SharePage 分享报告链接。

---

## 环境与安装

### Q21：conda 环境名是什么？

**`cQuanty`**（注意大小写）。激活：`conda activate cQuanty`。

### Q22：Rust 子模块构建失败？

- 确认已 `git submodule update --init --recursive`；
- 确认 Rust toolchain 已安装（`rustup show`）；
- 用 `scripts/build_rust.sh` 单独构建，查看详细错误；
- 纯 Python 研究可跳过 Rust（但事件驱动引擎不可用）。

### Q23：前后端端口是多少？

- 后端 API：`8000`（`http://localhost:8000/docs` Swagger）；
- 前端 Web：`3000`（`http://localhost:3000`）。

### Q24：忘记配置 TUSHARE_TOKEN？

Tushare 数据源需要 Token。若未配置，TDX / AKShare / yfinance 不受影响。设置：`export TUSHARE_TOKEN="你的token"`。

---

## 未解决问题

若以上 FAQ 未覆盖你的问题：
1. 查看 `python/tests/` 下的测试用例，了解功能预期行为；
2. 查看 `docs/` 下的 PRD 和 Review 文档；
3. 查看 `CLAUDE.md` 的模块索引和变更记录；
4. 提交 issue 并附上复现步骤。

---

## 相关文档

- [快速开始](getting-started.md)
- [因子研究指南](factor-research.md)
- [策略配置指南](strategy-config.md)
- [回测配置指南](backtest.md)
- [回测分析指南](backtest-analysis.md)
- [实盘交易指南](live-trading.md)
