"""cquant.bt_analyzer.engine — Orchestration entry point for backtest robustness analysis."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from cquant.backtest_vector.engine import BacktestResult

logger = logging.getLogger(__name__)
from cquant.bt_analyzer.cpcv import CPCVAnalyzer
from cquant.bt_analyzer.models import AnalysisReport, AnalysisSpec, OverfitScore, ValidationWindow
from cquant.bt_analyzer.multiple_testing import MultipleTestingCorrector
from cquant.bt_analyzer.sensitivity import SensitivityAnalyzer
from cquant.bt_analyzer.sharpe import SharpeMetrics
from cquant.bt_analyzer.stability import StabilityAnalyzer
from cquant.bt_analyzer.walk_forward import WalkForwardAnalyzer


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

    def run(self, result: BacktestResult, spec: AnalysisSpec | None = None) -> AnalysisReport:
        """Execute all analyzers and return a consolidated AnalysisReport."""
        active = spec or self.spec
        if result.portfolio_returns.is_empty():
            raise ValueError("BacktestResult.portfolio_returns is empty — nothing to analyze")

        returns = result.portfolio_returns.sort("trade_date").get_column("portfolio_return")

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

        # Optional Brinson attribution
        brinson_result = None
        try:
            if not result.positions.is_empty() and "target_weight" in result.positions.columns:
                import polars as pl
                from cquant.bt_analyzer.attribution import BrinsonAttribution

                port_weights_df = (
                    result.positions
                    .group_by("asset_id")
                    .agg(pl.col("target_weight").mean().alias("avg_weight"))
                )
                port_weights = dict(zip(
                    port_weights_df["asset_id"].to_list(),
                    port_weights_df["avg_weight"].to_list(),
                ))

                if port_weights:
                    assets = list(port_weights.keys())
                    bench_weights = {a: 1.0 / len(assets) for a in assets}

                    prices_df = result.spec.prices.filter(
                        (pl.col("asset_id").is_in(assets))
                        & (pl.col("trade_date") >= result.spec.start_date)
                        & (pl.col("trade_date") <= result.spec.end_date)
                    )
                    asset_returns = {}
                    for a in assets:
                        apx = prices_df.filter(pl.col("asset_id") == a).sort("trade_date")
                        if len(apx) >= 2:
                            asset_returns[a] = float(apx["close"][-1]) / float(apx["close"][0]) - 1

                    if asset_returns:
                        brinson_result = BrinsonAttribution().analyze(
                            portfolio_weights=port_weights,
                            benchmark_weights=bench_weights,
                            portfolio_returns=asset_returns,
                            benchmark_returns=asset_returns,
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
            created_at=datetime.now(tz=timezone.utc),
        )

    # Alias for convenience
    analyze = run

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
