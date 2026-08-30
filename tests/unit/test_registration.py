"""Unit tests for baseline registration. Not lunar accuracy evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from src.models import (
    ControlPoint,
    Correspondence,
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
    TransformationModel,
)
from src.pipeline.operations import register as pipeline_register
from src.registration import (
    RegistrationSettings,
    register,
    register_with_settings,
    unvalidated_software_defaults,
)
from src.registration.result import (
    FLAG_DEGENERATE_CONTROL_POINTS,
    FLAG_INSUFFICIENT_CONTROL_POINTS,
    FLAG_SOURCE_RASTER_UNAVAILABLE,
    FLAG_UNSUPPORTED_RASTER,
)
from src.registration.validation import validate_matrix


def _pair(
    tmp_path: Path | None = None,
    *,
    source_array: np.ndarray | None = None,
    reference_array: np.ndarray | None = None,
) -> RegistrationPair:
    source_uri = None
    reference_uri = None
    if tmp_path is not None and source_array is not None:
        source_uri = str(tmp_path / "source.npy")
        np.save(source_uri, source_array)
    if tmp_path is not None and reference_array is not None:
        reference_uri = str(tmp_path / "reference.npy")
        np.save(reference_uri, reference_array)
    return RegistrationPair(
        pair_id="pair-reg",
        source=LunarProduct(
            product_id="src-001", instrument="OHRC", raster_uri=source_uri
        ),
        reference=LunarProduct(
            product_id="ref-001", instrument="LRO_NAC", raster_uri=reference_uri
        ),
    )


def _cps(pairs: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[ControlPoint]:
    return [
        ControlPoint(source_xy=source, reference_xy=reference)
        for source, reference in pairs
    ]


def _correspondences(
    pair: RegistrationPair, matches: list[Correspondence] | None = None
) -> CorrespondenceSet:
    return CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id="unspecified",
        matches=list(matches or []),
    )


def _identity_corners(width: int, height: int) -> list[ControlPoint]:
    xmax = float(width - 1)
    ymax = float(height - 1)
    return _cps(
        [
            ((0.0, 0.0), (0.0, 0.0)),
            ((xmax, 0.0), (xmax, 0.0)),
            ((0.0, ymax), (0.0, ymax)),
            ((xmax, ymax), (xmax, ymax)),
            ((xmax / 2.0, ymax / 2.0), (xmax / 2.0, ymax / 2.0)),
        ]
    )


def _index_image(height: int, width: int) -> np.ndarray:
    rows = np.arange(height, dtype=float)[:, None]
    cols = np.arange(width, dtype=float)[None, :]
    return rows * width + cols


def test_register_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_register is register


def test_insufficient_control_points(registration_pair: RegistrationPair) -> None:
    correspondences = _correspondences(registration_pair)
    result = register(registration_pair, _cps([((0.0, 0.0), (1.0, 0.0))]), correspondences)
    assert result.transformation is None
    assert result.registered_source_uri is None
    assert result.metrics is None
    assert FLAG_INSUFFICIENT_CONTROL_POINTS in result.quality_flags
    assert result.correspondences is correspondences


def test_duplicate_points(registration_pair: RegistrationPair) -> None:
    point = ((0.0, 0.0), (1.0, 1.0))
    points = _cps([point, point, point, point])
    result = register(registration_pair, points, _correspondences(registration_pair))
    assert result.transformation is None
    assert FLAG_INSUFFICIENT_CONTROL_POINTS in result.quality_flags


def test_degenerate_control_points(registration_pair: RegistrationPair) -> None:
    points = _cps(
        [
            ((0.0, 0.0), (0.0, 0.0)),
            ((1.0, 0.0), (2.0, 0.0)),
            ((2.0, 0.0), (4.0, 0.0)),
            ((3.0, 0.0), (6.0, 0.0)),
        ]
    )
    result = register(registration_pair, points, _correspondences(registration_pair))
    assert result.transformation is None
    assert FLAG_DEGENERATE_CONTROL_POINTS in result.quality_flags


def test_non_finite_inputs(registration_pair: RegistrationPair) -> None:
    points = _cps(
        [
            ((math.inf, 0.0), (0.0, 0.0)),
            ((0.0, 1.0), (0.0, math.nan)),
            ((1.0, 1.0), (1.0, 1.0)),
            ((2.0, 2.0), (2.0, 2.0)),
        ]
    )
    result = register(registration_pair, points, _correspondences(registration_pair))
    assert result.transformation is None
    assert FLAG_INSUFFICIENT_CONTROL_POINTS in result.quality_flags


def test_invalid_transformation_rejected() -> None:
    singular = np.zeros((3, 3), dtype=float)
    assert validate_matrix(singular) is None
    almost = np.array([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=float)
    assert validate_matrix(almost) is None


def test_identity_transformation(tmp_path: Path) -> None:
    image = _index_image(16, 16)
    pair = _pair(tmp_path, source_array=image, reference_array=image)
    result = register(pair, _identity_corners(16, 16), _correspondences(pair))
    assert result.transformation is not None
    assert result.registered_source_uri is not None
    warped = np.load(result.registered_source_uri)
    assert warped.shape == (16, 16)
    np.testing.assert_allclose(warped, image, atol=1e-6)


def test_known_translation_without_raster(registration_pair: RegistrationPair) -> None:
    points = _cps(
        [
            ((0.0, 0.0), (4.0, 0.0)),
            ((10.0, 0.0), (14.0, 0.0)),
            ((0.0, 10.0), (4.0, 10.0)),
            ((10.0, 10.0), (14.0, 10.0)),
        ]
    )
    result = register(registration_pair, points, _correspondences(registration_pair))
    assert result.transformation is not None
    matrix = np.array(result.transformation.parameters["matrix"], dtype=float)
    mapped = matrix @ np.array([0.0, 0.0, 1.0])
    assert mapped[2] != 0
    assert abs(mapped[0] / mapped[2] - 4.0) < 1e-6
    assert abs(mapped[1] / mapped[2] - 0.0) < 1e-6
    assert result.registered_source_uri is None
    assert FLAG_SOURCE_RASTER_UNAVAILABLE in result.quality_flags


def test_output_image_dimensions(tmp_path: Path) -> None:
    source = _index_image(8, 10)
    reference = _index_image(12, 14)
    pair = _pair(tmp_path, source_array=source, reference_array=reference)
    result = register(pair, _identity_corners(8, 8), _correspondences(pair))
    assert result.registered_source_uri is not None
    warped = np.load(result.registered_source_uri)
    assert warped.shape == (12, 14)


def test_transformation_parameter_serialization(registration_pair: RegistrationPair) -> None:
    points = _identity_corners(8, 8)
    result = register(registration_pair, points, _correspondences(registration_pair))
    assert result.transformation is not None
    payload = result.transformation.model_dump_json()
    restored = TransformationModel.model_validate_json(payload)
    assert restored.model_name == "projective_2d_baseline"
    json.dumps(restored.parameters)
    assert restored.parameters["role"] == "software_baseline"


def test_correspondence_preservation(registration_pair: RegistrationPair) -> None:
    inlier = Correspondence(
        source_xy=(0.0, 0.0),
        reference_xy=(0.0, 0.0),
        status="inlier",
    )
    rejected = Correspondence(
        source_xy=(9.0, 9.0),
        reference_xy=(8.0, 8.0),
        status="rejected",
    )
    correspondences = _correspondences(registration_pair, [inlier, rejected])
    result = register(registration_pair, _identity_corners(8, 8), correspondences)
    assert result.correspondences is correspondences
    assert len(result.inliers) == 1
    assert result.inliers[0].source_xy == (0.0, 0.0)
    assert result.control_points == _identity_corners(8, 8)
    assert result.metrics is None
    assert result.confidence_class is None


def test_registration_result_construction_empty_flags_are_not_success_class(
    registration_pair: RegistrationPair,
) -> None:
    result = register(
        registration_pair, _identity_corners(8, 8), _correspondences(registration_pair)
    )
    assert result.pair_id == registration_pair.pair_id
    assert result.confidence_class is None
    assert result.metrics is None


def test_deterministic_output(tmp_path: Path) -> None:
    image = _index_image(12, 12)
    pair = _pair(tmp_path, source_array=image, reference_array=image)
    points = _identity_corners(16, 16)
    correspondences = _correspondences(pair)
    first = register(pair, points, correspondences)
    second = register(pair, points, correspondences)
    assert first.transformation == second.transformation
    assert first.registered_source_uri == second.registered_source_uri
    warped_a = np.load(first.registered_source_uri)
    warped_b = np.load(second.registered_source_uri)
    np.testing.assert_array_equal(warped_a, warped_b)


def test_unsupported_raster_encoding(tmp_path: Path) -> None:
    path = tmp_path / "source.tif"
    path.write_text("not-a-npy", encoding="utf-8")
    pair = RegistrationPair(
        pair_id="pair-reg",
        source=LunarProduct(product_id="src-001", instrument="OHRC", raster_uri=str(path)),
        reference=LunarProduct(product_id="ref-001", instrument="LRO_NAC"),
    )
    result = register(pair, _identity_corners(8, 8), _correspondences(pair))
    assert result.transformation is not None
    assert result.registered_source_uri is None
    assert FLAG_UNSUPPORTED_RASTER in result.quality_flags


def test_unknown_model_id_fails_clearly(registration_pair: RegistrationPair) -> None:
    with pytest.raises(ValueError, match="unknown registration model_id"):
        register_with_settings(
            registration_pair,
            _identity_corners(8, 8),
            _correspondences(registration_pair),
            RegistrationSettings(model_id="homography_as_lunar_model"),
        )


def test_affine_baseline_is_replaceable(registration_pair: RegistrationPair) -> None:
    points = _cps(
        [
            ((0.0, 0.0), (2.0, 1.0)),
            ((10.0, 0.0), (12.0, 1.0)),
            ((0.0, 10.0), (4.0, 11.0)),
            ((10.0, 10.0), (14.0, 11.0)),
        ]
    )
    result = register_with_settings(
        registration_pair,
        points,
        _correspondences(registration_pair),
        RegistrationSettings(model_id="affine_2d_baseline"),
    )
    assert result.transformation is not None
    assert result.transformation.model_name == "affine_2d_baseline"


def test_two_argument_api_uses_software_baseline() -> None:
    defaults = unvalidated_software_defaults()
    assert defaults.model_id == "projective_2d_baseline"
