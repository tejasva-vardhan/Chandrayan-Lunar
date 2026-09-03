"""EXP-004 orchestration tests on synthetic products.

These run the three representation variants without the external dataset.
They are not lunar accuracy evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.ingestion import DATA_ROOT_ENV
from src.io.exp004.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    REPRESENTATION_GRADIENT,
    REPRESENTATION_INTENSITY,
    REPRESENTATION_STRUCTURAL,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
)
from src.io.exp004.run import Exp004Error, run_exp004, run_exp004_from_products
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
    tmp_path = tmp_path_factory.mktemp("exp004")
    source_array = _texture()
    reference_array = np.roll(source_array, _SHIFT, axis=1)
    source = _product(
        tmp_path, "synthetic-ohrc", source_array, "OHRC", "Chandrayaan-2", 1.0
    )
    reference = _product(
        tmp_path, "synthetic-lroc", reference_array, "LRO_NAC", "LRO", 2.0
    )
    return run_exp004_from_products(
        source,
        reference,
        output_dir=tmp_path / "out",
        record_path=tmp_path / "pair_01_equatorial.json",
    )


def test_all_variants_run_and_record_required_metrics(synthetic_record) -> None:
    record = synthetic_record

    assert record["status"] == "completed"
    assert set(record["variants"]) == {VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID}
    for variant_id, arm in record["variants"].items():
        assert arm["status"] == "completed", f"{variant_id}: {arm.get('failure')}"
        assert arm["matcher_id"] == "sift"
        assert "verified_inlier_count" in arm["verify_matches"]
        assert "inlier_ratio" in arm["verify_matches"]
        assert "verified_match_coverage" in arm["spatial_distribution"]
        assert "control_point_count" in arm["select_control_points"]
        assert "transform_fitted" in arm["register"]
        assert "outcome" in arm["refine_points"]
        assert arm["runtime_seconds"]["match"] > 0
        assert arm["evaluate"]["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED


def test_variants_change_representation_not_matching_view_scale(synthetic_record) -> None:
    record = synthetic_record
    variant_a = record["variants"][VARIANT_A_ID]
    variant_b = record["variants"][VARIANT_B_ID]
    variant_c = record["variants"][VARIANT_C_ID]

    assert variant_a["generate_representation"]["representation_id"] == REPRESENTATION_INTENSITY
    assert variant_b["generate_representation"]["representation_id"] == REPRESENTATION_GRADIENT
    assert variant_c["generate_representation"]["representation_id"] == REPRESENTATION_STRUCTURAL
    assert variant_a["uses_frozen_generate_representation"] is True
    assert variant_a["uses_original_pair_for_representation"] is True
    assert variant_b["uses_original_pair_for_representation"] is False
    assert variant_c["uses_original_pair_for_representation"] is False

    assert variant_a["generate_representation"]["source_matching_view"]["stride"] == 1
    assert variant_a["generate_representation"]["reference_matching_view"]["stride"] == 1
    assert variant_b["generate_representation"]["source_matching_view"]["stride"] == 1
    assert variant_b["generate_representation"]["reference_matching_view"]["stride"] == 1
    assert variant_c["generate_representation"]["source_matching_view"]["stride"] == 1
    assert variant_c["generate_representation"]["reference_matching_view"]["stride"] == 1
    assert record["interpretation"]["matching_view_strides_held_fixed"] is True
    assert record["interpretation"]["representation_changed"] is True
    assert record["interpretation"]["independent_variable_applied"] is True


def test_interpretation_never_claims_independent_accuracy(synthetic_record) -> None:
    interpretation = synthetic_record["interpretation"]
    assert interpretation["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["four_point_dlt_residuals_are_not_accuracy"] is True
    assert interpretation["primary_metric"] == "verified_inlier_count"
    assert "hypothesis_supported" in interpretation
    assert "verified_inliers_improved" in interpretation


def test_comparison_table_has_one_row_per_variant(synthetic_record) -> None:
    rows = synthetic_record["comparison"]["rows"]
    assert [row["variant"] for row in rows] == [VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID]
    assert [row["representation_id"] for row in rows] == [
        REPRESENTATION_INTENSITY,
        REPRESENTATION_GRADIENT,
        REPRESENTATION_STRUCTURAL,
    ]
    for row in rows:
        assert "stride_source" in row
        assert "stride_reference" in row
        assert "raw_matches" in row
        assert "verified_inliers" in row
        assert "inlier_ratio" in row
        assert "spatial_coverage" in row
        assert "control_point_count" in row
        assert "transform_status" in row
        assert "refinement_status" in row
        assert "runtime_seconds" in row


def test_missing_data_root_is_reported_not_guessed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    with pytest.raises(Exp004Error, match=DATA_ROOT_ENV):
        run_exp004(data_root=None, output_dir=tmp_path, record_path=tmp_path / "x.json")
