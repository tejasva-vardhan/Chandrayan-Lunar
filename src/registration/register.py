"""Baseline image registration orchestration.

Frozen pipeline surface:
register(pair, control_points, correspondences) -> RegistrationResult.

Estimates a replaceable 2D transform from control points, validates it, and
warps the source raster when a software-baseline .npy handle is available.
Does not re-run matching or verification. Does not invent metrics.
"""

from __future__ import annotations

import numpy as np

from src.models.correspondence_set import CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult, TransformationModel
from src.registration.estimation import eligible_control_points, estimate_matrix
from src.registration.models import get_transform_model
from src.registration.raster_io import load_raster, registered_uri_for, save_raster
from src.registration.result import (
    FLAG_DEGENERATE_CONTROL_POINTS,
    FLAG_INSUFFICIENT_CONTROL_POINTS,
    FLAG_INVALID_TRANSFORMATION,
    FLAG_SOURCE_RASTER_UNAVAILABLE,
    FLAG_UNSUPPORTED_RASTER,
    FLAG_WARP_FAILED,
    build_result,
    matrix_parameters,
)
from src.registration.settings import RegistrationSettings, unvalidated_software_defaults
from src.registration.validation import invert_matrix, validate_matrix
from src.registration.warp import warp_to_grid


def register(
    pair: RegistrationPair,
    control_points: list[ControlPoint],
    correspondences: CorrespondenceSet,
) -> RegistrationResult:
    """Estimate a transform and warp the source when a raster handle exists.

    Uses unvalidated_software_defaults(). model_id=projective_2d_baseline is
    an engineering software baseline, not a final lunar model (D-010).
    """

    return register_with_settings(
        pair, control_points, correspondences, unvalidated_software_defaults()
    )


def register_with_settings(
    pair: RegistrationPair,
    control_points: list[ControlPoint],
    correspondences: CorrespondenceSet,
    settings: RegistrationSettings,
) -> RegistrationResult:
    model = get_transform_model(settings.model_id)
    eligible = eligible_control_points(control_points)
    if len(eligible) < model.min_samples:
        return build_result(
            pair,
            control_points,
            correspondences,
            None,
            None,
            [FLAG_INSUFFICIENT_CONTROL_POINTS],
        )

    fitted = estimate_matrix(eligible, model)
    if fitted is None:
        return build_result(
            pair,
            control_points,
            correspondences,
            None,
            None,
            [FLAG_DEGENERATE_CONTROL_POINTS],
        )

    validated = validate_matrix(fitted)
    if validated is None or invert_matrix(validated) is None:
        return build_result(
            pair,
            control_points,
            correspondences,
            None,
            None,
            [FLAG_INVALID_TRANSFORMATION],
        )

    transformation = TransformationModel(
        model_name=model.model_id,
        parameters=matrix_parameters(validated),
    )

    source_uri = pair.source.raster_uri
    if source_uri is None:
        return build_result(
            pair,
            control_points,
            correspondences,
            transformation,
            None,
            [FLAG_SOURCE_RASTER_UNAVAILABLE],
        )

    try:
        source = load_raster(source_uri)
    except ValueError:
        return build_result(
            pair,
            control_points,
            correspondences,
            transformation,
            None,
            [FLAG_UNSUPPORTED_RASTER],
        )
    except OSError:
        return build_result(
            pair,
            control_points,
            correspondences,
            transformation,
            None,
            [FLAG_SOURCE_RASTER_UNAVAILABLE],
        )

    height, width = _output_hw(pair, source)
    try:
        warped = warp_to_grid(source, validated, height, width)
        uri = save_raster(registered_uri_for(source_uri), warped)
    except (ValueError, OSError):
        return build_result(
            pair,
            control_points,
            correspondences,
            transformation,
            None,
            [FLAG_WARP_FAILED],
        )

    return build_result(pair, control_points, correspondences, transformation, uri, [])


def _output_hw(pair: RegistrationPair, source: np.ndarray) -> tuple[int, int]:
    reference_uri = pair.reference.raster_uri
    if reference_uri is not None:
        try:
            reference = load_raster(reference_uri)
        except (ValueError, OSError):
            reference = None
        else:
            return int(reference.shape[0]), int(reference.shape[1])
    return int(source.shape[0]), int(source.shape[1])
