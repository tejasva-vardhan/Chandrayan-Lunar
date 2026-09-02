"""Software correctness tests for portable baseline result packages."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

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
from src.models.common import Provenance


def _pair() -> RegistrationPair:
    return RegistrationPair(
        pair_id="pair-export",
        source=LunarProduct(
            product_id="source",
            instrument="OHRC",
            raster_uri="C:/machine-specific/source.npy",
            provenance=Provenance(source_uri="C:/machine-specific/source.xml"),
        ),
        reference=LunarProduct(product_id="reference", instrument="LRO_NAC"),
    )


def test_export_writes_portable_complete_package(tmp_path: Path) -> None:
    pair = _pair()
    registered = tmp_path / "derived" / "source.registered.npy"
    registered.parent.mkdir()
    np.save(registered, np.arange(9).reshape(3, 3))
    match = Correspondence(
        source_xy=(1.0, 2.0), reference_xy=(3.0, 4.0), status="inlier", residual=0.2
    )
    result = RegistrationResult(
        pair_id=pair.pair_id,
        correspondences=CorrespondenceSet(pair_id=pair.pair_id, matcher_id="sift", matches=[match]),
        inliers=[match],
        control_points=[ControlPoint(source_xy=(1.0, 2.0), reference_xy=(3.0, 4.0))],
        transformation=TransformationModel(
            model_name="projective_2d_baseline",
            parameters={"matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        ),
        registered_source_uri=str(registered),
        metrics=RegistrationMetrics(rmse=0.2, inlier_count=1, inlier_ratio=1.0),
    )

    manifest = export_result(result, pair, tmp_path / "package")

    assert manifest.registered_source == "registered_source.npy"
    assert manifest.all_matches == "correspondences.json"
    assert manifest.inliers == "inliers.json"
    assert manifest.control_points == "control_points.json"
    assert manifest.transformation == "transformation.json"
    assert manifest.metrics == "metrics.json"
    assert manifest.registration_report == "registration_report.json"
    exported = np.load(tmp_path / "package" / "registered_source.npy")
    assert np.array_equal(exported, np.arange(9).reshape(3, 3))
    report_text = (tmp_path / "package" / "registration_report.json").read_text(encoding="utf-8")
    assert "C:/machine-specific" not in report_text
    assert json.loads(report_text)["status"]["registered_output_available"] is True


def test_failure_export_preserves_status_without_placeholder_outputs(tmp_path: Path) -> None:
    pair = _pair()
    result = RegistrationResult(
        pair_id=pair.pair_id,
        quality_flags=["insufficient_control_points", "evaluation_unavailable"],
    )

    manifest = export_result(result, pair, tmp_path)

    assert manifest.registered_source is None
    assert manifest.metrics is None
    assert manifest.registration_report == "registration_report.json"
    report = json.loads((tmp_path / "registration_report.json").read_text(encoding="utf-8"))
    assert report["status"]["quality_flags"] == result.quality_flags
    assert report["status"]["evaluation_available"] is False
