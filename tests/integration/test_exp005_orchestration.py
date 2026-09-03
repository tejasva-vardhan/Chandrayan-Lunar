"""EXP-005 orchestration tests on synthetic products.

These run identity vs existing ZNCC refinement without the external dataset.
They are not lunar accuracy evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.ingestion import DATA_ROOT_ENV
from src.io.exp005.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    METHOD_IDENTITY,
    METHOD_ZNCC,
    VARIANT_A_ID,
    VARIANT_B_ID,
)
from src.io.exp005.run import Exp005Error, run_exp005, run_exp005_from_products
from src.models.common import ImageDimensions, Provenance
from src.models.lunar_product import LunarProduct

pytestmark = pytest.mark.wiring

_SIDE = 384
_SHIFT = 17


@pytest.fixture(autouse=True)
def _redirect_derived_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path / "manifests"))
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path / "processed"))


def _texture(side: int = _SIDE, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.4 + 0.04 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(45):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(5.0, 18.0)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        image += 0.3 * np.exp(-(((distance - radius) / 2.5) ** 2))
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _product(
    tmp_path: Path,
    name: str,
    array: np.ndarray,
    instrument: str,
    mission: str,
    gsd_meters: float | None,
) -> LunarProduct:
    raster = tmp_path / f"{name}.npy"
    np.save(raster, array)
    return LunarProduct(
        product_id=name,
        instrument=instrument,
        mission=mission,
        raster_uri=str(raster),
        gsd_meters=gsd_meters,
        dimensions=ImageDimensions(
            width_px=array.shape[1], height_px=array.shape[0], band_count=1
        ),
        provenance=Provenance(source_uri=str(raster), reader="synthetic"),
    )


@pytest.fixture(scope="module")
def synthetic_record(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp_path = tmp_path_factory.mktemp("exp005")
    source_array = _texture()
    reference_array = np.roll(source_array, _SHIFT, axis=1)
    source = _product(
        tmp_path, "synthetic-ohrc", source_array, "OHRC", "Chandrayaan-2", 1.0
    )
    reference = _product(
        tmp_path, "synthetic-lroc", reference_array, "LRO_NAC", "LRO", 1.0
    )
    return run_exp005_from_products(
        source,
        reference,
        output_dir=tmp_path / "out",
        record_path=tmp_path / "pair_02_mid_equatorial.json",
    )


def test_both_variants_run_and_share_correspondences(synthetic_record) -> None:
    record = synthetic_record

    assert record["status"] == "completed"
    assert set(record["variants"]) == {VARIANT_A_ID, VARIANT_B_ID}
    assert record["stages"]["match"]["shared_across_variants"] is True
    assert record["stages"]["verify_matches"]["shared_across_variants"] is True
    assert record["stages"]["select_control_points"]["shared_across_variants"] is True
    verified = record["stages"]["verify_matches"]["verified_inlier_count"]
    control_points = record["stages"]["select_control_points"]["control_point_count"]
    for variant_id, arm in record["variants"].items():
        assert arm["status"] == "completed", f"{variant_id}: {arm.get('failure')}"
        assert arm["matcher_id"] == "sift"
        assert arm["uses_shared_correspondences"] is True
        assert arm["uses_shared_control_points"] is True
        assert arm["select_control_points"]["control_point_count"] == control_points
        assert "coordinates_changed_count" in arm["refine_points"]
        assert "mean_displacement_pixels" in arm["refine_points"]
        assert "max_displacement_pixels" in arm["refine_points"]
        assert "points_before" in arm["refine_points"]
        assert "points_after" in arm["refine_points"]
        assert "unselected_verified_checkpoints" in arm
        assert "control_point_held_out" in arm
        assert arm["evaluate"]["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
        assert arm["runtime_seconds"]["refine_points"] >= 0
    assert verified >= 0


def test_variant_a_is_identity_and_does_not_move_coordinates(synthetic_record) -> None:
    arm = synthetic_record["variants"][VARIANT_A_ID]
    assert arm["method_id"] == METHOD_IDENTITY
    assert arm["refine_points"]["method_id"] == METHOD_IDENTITY
    assert arm["refine_points"]["coordinates_changed_count"] == 0
    assert arm["zncc_acceptance"]["available"] is False


def test_variant_b_uses_existing_zncc_callable(synthetic_record) -> None:
    arm = synthetic_record["variants"][VARIANT_B_ID]
    assert arm["method_id"] == METHOD_ZNCC
    assert arm["refine_points"]["method_id"] == METHOD_ZNCC
    assert "accepted_count" in arm["zncc_acceptance"]
    assert "rejected_count" in arm["zncc_acceptance"]


def test_interpretation_never_claims_independent_accuracy(synthetic_record) -> None:
    interpretation = synthetic_record["interpretation"]
    assert interpretation["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["independent_validation_status"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["coordinate_change_is_not_accuracy"] is True
    assert interpretation["matcher_derived_held_out_is_not_ground_truth"] is True
    assert interpretation["four_point_dlt_residuals_are_not_accuracy"] is True
    if interpretation["hypothesis_supported"] is True:
        assert interpretation["coordinates_changed"] is True
        assert interpretation["held_out_improved"] is True
        assert interpretation["held_out_comparable"] is True
    if interpretation["coordinates_changed"] and not interpretation["held_out_improved"]:
        assert interpretation["hypothesis_supported"] is False


def test_comparison_table_has_one_row_per_variant(synthetic_record) -> None:
    rows = synthetic_record["comparison"]["rows"]
    assert [row["variant"] for row in rows] == [VARIANT_A_ID, VARIANT_B_ID]
    assert [row["method_id"] for row in rows] == [METHOD_IDENTITY, METHOD_ZNCC]
    for row in rows:
        assert "verified_inliers" in row
        assert "control_point_count" in row
        assert "coordinates_changed_count" in row
        assert "mean_displacement_pixels" in row
        assert "max_displacement_pixels" in row
        assert "unselected_checkpoint_rmse" in row
        assert "runtime_seconds" in row


def test_missing_data_root_is_reported_not_guessed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    with pytest.raises(Exp005Error, match=DATA_ROOT_ENV):
        run_exp005(data_root=None, output_dir=tmp_path, record_path=tmp_path / "x.json")
