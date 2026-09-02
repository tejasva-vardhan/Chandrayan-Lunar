"""Assemble RegistrationResult without fabricating metrics."""

from __future__ import annotations

import numpy as np

from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import (
    ControlPoint,
    RegistrationResult,
    TransformationModel,
)

# Engineering failure labels. Not SIH evaluator vocabulary.
FLAG_INSUFFICIENT_CONTROL_POINTS = "insufficient_control_points"
FLAG_DEGENERATE_CONTROL_POINTS = "degenerate_control_points"
FLAG_INVALID_TRANSFORMATION = "invalid_transformation"
FLAG_SOURCE_RASTER_UNAVAILABLE = "source_raster_unavailable"
FLAG_UNSUPPORTED_RASTER = "unsupported_raster_encoding"
FLAG_WARP_FAILED = "warp_failed"
FLAG_OUTPUT_TOO_LARGE = "registration_output_too_large"


def snapshot_inliers(correspondences: CorrespondenceSet) -> list[Correspondence]:
    """Copy matches already labeled inlier. Does not invent inliers."""

    return [item for item in correspondences.matches if item.status == "inlier"]


def build_result(
    pair: RegistrationPair,
    control_points: list[ControlPoint],
    correspondences: CorrespondenceSet,
    transformation: TransformationModel | None,
    registered_source_uri: str | None,
    quality_flags: list[str],
) -> RegistrationResult:
    return RegistrationResult(
        pair_id=pair.pair_id,
        correspondences=correspondences,
        inliers=snapshot_inliers(correspondences),
        control_points=list(control_points),
        transformation=transformation,
        registered_source_uri=registered_source_uri,
        metrics=None,
        quality_flags=quality_flags,
        confidence_class=None,
        provenance=None,
    )


def matrix_parameters(matrix: np.ndarray) -> dict[str, object]:
    return {
        "matrix": [[float(matrix[row, col]) for col in range(3)] for row in range(3)],
        "role": "software_baseline",
    }
