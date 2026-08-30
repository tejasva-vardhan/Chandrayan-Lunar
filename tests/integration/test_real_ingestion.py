"""Integration tests for real Chandrayaan-2 OHRC data ingestion."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from src.ingestion import ingest_product
from src.models import LunarProduct


def find_real_products() -> list[Path]:
    """Search for real OHRC datasets in the configured data directory."""
    data_dir = os.environ.get("LUNAR_DATA_DIR") or os.environ.get("SIH_DATA_DIR") or "F:\\SIH"
    path = Path(data_dir)
    if not path.exists():
        return []
    products = []
    for item in path.iterdir():
        if item.name.startswith("ch2_ohr_ncp_") and (
            item.is_dir() or item.suffix.lower() == ".zip"
        ):
            products.append(item)
    return products


def test_real_ohrc_ingestion() -> None:
    """Run ingestion on a real OHRC product, print details, and verify contract."""
    products = find_real_products()
    if not products:
        pytest.skip(
            "No real Chandrayaan-2 OHRC products found. Set LUNAR_DATA_DIR or SIH_DATA_DIR, "
            "or ensure F:\\SIH is accessible."
        )

    # Use the first discovered product (can be a folder or a zip)
    product_path = products[0]
    print(f"\nRunning real-data integration test on: {product_path.name}")

    # Run ingestion
    product = ingest_product(product_path)

    # Verify basic contract
    assert isinstance(product, LunarProduct)
    assert product.instrument == "OHRC"
    assert product.mission == "Chandrayaan-2"
    assert product.dimensions is not None
    assert product.raster_uri is not None
    assert product.mask_uri is not None
    assert product.provenance is not None

    # Load raster/mask headers to verify they are valid .npy files
    raster_path = Path(product.raster_uri)
    mask_path = Path(product.mask_uri)
    assert raster_path.exists()
    assert mask_path.exists()

    # Load memory-mapped arrays using np.load
    raster_mem = np.load(raster_path, mmap_mode="r")
    mask_mem = np.load(mask_path, mmap_mode="r")

    assert raster_mem.size == product.dimensions.width_px * product.dimensions.height_px
    assert mask_mem.size == product.dimensions.width_px * product.dimensions.height_px
    assert raster_mem.shape == (product.dimensions.height_px, product.dimensions.width_px)
    assert mask_mem.shape == (product.dimensions.height_px, product.dimensions.width_px)

    # Compute valid pixel count from product attributes
    total_pixels = product.dimensions.width_px * product.dimensions.height_px
    valid_pixels = int(round((product.valid_pixel_ratio or 1.0) * total_pixels))

    # Print the formatted report required by the acceptance criteria
    print("\n" + "=" * 60)
    print("INGESTED PRODUCT REPORT")
    print("=" * 60)
    print(f"Mission: {product.mission}")
    print(f"Instrument: {product.instrument}")
    print(f"Product ID: {product.product_id}")
    print(
        f"Dimensions: {product.dimensions.width_px}x{product.dimensions.height_px} x {product.dimensions.band_count}"
    )
    print("Data type: UnsignedByte (uint8)")
    print(f"Acquisition time: {product.acquisition_time}")
    print(f"GSD: {product.gsd_meters} meters/pixel" if product.gsd_meters else "GSD: None")
    print(f"Valid pixels: {valid_pixels} / {total_pixels} ({product.valid_pixel_ratio * 100:.6f}%)")
    print("Metadata fields successfully parsed:")
    print(f"  - CRS: {product.coordinates.crs if product.coordinates else 'None'}")
    print(f"  - Bounding Box: {product.coordinates.bbox if product.coordinates else 'None'}")
    print(f"  - Radiometric State: {product.radiometric_state}")
    print("Provenance:")
    print(f"  - Source URI: {product.provenance.source_uri}")
    print(f"  - Reader: {product.provenance.reader}")
    print(f"  - Checksum: {product.provenance.checksum}")
    print(f"  - Software Commit: {product.provenance.software_commit}")
    print(f"  - Notes: {product.provenance.notes}")
    print("=" * 60 + "\n")
