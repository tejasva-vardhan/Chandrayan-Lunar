"""SPICE and geometry. Owned by Shashwat.

Pipeline import surface: characterize_pair(source, reference) -> RegistrationPair.

Geometry owns the calculations stored on PairCharacterization. The models only
store results. Do not encode routing thresholds here.

This stage is observational. It does not implement SPICE, DEM, or route().
"""

from src.geometry.characterize import (
    build_characterization,
    characterize_pair,
    characterize_pair_with_provider,
)

__all__ = [
    "build_characterization",
    "characterize_pair",
    "characterize_pair_with_provider",
]
