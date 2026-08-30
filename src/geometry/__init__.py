"""SPICE and geometry. Owned by Shashwat.

Pipeline import surface: characterize_pair(source, reference) -> RegistrationPair.

Geometry owns the calculations stored on PairCharacterization. The models only
store results. Do not encode routing thresholds here.
"""

from __future__ import annotations

from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair


def characterize_pair(source: LunarProduct, reference: LunarProduct) -> RegistrationPair:
    """Build a RegistrationPair and fill characterization when values are computed."""
    raise NotImplementedError(
        "characterize_pair is not implemented. "
        f"source={source.product_id} reference={reference.product_id}"
    )


__all__ = ["characterize_pair"]
