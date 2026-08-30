"""Independent evaluation orchestration.

Frozen pipeline surface: evaluate(result, pair) -> RegistrationResult.

Fills RegistrationMetrics from actual CorrespondenceSet, ControlPoint, and
pair dimension data. Does not re-run matching, verification, selection,
refinement, or registration. Does not warp images or compute intensity
similarity. Does not set confidence_class.
"""

from __future__ import annotations

from src.evaluation.metrics import compute_registration_metrics
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult


def evaluate(result: RegistrationResult, pair: RegistrationPair) -> RegistrationResult:
    """Return a copy of result with measured RegistrationMetrics attached.

    Existing transformation, correspondences, control points, quality_flags,
    registered_source_uri, confidence_class, and provenance are preserved.
    The input result is not mutated. Uncomputable metric fields stay None.
    """

    metrics = compute_registration_metrics(result, pair)
    return result.model_copy(update={"metrics": metrics})
