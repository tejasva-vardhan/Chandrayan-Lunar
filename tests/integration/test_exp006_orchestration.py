"""EXP-006 orchestration tests on synthetic products.

These run one-way SIFT vs reciprocal SIFT without the external dataset.
They are not lunar accuracy evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.ingestion import DATA_ROOT_ENV
from src.io.exp006.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PROTOCOL_ONE_WAY,
    PROTOCOL_RECIPROCAL,
    VARIANT_A_ID,
    VARIANT_B_ID,
)
from src.io.exp006.run import Exp006Error, run_exp006, run_exp006_from_products
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
    tmp_path = tmp_path_factory.mktemp("exp006")
    source_array = _texture()
    reference_array = np.roll(source_array, _SHIFT, axis=1)
    source = _product(
        tmp_path, "synthetic-ohrc", source_array, "OHRC", "Chandrayaan-2", 1.0
    )
    reference = _product(
        tmp_path, "synthetic-lroc", reference_array, "LRO_NAC", "LRO", 1.0
    )
    return run_exp006_from_products(
        source,
        reference,
        output_dir=tmp_path / "out",
        record_path=tmp_path / "pair_02_mid_equatorial.json",
    )


def test_both_variants_run_on_shared_representation(synthetic_record) -> None:
    record = synthetic_record

    assert record["status"] == "completed"
    assert set(record["variants"]) == {VARIANT_A_ID, VARIANT_B_ID}
    assert record["stages"]["generate_representation"]["shared_across_variants"] is True
    for variant_id, arm in record["variants"].items():
        assert arm["status"] == "completed", f"{variant_id}: {arm.get('failure')}"
        assert arm["matcher_id"] == "sift"
        assert arm["uses_shared_representation"] is True
        assert "spatial_distribution" in arm
        assert "residual_distribution" in arm["verify_matches"]
        assert "repeat_stability" in arm["match"]
        assert arm["evaluate"]["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
        assert arm["runtime_seconds"]["match"] >= 0


def test_variant_a_is_frozen_one_way_match(synthetic_record) -> None:
    arm = synthetic_record["variants"][VARIANT_A_ID]
    assert arm["protocol_id"] == PROTOCOL_ONE_WAY
    assert arm["require_reciprocal"] is False
    assert arm["uses_frozen_match_surface"] is True


def test_variant_b_is_reciprocal_sift_not_a_new_matcher(synthetic_record) -> None:
    arm = synthetic_record["variants"][VARIANT_B_ID]
    assert arm["protocol_id"] == PROTOCOL_RECIPROCAL
    assert arm["require_reciprocal"] is True
    assert arm["uses_frozen_match_surface"] is False
    assert arm["matcher_id"] == "sift"
    one_way = synthetic_record["variants"][VARIANT_A_ID]["match"]["raw_match_count"]
    reciprocal = arm["match"]["raw_match_count"]
    assert reciprocal <= one_way


def test_interpretation_never_claims_independent_accuracy(synthetic_record) -> None:
    interpretation = synthetic_record["interpretation"]
    assert interpretation["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["independent_validation_status"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["matcher_derived_held_out_is_not_ground_truth"] is True
    assert interpretation["four_point_dlt_residuals_are_not_accuracy"] is True
    assert interpretation["raw_match_count_is_not_success"] is True
    assert interpretation["decision"] in {
        "SUPPORTED",
        "NOT SUPPORTED",
        "INDETERMINATE",
    }
    if interpretation["decision"] == "SUPPORTED":
        assert interpretation["quality_improved"] is True
        assert interpretation["spatial_maintained_or_improved"] is True
        assert interpretation["transform_stable"] is True
        assert interpretation["runtime_acceptable"] is True


def test_missing_data_root_is_a_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    with pytest.raises(Exp006Error, match=DATA_ROOT_ENV):
        run_exp006(data_root=None, output_dir=tmp_path / "out", record_dir=tmp_path)
