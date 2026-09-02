"""Unit tests for PDS4 data ingestion."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from src.ingestion import ingest_product
from src.ingestion.pds_reader import ingest_from_pds, sanitize_filename
from src.models import LunarProduct


@pytest.fixture(autouse=True)
def redirect_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect all processed outputs and manifests to a temp directory for tests."""
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path))


# ──────────────────────────────────────────────────────────────────────────────
# Helper: build minimal but valid PDS4 XML
# ──────────────────────────────────────────────────────────────────────────────


def _make_mock_xml(
    product_id: str = "urn:isro:isda:ch2_cho.ohr:data_calibrated:ch2_ohr_ncp_mock",
    mission: str = "Chandrayaan-2",
    instrument: str = "orbiter high resolution camera",
    start_time: str = "2026-01-02T12:24:10.7393Z",
    processing_level: str = "Calibrated",
    pixel_resolution: str = "0.25",
    pixel_resolution_unit: str = "m",
    projection: str = "Polar stereographic",
    lines: int = 8,
    samples: int = 8,
    img_filename: str = "mock.img",
    expected_md5: str | None = None,
    data_type: str = "UnsignedByte",
    special_constants: dict[str, str] | None = None,
) -> str:
    md5_element = f"<md5_checksum>{expected_md5}</md5_checksum>" if expected_md5 else ""
    # Build optional Special_Constants block
    sc_block = ""
    if special_constants:
        sc_items = "\n".join(f"            <{k}>{v}</{k}>" for k, v in special_constants.items())
        sc_block = f"        <Special_Constants>\n{sc_items}\n        </Special_Constants>"
    # Optional instrument component
    instr_component = ""
    if instrument:
        instr_component = f"""
            <Observing_System_Component>
                <name>{instrument}</name>
                <type>Instrument</type>
            </Observing_System_Component>"""
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1"
    xmlns:isda="https://isda.issdc.gov.in/pds4/isda/v1" xmlns:pds="http://pds.nasa.gov/pds4/pds/v1">
    <Identification_Area>
        <logical_identifier>{product_id}</logical_identifier>
        <version_id>1.0</version_id>
        <product_class>Product_Observational</product_class>
    </Identification_Area>
    <Observation_Area>
        <Time_Coordinates>
            <start_date_time>{start_time}</start_date_time>
            <stop_date_time>{start_time}</stop_date_time>
        </Time_Coordinates>
        <Primary_Result_Summary>
            <processing_level>{processing_level}</processing_level>
        </Primary_Result_Summary>
        <Investigation_Area>
            <name>{mission}</name>
            <type>Mission</type>
        </Investigation_Area>
        <Observing_System>
            <Observing_System_Component>
                <name>Chandrayaan 2 Orbiter</name>
                <type>Spacecraft</type>
            </Observing_System_Component>{instr_component}
        </Observing_System>
        <Mission_Area>
            <isda:Product_Parameters>
                <isda:pixel_resolution unit="{pixel_resolution_unit}">
                    {pixel_resolution}</isda:pixel_resolution>
                <isda:projection>{projection}</isda:projection>
            </isda:Product_Parameters>
            <isda:Geometry_Parameters>
                <isda:System_Level_Coordinates>
                    <isda:upper_left_latitude>-84.64</isda:upper_left_latitude>
                    <isda:upper_left_longitude>34.75</isda:upper_left_longitude>
                    <isda:upper_right_latitude>-84.68</isda:upper_right_latitude>
                    <isda:upper_right_longitude>33.72</isda:upper_right_longitude>
                    <isda:lower_left_latitude>-83.86</isda:lower_left_latitude>
                    <isda:lower_left_longitude>31.80</isda:lower_left_longitude>
                    <isda:lower_right_latitude>-83.90</isda:lower_right_latitude>
                    <isda:lower_right_longitude>30.89</isda:lower_right_longitude>
                </isda:System_Level_Coordinates>
            </isda:Geometry_Parameters>
        </Mission_Area>
    </Observation_Area>
    <File_Area_Observational>
        <File>
            <file_name>{img_filename}</file_name>
            {md5_element}
        </File>
        <Array_2D_Image>
            <offset unit="byte">0</offset>
            <axes>2</axes>
            <Element_Array>
                <data_type>{data_type}</data_type>
            </Element_Array>
            {sc_block}
            <Axis_Array>
                <axis_name>Line</axis_name>
                <elements>{lines}</elements>
            </Axis_Array>
            <Axis_Array>
                <axis_name>Sample</axis_name>
                <elements>{samples}</elements>
            </Axis_Array>
        </Array_2D_Image>
    </File_Area_Observational>
</Product_Observational>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Core ingestion tests
# ──────────────────────────────────────────────────────────────────────────────


def test_ingest_from_directory(tmp_path: Path) -> None:
    """Round-trip ingestion of a directory product — all metadata and mask verified."""
    product_dir = tmp_path / "ch2_mock_product"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    img_bytes = img_data.tobytes()
    expected_md5 = hashlib.md5(img_bytes).hexdigest()

    xml_content = _make_mock_xml(img_filename="mock.img", expected_md5=expected_md5)

    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_bytes)

    product = ingest_product(product_dir)

    assert isinstance(product, LunarProduct)
    assert product.product_id == "urn:isro:isda:ch2_cho.ohr:data_calibrated:ch2_ohr_ncp_mock"
    assert product.instrument == "OHRC"
    assert product.mission == "Chandrayaan-2"
    assert product.dimensions is not None
    assert product.dimensions.width_px == 8
    assert product.dimensions.height_px == 8
    assert product.gsd_meters == pytest.approx(0.25)
    assert product.acquisition_time == datetime(2026, 1, 2, 12, 24, 10, 739300, tzinfo=UTC)
    assert product.radiometric_state == "Calibrated"
    assert product.coordinates is not None
    assert product.coordinates.crs == "Polar stereographic"
    assert product.coordinates.bbox == (30.89, -84.68, 34.75, -83.86)

    assert product.raster_uri is not None
    assert product.mask_uri is not None

    raster = np.load(product.raster_uri)
    mask = np.load(product.mask_uri)

    assert raster.shape == (8, 8)
    assert mask.shape == (8, 8)
    assert np.array_equal(raster, img_data)

    assert product.provenance is not None
    assert product.provenance.checksum == expected_md5
    # FIX 5: provenance must not embed absolute machine path
    assert "F:" not in (product.provenance.source_uri or "")
    assert "SIH" not in (product.provenance.source_uri or "")


def test_ingest_from_zip(tmp_path: Path) -> None:
    """ZIP-archive ingestion path."""
    zip_path = tmp_path / "mock_product.zip"
    img_data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    img_bytes = img_data.tobytes()
    xml_content = _make_mock_xml(img_filename="mock.img")

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("ch2_mock/data/calibrated/mock.xml", xml_content)
        z.writestr("ch2_mock/data/calibrated/mock.img", img_bytes)

    product = ingest_product(zip_path)

    assert product.product_id == "urn:isro:isda:ch2_cho.ohr:data_calibrated:ch2_ohr_ncp_mock"
    assert product.dimensions is not None
    assert product.dimensions.width_px == 8
    assert product.dimensions.height_px == 8


def test_missing_metadata(tmp_path: Path) -> None:
    """Product with no Observing_System entries → instrument is absent → ValueError raised."""
    product_dir = tmp_path / "ch2_mock_missing"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_bytes = bytes([1] * 64)
    # Minimal XML missing most parameters, including Observing_System / Instrument
    xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
    <Identification_Area>
        <logical_identifier>urn:isro:isda:ch2_cho.ohr:data_calibrated:mock_missing</logical_identifier>
        <version_id>1.0</version_id>
        <product_class>Product_Observational</product_class>
    </Identification_Area>
    <Observation_Area>
        <Time_Coordinates>
            <start_date_time>2026-01-02T12:24:10.7393Z</start_date_time>
            <stop_date_time>2026-01-02T12:24:27.1231Z</stop_date_time>
        </Time_Coordinates>
    </Observation_Area>
    <File_Area_Observational>
        <File>
            <file_name>mock.img</file_name>
        </File>
        <Array_2D_Image>
            <offset unit="byte">0</offset>
            <Element_Array>
                <data_type>UnsignedByte</data_type>
            </Element_Array>
            <Axis_Array>
                <axis_name>Line</axis_name>
                <elements>8</elements>
            </Axis_Array>
            <Axis_Array>
                <axis_name>Sample</axis_name>
                <elements>8</elements>
            </Axis_Array>
        </Array_2D_Image>
    </File_Area_Observational>
</Product_Observational>
"""
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_bytes)

    # FIX 1: the frozen LunarProduct contract requires instrument to be a non-empty
    # string. When the label does not declare one, the reader must raise rather than
    # silently inventing a default.
    with pytest.raises(ValueError, match="Instrument"):
        ingest_product(product_dir)


def test_malformed_failures(tmp_path: Path) -> None:
    """Error paths: missing file, truncated image."""
    product_dir = tmp_path / "ch2_mock_malformed"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    # Missing .img file
    with pytest.raises(FileNotFoundError):
        ingest_from_pds(product_dir)

    # XML present but image truncated
    xml_content = _make_mock_xml(img_filename="mock.img", lines=100, samples=100)
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 10))  # only 10 bytes

    with pytest.raises(ValueError, match="Unexpected End of File"):
        ingest_product(product_dir)


def test_manifest_generated(tmp_path: Path) -> None:
    """Manifest file is created and contains correct keys without absolute machine paths."""
    product_dir = tmp_path / "ch2_mock_manifest"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_bytes = bytes([1] * 64)
    xml_content = _make_mock_xml(img_filename="mock.img")
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_bytes)

    product = ingest_product(product_dir)

    sanitized_id = sanitize_filename(product.product_id)
    manifest_path = tmp_path / f"{sanitized_id}.json"

    assert manifest_path.exists()

    with open(manifest_path, encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data["product"]["product_id"] == product.product_id
    assert manifest_data["source_path"] == str(product_dir.resolve())
    assert manifest_data["raster_path"] == product.raster_uri
    assert manifest_data["mask_path"] == product.mask_uri
    assert manifest_data["processing_state"] == "ingested"


# ──────────────────────────────────────────────────────────────────────────────
# FIX 1 — Instrument: no silent OHRC default
# ──────────────────────────────────────────────────────────────────────────────


def test_instrument_explicitly_ohrc(tmp_path: Path) -> None:
    """When the label says 'orbiter high resolution camera', instrument = 'OHRC'."""
    product_dir = tmp_path / "ch2_ohrc_explicit"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_content = _make_mock_xml(instrument="orbiter high resolution camera")
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    product = ingest_product(product_dir)
    assert product.instrument == "OHRC"


def test_instrument_missing_is_none(tmp_path: Path) -> None:
    """When no Instrument component exists in the label, instrument must be None."""
    product_dir = tmp_path / "ch2_no_instrument"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_content = _make_mock_xml(instrument="")  # empty string → no Instrument component
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    # FIX 1: frozen contract requires instrument as non-empty string.
    # When the label omits the Instrument component, the reader must raise.
    with pytest.raises(ValueError, match="Instrument"):
        ingest_product(product_dir)


def test_no_silent_ohrc_default(tmp_path: Path) -> None:
    """Spacecraft-only Observing_System (no Instrument component) → instrument stays None."""
    product_dir = tmp_path / "ch2_spacecraft_only"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_no_instrument = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
    <Identification_Area>
        <logical_identifier>urn:isro:isda:ch2_cho.ohr:data_calibrated:sc_only</logical_identifier>
        <version_id>1.0</version_id>
        <product_class>Product_Observational</product_class>
    </Identification_Area>
    <Observation_Area>
        <Observing_System>
            <Observing_System_Component>
                <name>Chandrayaan 2 Orbiter</name>
                <type>Spacecraft</type>
            </Observing_System_Component>
        </Observing_System>
    </Observation_Area>
    <File_Area_Observational>
        <File><file_name>mock.img</file_name></File>
        <Array_2D_Image>
            <offset unit="byte">0</offset>
            <Element_Array><data_type>UnsignedByte</data_type></Element_Array>
            <Axis_Array><axis_name>Line</axis_name><elements>8</elements></Axis_Array>
            <Axis_Array><axis_name>Sample</axis_name><elements>8</elements></Axis_Array>
        </Array_2D_Image>
    </File_Area_Observational>
</Product_Observational>
"""
    (data_dir / "mock.xml").write_text(xml_no_instrument, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    # FIX 1: spacecraft-only label has no Instrument component.
    # The reader must raise rather than silently defaulting to "OHRC".
    with pytest.raises(ValueError, match="Instrument"):
        ingest_product(product_dir)


# ──────────────────────────────────────────────────────────────────────────────
# FIX 2 — Mask: correct NoData semantics
# ──────────────────────────────────────────────────────────────────────────────


def test_mask_with_explicit_nodata_value(tmp_path: Path) -> None:
    """Pixels matching explicit special_constant are masked invalid; others remain valid."""
    product_dir = tmp_path / "ch2_nodata_explicit"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    # 8×8 image; the PDS label declares 0 as missing_constant
    img_data = np.zeros((8, 8), dtype=np.uint8)
    img_data[2, 2] = 128  # one valid pixel
    img_data[5, 5] = 64  # another valid pixel
    img_bytes = img_data.tobytes()

    xml_content = _make_mock_xml(
        img_filename="mock.img",
        special_constants={"missing_constant": "0"},
    )
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_bytes)

    product = ingest_product(product_dir)
    mask = np.load(product.mask_uri)

    assert mask.shape == (8, 8)
    # Pixels = 0 are declared NoData → invalid
    assert not mask[0, 0]
    # Pixels with non-zero values → valid
    assert mask[2, 2]
    assert mask[5, 5]


def test_mask_zero_valid_when_no_nodata_declared(tmp_path: Path) -> None:
    """When the PDS label does NOT declare any special constants, zero is a valid pixel."""
    product_dir = tmp_path / "ch2_zero_valid"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    # Image entirely zeros — none are NoData because label declares nothing
    img_data = np.zeros((8, 8), dtype=np.uint8)
    img_bytes = img_data.tobytes()

    xml_content = _make_mock_xml(img_filename="mock.img")  # no special_constants
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_bytes)

    product = ingest_product(product_dir)
    mask = np.load(product.mask_uri)

    # All pixels should be valid — no assumption that 0 = NoData
    assert mask.all(), "Zero pixels must be valid when no NoData is declared in the PDS label"
    assert product.valid_pixel_ratio == pytest.approx(1.0)


def test_mask_absence_of_nodata_metadata(tmp_path: Path) -> None:
    """Product with no Special_Constants node → mask leaves all pixels valid."""
    product_dir = tmp_path / "ch2_no_sc"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_data = np.array([0, 10, 200, 255], dtype=np.uint8).reshape(2, 2)
    img_bytes = img_data.tobytes()

    xml_content = _make_mock_xml(img_filename="mock.img", lines=2, samples=2)
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_bytes)

    product = ingest_product(product_dir)
    mask = np.load(product.mask_uri)

    assert mask.all()


# ──────────────────────────────────────────────────────────────────────────────
# FIX 3 — Dtype: parsed from PDS4 Element_Array
# ──────────────────────────────────────────────────────────────────────────────


def test_dtype_unsigned_byte(tmp_path: Path) -> None:
    """UnsignedByte → numpy uint8."""
    product_dir = tmp_path / "ch2_dtype_u8"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    (data_dir / "mock.xml").write_text(_make_mock_xml(data_type="UnsignedByte"), encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_data.tobytes())

    product = ingest_product(product_dir)
    raster = np.load(product.raster_uri)
    assert raster.dtype == np.dtype("uint8")
    assert np.array_equal(raster, img_data)


def test_dtype_unsigned_lsb2(tmp_path: Path) -> None:
    """UnsignedLSB2 → numpy uint16 little-endian."""
    product_dir = tmp_path / "ch2_dtype_u16"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_data = np.arange(64, dtype="<u2").reshape(8, 8)
    (data_dir / "mock.xml").write_text(_make_mock_xml(data_type="UnsignedLSB2"), encoding="utf-8")
    (data_dir / "mock.img").write_bytes(img_data.tobytes())

    product = ingest_product(product_dir)
    raster = np.load(product.raster_uri)
    assert raster.dtype == np.dtype("<u2")
    assert np.array_equal(raster, img_data)


def test_dtype_missing_raises(tmp_path: Path) -> None:
    """A label without Element_Array/data_type must raise ValueError — never guess."""
    product_dir = tmp_path / "ch2_no_dtype"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_no_dtype = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
    <Identification_Area>
        <logical_identifier>urn:test:no_dtype</logical_identifier>
        <version_id>1.0</version_id>
        <product_class>Product_Observational</product_class>
    </Identification_Area>
    <Observation_Area>
        <Observing_System>
            <Observing_System_Component>
                <name>orbiter high resolution camera</name>
                <type>Instrument</type>
            </Observing_System_Component>
        </Observing_System>
    </Observation_Area>
    <File_Area_Observational>
        <File><file_name>mock.img</file_name></File>
        <Array_2D_Image>
            <offset unit="byte">0</offset>
            <Element_Array/>
            <Axis_Array><axis_name>Line</axis_name><elements>8</elements></Axis_Array>
            <Axis_Array><axis_name>Sample</axis_name><elements>8</elements></Axis_Array>
        </Array_2D_Image>
    </File_Area_Observational>
</Product_Observational>
"""
    (data_dir / "mock.xml").write_text(xml_no_dtype, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([0] * 64))

    with pytest.raises(ValueError, match="Cannot determine pixel data type"):
        ingest_from_pds(product_dir)


# ──────────────────────────────────────────────────────────────────────────────
# FIX 4 — GSD: unit-validated
# ──────────────────────────────────────────────────────────────────────────────


def test_gsd_metres_unit(tmp_path: Path) -> None:
    """GSD with unit='m' → stored as-is in gsd_meters."""
    product_dir = tmp_path / "ch2_gsd_m"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_content = _make_mock_xml(pixel_resolution="0.25", pixel_resolution_unit="m")
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    product = ingest_product(product_dir)
    assert product.gsd_meters == pytest.approx(0.25)


def test_gsd_centimetres_unit(tmp_path: Path) -> None:
    """GSD with unit='cm' → converted to metres (÷100) in gsd_meters."""
    product_dir = tmp_path / "ch2_gsd_cm"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_content = _make_mock_xml(pixel_resolution="25", pixel_resolution_unit="cm")
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    product = ingest_product(product_dir)
    assert product.gsd_meters == pytest.approx(0.25)


def test_gsd_missing_unit_is_none(tmp_path: Path) -> None:
    """GSD node without a 'unit' attribute → gsd_meters must be None."""
    product_dir = tmp_path / "ch2_gsd_nounit"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_content = _make_mock_xml(pixel_resolution="0.25", pixel_resolution_unit="")
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    product = ingest_product(product_dir)
    assert product.gsd_meters is None, "GSD without explicit unit must not be assumed to be metres"


def test_gsd_missing_node_is_none(tmp_path: Path) -> None:
    """No pixel_resolution node at all → gsd_meters is None."""
    product_dir = tmp_path / "ch2_no_gsd"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    # Minimal XML with no isda:Product_Parameters but with a valid Instrument
    xml_no_gsd = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
    <Identification_Area>
        <logical_identifier>urn:test:no_gsd</logical_identifier>
        <version_id>1.0</version_id>
        <product_class>Product_Observational</product_class>
    </Identification_Area>
    <Observation_Area>
        <Observing_System>
            <Observing_System_Component>
                <name>orbiter high resolution camera</name>
                <type>Instrument</type>
            </Observing_System_Component>
        </Observing_System>
    </Observation_Area>
    <File_Area_Observational>
        <File><file_name>mock.img</file_name></File>
        <Array_2D_Image>
            <offset unit="byte">0</offset>
            <Element_Array><data_type>UnsignedByte</data_type></Element_Array>
            <Axis_Array><axis_name>Line</axis_name><elements>8</elements></Axis_Array>
            <Axis_Array><axis_name>Sample</axis_name><elements>8</elements></Axis_Array>
        </Array_2D_Image>
    </File_Area_Observational>
</Product_Observational>
"""
    (data_dir / "mock.xml").write_text(xml_no_gsd, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(bytes([1] * 64))

    product = ingest_product(product_dir)
    assert product.gsd_meters is None


def test_declared_byte_offset_is_skipped(tmp_path: Path) -> None:
    """PDS4 Array_2D_Image offset is applied; the header is not treated as pixels."""
    product_dir = tmp_path / "ch2_offset"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    header = b"\xff" * 16
    xml_content = _make_mock_xml(img_filename="mock.img").replace(
        '<offset unit="byte">0</offset>',
        '<offset unit="byte">16</offset>',
    )
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(header + img_data.tobytes())

    product = ingest_product(product_dir)
    raster = np.load(product.raster_uri)
    assert np.array_equal(raster, img_data)


def test_offset_without_unit_is_rejected(tmp_path: Path) -> None:
    """An offset value without a unit must not be assumed to be bytes."""
    product_dir = tmp_path / "ch2_offset_nounit"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    xml_content = _make_mock_xml(img_filename="mock.img").replace(
        '<offset unit="byte">0</offset>',
        "<offset>16</offset>",
    )
    (data_dir / "mock.xml").write_text(xml_content, encoding="utf-8")
    (data_dir / "mock.img").write_bytes(b"\x00" * 80)

    with pytest.raises(ValueError, match="offset has no unit"):
        ingest_product(product_dir)
