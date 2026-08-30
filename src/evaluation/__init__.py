"""Independent evaluation. Owned by Shaiz.

Pipeline import surface: evaluate(result, pair) -> RegistrationResult.

Use result.correspondences as the canonical match collection.
Do not invent metrics. Leave uncomputed RegistrationMetrics fields as None.
"""

from __future__ import annotations

from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult


def evaluate(result: RegistrationResult, pair: RegistrationPair) -> RegistrationResult:
    """Compute independent validation metrics when they are actually measured."""
    raise NotImplementedError(f"evaluate is not implemented. pair_id={pair.pair_id}")


__all__ = ["evaluate"]
