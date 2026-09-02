"""Unit tests for registration-package exports, not lunar accuracy evidence."""

from __future__ import annotations

import json

import pytest

from src.io import export_result
from src.models import (
    ControlPoint,
    Correspondence,
    CorrespondenceSet,
    LunarProduct,
    RegistrationMetrics,
    RegistrationPair,
    RegistrationResult,
    TransformationModel,
)


def _pair() -> RegistrationPair:
    return RegistrationPair(
        pair_id="export-pair",
        source=LunarProduct(product_id="source", instrument="OHRC"),
        reference=LunarProduct(product_id="reference", instrument="LRO_NAC"),
    )


def test_export_writes_observed_result_data_and_limitation(tmp_path) -> None:
    pair = _pair()
    inlier = Correspondence(
        source_xy=(1.0, 2.0), reference_xy=(3.0, 4.0), status="inlier", residual=0.5
    )
    result = RegistrationResult(
        pair_id=pair.pair_id,
        correspondences=CorrespondenceSet(
            pair_id=pair.pair_id, matcher_id="sift", matches=[inlier]
        ),
        inliers=[inlier],
        control_points=[
            ControlPoint(source_xy=(1.0, 2.0), reference_xy=(3.0, 4.0)),
            ControlPoint(source_xy=(2.0, 2.0), reference_xy=(4.0, 4.0)),
            ControlPoint(source_xy=(1.0, 3.0), reference_xy=(3.0, 5.0)),
            ControlPoint(source_xy=(2.0, 3.0), reference_xy=(4.0, 5.0)),
        ],
        transformation=TransformationModel(model_name="projective_2d_baseline"),
        metrics=RegistrationMetrics(inlier_count=1, inlier_ratio=1.0, rmse=0.5),
    )

    manifest = export_result(result, pair, tmp_path)

    assert manifest.registered_source is None
    assert manifest.all_matches is not None
    assert manifest.inliers is not None
    assert manifest.control_points is not None
    assert manifest.transformation is not None
    assert manifest.metrics is not None
    assert manifest.registration_report is not None
    report = json.loads((tmp_path / "registration_report.json").read_text(encoding="utf-8"))
    assert "not an independent registration-accuracy metric" in report["evaluation_limitation"]
    assert "exactly its four-point minimum" in report["projective_fit_limitation"]
    assert report["independent_ground_truth_used"] is False
    assert "0.5 * (source_bbox_area" in report["spatial_coverage_definition"]
    assert "does not create correspondences" in report["control_point_selection_note"]
    assert "indeterminate" in report["refinement_outcome_note"]
    assert report["raw_correspondence_count"] == 1


def test_export_omits_unavailable_transformation_and_metrics(tmp_path) -> None:
    pair = _pair()
    result = RegistrationResult(
        pair_id=pair.pair_id,
        correspondences=CorrespondenceSet(pair_id=pair.pair_id, matcher_id="sift"),
        quality_flags=["insufficient_control_points"],
    )

    manifest = export_result(result, pair, tmp_path)

    assert manifest.transformation is None
    assert manifest.metrics is None
    assert (tmp_path / "all_matches.json").exists()
    assert not (tmp_path / "transformation.json").exists()
    assert not (tmp_path / "metrics.json").exists()


def test_export_rejects_result_for_a_different_pair(tmp_path) -> None:
    with pytest.raises(ValueError, match="does not match"):
        export_result(RegistrationResult(pair_id="other"), _pair(), tmp_path)
