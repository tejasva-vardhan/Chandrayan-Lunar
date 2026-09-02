"""Optional real-data ingestion checks for the EXP-000 pair.

These tests require the external demo dataset configured through
``CHANDRAYAN_DATA_ROOT``. They skip when that variable is unset.

They do not run SIFT, registration, or the scientific pipeline. They only
validate that the existing ingestion layer can load the named products.

Never commit the raw products into Git.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.ingestion import (
    DATA_ROOT_ENV,
    PAIR_01_LROC_ID,
    PAIR_01_OHRC_ID,
    DataRootError,
    configured_data_root,
    find_product,
    ingest_product,
    mmap_product_array,
    read_lroc_pds3_label,
    read_lunar_product_window,
)
from src.models import LunarProduct


def _data_root_or_skip() -> Path:
    try:
        root = configured_data_root()
    except DataRootError as exc:
        pytest.fail(str(exc))
    if root is None:
        pytest.skip(
            f"Real dataset not configured. Set {DATA_ROOT_ENV} to the external "
            "folder that contains the EXP-000 OHRC and LROC products."
        )
    return root


@pytest.fixture(autouse=True)
def _redirect_derived_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path / "manifests"))
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path / "processed"))


def _require_product(root: Path, product_id: str) -> Path:
    path = find_product(root, product_id)
    if path is None:
        pytest.skip(f"{product_id} not found under {DATA_ROOT_ENV}={root}")
    return path


@pytest.mark.wiring
def test_pair_01_lroc_pds3_ingestion() -> None:
    root = _data_root_or_skip()
    path = _require_product(root, PAIR_01_LROC_ID)
    label = read_lroc_pds3_label(path)
    product = ingest_product(path)

    assert label.target_name == "MOON"
    assert label.instrument_name == "LUNAR RECONNAISSANCE ORBITER CAMERA"
    assert label.sample_bits == 16
    assert label.sample_type == "LSB_INTEGER"
    assert label.null_value == -32768
    assert -32766 in label.saturation_values
    assert -32765 in label.saturation_values
    _assert_ingested_raster(product, expected_height=label.lines, expected_width=label.line_samples)
    assert product.instrument == "LRO_NAC"
    assert product.product_id == PAIR_01_LROC_ID
    assert product.provenance is not None
    assert product.provenance.source_uri == path.name
    assert Path(product.provenance.source_uri).is_absolute() is False
    assert np.load(product.raster_uri, mmap_mode="r").dtype == np.dtype("<i2")
    _assert_window_access(product)


@pytest.mark.wiring
def test_pair_01_ohrc_pds4_ingestion() -> None:
    root = _data_root_or_skip()
    path = _require_product(root, PAIR_01_OHRC_ID)
    product = ingest_product(path)

    assert product.instrument == "OHRC"
    assert PAIR_01_OHRC_ID.lower() in product.product_id.lower()
    _assert_ingested_raster(product)
    assert product.provenance is not None
    assert product.provenance.source_uri is not None
    assert Path(product.provenance.source_uri).is_absolute() is False
    _assert_window_access(product)


def _assert_ingested_raster(
    product: LunarProduct,
    expected_height: int | None = None,
    expected_width: int | None = None,
) -> None:
    assert isinstance(product, LunarProduct)
    assert product.dimensions is not None
    assert product.raster_uri is not None
    assert product.mask_uri is not None
    if expected_height is not None:
        assert product.dimensions.height_px == expected_height
    if expected_width is not None:
        assert product.dimensions.width_px == expected_width

    raster = mmap_product_array(product.raster_uri)
    mask = mmap_product_array(product.mask_uri)
    assert raster.shape == (product.dimensions.height_px, product.dimensions.width_px)
    assert mask.shape == raster.shape
    if product.valid_pixel_ratio is not None:
        assert 0.0 <= product.valid_pixel_ratio <= 1.0


def _assert_window_access(product: LunarProduct) -> None:
    assert product.dimensions is not None
    assert product.raster_uri is not None
    assert Path(product.raster_uri).suffix.lower() == ".npy"
    mapped = mmap_product_array(product.raster_uri)
    height = min(32, product.dimensions.height_px)
    width = min(32, product.dimensions.width_px)
    window = read_lunar_product_window(product, 0, 0, height, width)
    assert window.shape == (height, width)
    full_nbytes = (
        product.dimensions.height_px * product.dimensions.width_px * window.dtype.itemsize
    )
    if full_nbytes > window.nbytes:
        assert window.nbytes < full_nbytes
    # Matching-view stride decimation requires a memory-mapped .npy handle.
    assert isinstance(mapped, np.memmap)
    pixel_count = product.dimensions.height_px * product.dimensions.width_px
    max_pixels_per_image = 4_194_304
    if pixel_count > max_pixels_per_image:
        stride = int(math.ceil(math.sqrt(pixel_count / max_pixels_per_image)))
        assert stride > 1
        matching_h = (product.dimensions.height_px + stride - 1) // stride
        matching_w = (product.dimensions.width_px + stride - 1) // stride
        assert matching_h * matching_w < pixel_count
