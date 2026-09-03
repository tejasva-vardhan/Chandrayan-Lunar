"""PS-closing correspondence orchestration on synthetic products."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.io.ps_correspondence.config import (
    INDEPENDENT_ACCURACY_NOT_VALIDATED,
    PROTOCOL_COARSE_TO_FINE,
    PROTOCOL_SINGLE_VIEW,
    VARIANT_A_ID,
    VARIANT_B_ID,
)
from src.io.ps_correspondence.run import run_ps_correspondence_from_products
from src.matching.coarse_to_fine import MATCHER_ID
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
    tmp_path = tmp_path_factory.mktemp("ps-correspondence")
    source_array = _texture()
    reference_array = np.roll(source_array, _SHIFT, axis=1)
    source = _product(tmp_path, "synthetic-ohrc", source_array, "OHRC", "Chandrayaan-2", 1.0)
    reference = _product(tmp_path, "synthetic-lroc", reference_array, "LRO_NAC", "LRO", 1.0)
    return run_ps_correspondence_from_products(
        source,
        reference,
        output_dir=tmp_path / "out",
        record_path=tmp_path / "pair_02_mid_equatorial.json",
    )


def test_both_variants_complete_on_shared_representation(synthetic_record) -> None:
    record = synthetic_record
    assert record["status"] == "completed"
    assert set(record["variants"]) == {VARIANT_A_ID, VARIANT_B_ID}
    assert record["stages"]["generate_representation"]["shared_across_variants"] is True
    for variant_id, arm in record["variants"].items():
        assert arm["status"] == "completed", f"{variant_id}: {arm.get('failure')}"
        assert arm["uses_shared_representation"] is True
        assert arm["evaluate"]["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
        assert arm["runtime_seconds"]["match"] >= 0
        assert "geometry_inspection" in arm


def test_variant_a_is_frozen_single_view_sift(synthetic_record) -> None:
    arm = synthetic_record["variants"][VARIANT_A_ID]
    assert arm["protocol_id"] == PROTOCOL_SINGLE_VIEW
    assert arm["uses_frozen_match_surface"] is True
    assert arm["matcher_id"] == "sift"


def test_variant_b_is_coarse_to_fine_not_a_matcher_swap(synthetic_record) -> None:
    arm = synthetic_record["variants"][VARIANT_B_ID]
    control = synthetic_record["variants"][VARIANT_A_ID]
    assert arm["protocol_id"] == PROTOCOL_COARSE_TO_FINE
    assert arm["uses_frozen_match_surface"] is False
    assert arm["matcher_id"] == MATCHER_ID
    assert arm["match"]["raw_match_count"] >= control["match"]["raw_match_count"]
