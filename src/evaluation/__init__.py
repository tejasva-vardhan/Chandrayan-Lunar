"""Independent evaluation. Owned per TEAM_MODULE_HANDOFF_V1 (Shaiz package).

Pipeline import surface: evaluate(result, pair) -> RegistrationResult.

Use result.correspondences as the canonical match collection.
Fill RegistrationMetrics only with values that can be computed from available
data. Leave uncomputed fields as None. Do not invent RMSE, ratios, coverage,
or counts.

Metric formulas in this package are ENGINEERING IMPLEMENTATION DEFINITIONS.
They are not official SIH evaluator definitions and are not lunar accuracy
claims (D-011).
"""

from src.evaluation.evaluate import evaluate

__all__ = ["evaluate"]
