"""Real-data integration tests for OHRC PDS4 and LROC PDS3 ingestion.

These tests run ONLY when the environment variable LUNAR_DEMO_DIR points to a
directory containing the four EXP-000 demo pairs produced for SIH26166.

If the variable is unset or the expected products are missing, each test skips
cleanly — it never fabricates success from absent data.

Expected directory structure under $LUNAR_DEMO_DIR::

    pair_01_equatorial/
        ohrc/ch2_ohr_ncp_20210402T0546284043_d_img_d18/   (PDS4 directory)
        lroc/M150368601RC.IMG                              (PDS3 embedded label)
    pair_02_mid_equatorial/
        ohrc/ch2_ohr_ncp_20250612T2229094979_d_img_d18/
        lroc/M1504316436RC.IMG
    pair_03_south_mid/
        ohrc/ch2_ohr_ncp_20230302T1959055531_d_img_n18/
        lroc/M106979273RC.IMG
    pair_04_south_pole/
        ohrc/ch2_ohr_ncp_20260103T1005176450_d_img_d18/
        lroc/M175153469LC.IMG

Reference manifests: data/manifests/demo_pair_*.json

IMPORTANT
---------
Presence of OHRC and LROC products within the same pair directory does NOT
constitute a scientifically verified spatially overlapping pair. No overlap
claims are made or tested here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from src.ingestion import ingest_product, load_lroc_pds3_raster, window_crop_ohrc
from src.ingestion.lroc_pds3 import read_lroc_pds3_label
from src.ingestion.pds_reader import ingest_from_pds, parse_metadata_file, sanitize_filename
from src.models import LunarProduct

# ── helpers ───────────────────────────────────────────────────────────────────


def _demo_dir() -> Path | None:
    """Return the configured LUNAR_DEMO_DIR, or None if absent/non-existent."""
    raw = os.environ.get("LUNAR_DEMO_DIR")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def _ohrc_dir(demo: Path, pair: str, stem: str) -> Path:
    return demo / pair / "ohrc" / stem


def _lroc_img(demo: Path, pair: str, product_id: str) -> Path:
    return demo / pair / "lroc" / f"{product_id}.IMG"


def _redirect_outputs(tmp_path: Path) -> dict[str, str | None]:
    """Set LUNAR_OUTPUT_DIR and LUNAR_MANIFEST_DIR; return old values for restore."""
    backup = {
        "LUNAR_OUTPUT_DIR": os.environ.get("LUNAR_OUTPUT_DIR"),
        "LUNAR_MANIFEST_DIR": os.environ.get("LUNAR_MANIFEST_DIR"),
    }
    os.environ["LUNAR_OUTPUT_DIR"] = str(tmp_path)
    os.environ["LUNAR_MANIFEST_DIR"] = str(tmp_path)
    return backup


def _restore_outputs(backup: dict[str, str | None]) -> None:
    for key, val in backup.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


# ── parametrize data ──────────────────────────────────────────────────────────

# (pair_dir, ohrc_stem, expected_height, expected_width, expected_gsd_m)
_OHRC_PRODUCTS = [
    ("pair_01_equatorial", "ch2_ohr_ncp_20210402T0546284043_d_img_d18", 78175, 12000, 0.26),
    ("pair_02_mid_equatorial", "ch2_ohr_ncp_20250612T2229094979_d_img_d18", 79780, 12000, 0.28),
    ("pair_03_south_mid", "ch2_ohr_ncp_20230302T1959055531_d_img_n18", 93692, 12000, 0.25),
    ("pair_04_south_pole", "ch2_ohr_ncp_20260103T1005176450_d_img_d18", 101075, 12000, 0.25),
]

# (pair_dir, lroc_product_id, expected_height_or_None, expected_width_or_None)
_LROC_PRODUCTS = [
    ("pair_01_equatorial", "M150368601RC", 52224, 5064),
    ("pair_02_mid_equatorial", "M1504316436RC", None, None),
    ("pair_03_south_mid", "M106979273RC", None, None),
    ("pair_04_south_pole", "M175153469LC", None, None),
]


# ── OHRC: label-only metadata tests ──────────────────────────────────────────


@pytest.mark.parametrize("pair,stem,exp_h,exp_w,exp_gsd", _OHRC_PRODUCTS)
def test_ohrc_metadata_parsed_from_label(
    pair: str, stem: str, exp_h: int, exp_w: int, exp_gsd: float
) -> None:
    """Parse PDS4 XML label; does NOT stream binary pixel data."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    ohrc_path = _ohrc_dir(demo, pair, stem)
    if not ohrc_path.is_dir():
        pytest.skip(f"OHRC product not found: {ohrc_path}")

    xml_paths = [
        p
        for p in (ohrc_path / "data").rglob("*.xml")
        if "browse" not in str(p).lower() and "geometry" not in str(p).lower()
    ]
    assert xml_paths, f"No data XML found under {ohrc_path}/data"

    md = parse_metadata_file(xml_paths[0])

    assert md["instrument"] == "OHRC"
    assert md["mission"] == "Chandrayaan-2"
    assert md["dimensions"] is not None
    assert md["dimensions"].width_px == exp_w
    assert md["dimensions"].height_px == exp_h
    # GSD must be populated from the "m/pixel" unit in real labels
    assert md["gsd_meters"] is not None, (
        "gsd_meters is None — check that unit='m/pixel' is in _METRE_UNITS"
    )
    assert md["gsd_meters"] == pytest.approx(exp_gsd, abs=0.005)
    assert md["coordinates"] is not None
    assert md["coordinates"].crs is not None
    assert md["acquisition_time"] is not None
    assert md["radiometric_state"] == "Calibrated"
    # Real OHRC labels do not declare Special_Constants
    assert md["nodata_values"] is None


# ── OHRC: full streaming ingestion tests ──────────────────────────────────────


@pytest.mark.parametrize("pair,stem,exp_h,exp_w,exp_gsd", _OHRC_PRODUCTS)
def test_ohrc_full_ingestion(
    pair: str, stem: str, exp_h: int, exp_w: int, exp_gsd: float, tmp_path: Path
) -> None:
    """Full streaming ingestion — reads every pixel byte from disk."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    ohrc_path = _ohrc_dir(demo, pair, stem)
    if not ohrc_path.is_dir():
        pytest.skip(f"OHRC product not found: {ohrc_path}")

    backup = _redirect_outputs(tmp_path)
    try:
        product = ingest_from_pds(ohrc_path)
    finally:
        _restore_outputs(backup)

    _assert_ohrc_product(product, exp_h, exp_w, exp_gsd)


def _assert_ohrc_product(product: LunarProduct, exp_h: int, exp_w: int, exp_gsd: float) -> None:
    """Shared contract assertions for an ingested OHRC LunarProduct."""
    assert isinstance(product, LunarProduct)
    assert product.instrument == "OHRC"
    assert product.mission == "Chandrayaan-2"
    assert product.dimensions is not None
    assert product.dimensions.height_px == exp_h
    assert product.dimensions.width_px == exp_w
    assert product.dimensions.band_count == 1
    assert product.gsd_meters is not None
    assert product.gsd_meters == pytest.approx(exp_gsd, abs=0.005)
    assert product.coordinates is not None
    assert product.coordinates.crs is not None
    assert product.acquisition_time is not None
    assert product.radiometric_state == "Calibrated"
    assert product.provenance is not None
    # Provenance must not embed an absolute machine path
    src = product.provenance.source_uri or ""
    assert not Path(src).is_absolute(), f"source_uri must not be absolute: {src!r}"
    # Raster and mask files must exist on disk
    raster_path = Path(product.raster_uri)
    mask_path = Path(product.mask_uri)
    assert raster_path.exists()
    assert mask_path.exists()
    # Verify shapes via memory-map (no full copy into RAM)
    raster = np.load(raster_path, mmap_mode="r")
    mask = np.load(mask_path, mmap_mode="r")
    assert raster.shape == (exp_h, exp_w)
    assert mask.shape == (exp_h, exp_w)
    assert raster.dtype == np.dtype("uint8")
    assert mask.dtype == np.dtype(bool)
    # No NoData declared in PDS4 label → all pixels valid
    assert mask.all(), "All pixels must be valid when no Special_Constants declared"
    assert product.valid_pixel_ratio == pytest.approx(1.0, abs=1e-6)


# ── OHRC: window/crop test ────────────────────────────────────────────────────


@pytest.mark.parametrize("pair,stem,exp_h,exp_w,exp_gsd", _OHRC_PRODUCTS[:1])
def test_ohrc_window_crop(
    pair: str, stem: str, exp_h: int, exp_w: int, exp_gsd: float, tmp_path: Path
) -> None:
    """window_crop_ohrc returns correct shape without resampling."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    ohrc_path = _ohrc_dir(demo, pair, stem)
    if not ohrc_path.is_dir():
        pytest.skip(f"OHRC product not found: {ohrc_path}")

    backup = _redirect_outputs(tmp_path)
    try:
        product = ingest_from_pds(ohrc_path)
    finally:
        _restore_outputs(backup)

    row_start, row_end = 0, 1000
    raster_w, mask_w = window_crop_ohrc(product.raster_uri, product.mask_uri, row_start, row_end)

    assert raster_w.shape == (row_end - row_start, exp_w)
    assert mask_w.shape == (row_end - row_start, exp_w)
    # dtype unchanged — no scaling/resampling
    assert raster_w.dtype == np.dtype("uint8")
    # Out-of-bounds clip: large end is silently clipped to total height
    big_r, _ = window_crop_ohrc(product.raster_uri, product.mask_uri, 0, 10**9)
    assert big_r.shape[0] == exp_h


# ── OHRC: manifest test ───────────────────────────────────────────────────────


@pytest.mark.parametrize("pair,stem,exp_h,exp_w,exp_gsd", _OHRC_PRODUCTS[:1])
def test_ohrc_manifest_created(
    pair: str, stem: str, exp_h: int, exp_w: int, exp_gsd: float, tmp_path: Path
) -> None:
    """ingest_product() creates a manifest with correct fields and no machine paths."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    ohrc_path = _ohrc_dir(demo, pair, stem)
    if not ohrc_path.is_dir():
        pytest.skip(f"OHRC product not found: {ohrc_path}")

    backup = _redirect_outputs(tmp_path)
    try:
        product = ingest_product(ohrc_path)
    finally:
        _restore_outputs(backup)

    manifest_path = tmp_path / f"{sanitize_filename(product.product_id)}.json"
    assert manifest_path.exists()

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["product"]["instrument"] == "OHRC"
    assert data["product"]["gsd_meters"] == pytest.approx(exp_gsd, abs=0.005)
    assert data["processing_state"] == "ingested"

    # provenance.source_uri must NOT be an absolute machine path — it should
    # be only the product stem (e.g. "ch2_ohr_ncp_20210402T0546284043_d_img_d18").
    src_uri = data["product"]["provenance"]["source_uri"]
    assert not Path(src_uri).is_absolute(), (
        f"provenance.source_uri must not be an absolute path: {src_uri!r}"
    )
    # raster_uri and mask_uri are absolute paths to the derived outputs — that is
    # correct and expected. We do not assert they are non-absolute.


# ── LROC: label parsing tests ─────────────────────────────────────────────────


@pytest.mark.parametrize("pair,product_id,exp_h,exp_w", _LROC_PRODUCTS)
def test_lroc_label_parsed(
    pair: str, product_id: str, exp_h: int | None, exp_w: int | None
) -> None:
    """Parse the embedded PDS3 label from a real LROC .IMG file."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    img_path = _lroc_img(demo, pair, product_id)
    if not img_path.is_file():
        pytest.skip(f"LROC product not found: {img_path}")

    label = read_lroc_pds3_label(img_path)

    assert label.instrument_name == "LUNAR RECONNAISSANCE ORBITER CAMERA"
    assert label.target_name == "MOON"
    assert label.sample_bits == 16
    assert label.sample_type == "LSB_INTEGER"
    assert label.null_value is not None
    assert label.lines > 0
    assert label.line_samples > 0
    if exp_h is not None:
        assert label.lines == exp_h
    if exp_w is not None:
        assert label.line_samples == exp_w


@pytest.mark.parametrize("pair,product_id,exp_h,exp_w", _LROC_PRODUCTS)
def test_lroc_raster_loaded(
    pair: str, product_id: str, exp_h: int | None, exp_w: int | None
) -> None:
    """Load raster + valid-pixel mask from a real LROC product; verify contract."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    img_path = _lroc_img(demo, pair, product_id)
    if not img_path.is_file():
        pytest.skip(f"LROC product not found: {img_path}")

    label = read_lroc_pds3_label(img_path)
    raster, mask = load_lroc_pds3_raster(img_path, label)

    assert raster.shape == (label.lines, label.line_samples)
    assert mask.shape == raster.shape
    assert raster.dtype == np.dtype("int16")
    assert mask.dtype == np.dtype(bool)
    # Null pixels are excluded from the valid mask
    null_pixels = raster == label.null_value
    assert not (null_pixels & mask).any(), "Null-value pixels must be masked invalid"
    # At least some pixels should be valid
    assert mask.any(), "Expected at least some valid pixels in LROC product"


@pytest.mark.parametrize("pair,product_id,exp_h,exp_w", _LROC_PRODUCTS)
def test_lroc_derived_npy_readable(
    pair: str, product_id: str, exp_h: int | None, exp_w: int | None
) -> None:
    """Pre-computed .lroc.npy/.lroc.mask.npy are readable and shape-consistent."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    npy_path = demo / pair / "lroc" / f"{product_id}.lroc.npy"
    mask_path = demo / pair / "lroc" / f"{product_id}.lroc.mask.npy"
    if not npy_path.is_file() or not mask_path.is_file():
        pytest.skip(f"Pre-computed LROC .npy not found for {product_id}")

    raster = np.load(npy_path, mmap_mode="r")
    mask = np.load(mask_path, mmap_mode="r")

    assert raster.ndim == 2
    assert mask.ndim == 2
    assert raster.shape == mask.shape
    # The pre-computed .lroc.mask.npy files in the demo dataset were produced by
    # save_software_raster() in lroc_pds3, which saves valid_mask.astype(np.uint8)
    # as a float64 .npy array.  Values are 0.0 (invalid) or 1.0 (valid).
    # We do NOT change this here — it is Tejas's module's output format.
    assert mask.dtype in (np.dtype(bool), np.dtype("uint8"), np.dtype("float64")), (
        f"Unexpected mask dtype: {mask.dtype}"
    )
    valid_mask = mask.astype(bool)
    if exp_h is not None and exp_w is not None:
        assert raster.shape == (exp_h, exp_w)
    assert valid_mask.any(), "Expected at least some valid pixels in pre-computed LROC mask"


@pytest.mark.parametrize("pair,product_id,exp_h,exp_w", _LROC_PRODUCTS[:1])
def test_lroc_ingest_product_dispatch(
    pair: str, product_id: str, exp_h: int | None, exp_w: int | None, tmp_path: Path
) -> None:
    """ingest_product() dispatcher identifies and ingests a LROC .IMG correctly."""
    demo = _demo_dir()
    if demo is None:
        pytest.skip("LUNAR_DEMO_DIR not set or does not exist")
    img_path = _lroc_img(demo, pair, product_id)
    if not img_path.is_file():
        pytest.skip(f"LROC product not found: {img_path}")

    backup = _redirect_outputs(tmp_path)
    try:
        product = ingest_product(img_path)
    finally:
        _restore_outputs(backup)

    assert isinstance(product, LunarProduct)
    assert product.instrument == "LRO_NAC"
    assert product.mission == "LRO"
    assert product.dimensions is not None
    if exp_h is not None:
        assert product.dimensions.height_px == exp_h
    if exp_w is not None:
        assert product.dimensions.width_px == exp_w
    assert product.raster_uri is not None
    assert product.mask_uri is not None
    assert product.provenance is not None
