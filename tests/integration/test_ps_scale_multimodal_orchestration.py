"""PS-SCALE-MULTIMODAL orchestration on synthetic products."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.io.ps_scale_multimodal.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    REPRESENTATION_CROSS_SENSOR,
    REPRESENTATION_INTENSITY,
    VARIANT_A_ID,
    VARIANT_B_ID,
    VARIANT_C_ID,
)
from src.io.ps_scale_multimodal.run import run_ps_scale_multimodal_from_products
from src.matching.coarse_to_fine import MATCHER_ID
from src.models.common import ImageDimensions, Provenance
from src.models.lunar_product import LunarProduct
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
)

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
    tmp_path = tmp_path_factory.mktemp("ps-scale-multimodal")
    source_array = _texture()
    # Mild gain/bias change to emulate cross-sensor radiometry without
    # destroying overlap geometry.
    reference_array = np.clip(np.roll(source_array, _SHIFT, axis=1) * 0.85 + 0.05, 0, 1)
    source = _product(tmp_path, "synthetic-ohrc", source_array, "OHRC", "Chandrayaan-2", 0.28)
    reference = _product(tmp_path, "synthetic-lroc", reference_array, "LRO_NAC", "LRO", None)
    return run_ps_scale_multimodal_from_products(
        source,
        reference,
        output_dir=tmp_path / "out",
        record_path=tmp_path / "pair_02_mid_equatorial.json",
    )


def test_three_variants_complete(synthetic_record) -> None:
    record = synthetic_record
    assert record["status"] == "completed"
    assert set(record["variants"]) == {VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID}
    for variant_id, arm in record["variants"].items():
        assert arm["status"] == "completed", f"{variant_id}: {arm.get('failure')}"
        assert arm["matcher_id"] == MATCHER_ID
        assert arm["evaluate"]["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED


def test_independent_variables_applied(synthetic_record) -> None:
    variants = synthetic_record["variants"]
    assert variants[VARIANT_A_ID]["scale_policy"] == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert variants[VARIANT_B_ID]["scale_policy"] == SCALE_POLICY_COMMON_PHYSICAL_GSD
    assert variants[VARIANT_C_ID]["scale_policy"] == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    assert variants[VARIANT_A_ID]["match"]["representation_id"] == REPRESENTATION_INTENSITY
    assert variants[VARIANT_B_ID]["match"]["representation_id"] == REPRESENTATION_INTENSITY
    assert variants[VARIANT_C_ID]["match"]["representation_id"] == REPRESENTATION_CROSS_SENSOR


def test_gsd_context_and_interpretation_present(synthetic_record) -> None:
    gsd = synthetic_record["stages"]["gsd_scale_context"]
    assert gsd["source_gsd_meters"] == 0.28
    assert gsd["reference_gsd_meters"] == 0.5
    assert gsd["native_gsd_ratio_source_over_reference"] == pytest.approx(0.56)
    interpretation = synthetic_record["interpretation"]
    assert "scale" in interpretation
    assert "cross_sensor" in interpretation
    assert interpretation["independent_validation_status"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
    assert interpretation["cross_sensor"]["modality_claim"].startswith("cross-instrument")
