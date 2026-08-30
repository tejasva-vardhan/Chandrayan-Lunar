"""Mathematical pair measurements from available metadata.

Each function returns a computed value or None. None means unavailable or
undefended, never a substituted default. Zero is returned only when it is
the actual measured result (for example identical acquisition times).

Convention notes
----------------
gsd_ratio
    Interface Freeze v1: source GSD / reference GSD. GSD units are metres
    per pixel as stored on LunarProduct.gsd_meters. The ratio is
    dimensionless. This is a descriptive measurement, not a routing
    threshold.

sun_angle_difference_degrees
    ENGINEERING IMPLEMENTATION DEFINITION when both products supply a
    3-vector Sun direction in the same frame: angular separation of those
    vectors, in degrees. Incidence/azimuth combination is not defined and
    is not used. LunarProduct currently has no Sun metadata, so the
    product adapter leaves this unavailable.

viewing_geometry_difference
    Intentionally undefined (Interface Freeze v1 §8, v3 open definition).
    Always None. Look-vector angular separation is not written into this
    opaque contract field.

expected_overlap
    Only a caller-supplied overlap fraction in [0, 1] is accepted.
    Image bounding-box intersection is not lunar geographic overlap.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np


def finite_positive(value: float | None) -> float | None:
    """Return value if it is a finite number > 0, otherwise None."""

    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def image_dimensions(
    width_px: int | None, height_px: int | None
) -> tuple[int, int] | None:
    """Return (width, height) when both are integers > 0.

    Does not fabricate dimensions. Rejects None, non-integers, booleans,
    and non-positive extents.
    """

    if width_px is None or height_px is None:
        return None
    if isinstance(width_px, bool) or isinstance(height_px, bool):
        return None
    if not isinstance(width_px, int) or not isinstance(height_px, int):
        return None
    if width_px <= 0 or height_px <= 0:
        return None
    return (width_px, height_px)


def gsd_ratio(
    source_gsd_meters: float | None, reference_gsd_meters: float | None
) -> float | None:
    """source GSD / reference GSD.

    Interface Freeze v1 convention. Both arguments must be finite and > 0
    metres/pixel. Missing, zero, negative, or non-finite GSD → None.
    There is no unit conversion: LunarProduct stores metres only.
    """

    source = finite_positive(source_gsd_meters)
    reference = finite_positive(reference_gsd_meters)
    if source is None or reference is None:
        return None
    return source / reference


def _finite_vector3(
    vector: tuple[float, float, float] | None,
) -> np.ndarray | None:
    if vector is None:
        return None
    if len(vector) != 3:
        return None
    array = np.asarray(vector, dtype=float)
    if array.shape != (3,) or not bool(np.all(np.isfinite(array))):
        return None
    return array


def angular_separation_degrees(
    vector_a: tuple[float, float, float] | None,
    vector_b: tuple[float, float, float] | None,
) -> float | None:
    """Angular separation of two 3-vectors, in degrees.

    Definition: atan2(||a_hat × b_hat||, a_hat · b_hat) converted to
    degrees, where hats are unit vectors. Missing, non-finite, wrong-length,
    or zero-length vectors → None.

    Vectors are treated as directions in a shared unspecified frame. This
    module does not transform frames (SPICE is not implemented).
    """

    raw_a = _finite_vector3(vector_a)
    raw_b = _finite_vector3(vector_b)
    if raw_a is None or raw_b is None:
        return None
    norm_a = float(np.linalg.norm(raw_a))
    norm_b = float(np.linalg.norm(raw_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    unit_a = raw_a / norm_a
    unit_b = raw_b / norm_b
    sine = float(np.linalg.norm(np.cross(unit_a, unit_b)))
    cosine = float(np.dot(unit_a, unit_b))
    return math.degrees(math.atan2(sine, cosine))


def sun_angle_difference_degrees(
    source_sun_vector: tuple[float, float, float] | None,
    reference_sun_vector: tuple[float, float, float] | None,
) -> float | None:
    """Sun-direction angular separation in degrees, or None.

    ENGINEERING IMPLEMENTATION DEFINITION for the frozen field
    sun_angle_difference_degrees when both Sun direction vectors exist.
    Not an incidence/azimuth combination. Not a scientifically validated
    lunar illumination metric.
    """

    return angular_separation_degrees(source_sun_vector, reference_sun_vector)


def viewing_geometry_difference(
    source_look_vector: tuple[float, float, float] | None = None,
    reference_look_vector: tuple[float, float, float] | None = None,
) -> None:
    """Always None.

    Interface Freeze v1 does not define a unit or formula for
    viewing_geometry_difference. v3 leaves the definition open. Look
    vectors, if present, are not converted into this opaque scalar.
    """

    del source_look_vector, reference_look_vector
    return None


def acquisition_time_difference_seconds(
    source_time: datetime | None, reference_time: datetime | None
) -> float | None:
    """Absolute |t_source − t_reference| in seconds, or None.

    Mixed timezone-aware and naive datetimes are not comparable; the
    difference stays None rather than assuming UTC. Identical times yield
    0.0 (a measured difference, not missing data).
    """

    if source_time is None or reference_time is None:
        return None
    try:
        seconds = abs((source_time - reference_time).total_seconds())
    except TypeError:
        return None
    if not math.isfinite(seconds):
        return None
    return seconds


def expected_overlap(
    overlap_fraction: float | None,
    source_bbox: tuple[float, float, float, float] | None = None,
    reference_bbox: tuple[float, float, float, float] | None = None,
) -> float | None:
    """Return overlap_fraction when it is finite and in [0, 1].

    Bounding boxes are accepted so they are not used elsewhere to fake
    overlap. They are ignored. Image AABB intersection is not lunar
    geographic overlap.
    """

    del source_bbox, reference_bbox
    if overlap_fraction is None:
        return None
    value = float(overlap_fraction)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        return None
    return value


def explicit_identifier(value: str | None) -> str | None:
    """Return a non-empty identifier, otherwise None. Does not guess."""

    if value is None or value == "":
        return None
    return value


def sensor_pair_label(
    source_instrument: str | None, reference_instrument: str | None
) -> str | None:
    """source_instrument/reference_instrument from explicit metadata only."""

    source = explicit_identifier(source_instrument)
    reference = explicit_identifier(reference_instrument)
    if source is None or reference is None:
        return None
    return f"{source}/{reference}"


def pair_modality_label(
    source_instrument: str | None, reference_instrument: str | None
) -> str | None:
    """Pair modality as the explicit instrument pairing.

    LunarProduct has no separate modality field. Instrument strings are
    preserved, not mapped onto an optical/spectral/multimodal taxonomy
    and not inferred from filenames.
    """

    return sensor_pair_label(source_instrument, reference_instrument)


def pair_id_for(source_product_id: str, reference_product_id: str) -> str:
    """Engineering pair identifier. Not a scientific measurement."""

    return f"{source_product_id}__{reference_product_id}"
