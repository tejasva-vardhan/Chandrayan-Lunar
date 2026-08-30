"""Representation engine. Owned by Chuba.

Pipeline import surface: generate_representation(pair) -> Any.

Return type is intentionally unconstrained (interface freeze v1 §8).
Representation choice is experimental (v3 §11). Do not assume a final
representation in this package.
"""

from __future__ import annotations

from typing import Any

from src.models.registration_pair import RegistrationPair


def generate_representation(pair: RegistrationPair) -> Any:
    """Build a representation for matching. Schema is not frozen."""
    raise NotImplementedError(
        f"generate_representation is not implemented. pair_id={pair.pair_id}"
    )


__all__ = ["generate_representation"]
