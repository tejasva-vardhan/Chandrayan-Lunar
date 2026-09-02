"""Helpers shared by every matcher adapter.

EXP-001 compares matchers under one controlled protocol. Anything outside the
detector/descriptor itself must therefore be identical across adapters:
how arrays are taken from the representation, how validity masks are applied,
how matching-view coordinates are mapped back to original image pixels, and
how native distances are normalised into ``Correspondence.confidence``.

These functions are the SIFT adapter's original private helpers, promoted so
the other adapters cannot drift from them. Behaviour is unchanged; the SIFT
baseline must still reproduce the EXP-000 counts exactly, which
``tests/integration/test_exp001_real_pipeline.py`` asserts against the
committed EXP-000 record.
"""

from __future__ import annotations

import numpy as np

from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult


def representation_arrays(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Return (source_array, reference_array), or (None, None) when unavailable.

    Accepts a RepresentationResult or falls back to loading from raster_uri.
    A non-RepresentationResult object (a wiring double, for example) is
    treated as if it were None.
    """

    if isinstance(representation, RepresentationResult):
        if representation.metadata.get("no_raster_uri"):
            return None, None
        source_array = representation.array
        reference_array = representation.metadata.get("reference_array")
        if reference_array is None:
            raise ValueError(
                "RepresentationResult.metadata['reference_array'] is missing. "
                "generate_representation() should populate this key."
            )
        if not isinstance(reference_array, np.ndarray):
            raise ValueError(
                "RepresentationResult.metadata['reference_array'] must be a numpy array."
            )
        return source_array, reference_array

    source_uri = pair.source.raster_uri
    reference_uri = pair.reference.raster_uri
    if source_uri is None or reference_uri is None:
        return None, None
    from src.representation._loader import load_array

    return load_array(source_uri), load_array(reference_uri)


def representation_id(representation: RepresentationResult | None) -> str | None:
    return representation.representation_id if representation is not None else None


def matching_view_scale(
    representation: RepresentationResult | None,
    role: str,
) -> tuple[float, float]:
    """Matching-view to original-image coordinate scale for one product."""

    if not isinstance(representation, RepresentationResult):
        return 1.0, 1.0

    view = representation.metadata.get(f"{role}_matching_view")
    if not isinstance(view, dict):
        return 1.0, 1.0

    x_scale = float(view.get("x_scale", 1.0))
    y_scale = float(view.get("y_scale", 1.0))
    if not np.isfinite(x_scale) or not np.isfinite(y_scale) or x_scale <= 0 or y_scale <= 0:
        raise ValueError(f"invalid {role} matching-view coordinate scale")
    return x_scale, y_scale


def matching_mask(
    representation: RepresentationResult | None,
    role: str,
    array: np.ndarray | None,
) -> np.ndarray | None:
    """Return an OpenCV-compatible validity mask for a matching view."""

    if array is None or not isinstance(representation, RepresentationResult):
        return None

    mask = representation.metadata.get(f"{role}_valid_mask")
    if mask is None:
        return None
    if not isinstance(mask, np.ndarray) or mask.shape != array.shape:
        raise ValueError(f"{role} valid mask does not match its matching view")
    return mask.astype(np.uint8, copy=False) * 255


def map_point_to_original(
    point: tuple[float, float],
    scale: tuple[float, float],
) -> tuple[float, float]:
    """Map one matching-view point back to original image pixel coordinates."""

    return (float(point[0] * scale[0]), float(point[1] * scale[1]))


def to_uint8(array: np.ndarray) -> np.ndarray:
    """Convert a float [0, 1] representation array to uint8 for OpenCV."""

    return (array * 255.0).clip(0, 255).astype(np.uint8)


def empty_set(
    pair: RegistrationPair,
    matcher_id: str,
    representation: RepresentationResult | None,
) -> CorrespondenceSet:
    """An empty result. Not a crash condition; the caller handles low yield."""

    return CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id=matcher_id,
        matches=[],
        representation_id=representation_id(representation),
    )


def normalised_confidence(distances: np.ndarray) -> list[float | None]:
    """Map native match distances to Correspondence.confidence in [0, 1].

    Closer match -> higher confidence, normalised by the largest surviving
    distance in the same run. When every distance is zero no meaningful
    normalisation exists and confidence stays None.
    """

    values = np.asarray(distances, dtype=np.float64)
    if values.size == 0:
        return []
    largest = float(values.max())
    if largest <= 0.0:
        return [None] * values.size
    scaled = 1.0 - values / largest
    return [float(min(1.0, max(0.0, item))) for item in scaled]


def correspondences_from_matches(
    *,
    pair: RegistrationPair,
    matcher_id: str,
    representation: RepresentationResult | None,
    source_xy: np.ndarray,
    reference_xy: np.ndarray,
    distances: np.ndarray,
    source_scale: tuple[float, float],
    reference_scale: tuple[float, float],
) -> CorrespondenceSet:
    """Build a raw CorrespondenceSet in original image pixel coordinates."""

    confidences = normalised_confidence(distances)
    matches: list[Correspondence] = []
    for index in range(len(confidences)):
        matches.append(
            Correspondence(
                source_xy=map_point_to_original(source_xy[index], source_scale),
                reference_xy=map_point_to_original(reference_xy[index], reference_scale),
                confidence=confidences[index],
                status="raw",
            )
        )
    return CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id=matcher_id,
        matches=matches,
        representation_id=representation_id(representation),
    )


__all__ = [
    "correspondences_from_matches",
    "empty_set",
    "map_point_to_original",
    "matching_mask",
    "matching_view_scale",
    "normalised_confidence",
    "representation_arrays",
    "representation_id",
    "to_uint8",
]
