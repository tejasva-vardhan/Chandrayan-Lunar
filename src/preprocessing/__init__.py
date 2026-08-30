"""Product preprocessing. Owned by Haruto.

Pipeline import surface: preprocess(pair) -> RegistrationPair.

Owns pair-aware normalization, orientation when required, and scale-aware
resampling when required. Do not invent thresholds in this package.
Preserve characterization produced by geometry unless a later architecture
decision says otherwise.
"""

from __future__ import annotations

from src.models.registration_pair import RegistrationPair


def preprocess(pair: RegistrationPair) -> RegistrationPair:
    """Return an updated pair after pair-aware preprocessing."""
    raise NotImplementedError(f"preprocess is not implemented. pair_id={pair.pair_id}")


__all__ = ["preprocess"]
