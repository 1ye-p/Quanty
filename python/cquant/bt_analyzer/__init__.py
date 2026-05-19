"""cquant.bt_analyzer — Post-backtest robustness and overfitting analysis.

Reference methodology: Lopez de Prado, "Advances in Financial Machine Learning" (2018).

Usage::

    from cquant.bt_analyzer import AnalysisEngine, AnalysisSpec

    engine = AnalysisEngine()
    report = engine.run(backtest_result)
    print(report.summary)
    print(f"Overfit score: {report.overall_overfit_score.score:.2f}")
    print(f"PSR={report.psr:.2f}  DSR={report.dsr:.2f}")
"""

from cquant.bt_analyzer.cpcv import CPCVAnalyzer
from cquant.bt_analyzer.engine import AnalysisEngine
from cquant.bt_analyzer.models import (
    AnalysisReport,
    AnalysisSpec,
    OverfitScore,
    ValidationWindow,
)
from cquant.bt_analyzer.multiple_testing import MultipleTestingCorrector
from cquant.bt_analyzer.sensitivity import SensitivityAnalyzer
from cquant.bt_analyzer.sharpe import SharpeMetrics
from cquant.bt_analyzer.stability import StabilityAnalyzer
from cquant.bt_analyzer.walk_forward import WalkForwardAnalyzer

__all__ = [
    "AnalysisEngine",
    "AnalysisReport",
    "AnalysisSpec",
    "CPCVAnalyzer",
    "MultipleTestingCorrector",
    "OverfitScore",
    "SensitivityAnalyzer",
    "SharpeMetrics",
    "StabilityAnalyzer",
    "ValidationWindow",
    "WalkForwardAnalyzer",
]
