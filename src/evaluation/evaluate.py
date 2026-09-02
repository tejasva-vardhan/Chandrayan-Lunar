"""Independent evaluation orchestration.

Frozen pipeline surface: evaluate(result, pair) -> RegistrationResult.

Fills RegistrationMetrics from actual CorrespondenceSet, ControlPoint, and
pair dimension data. Does not re-run matching, verification, selection,
refinement, or registration. Does not warp images or compute intensity
similarity. Does not set confidence_class.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.evaluation.checkpoints import EvaluationCheckpoint, independent_checkpoint_residuals
from src.evaluation.metrics import compute_registration_metrics
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult


def evaluate(result: RegistrationResult, pair: RegistrationPair) -> RegistrationResult:
    """Return a copy of result with measured RegistrationMetrics attached.

    Existing transformation, correspondences, control points, quality_flags,
    registered_source_uri, confidence_class, and provenance are preserved.
    The input result is not mutated. Uncomputable metric fields stay None.
    """

    return evaluate_with_checkpoints(result, pair, checkpoints=None)


def evaluate_with_checkpoints(
    result: RegistrationResult,
    pair: RegistrationPair,
    checkpoints: Iterable[EvaluationCheckpoint] | None,
) -> RegistrationResult:
    """Evaluate with explicitly supplied held-out checkpoints when available.

    This does not alter the frozen ``evaluate(result, pair)`` pipeline
    callable.  Without checkpoint data, RMSE is deliberately unavailable;
    verification residuals are fit diagnostics, not independent evaluation.
    """

    residuals = (
        independent_checkpoint_residuals(result, checkpoints)
        if checkpoints is not None
        else None
    )
    flags = list(result.quality_flags)
    if residuals is None and "evaluation_unavailable" not in flags:
        flags.append("evaluation_unavailable")
    metrics = compute_registration_metrics(result, pair, residuals)
    return result.model_copy(update={"metrics": metrics, "quality_flags": flags})
