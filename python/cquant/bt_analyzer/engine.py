"""cquant.bt_analyzer.engine — Orchestration entry point for backtest robustness analysis."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import polars as pl

from cquant.backtest_vector.engine import BacktestResult

logger = logging.getLogger(__name__)
from cquant.bt_analyzer.cpcv import CPCVAnalyzer
from cquant.bt_analyzer.models import AnalysisReport, AnalysisSpec, OverfitScore, ValidationWindow
from cquant.bt_analyzer.multiple_testing import MultipleTestingCorrector
from cquant.bt_analyzer.sensitivity import SensitivityAnalyzer
from cquant.bt_analyzer.sharpe import SharpeMetrics
from cquant.bt_analyzer.stability import StabilityAnalyzer
from cquant.bt_analyzer.walk_forward import WalkForwardAnalyzer
from cquant.bt_analyzer.walk_forward_refit import WalkForwardRefit


class AnalysisEngine:
    """Run the full suite of post-backtest robustness checks.

    Usage::

        engine = AnalysisEngine()
        report = engine.run(backtest_result)
        # or with custom config:
        report = engine.run(backtest_result, spec=AnalysisSpec(n_trials=10))
        print(report.summary)
    """

    def __init__(self, spec: AnalysisSpec | None = None) -> None:
        self.spec = spec or AnalysisSpec()

    def run(
        self,
        result: BacktestResult,
        spec: AnalysisSpec | None = None,
        use_refit: bool = False,
        refit_callback=None,
    ) -> AnalysisReport:
        """Execute all analyzers and return a consolidated AnalysisReport.

        Parameters
        ----------
        result:
            Completed backtest result to analyze.
        spec:
            Analysis configuration.  Falls back to ``self.spec``.
        use_refit:
            If True, use WalkForwardRefit (with strategy re-fitting per fold)
            instead of WalkForwardAnalyzer (return slicing only).
            Requires a strategy that supports ``fit()`` or a refit_callback.
        refit_callback:
            Optional callback ``(base_spec, train_start, train_end) -> spec``
            for WalkForwardRefit.  Only used when ``use_refit=True``.
        """
        active = spec or self.spec
        if result.portfolio_returns.is_empty():
            raise ValueError("BacktestResult.portfolio_returns is empty — nothing to analyze")

        returns = result.portfolio_returns.sort("trade_date").get_column("portfolio_return")

        if use_refit:
            wf_windows = self._run_walk_forward_refit(result, active, refit_callback)
        else:
            wf_windows = WalkForwardAnalyzer(active).analyze(result)
        cpcv_windows = CPCVAnalyzer(active).analyze(result)

        psr = SharpeMetrics.probabilistic_sharpe_ratio(
            returns,
            benchmark_sharpe=active.benchmark_sharpe,
            trading_days_per_year=active.trading_days_per_year,
        )
        dsr = SharpeMetrics.deflated_sharpe_ratio(
            returns,
            benchmark_sharpe=active.benchmark_sharpe,
            n_trials=active.n_trials,
            trading_days_per_year=active.trading_days_per_year,
        )

        mt_result = MultipleTestingCorrector.correct(
            p_values=[max(0.0, min(1.0, 1.0 - psr))],
            alpha=active.alpha,
            n_trials=active.n_trials,
        )

        sens = SensitivityAnalyzer(active).analyze(result)
        stab = StabilityAnalyzer(active).analyze(result)
        all_stability = {**stab, **{f"sensitivity_{k}": v for k, v in sens.items()}}

        overfit = self._compute_overfit(
            in_sample_sharpe=result.metrics.sharpe_ratio,
            wf_windows=wf_windows,
            cpcv_windows=cpcv_windows,
            psr=psr,
            stability=all_stability,
        )

        # TCA analysis
        tca_summary = None
        tca_by_asset = None
        tca_by_date = None
        try:
            from cquant.backtest_vector.tca import TransactionCostAnalyzer
            tca_analyzer = TransactionCostAnalyzer()
            tca_summary = tca_analyzer.analyze(result.fills)
            tca_by_asset = tca_analyzer.analyze_by_asset(result.fills)
            tca_by_date = tca_analyzer.analyze_by_date(result.fills)
        except Exception as exc:
            logger.debug("TCA analysis skipped: %s", exc)

        # Brinson attribution (enhanced)
        brinson_result = None
        brinson_daily = None
        benchmark_return_val = None
        active_return_val = None
        try:
            if not result.positions.is_empty() and "target_weight" in result.positions.columns:
                from cquant.bt_analyzer.attribution import BrinsonAttribution

                assets = sorted(result.positions["asset_id"].unique().to_list())
                if len(assets) > 1:
                    port_weights_df = (
                        result.positions
                        .group_by("asset_id")
                        .agg(pl.col("target_weight").mean().alias("avg_weight"))
                    )
                    port_weights = dict(zip(
                        port_weights_df["asset_id"].to_list(),
                        port_weights_df["avg_weight"].to_list(),
                    ))

                    bench_weights = {a: 1.0 / len(assets) for a in assets}

                    # No date filter — _compute_period_brinson needs prices at all rebalance dates
                    prices_df = result.spec.prices.filter(
                        pl.col("asset_id").is_in(assets)
                    )
                    asset_returns = {}
                    for a in assets:
                        apx = prices_df.filter(pl.col("asset_id") == a).sort("trade_date")
                        if len(apx) >= 2:
                            asset_returns[a] = float(apx["close"][-1]) / float(apx["close"][0]) - 1

                    if asset_returns:
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

                        brinson_daily = _compute_period_brinson(
                            result.positions, prices_df, bench_weights,
                        )
        except Exception as _exc:
            logger.debug("Brinson attribution skipped: %s", _exc)

        return AnalysisReport(
            analysis_run_id=str(uuid.uuid4()),
            backtest_run_id=result.run_id,
            spec=active,
            overall_overfit_score=overfit,
            dsr=dsr,
            psr=psr,
            walk_forward_windows=wf_windows,
            cpcv_windows=cpcv_windows or None,
            multiple_testing_result=mt_result,
            stability_metrics=all_stability,
            summary=_build_summary(result.run_id, overfit, psr, dsr, wf_windows, cpcv_windows),
            brinson_attribution=brinson_result,
            brinson_daily=brinson_daily,
            benchmark_return=benchmark_return_val,
            active_return=active_return_val,
            tca_summary=tca_summary,
            tca_by_asset=tca_by_asset,
            tca_by_date=tca_by_date,
            created_at=datetime.now(tz=timezone.utc),
        )

    # Alias for convenience
    analyze = run

    @staticmethod
    def _run_walk_forward_refit(
        result: BacktestResult,
        spec: AnalysisSpec,
        refit_callback=None,
    ) -> list[ValidationWindow]:
        """Run WalkForwardRefit and convert folds to ValidationWindow format.

        This bridges the WalkForwardRefit output (FoldResult with train/test
        metrics) into the ValidationWindow format expected by overfit scoring.
        """
        refit = WalkForwardRefit(
            base_spec=result.spec,
            n_folds=spec.n_oos_windows,
            train_ratio=0.7,
            gap_days=spec.gap_days,
            refit_callback=refit_callback,
        )
        wf_result = refit.run()

        windows: list[ValidationWindow] = []
        for fold in wf_result.folds:
            if not fold.success:
                continue
            windows.append(ValidationWindow(
                window_id=fold.fold_id,
                train_start=fold.train_start,
                train_end=fold.train_end,
                test_start=fold.test_start,
                test_end=fold.test_end,
                metrics=fold.test_metrics,
            ))
        return windows

    @staticmethod
    def _compute_overfit(
        in_sample_sharpe: float,
        wf_windows: list[ValidationWindow],
        cpcv_windows: list[ValidationWindow],
        psr: float,
        stability: dict[str, float],
    ) -> OverfitScore:
        mean_oos = _mean_metric(wf_windows, "sharpe")
        oos_ratio = (
            min(max(mean_oos / max(in_sample_sharpe, 1e-12), 0.0), 1.0)
            if in_sample_sharpe > 0 else 0.0
        )
        instability = max(
            stability.get("instability", 0.0),
            stability.get("sensitivity_instability", 0.0),
        )
        if cpcv_windows:
            cpcv_instability = 1.0 - _cpcv_consistency(cpcv_windows)
            instability = min(max((instability + cpcv_instability) / 2.0, 0.0), 1.0)

        score = min(max(
            (1.0 - oos_ratio) * 0.4 + (1.0 - psr) * 0.3 + instability * 0.3,
            0.0,
        ), 1.0)

        factors: list[str] = []
        if oos_ratio < 0.75:
            factors.append("Out-of-sample Sharpe decayed vs full-sample in-sample Sharpe.")
        if psr < 0.8:
            factors.append("Probabilistic Sharpe support is weak after higher-moment adjustment.")
        if instability > 0.4:
            factors.append("Sharpe varies materially across time slices or CPCV folds.")

        confidence = (
            "high" if len(wf_windows) >= 3 and cpcv_windows
            else "medium" if wf_windows
            else "low"
        )
        return OverfitScore(score=score, confidence=confidence, contributing_factors=factors)


def _compute_period_brinson(
    positions: pl.DataFrame,
    prices: pl.DataFrame,
    bench_weights: dict[str, float],
) -> list[dict]:
    """Compute Brinson attribution for each rebalance period (not trading days)."""
    from cquant.bt_analyzer.attribution import BrinsonAttribution

    dates = sorted(positions["trade_date"].unique().to_list())
    if len(dates) < 2:
        return []

    results = []
    analyzer = BrinsonAttribution()

    for i in range(len(dates) - 1):
        td = dates[i]
        next_td = dates[i + 1]

        pos = positions.filter(pl.col("trade_date") == td)
        if pos.is_empty():
            continue
        port_weights = dict(zip(pos["asset_id"].to_list(), pos["target_weight"].to_list()))
        assets = list(port_weights.keys())

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
        except Exception as exc:
            logger.debug("Period Brinson attribution skipped for %s: %s", next_td, exc)
            continue

    return results


def _mean_metric(windows: list[ValidationWindow], key: str) -> float:
    vals = [w.metrics.get(key, 0.0) for w in windows]
    return sum(vals) / len(vals) if vals else 0.0


def _cpcv_consistency(windows: list[ValidationWindow]) -> float:
    sharpes = [w.metrics.get("sharpe", 0.0) for w in windows]
    if not sharpes:
        return 0.0
    pos = sum(1 for s in sharpes if s > 0) / len(sharpes)
    m = sum(sharpes) / len(sharpes)
    v = sum((s - m) ** 2 for s in sharpes) / len(sharpes)
    disp = min((v ** 0.5) / max(abs(m), 1.0), 1.0)
    return min(max(0.5 * pos + 0.5 * (1.0 - disp), 0.0), 1.0)


def _build_summary(
    run_id: str,
    overfit: OverfitScore,
    psr: float,
    dsr: float,
    wf_windows: list[ValidationWindow],
    cpcv_windows: list[ValidationWindow],
) -> str:
    mean_oos = _mean_metric(wf_windows, "sharpe")
    cpcv_c = _cpcv_consistency(cpcv_windows) if cpcv_windows else 0.0
    return (
        f"Backtest {run_id}: overfit_score={overfit.score:.2f} "
        f"({overfit.confidence} confidence); "
        f"PSR={psr:.2f}, DSR={dsr:.2f}, "
        f"mean_OOS_Sharpe={mean_oos:.2f}, "
        f"CPCV_consistency={cpcv_c:.2f}."
    )
