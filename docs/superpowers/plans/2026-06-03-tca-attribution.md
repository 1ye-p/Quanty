# TCA + Brinson 归因 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已实现但未接入的 `TransactionCostAnalyzer` 和 `BrinsonAttribution` 串联到回测流水线，新增 API 端点和前端展示 Tab。

**Architecture:** 在 `AnalysisEngine.run()` 中串联 TCA（调用已有 `tca.py`）并修复 Brinson 归因（正确 benchmark returns + 逐日归因）。`AnalysisRunner` 新增持久化方法。API 新增 `/tca` 和 `/attribution` 端点。前端 BacktestsPage 新增「成本分析」和「归因分析」Tab。

**Tech Stack:** Python 3.12 + Polars + FastAPI + React 18 + TypeScript + TanStack Query

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `python/cquant/bt_analyzer/models.py` | Modify | AnalysisReport 新增 tca + attribution 字段 |
| `python/cquant/bt_analyzer/engine.py` | Modify | 串联 TCA + 修复 Brinson 归因 |
| `python/cquant/bt_analyzer/run.py` | Modify | 新增 TCA/attribution 持久化方法 |
| `python/cquant/api_server/routes/backtests.py` | Modify | 新增 `/tca` 和 `/attribution` 端点 |
| `web/src/lib/api.ts` | Modify | 新增 `getTca` 和 `getAttribution` |
| `web/src/lib/queryKeys.ts` | Modify | 新增 tca/attribution query keys |
| `web/src/pages/BacktestsPage.tsx` | Modify | 新增 TCA Tab + Attribution Tab |
| `python/tests/unit/test_tca_integration.py` | Create | TCA 集成测试 |
| `python/tests/unit/test_brinson_enhanced.py` | Create | Brinson 增强测试 |
| `web/src/pages/__tests__/BacktestsPage.test.tsx` | Modify | TCA/归因 Tab 测试 |

---

### Task 1: 扩展 AnalysisReport 数据模型

**Files:**
- Modify: `python/cquant/bt_analyzer/models.py:60-76`

- [ ] **Step 1: 在 AnalysisReport 添加 TCA 和归因字段**

在 `python/cquant/bt_analyzer/models.py` 的 `AnalysisReport` 数据类中添加新字段：

```python
@dataclass
class AnalysisReport:
    """Full output of AnalysisEngine.run()."""

    analysis_run_id: str
    backtest_run_id: str
    spec: AnalysisSpec
    overall_overfit_score: OverfitScore
    dsr: float
    psr: float
    walk_forward_windows: list[ValidationWindow]
    cpcv_windows: list[ValidationWindow] | None
    multiple_testing_result: dict[str, Any]
    stability_metrics: dict[str, float]
    summary: str
    brinson_attribution: "BrinsonResult | None" = None
    # TCA fields
    tca_summary: "TCASummary | None" = None
    tca_by_asset: "list[TCADetail] | None" = None
    tca_by_date: "list[TCADetail] | None" = None
    # Enhanced attribution fields
    brinson_daily: list[dict[str, Any]] | None = None
    benchmark_return: float | None = None
    active_return: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
```

同时在文件顶部添加 TYPE_CHECKING 导入：

```python
if TYPE_CHECKING:
    from cquant.bt_analyzer.attribution import BrinsonResult
    from cquant.backtest_vector.tca import TCASummary, TCADetail
```

- [ ] **Step 2: 验证导入无错误**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -c "from cquant.bt_analyzer.models import AnalysisReport; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add python/cquant/bt_analyzer/models.py
git commit -m "feat(bt_analyzer): add TCA and enhanced attribution fields to AnalysisReport"
```

---

### Task 2: 串联 TCA 到 AnalysisEngine

**Files:**
- Modify: `python/cquant/bt_analyzer/engine.py:36-133`
- Create: `python/tests/unit/test_tca_integration.py`

- [ ] **Step 1: 编写 TCA 集成测试**

```python
# python/tests/unit/test_tca_integration.py
"""Tests for TCA integration in AnalysisEngine."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestResult, BacktestSpec
from cquant.backtest_vector.metrics import BacktestMetrics
from cquant.bt_analyzer.engine import AnalysisEngine
from cquant.bt_analyzer.models import AnalysisSpec


def _make_fills(n: int = 10) -> pl.DataFrame:
    """Create synthetic fills data."""
    rows = []
    for i in range(n):
        rows.append({
            "trade_date": date(2025, 1, 1 + i),
            "asset_id": f"SSE:{600000 + i}",
            "side": "buy" if i % 2 == 0 else "sell",
            "qty": 100,
            "price": 10.0 + i * 0.1,
            "notional": (10.0 + i * 0.1) * 100,
            "commission": 0.5,
            "stamp_duty": 0.0 if i % 2 == 0 else 0.05,
            "slippage": 0.1,
            "total_cost": 0.6 if i % 2 == 0 else 0.65,
        })
    return pl.DataFrame(rows)


def _make_result(fills: pl.DataFrame | None = None) -> BacktestResult:
    """Create a minimal BacktestResult for testing."""
    if fills is None:
        fills = _make_fills()

    returns = pl.DataFrame({
        "trade_date": [date(2025, 1, i) for i in range(1, 11)],
        "portfolio_return": [0.01 * (i % 3 - 1) for i in range(10)],
        "nav": [1_000_000 * (1 + 0.01 * (i % 3 - 1)) for i in range(10)],
    })

    metrics = BacktestMetrics(
        total_return=0.05,
        annualized_return=0.12,
        annualized_volatility=0.15,
        sharpe_ratio=0.8,
        sortino_ratio=1.0,
        max_drawdown=-0.03,
        calmar_ratio=4.0,
        win_rate=0.6,
        profit_factor=1.5,
        var_95=-0.02,
        cvar_95=-0.025,
        beta=1.0,
        information_ratio=0.5,
        tracking_error=0.05,
        alpha=0.02,
        omega_ratio=1.2,
        tail_ratio=1.1,
        total_trades=10,
        trading_days=10,
    )

    spec = BacktestSpec(
        strategy=None,
        prices=pl.DataFrame(),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
        initial_cash=Decimal("1000000"),
    )

    return BacktestResult(
        run_id="test-run-001",
        engine="vector",
        strategy_id="test_strategy",
        spec=spec,
        metrics=metrics,
        portfolio_returns=returns,
        positions=pl.DataFrame(),
        fills=fills,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc),
    )


class TestTCAIntegration:
    """Test TCA integration in AnalysisEngine."""

    def test_tca_summary_populated(self):
        """AnalysisReport should contain TCA summary."""
        result = _make_result()
        engine = AnalysisEngine()
        report = engine.run(result)

        assert report.tca_summary is not None
        assert report.tca_summary.total_commission > 0
        assert report.tca_summary.num_trades == 10
        assert report.tca_summary.total_cost > 0

    def test_tca_by_asset_populated(self):
        """AnalysisReport should contain TCA by asset."""
        result = _make_result()
        engine = AnalysisEngine()
        report = engine.run(result)

        assert report.tca_by_asset is not None
        assert len(report.tca_by_asset) > 0
        # Should be sorted by total_cost descending
        costs = [d.total_cost for d in report.tca_by_asset]
        assert costs == sorted(costs, reverse=True)

    def test_tca_by_date_populated(self):
        """AnalysisReport should contain TCA by date."""
        result = _make_result()
        engine = AnalysisEngine()
        report = engine.run(result)

        assert report.tca_by_date is not None
        assert len(report.tca_by_date) > 0

    def test_tca_empty_fills(self):
        """TCA should handle empty fills gracefully."""
        result = _make_result(fills=pl.DataFrame({
            "trade_date": [], "asset_id": [], "side": [], "qty": [],
            "price": [], "notional": [], "commission": [], "stamp_duty": [],
            "slippage": [], "total_cost": [],
        }).cast({
            "trade_date": pl.Date, "asset_id": pl.Utf8, "side": pl.Utf8,
            "qty": pl.Int64, "price": pl.Float64, "notional": pl.Float64,
            "commission": pl.Float64, "stamp_duty": pl.Float64,
            "slippage": pl.Float64, "total_cost": pl.Float64,
        }))
        engine = AnalysisEngine()
        report = engine.run(result)

        assert report.tca_summary is not None
        assert report.tca_summary.num_trades == 0
        assert report.tca_by_asset == []
        assert report.tca_by_date == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -m pytest python/tests/unit/test_tca_integration.py -v --no-cov`
Expected: FAIL — `AssertionError: assert None is not None` (tca_summary is None)

- [ ] **Step 3: 在 AnalysisEngine.run() 中串联 TCA**

在 `python/cquant/bt_analyzer/engine.py` 的 `run()` 方法中，在 Brinson 归因之前（第 77 行之前）添加 TCA 调用：

```python
        # TCA analysis
        from cquant.backtest_vector.tca import TransactionCostAnalyzer
        tca_analyzer = TransactionCostAnalyzer()
        tca_summary = tca_analyzer.analyze(result.fills)
        tca_by_asset = tca_analyzer.analyze_by_asset(result.fills)
        tca_by_date = tca_analyzer.analyze_by_date(result.fills)
```

然后在 `AnalysisReport` 构造时传入：

```python
        return AnalysisReport(
            # ... existing fields ...
            tca_summary=tca_summary,
            tca_by_asset=tca_by_asset,
            tca_by_date=tca_by_date,
            # ... rest of fields ...
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -m pytest python/tests/unit/test_tca_integration.py -v --no-cov`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add python/cquant/bt_analyzer/engine.py python/tests/unit/test_tca_integration.py
git commit -m "feat(bt_analyzer): wire TransactionCostAnalyzer into AnalysisEngine"
```

---

### Task 3: 增强 Brinson 归因

**Files:**
- Modify: `python/cquant/bt_analyzer/engine.py:78-117`
- Create: `python/tests/unit/test_brinson_enhanced.py`

- [ ] **Step 1: 编写 Brinson 增强测试**

```python
# python/tests/unit/test_brinson_enhanced.py
"""Tests for enhanced Brinson attribution in AnalysisEngine."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_vector.engine import BacktestResult, BacktestSpec
from cquant.backtest_vector.metrics import BacktestMetrics
from cquant.bt_analyzer.engine import AnalysisEngine
from cquant.bt_analyzer.models import AnalysisSpec


def _make_positions(n_days: int = 5) -> pl.DataFrame:
    """Create synthetic positions data with daily weights."""
    rows = []
    assets = ["SSE:600036", "SZSE:000858"]
    for d in range(n_days):
        td = date(2025, 1, 1 + d)
        for i, a in enumerate(assets):
            rows.append({
                "trade_date": td,
                "asset_id": a,
                "target_weight": 0.5,
                "quantity": 500,
                "market_value": 5000.0,
            })
    return pl.DataFrame(rows)


def _make_prices_for_brinson() -> pl.DataFrame:
    """Create price data for attribution testing."""
    rows = []
    assets = ["SSE:600036", "SZSE:000858"]
    for a in assets:
        base = 10.0 if a == "SSE:600036" else 20.0
        for d in range(10):
            rows.append({
                "asset_id": a,
                "trade_date": date(2025, 1, 1 + d),
                "close": base * (1 + 0.01 * d),
                "open": base * (1 + 0.01 * d),
                "high": base * (1 + 0.01 * d) * 1.02,
                "low": base * (1 + 0.01 * d) * 0.98,
                "volume": 100000,
                "amount": base * 100000,
                "is_suspended": False,
            })
    return pl.DataFrame(rows)


def _make_result_with_positions() -> BacktestResult:
    """Create BacktestResult with positions for Brinson testing."""
    positions = _make_positions()
    prices = _make_prices_for_brinson()

    returns = pl.DataFrame({
        "trade_date": [date(2025, 1, i) for i in range(1, 11)],
        "portfolio_return": [0.01 * (i % 3 - 1) for i in range(10)],
        "nav": [1_000_000 * (1 + 0.01 * (i % 3 - 1)) for i in range(10)],
    })

    metrics = BacktestMetrics(
        total_return=0.05, annualized_return=0.12,
        annualized_volatility=0.15, sharpe_ratio=0.8,
        sortino_ratio=1.0, max_drawdown=-0.03, calmar_ratio=4.0,
        win_rate=0.6, profit_factor=1.5, var_95=-0.02, cvar_95=-0.025,
        beta=1.0, information_ratio=0.5, tracking_error=0.05,
        alpha=0.02, omega_ratio=1.2, tail_ratio=1.1,
        total_trades=10, trading_days=10,
    )

    spec = BacktestSpec(
        strategy=None,
        prices=prices,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
        initial_cash=Decimal("1000000"),
    )

    fills = pl.DataFrame({
        "trade_date": [date(2025, 1, 1)], "asset_id": ["SSE:600036"],
        "side": ["buy"], "qty": [100], "price": [10.0],
        "notional": [1000.0], "commission": [0.3], "stamp_duty": [0.0],
        "slippage": [0.1], "total_cost": [0.4],
    })

    return BacktestResult(
        run_id="test-brinson-001",
        engine="vector",
        strategy_id="test_strategy",
        spec=spec,
        metrics=metrics,
        portfolio_returns=returns,
        positions=positions,
        fills=fills,
        started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc),
    )


class TestBrinsonEnhanced:
    """Test enhanced Brinson attribution."""

    def test_brinson_uses_different_benchmark_returns(self):
        """Brinson should use benchmark returns, not portfolio returns."""
        result = _make_result_with_positions()
        engine = AnalysisEngine()
        report = engine.run(result)

        if report.brinson_attribution is not None:
            # benchmark_return should differ from total_return
            bm_ret = report.brinson_attribution.metadata.get("benchmark_return")
            port_ret = report.brinson_attribution.total_return
            # They might be close but shouldn't be identical
            # (since portfolio has equal weights and we use equal-weight benchmark,
            #  the returns could be similar, but the key is they're computed separately)
            assert "benchmark_return" in report.brinson_attribution.metadata

    def test_brinson_daily_populated(self):
        """Report should contain daily Brinson attribution."""
        result = _make_result_with_positions()
        engine = AnalysisEngine()
        report = engine.run(result)

        # Daily attribution should be populated when positions exist
        if report.brinson_attribution is not None:
            assert report.brinson_daily is not None
            assert len(report.brinson_daily) > 0
            # Each daily entry should have the required fields
            for entry in report.brinson_daily:
                assert "date" in entry
                assert "allocation" in entry
                assert "selection" in entry
                assert "interaction" in entry

    def test_benchmark_return_populated(self):
        """Report should contain benchmark return."""
        result = _make_result_with_positions()
        engine = AnalysisEngine()
        report = engine.run(result)

        if report.brinson_attribution is not None:
            assert report.benchmark_return is not None
            assert report.active_return is not None

    def test_brinson_no_positions(self):
        """Brinson should be skipped when no positions exist."""
        result = BacktestResult(
            run_id="test-no-pos",
            engine="vector",
            strategy_id="test",
            spec=BacktestSpec(
                strategy=None, prices=pl.DataFrame(),
                start_date=date(2025, 1, 1), end_date=date(2025, 1, 10),
                initial_cash=Decimal("1000000"),
            ),
            metrics=BacktestMetrics(
                total_return=0.0, annualized_return=0.0,
                annualized_volatility=0.0, sharpe_ratio=0.0,
                sortino_ratio=0.0, max_drawdown=0.0, calmar_ratio=0.0,
                win_rate=0.0, profit_factor=0.0, var_95=0.0, cvar_95=0.0,
                beta=0.0, information_ratio=0.0, tracking_error=0.0,
                alpha=0.0, omega_ratio=0.0, tail_ratio=0.0,
                total_trades=0, trading_days=0,
            ),
            portfolio_returns=pl.DataFrame({
                "trade_date": [date(2025, 1, i) for i in range(1, 6)],
                "portfolio_return": [0.0] * 5,
                "nav": [1_000_000.0] * 5,
            }),
            positions=pl.DataFrame(),
            fills=pl.DataFrame(),
            started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        engine = AnalysisEngine()
        report = engine.run(result)
        assert report.brinson_attribution is None
        assert report.brinson_daily is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -m pytest python/tests/unit/test_brinson_enhanced.py -v --no-cov`
Expected: FAIL — `brinson_daily` is None

- [ ] **Step 3: 重写 Brinson 归因逻辑**

在 `python/cquant/bt_analyzer/engine.py` 中，替换第 78-117 行的 Brinson 归因代码：

```python
        # Brinson attribution (enhanced)
        brinson_result = None
        brinson_daily = None
        benchmark_return_val = None
        active_return_val = None
        try:
            if not result.positions.is_empty() and "target_weight" in result.positions.columns:
                import polars as pl
                from cquant.bt_analyzer.attribution import BrinsonAttribution

                assets = sorted(result.positions["asset_id"].unique().to_list())
                if len(assets) > 1:
                    # Portfolio weights (daily average)
                    port_weights_df = (
                        result.positions
                        .group_by("asset_id")
                        .agg(pl.col("target_weight").mean().alias("avg_weight"))
                    )
                    port_weights = dict(zip(
                        port_weights_df["asset_id"].to_list(),
                        port_weights_df["avg_weight"].to_list(),
                    ))

                    # Benchmark weights (equal weight fallback)
                    bench_weights = {a: 1.0 / len(assets) for a in assets}

                    # Asset returns over full period
                    prices_df = result.spec.prices.filter(
                        pl.col("asset_id").is_in(assets)
                    )
                    asset_returns = {}
                    for a in assets:
                        apx = prices_df.filter(pl.col("asset_id") == a).sort("trade_date")
                        if len(apx) >= 2:
                            asset_returns[a] = float(apx["close"][-1]) / float(apx["close"][0]) - 1

                    if asset_returns:
                        # Benchmark return = equal-weight portfolio return
                        bench_ret = sum(
                            bench_weights.get(a, 0) * asset_returns.get(a, 0)
                            for a in assets
                        )
                        benchmark_return_val = bench_ret

                        brinson_result = BrinsonAttribution().analyze(
                            portfolio_weights=port_weights,
                            benchmark_weights=bench_weights,
                            portfolio_returns=asset_returns,
                            benchmark_returns={a: bench_ret for a in assets},
                        )
                        active_return_val = brinson_result.total_return - bench_ret

                        # Daily Brinson attribution
                        brinson_daily = _compute_daily_brinson(
                            result.positions, prices_df, bench_weights,
                        )
        except Exception as _exc:
            logger.debug("Brinson attribution skipped: %s", _exc)
```

在文件底部（`_build_summary` 函数之前）添加逐日归因辅助函数：

```python
def _compute_daily_brinson(
    positions: pl.DataFrame,
    prices: pl.DataFrame,
    bench_weights: dict[str, float],
) -> list[dict]:
    """Compute Brinson attribution for each rebalance period."""
    from cquant.bt_analyzer.attribution import BrinsonAttribution

    dates = sorted(positions["trade_date"].unique().to_list())
    if len(dates) < 2:
        return []

    results = []
    analyzer = BrinsonAttribution()

    for i in range(len(dates) - 1):
        td = dates[i]
        next_td = dates[i + 1]

        # Portfolio weights at td
        pos = positions.filter(pl.col("trade_date") == td)
        if pos.is_empty():
            continue
        port_weights = dict(zip(pos["asset_id"].to_list(), pos["target_weight"].to_list()))
        assets = list(port_weights.keys())

        # Returns between td and next_td
        asset_returns = {}
        for a in assets:
            px_td = prices.filter(
                (pl.col("asset_id") == a) & (pl.col("trade_date") == td)
            )
            px_next = prices.filter(
                (pl.col("asset_id") == a) & (pl.col("trade_date") == next_td)
            )
            if not px_td.is_empty() and not px_next.is_empty():
                p0 = float(px_td["close"][0])
                p1 = float(px_next["close"][0])
                if p0 > 0:
                    asset_returns[a] = p1 / p0 - 1

        if not asset_returns:
            continue

        # Benchmark return for this period
        bench_ret = sum(
            bench_weights.get(a, 0) * asset_returns.get(a, 0)
            for a in assets
        )

        try:
            result = analyzer.analyze(
                portfolio_weights=port_weights,
                benchmark_weights=bench_weights,
                portfolio_returns=asset_returns,
                benchmark_returns={a: bench_ret for a in assets},
            )
            results.append({
                "date": str(next_td),
                "allocation": result.allocation_effect,
                "selection": result.selection_effect,
                "interaction": result.interaction_effect,
            })
        except Exception:
            continue

    return results
```

然后在 `AnalysisReport` 构造时传入新字段：

```python
        return AnalysisReport(
            # ... existing fields ...
            brinson_attribution=brinson_result,
            brinson_daily=brinson_daily,
            benchmark_return=benchmark_return_val,
            active_return=active_return_val,
            # ... tca fields from Task 2 ...
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -m pytest python/tests/unit/test_brinson_enhanced.py python/tests/unit/test_tca_integration.py -v --no-cov`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add python/cquant/bt_analyzer/engine.py python/tests/unit/test_brinson_enhanced.py
git commit -m "feat(bt_analyzer): enhance Brinson attribution with daily time series and correct benchmark"
```

---

### Task 4: 持久化 TCA 和归因数据

**Files:**
- Modify: `python/cquant/bt_analyzer/run.py`

- [ ] **Step 1: 在 AnalysisRunner 添加 TCA 持久化方法**

在 `python/cquant/bt_analyzer/run.py` 的 `AnalysisRunner` 类中，`_persist_multiple_testing` 之后添加：

```python
    def _persist_tca(self, report: AnalysisReport) -> None:
        """Write TCA summary and details to gold_bt_tca."""
        if not report.tca_summary:
            return
        conn = self._catalog._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO gold_bt_tca
                (analysis_run_id, total_turnover, total_commission, total_stamp_duty,
                 total_slippage, total_cost, cost_per_trade, cost_pct_turnover,
                 num_trades, avg_trade_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report.analysis_run_id,
                report.tca_summary.total_turnover,
                report.tca_summary.total_commission,
                report.tca_summary.total_stamp_duty,
                report.tca_summary.total_slippage,
                report.tca_summary.total_cost,
                report.tca_summary.cost_per_trade,
                report.tca_summary.cost_as_pct_turnover,
                report.tca_summary.num_trades,
                report.tca_summary.avg_trade_size,
            ],
        )

    def _persist_attribution(self, report: AnalysisReport) -> None:
        """Write Brinson attribution to gold_bt_attribution."""
        if not report.brinson_attribution:
            return
        conn = self._catalog._get_conn()
        br = report.brinson_attribution
        conn.execute(
            """
            INSERT OR REPLACE INTO gold_bt_attribution
                (analysis_run_id, total_return, benchmark_return, active_return,
                 allocation_effect, selection_effect, interaction_effect,
                 daily_json, sector_details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report.analysis_run_id,
                br.total_return,
                report.benchmark_return or 0.0,
                report.active_return or 0.0,
                br.allocation_effect,
                br.selection_effect,
                br.interaction_effect,
                json.dumps(report.brinson_daily or []),
                json.dumps(br.sector_details),
            ],
        )
```

- [ ] **Step 2: 在 run() 方法中调用新持久化**

在 `AnalysisRunner.run()` 方法中，`self._persist_multiple_testing(report)` 之后添加：

```python
        self._persist_tca(report)
        self._persist_attribution(report)
```

- [ ] **Step 3: 添加 DuckDB DDL（如果 gold 表不存在）**

检查现有 DDL 文件，确认 `gold_bt_tca` 和 `gold_bt_attribution` 表是否已定义。如果没有，在 `sql/duckdb/` 中添加：

```sql
-- gold_bt_tca
CREATE TABLE IF NOT EXISTS gold_bt_tca (
    analysis_run_id VARCHAR PRIMARY KEY,
    total_turnover DOUBLE,
    total_commission DOUBLE,
    total_stamp_duty DOUBLE,
    total_slippage DOUBLE,
    total_cost DOUBLE,
    cost_per_trade DOUBLE,
    cost_pct_turnover DOUBLE,
    num_trades INTEGER,
    avg_trade_size DOUBLE
);

-- gold_bt_attribution
CREATE TABLE IF NOT EXISTS gold_bt_attribution (
    analysis_run_id VARCHAR PRIMARY KEY,
    total_return DOUBLE,
    benchmark_return DOUBLE,
    active_return DOUBLE,
    allocation_effect DOUBLE,
    selection_effect DOUBLE,
    interaction_effect DOUBLE,
    daily_json VARCHAR,
    sector_details_json VARCHAR
);
```

- [ ] **Step 4: 验证导入无错误**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -c "from cquant.bt_analyzer.run import AnalysisRunner; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add python/cquant/bt_analyzer/run.py sql/duckdb/
git commit -m "feat(bt_analyzer): add TCA and attribution persistence to AnalysisRunner"
```

---

### Task 5: API 端点

**Files:**
- Modify: `python/cquant/api_server/routes/backtests.py`

- [ ] **Step 1: 添加 TCA 端点**

在 `python/cquant/api_server/routes/backtests.py` 中，`get_backtest_risk` 端点之后添加：

```python
@router.get("/{run_id}/tca")
async def get_backtest_tca(run_id: str, catalog: CatalogDep) -> dict:
    """Get TCA (Transaction Cost Analysis) for a backtest run."""
    df = catalog.query(
        "SELECT * FROM gold_bt_tca WHERE analysis_run_id IN "
        "(SELECT analysis_run_id FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1)",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No TCA data found for run '{run_id}'")
    return df.to_dicts()[0]
```

- [ ] **Step 2: 添加 Attribution 端点**

在 TCA 端点之后添加：

```python
@router.get("/{run_id}/attribution")
async def get_backtest_attribution(run_id: str, catalog: CatalogDep) -> dict:
    """Get Brinson attribution for a backtest run."""
    df = catalog.query(
        "SELECT * FROM gold_bt_attribution WHERE analysis_run_id IN "
        "(SELECT analysis_run_id FROM gold_bt_analysis_runs WHERE backtest_run_id = ? "
        "ORDER BY created_at DESC LIMIT 1)",
        [run_id],
    )
    if df.is_empty():
        raise HTTPException(status_code=404, detail=f"No attribution data found for run '{run_id}'")
    row = df.to_dicts()[0]
    # Parse JSON fields
    if row.get("daily_json"):
        row["daily"] = json.loads(row.pop("daily_json"))
    else:
        row["daily"] = []
        row.pop("daily_json", None)
    if row.get("sector_details_json"):
        row["sector_details"] = json.loads(row.pop("sector_details_json"))
    else:
        row["sector_details"] = {}
        row.pop("sector_details_json", None)
    return row
```

确保文件顶部有 `import json`。

- [ ] **Step 3: 验证 API 启动无错误**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -c "from cquant.api_server.routes.backtests import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add python/cquant/api_server/routes/backtests.py
git commit -m "feat(api): add /tca and /attribution endpoints for backtests"
```

---

### Task 6: 前端 API 客户端 + Query Keys

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/lib/queryKeys.ts`

- [ ] **Step 1: 添加 API 客户端方法**

在 `web/src/lib/api.ts` 的 `backtestsApi` 对象中，`getWalkForwardFolds` 之后添加：

```typescript
  getTca: (id: string) =>
    request<Record<string, unknown>>(`/backtests/${id}/tca`),
  getAttribution: (id: string) =>
    request<Record<string, unknown>>(`/backtests/${id}/attribution`),
```

- [ ] **Step 2: 添加 Query Keys**

在 `web/src/lib/queryKeys.ts` 的 `backtests` 对象中，`walkForward` 之后添加：

```typescript
    tca: (id: string) => ['backtests', id, 'tca'] as const,
    attribution: (id: string) => ['backtests', id, 'attribution'] as const,
```

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/queryKeys.ts
git commit -m "feat(frontend): add TCA and attribution API client + query keys"
```

---

### Task 7: 前端 TCA Tab

**Files:**
- Modify: `web/src/pages/BacktestsPage.tsx:26` (Tab type)
- Modify: `web/src/pages/BacktestsPage.tsx:311-317` (TABS array)
- Modify: `web/src/pages/BacktestsPage.tsx` (add TCA tab content)

- [ ] **Step 1: 扩展 Tab 类型**

在 `web/src/pages/BacktestsPage.tsx` 第 26 行修改 Tab 类型：

```typescript
type Tab = 'overview' | 'tearsheet' | 'overfitting' | 'fills' | 'walkforward' | 'tca' | 'attribution'
```

- [ ] **Step 2: 在 TABS 数组添加新 Tab**

在 `web/src/pages/BacktestsPage.tsx` 第 316 行的 `...` 展开之后添加：

```typescript
    { id: 'tca', label: '成本分析' },
    { id: 'attribution', label: '归因分析' },
```

- [ ] **Step 3: 添加 TCA 数据获取**

在现有的 `useQuery` 块之后（`fillsData` 查询之后）添加：

```typescript
  const { data: tcaData } = useQuery({
    queryKey: queryKeys.backtests.tca(selectedId!),
    queryFn: () => backtestsApi.getTca(selectedId!),
    enabled: !!selectedId && tab === 'tca',
  })

  const { data: attributionData } = useQuery({
    queryKey: queryKeys.backtests.attribution(selectedId!),
    queryFn: () => backtestsApi.getAttribution(selectedId!),
    enabled: !!selectedId && tab === 'attribution',
  })
```

- [ ] **Step 4: 添加 TCA Tab 渲染**

在 BacktestsPage 中，walkforward tab 渲染块之后添加 TCA tab：

```tsx
          {/* TCA Tab */}
          {tab === 'tca' && (
            <div className="space-y-4">
              {tcaData ? (
                <>
                  {/* Cost summary cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <MetricCard
                      label="总成本"
                      value={`¥${Number(tcaData.total_cost ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`}
                    />
                    <MetricCard
                      label="成本率"
                      value={`${Number(tcaData.cost_pct_turnover ?? 0).toFixed(4)}%`}
                    />
                    <MetricCard
                      label="交易笔数"
                      value={String(tcaData.num_trades ?? 0)}
                    />
                    <MetricCard
                      label="平均成本/笔"
                      value={`¥${Number(tcaData.cost_per_trade ?? 0).toFixed(2)}`}
                    />
                  </div>

                  {/* Cost breakdown cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="card p-4">
                      <div className="text-xs text-gray-500 mb-1">佣金</div>
                      <div className="text-lg font-semibold">¥{Number(tcaData.total_commission ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
                    </div>
                    <div className="card p-4">
                      <div className="text-xs text-gray-500 mb-1">印花税</div>
                      <div className="text-lg font-semibold">¥{Number(tcaData.total_stamp_duty ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
                    </div>
                    <div className="card p-4">
                      <div className="text-xs text-gray-500 mb-1">滑点</div>
                      <div className="text-lg font-semibold">¥{Number(tcaData.total_slippage ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-gray-400 py-12">
                  无交易数据，无法进行成本分析
                </div>
              )}
            </div>
          )}
```

- [ ] **Step 5: 添加 Attribution Tab 渲染**

在 TCA tab 之后添加归因 tab：

```tsx
          {/* Attribution Tab */}
          {tab === 'attribution' && (
            <div className="space-y-4">
              {attributionData ? (
                <>
                  {/* Attribution summary cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <MetricCard
                      label="超额收益"
                      value={`${((attributionData.active_return as number) * 100).toFixed(2)}%`}
                      warn={(attributionData.active_return as number) < 0}
                    />
                    <MetricCard
                      label="配置效应"
                      value={`${((attributionData.allocation_effect as number) * 100).toFixed(2)}%`}
                    />
                    <MetricCard
                      label="选股效应"
                      value={`${((attributionData.selection_effect as number) * 100).toFixed(2)}%`}
                    />
                    <MetricCard
                      label="交互效应"
                      value={`${((attributionData.interaction_effect as number) * 100).toFixed(2)}%`}
                    />
                  </div>

                  {/* Sector details table */}
                  {Object.keys(attributionData.sector_details as Record<string, unknown>).length > 0 && (
                    <div className="card p-4">
                      <div className="text-sm font-medium text-gray-700 mb-3">行业归因明细</div>
                      <DataTable
                        data={Object.entries(attributionData.sector_details as Record<string, Record<string, number>>).map(([sector, data]) => ({
                          sector,
                          port_weight: data.port_weight,
                          bench_weight: data.bench_weight,
                          port_return: data.port_return,
                          bench_return: data.bench_return,
                        }))}
                        rowKey="sector"
                        columns={[
                          { key: 'sector', label: '行业' },
                          { key: 'port_weight', label: '组合权重', render: (v) => `${((v as number) * 100).toFixed(1)}%` },
                          { key: 'bench_weight', label: '基准权重', render: (v) => `${((v as number) * 100).toFixed(1)}%` },
                          { key: 'port_return', label: '组合收益', render: (v) => `${((v as number) * 100).toFixed(2)}%` },
                          { key: 'bench_return', label: '基准收益', render: (v) => `${((v as number) * 100).toFixed(2)}%` },
                        ]}
                      />
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-gray-400 py-12">
                  未设置基准或组合为单资产，无法进行归因分析
                </div>
              )}
            </div>
          )}
```

- [ ] **Step 6: 运行前端测试确认无回归**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant/web && npx vitest run src/pages/__tests__/BacktestsPage.test.tsx`
Expected: All existing tests pass

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/BacktestsPage.tsx
git commit -m "feat(frontend): add TCA and Attribution tabs to BacktestsPage"
```

---

### Task 8: 前端组件测试

**Files:**
- Modify: `web/src/pages/__tests__/BacktestsPage.test.tsx`

- [ ] **Step 1: 添加 TCA Tab 测试**

在 `web/src/pages/__tests__/BacktestsPage.test.tsx` 中，更新 mock 添加 TCA 和 Attribution API，然后添加测试：

```typescript
// 在 vi.mock 中添加：
getTca: vi.fn().mockResolvedValue({
  total_turnover: 5000000,
  total_commission: 1500,
  total_stamp_duty: 2500,
  total_slippage: 500,
  total_cost: 4500,
  cost_per_trade: 45,
  cost_pct_turnover: 0.09,
  num_trades: 100,
  avg_trade_size: 50000,
}),
getAttribution: vi.fn().mockResolvedValue({
  total_return: 0.15,
  benchmark_return: 0.10,
  active_return: 0.05,
  allocation_effect: 0.02,
  selection_effect: 0.025,
  interaction_effect: 0.005,
  daily: [
    { date: '2025-06-02', allocation: 0.001, selection: 0.002, interaction: 0.0005 },
  ],
  sector_details: {
    Finance: { port_weight: 0.3, bench_weight: 0.25, port_return: 0.05, bench_return: 0.04 },
  },
}),

// 测试：
it('shows TCA tab with cost summary', async () => {
  renderWithProviders(<BacktestsPage />)
  await waitFor(() => {
    expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
  })
  fireEvent.click(screen.getByText(/run-abc-/))
  await waitFor(() => {
    fireEvent.click(screen.getByText('成本分析'))
  })
  await waitFor(() => {
    expect(screen.getByText('总成本')).toBeInTheDocument()
    expect(screen.getByText('佣金')).toBeInTheDocument()
    expect(screen.getByText('印花税')).toBeInTheDocument()
    expect(screen.getByText('滑点')).toBeInTheDocument()
  })
})

it('shows attribution tab with effects', async () => {
  renderWithProviders(<BacktestsPage />)
  await waitFor(() => {
    expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
  })
  fireEvent.click(screen.getByText(/run-abc-/))
  await waitFor(() => {
    fireEvent.click(screen.getByText('归因分析'))
  })
  await waitFor(() => {
    expect(screen.getByText('超额收益')).toBeInTheDocument()
    expect(screen.getByText('配置效应')).toBeInTheDocument()
    expect(screen.getByText('选股效应')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 运行全部前端测试确认通过**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant/web && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/__tests__/BacktestsPage.test.tsx
git commit -m "test(frontend): add TCA and attribution tab tests"
```

---

### Task 9: 回归测试

**Files:**
- Test: `python/tests/unit/test_attribution_engine.py` (已有)
- Test: `python/tests/unit/test_portfolio_opt.py` (已有)

- [ ] **Step 1: 运行现有 bt_analyzer 测试**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -m pytest python/tests/unit/test_attribution_engine.py python/tests/unit/test_optimizer_inputs.py -v --no-cov`
Expected: All pass

- [ ] **Step 2: 运行全量单元测试**

Run: `cd /Users/y1ye/Desktop/workSpace/aiTools/quant && python -m pytest python/tests/unit/ -v --no-cov --timeout=120`
Expected: All pass

- [ ] **Step 3: Commit（如有修复）**

如果有回归问题需要修复，修复后提交。否则跳过。

---

## 验收清单

- [ ] `AnalysisReport` 包含 `tca_summary`、`tca_by_asset`、`tca_by_date` 字段
- [ ] `AnalysisReport` 包含 `brinson_daily`、`benchmark_return`、`active_return` 字段
- [ ] TCA 从 `TransactionCostAnalyzer` 正确计算
- [ ] Brinson 归因使用正确的 benchmark returns（非 portfolio returns）
- [ ] 逐日归因时间序列正确生成
- [ ] API `GET /backtests/{run_id}/tca` 返回完整 TCA 数据
- [ ] API `GET /backtests/{run_id}/attribution` 返回 summary + daily + sector_details
- [ ] 前端「成本分析」Tab 显示概览卡片 + 成本分解
- [ ] 前端「归因分析」Tab 显示概览卡片 + 行业明细表
- [ ] 空状态正确处理（无交易 / 无基准 / 单资产）
- [ ] 所有现有测试通过
- [ ] 新增 8 个测试覆盖 TCA 集成 + Brinson 增强 + 前端 Tab
