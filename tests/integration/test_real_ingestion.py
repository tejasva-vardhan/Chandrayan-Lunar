"""Integration test for real Chandrayaan-2 OHRC data ingestion.

This test is OPTIONAL and requires a locally downloaded OHRC product.
Configure the data directory via the environment variable LUNAR_DATA_DIR
(e.g. set LUNAR_DATA_DIR=D:\\mydata before running pytest).

The test skips cleanly if the configured directory does not exist or contains
no recognised OHRC products.  It does NOT fall back to any hard-coded path.

Never commit the raw OHRC datasets into the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from src.ingestion import ingest_product
from src.models import LunarProduct


def _get_data_dir() -> Path | None:
    """Return the configured external OHRC data directory, or None."""
    raw = os.environ.get("LUNAR_DATA_DIR") or os.environ.get("SIH_DATA_DIR")
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


def find_real_products(data_dir: Path) -> list[Path]:
    """Search for real OHRC datasets in *data_dir*."""
    products = []
    for item in data_dir.iterdir():
        if item.name.startswith("ch2_ohr_ncp_") and (
            item.is_dir() or item.suffix.lower() == ".zip"
        ):
            products.append(item)
    return products


def test_real_ohrc_ingestion() -> None:
    """Run ingestion on a real OHRC product and validate the pipeline contract.

    Skip if the external dataset is not configured or unavailable.
    """
    data_dir = _get_data_dir()
    if data_dir is None:
        pytest.skip(
            "Real OHRC dataset not configured. "
            "Set the LUNAR_DATA_DIR environment variable to a directory "
            "containing ch2_ohr_ncp_* products to enable this test."
        )

    products = find_real_products(data_dir)
    if not products:
        pytest.skip(
            f"No ch2_ohr_ncp_* products found in LUNAR_DATA_DIR={data_dir}. "
            "Download OHRC products from ISRO PRADAN/ISSDC before running this test."
        )

    product_path = products[0]
    print(f"\nRunning real-data integration test on: {product_path.name}")

    product = ingest_product(product_path)

    # ── Contract checks ──────────────────────────────────────────────────────
    assert isinstance(product, LunarProduct)
    # instrument may be None for products where the label omits the Instrument
    # component, so we do NOT assert == "OHRC" unconditionally.
    assert product.dimensions is not None
    assert product.raster_uri is not None
    assert product.mask_uri is not None
    assert product.provenance is not None

    # Provenance must not embed absolute machine-specific paths
    source_uri = product.provenance.source_uri or ""
    assert os.sep not in source_uri or not Path(source_uri).is_absolute(), (
        "Provenance source_uri must not be an absolute machine path"
    )

    # ── Array sanity checks ──────────────────────────────────────────────────
    raster_path = Path(product.raster_uri)
    mask_path = Path(product.mask_uri)
    assert raster_path.exists()
    assert mask_path.exists()

    raster_mem = np.load(raster_path, mmap_mode="r")
    mask_mem = np.load(mask_path, mmap_mode="r")

    expected_size = product.dimensions.width_px * product.dimensions.height_px
    assert raster_mem.size == expected_size
    assert mask_mem.size == expected_size
    assert raster_mem.shape == (product.dimensions.height_px, product.dimensions.width_px)
    assert mask_mem.shape == (product.dimensions.height_px, product.dimensions.width_px)

    # ── Print report ─────────────────────────────────────────────────────────
    total_pixels = product.dimensions.width_px * product.dimensions.height_px
    valid_pixels = int(round((product.valid_pixel_ratio or 1.0) * total_pixels))

    print("\n" + "=" * 60)
    print("INGESTED PRODUCT REPORT")
    print("=" * 60)
    print(f"Mission:          {product.mission}")
    print(f"Instrument:       {product.instrument}")
    print(f"Product ID:       {product.product_id}")
    w = product.dimensions.width_px
    h = product.dimensions.height_px
    b = product.dimensions.band_count
    print(f"Dimensions:       {w}x{h} x {b}")
    print(f"Raster dtype:     {raster_mem.dtype}")
    print(f"Acquisition time: {product.acquisition_time}")
    if product.gsd_meters is not None:
        print(f"GSD:              {product.gsd_meters} m/pixel")
    else:
        print("GSD:              unknown (unit not declared in label)")
    vr = product.valid_pixel_ratio
    print(f"Valid pixels:     {valid_pixels} / {total_pixels} ({(vr or 0) * 100:.6f}%)")
    if product.coordinates:
        print(f"CRS:              {product.coordinates.crs}")
        print(f"Bounding Box:     {product.coordinates.bbox}")
    else:
        print("Coordinates:      None")
    print(f"Radiometric state:{product.radiometric_state}")
    print("Provenance:")
    print(f"  Source ref:     {product.provenance.source_uri}")
    print(f"  Reader:         {product.provenance.reader}")
    print(f"  Checksum:       {product.provenance.checksum}")
    print(f"  Commit:         {product.provenance.software_commit}")
    print(f"  Notes:          {product.provenance.notes}")
    print("=" * 60 + "\n")
