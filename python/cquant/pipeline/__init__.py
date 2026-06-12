"""cquant.pipeline — Automated ML pipeline: factors, training, backtest, analysis, promotion."""

from __future__ import annotations

from cquant.pipeline.config import PipelineConfig
from cquant.pipeline.orchestrator import PipelineOrchestrator

__all__ = ["PipelineConfig", "PipelineOrchestrator"]
