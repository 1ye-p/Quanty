"""cquant.factorlab — Factor DSL, DAG execution, and feature pipeline."""

from cquant.factorlab.factor import Factor, FactorContext, FactorRegistry
from cquant.factorlab.materialize import FactorMaterializer, FactorMaterializationSpec
from cquant.factorlab.evaluation import FactorEvaluator
from cquant.factorlab.pipeline import FeaturePipeline, PipelineSpec
from cquant.factorlab.universe import UniverseBuilder
from cquant.factorlab.factor_descriptions import FactorDescriptionManager

__all__ = [
    "Factor",
    "FactorContext",
    "FactorRegistry",
    "FactorEvaluator",
    "FactorMaterializer",
    "FactorMaterializationSpec",
    "FeaturePipeline",
    "PipelineSpec",
    "UniverseBuilder",
    "FactorDescriptionManager",
]
