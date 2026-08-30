"""Deterministic candidate ordering. Not a new quality metric.

Uses only Correspondence.residual and Correspondence.confidence as already
stored. Missing values are not treated as zero. No composite score is computed.
"""

from __future__ import annotations

import math

from src.control_points.candidates import EligibleCandidate


def quality_sort_key(candidate: EligibleCandidate) -> tuple[int, float, int, float, int]:
    """Lexicographic key. Smaller is better.

    1. Finite residual present (0) before missing residual (1).
       Residual is copied from verification when present; missing is not
       invented as 0 or as +inf inside a numeric score.
    2. Smaller residual when both have a finite residual.
    3. Finite confidence present (0) before missing confidence (1).
       Missing confidence is not treated as 0.0.
    4. Larger confidence when both have a finite confidence.
    5. Original index in CorrespondenceSet.matches (deterministic tie-break).
    """

    item = candidate.correspondence
    residual = item.residual
    has_residual = residual is not None and math.isfinite(residual)
    confidence = item.confidence
    has_confidence = confidence is not None and math.isfinite(confidence)
    return (
        0 if has_residual else 1,
        residual if has_residual else 0.0,
        0 if has_confidence else 1,
        -confidence if has_confidence else 0.0,
        candidate.index,
    )
