"""Sub-pixel control-point refinement orchestration.

Frozen pipeline surface:
refine_points(control_points, pair) -> list[ControlPoint].

Coarse selected control points are refined from local image evidence. This
stage does not rematch, does not rerun RANSAC, does not change the selected
population, and does not call register().

Failure does not fabricate a refined coordinate: the original point is
preserved. The frozen ControlPoint contract has no per-point success flag.
"""

from __future__ import annotations

import numpy as np

from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint
from src.refinement.methods import get_refinement_method
from src.refinement.raster import as_intensity, load_software_raster
from src.refinement.settings import RefinementSettings, unvalidated_software_defaults


def refine_points(
    control_points: list[ControlPoint], pair: RegistrationPair
) -> list[ControlPoint]:
    """Refine control-point coordinates (frozen two-argument API).

    Uses unvalidated_software_defaults(): method_id=zncc_parabolic_baseline,
    window_radius=7, search_radius=3, min_valid_pixel_fraction=0.75,
    min_peak_zncc=0.25, fine_half_width=1.0, fine_step=0.1. Those numbers
    exist only because this frozen signature has no settings argument. They
    are SAME-MODALITY software/test defaults, not SIH thresholds, not
    lunar-validated parameters, not a multimodal solution, and not
    benchmark results (D-006).

    Call refine_points_with_settings to supply explicit settings.
    """

    return refine_points_with_settings(
        control_points, pair, unvalidated_software_defaults()
    )


def refine_points_with_settings(
    control_points: list[ControlPoint],
    pair: RegistrationPair,
    settings: RefinementSettings,
) -> list[ControlPoint]:
    """Configurable refinement. Does not mutate the input list or points."""

    method = get_refinement_method(settings.method_id)
    if not control_points:
        return []

    source_intensity, reference_intensity = _load_intensity_pair(pair, method.requires_rasters)
    if method.requires_rasters and (source_intensity is None or reference_intensity is None):
        return [_copy_point(point) for point in control_points]

    refined: list[ControlPoint] = []
    for point in control_points:
        result = method.refine_point(source_intensity, reference_intensity, point, settings)
        if result is None:
            refined.append(_copy_point(point))
        else:
            refined.append(result)
    return refined


def _load_intensity_pair(
    pair: RegistrationPair, required: bool
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if not required:
        return None, None
    source_array, source_error = load_software_raster(pair.source.raster_uri)
    reference_array, reference_error = load_software_raster(pair.reference.raster_uri)
    if source_array is None or reference_array is None:
        return None, None
    if source_error is not None or reference_error is not None:
        return None, None
    return as_intensity(source_array), as_intensity(reference_array)


def _copy_point(point: ControlPoint) -> ControlPoint:
    return point.model_copy()
