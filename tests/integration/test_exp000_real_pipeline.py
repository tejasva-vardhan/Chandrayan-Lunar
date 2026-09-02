"""Optional real-data EXP-000 end-to-end check.

Requires CHANDRAYAN_DATA_ROOT with pair-01 OHRC and LROC products.
Skips when the external dataset is not configured. Not official SIH evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion import (
    DATA_ROOT_ENV,
    PAIR_01_LROC_ID,
    PAIR_01_OHRC_ID,
    DataRootError,
    configured_data_root,
    find_product,
)
from src.io.exp000 import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    REFINEMENT_OUTCOME_INDETERMINATE,
    run_exp000,
)
from src.io.exp000.run import Exp000Error
from src.registration.result import FLAG_OUTPUT_TOO_LARGE


@pytest.fixture(autouse=True)
def _redirect_derived_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path / "manifests"))
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path / "processed"))


def _require_pair_root() -> Path:
    try:
        root = configured_data_root()
    except DataRootError as exc:
        pytest.fail(str(exc))
    if root is None:
        pytest.skip(f"Set {DATA_ROOT_ENV} to run the external EXP-000 pipeline")
    if find_product(root, PAIR_01_OHRC_ID) is None or find_product(root, PAIR_01_LROC_ID) is None:
        pytest.skip("EXP-000 pair-01 products are unavailable under the configured root")
    return root


@pytest.mark.scientific
def test_exp000_real_pair_runs_every_frozen_stage(tmp_path: Path) -> None:
    root = _require_pair_root()
    output_dir = tmp_path / "exp000"
    record_path = tmp_path / "pair_01_equatorial.json"

    record = run_exp000(data_root=root, output_dir=output_dir, record_path=record_path)

    assert record["status"] == "completed"
    assert record["failed_stage"] is None
    stages = record["stages"]
    for name in (
        "ingest_product",
        "characterize_pair",
        "preprocess",
        "generate_representation",
        "match",
        "verify_matches",
        "select_control_points",
        "refine_points",
        "register",
        "evaluate",
        "export_result",
    ):
        assert name in stages
        assert name in record["runtime_seconds"]

    ingest = stages["ingest_product"]
    assert PAIR_01_OHRC_ID.lower() in ingest["source"]["product_id"].lower()
    assert ingest["reference"]["product_id"] == PAIR_01_LROC_ID
    assert ingest["source"]["illumination_metadata"]["populated_from_product"] is False
    assert ingest["reference"]["acquisition_time"] is not None

    view = stages["generate_representation"]
    assert view["source_matching_view"]["policy"] in {"stride_decimation", "full_resolution"}
    assert view["lroc_invalid_mask_respected"] is True
    source_view = view["source_matching_view"]
    if source_view["stride"] > 1:
        sx = source_view["matching_shape"][0] * source_view["stride"]
        assert sx >= source_view["original_shape"][0]

    raw = stages["match"]["raw_match_count"]
    inliers = stages["verify_matches"]["verified_inlier_count"]
    assert raw >= 0
    assert 0 <= inliers <= raw
    assert stages["match"]["coordinates"] == "original_image_pixels_after_matching_view_scale"

    register = stages["register"]
    assert register["full_raster_warp_blocked"] is True
    assert FLAG_OUTPUT_TOO_LARGE in register["quality_flags"]
    assert register["registered_source_uri"] is None
    crop = register["diagnostic_crop"]
    cap = 16_777_216
    assert crop["produced"] is True
    assert crop["window"]["pixel_count"] <= cap
    assert crop["window"]["pixel_count"] < (
        ingest["reference"]["dimensions"]["pixel_count"]
    )
    total_cp = stages["select_control_points"]["control_point_count"]
    assert crop["control_points_total"] == total_cp
    assert 0 <= crop["control_points_inside_count"] <= total_cp
    if total_cp > 0:
        assert crop["control_points_inside_count"] >= 1
    if crop["control_points_inside_count"] < total_cp:
        assert crop["control_points_not_all_included_reason"]

    evaluate = stages["evaluate"]
    assert evaluate["independent_ground_truth_used"] is False
    assert evaluate["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    if stages["select_control_points"]["control_point_count"] == 4:
        residuals = evaluate["projective_dlt_fit_residuals_on_control_points_pixels"]
        assert residuals
        assert max(residuals) < 1e-6
        assert any("four points" in warning.lower() for warning in record["warnings"])

    refine = stages["refine_points"]
    if refine["coordinates_changed_count"] == 0 and refine["output_count"] > 0:
        assert refine["outcome"] == REFINEMENT_OUTCOME_INDETERMINATE
        assert "not a successful refinement" in refine["limitation"]

    assert record_path.is_file()
    assert (output_dir / "export" / "registration_report.json").is_file()
    assert record["scientific_interpretation"]["independent_accuracy"] == (
        INDEPENDENT_ACCURACY_NOT_VALIDATED
    )


def test_run_exp000_fails_closed_without_data_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    with pytest.raises(Exp000Error, match=DATA_ROOT_ENV):
        run_exp000()


def test_run_exp000_fails_when_pair_products_are_missing(tmp_path: Path) -> None:
    import json

    record_path = tmp_path / "blocked.json"
    with pytest.raises(Exp000Error, match="were not found"):
        run_exp000(data_root=tmp_path, record_path=record_path)
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    assert payload["status"] == "could_not_start"
    assert payload["failed_stage"] == "ingest_product"
    assert payload["dataset"]["ohrc_found"] is False
    assert payload["scientific_interpretation"]["independent_accuracy"] == (
        INDEPENDENT_ACCURACY_NOT_VALIDATED
    )
