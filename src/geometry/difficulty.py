"""Descriptive difficulty factors. Not a routing policy.

v3 §8 lists easy/normal/difficult as a later use of pair characteristics
and states that routing thresholds must be learned or validated, not
invented. This module therefore:

- never writes PairCharacterization.difficulty
- never applies numeric cutoffs such as scale > 2 → hard
- records availability / instrument-inequality flags only

Flags are ENGINEERING labels for later experiment stratification. They
are not scientifically validated difficulty grades and are not consumed
by route().
"""

from __future__ import annotations

FLAG_SCALE_DIFFERENCE_AVAILABLE = "scale_difference_available"
FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE = "illumination_difference_available"
FLAG_VIEWING_GEOMETRY_DIFFERENCE_AVAILABLE = "viewing_geometry_difference_available"
FLAG_MULTIMODAL_PAIR = "multimodal_pair"
FLAG_ACQUISITION_TIME_DIFFERENCE_AVAILABLE = "acquisition_time_difference_available"

# Deterministic emission order. Do not sort alphabetically in a way that
# would hide this documented sequence.
_FLAG_ORDER: tuple[str, ...] = (
    FLAG_SCALE_DIFFERENCE_AVAILABLE,
    FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE,
    FLAG_VIEWING_GEOMETRY_DIFFERENCE_AVAILABLE,
    FLAG_MULTIMODAL_PAIR,
    FLAG_ACQUISITION_TIME_DIFFERENCE_AVAILABLE,
)


def categorical_difficulty() -> None:
    """Always None. No easy/normal/difficult assignment is defined."""

    return None


def quality_flags(
    *,
    gsd_ratio: float | None,
    sun_angle_difference_degrees: float | None,
    viewing_geometry_difference: float | None,
    source_instrument: str | None,
    reference_instrument: str | None,
    acquisition_time_difference_seconds: float | None,
) -> list[str]:
    """Availability and instrument-inequality flags.

    multimodal_pair means the two explicit instrument strings differ. It
    is not a scientific optical-vs-spectral classification.

    strong_scale_difference and low_valid_pixel_quality are not emitted:
    they require numeric thresholds that v3 does not define.
    """

    present: set[str] = set()
    if gsd_ratio is not None:
        present.add(FLAG_SCALE_DIFFERENCE_AVAILABLE)
    if sun_angle_difference_degrees is not None:
        present.add(FLAG_ILLUMINATION_DIFFERENCE_AVAILABLE)
    if viewing_geometry_difference is not None:
        present.add(FLAG_VIEWING_GEOMETRY_DIFFERENCE_AVAILABLE)
    if (
        source_instrument is not None
        and reference_instrument is not None
        and source_instrument != reference_instrument
    ):
        present.add(FLAG_MULTIMODAL_PAIR)
    if acquisition_time_difference_seconds is not None:
        present.add(FLAG_ACQUISITION_TIME_DIFFERENCE_AVAILABLE)
    return [flag for flag in _FLAG_ORDER if flag in present]
