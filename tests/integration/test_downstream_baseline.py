"""Downstream contract integration using software .npy rasters, not lunar validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.control_points import select_control_points
from src.evaluation import evaluate
from src.io import export_result
from src.models import Correspondence, CorrespondenceSet, LunarProduct, RegistrationPair
from src.refinement import refine_points
from src.registration import register
from src.verification import verify_matches


def test_verified_correspondences_flow_to_registration_and_export(tmp_path: Path) -> None:
    source_uri = tmp_path / "source.npy"
    reference_uri = tmp_path / "reference.npy"
    image = np.arange(64, dtype=np.float32).reshape(8, 8)
    np.save(source_uri, image)
    np.save(reference_uri, image)
    pair = RegistrationPair(
        pair_id="downstream-npy",
        source=LunarProduct(product_id="source", instrument="OHRC", raster_uri=str(source_uri)),
        reference=LunarProduct(
            product_id="reference", instrument="LRO_NAC", raster_uri=str(reference_uri)
        ),
    )
    raw = CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id="software-test",
        matches=[
            Correspondence(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
            Correspondence(source_xy=(7.0, 0.0), reference_xy=(7.0, 0.0)),
            Correspondence(source_xy=(0.0, 7.0), reference_xy=(0.0, 7.0)),
            Correspondence(source_xy=(7.0, 7.0), reference_xy=(7.0, 7.0)),
        ],
    )

    verified = verify_matches(raw, pair)
    control_points = select_control_points(verified, pair)
    refined = refine_points(control_points, pair)
    registered = register(pair, refined, verified)
    evaluated = evaluate(registered, pair)
    manifest = export_result(evaluated, pair, tmp_path / "package")

    assert all(item.status == "inlier" for item in verified.matches)
    assert len(refined) == len(control_points)
    assert registered.correspondences is verified
    assert registered.registered_source_uri is not None
    assert evaluated.metrics is not None
    assert evaluated.metrics.rmse is None
    assert "evaluation_unavailable" in evaluated.quality_flags
    assert manifest.registered_source == "registered_source.npy"
    assert manifest.registration_report == "registration_report.json"
