from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.ingestion import (
    ingest_lroc_pds3_product,
    read_lroc_pds3_label,
)

REAL_PRODUCT_NAMES = (
    "M150368601RC.IMG",
    "M1504316436RC.IMG",
    "M106979273RC.IMG",
    "M175153469LC.IMG",
)


def _discover_expected_products(data_root: Path) -> list[Path]:
    discovered: list[Path] = []
    for name in REAL_PRODUCT_NAMES:
        matches = sorted(path for path in data_root.rglob(name) if path.is_file())
        if matches:
            discovered.append(matches[0])
    return discovered


@pytest.mark.wiring
def test_real_lroc_demo_products_when_available() -> None:
    root = os.environ.get("LUNAR_DEMO_DATA_ROOT")
    if not root:
        pytest.skip("set LUNAR_DEMO_DATA_ROOT to enable optional real-data ingestion checks")

    data_root = Path(root)
    available = _discover_expected_products(data_root)
    if not available:
        pytest.skip("no demo LROC PDS3 products found under LUNAR_DEMO_DATA_ROOT")

    for path in available:
        label = read_lroc_pds3_label(path)
        product = ingest_lroc_pds3_product(path)
        assert label.target_name == "MOON"
        assert label.instrument_name == "LUNAR RECONNAISSANCE ORBITER CAMERA"
        assert product.product_id == path.stem
        assert product.dimensions is not None
        assert product.dimensions.height_px == label.lines
        assert product.dimensions.width_px == label.line_samples
        assert product.raster_uri is not None
        assert product.mask_uri is not None
