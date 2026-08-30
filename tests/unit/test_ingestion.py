"""Unit tests for PDS4 data ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

from src.ingestion import ingest_product
from src.ingestion.pds_reader import get_output_dir, ingest_from_pds, sanitize_filename
from src.models import LunarProduct


@pytest.fixture(autouse=True)
def redirect_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect all processed outputs and manifests to a temp directory for tests."""
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path))


def _make_mock_xml(
    product_id: str = "urn:isro:isda:ch2_cho.ohr:data_calibrated:ch2_ohr_ncp_mock",
    mission: str = "Chandrayaan-2",
    instrument: str = "orbiter high resolution camera",
    start_time: str = "2026-01-02T12:24:10.7393Z",
    processing_level: str = "Calibrated",
    pixel_resolution: str = "0.25",
    projection: str = "Polar stereographic",
    lines: int = 8,
    samples: int = 8,
    img_filename: str = "mock.img",
    expected_md5: str | None = None,
) -> str:
    md5_element = f"<md5_checksum>{expected_md5}</md5_checksum>" if expected_md5 else ""
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1" xmlns:isda="https://isda.issdc.gov.in/pds4/isda/v1" xmlns:pds="http://pds.nasa.gov/pds4/pds/v1">
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
            </Observing_System_Component>
            <Observing_System_Component>
                <name>{instrument}</name>
                <type>Instrument</type>
            </Observing_System_Component>
        </Observing_System>
        <Mission_Area>
            <isda:Product_Parameters>
                <isda:pixel_resolution>{pixel_resolution}</isda:pixel_resolution>
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
                <data_type>UnsignedByte</data_type>
            </Element_Array>
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


def test_ingest_from_directory(tmp_path: Path) -> None:
    # 1. Setup mock files in a directory
    product_dir = tmp_path / "ch2_mock_product"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    # Set a few zeros to test the valid mask
    img_data[0, 0] = 0
    img_data[4, 4] = 0

    img_bytes = img_data.tobytes()
    expected_md5 = hashlib.md5(img_bytes).hexdigest()

    xml_content = _make_mock_xml(img_filename="mock.img", expected_md5=expected_md5)

    with open(data_dir / "mock.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)

    with open(data_dir / "mock.img", "wb") as f:
        f.write(img_bytes)

    # 2. Run ingestion
    product = ingest_product(product_dir)

    # 3. Assertions
    assert isinstance(product, LunarProduct)
    assert product.product_id == "urn:isro:isda:ch2_cho.ohr:data_calibrated:ch2_ohr_ncp_mock"
    assert product.instrument == "OHRC"
    assert product.mission == "Chandrayaan-2"
    assert product.dimensions is not None
    assert product.dimensions.width_px == 8
    assert product.dimensions.height_px == 8
    assert product.gsd_meters == 0.25
    assert product.acquisition_time == datetime(2026, 1, 2, 12, 24, 10, 739300, tzinfo=timezone.utc)
    assert product.radiometric_state == "Calibrated"
    assert product.coordinates is not None
    assert product.coordinates.crs == "Polar stereographic"
    assert product.coordinates.bbox == (30.89, -84.68, 34.75, -83.86)

    # Check raster and mask exist and are correct
    assert product.raster_uri is not None
    assert product.mask_uri is not None

    raster = np.load(product.raster_uri)
    mask = np.load(product.mask_uri)

    assert raster.shape == (8, 8)
    assert mask.shape == (8, 8)
    assert np.array_equal(raster, img_data)

    # Mask should be False where image is 0
    assert not mask[0, 0]
    assert not mask[4, 4]
    assert mask[0, 1]
    assert mask[7, 7]

    # total_pixels = 64, invalid = 2, so valid ratio = 62/64 = 0.96875
    assert product.valid_pixel_ratio == 62.0 / 64.0
    assert product.provenance is not None
    assert product.provenance.checksum == expected_md5


def test_ingest_from_zip(tmp_path: Path) -> None:
    # 1. Setup mock ZIP file
    zip_path = tmp_path / "mock_product.zip"
    img_data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    img_bytes = img_data.tobytes()
    xml_content = _make_mock_xml(img_filename="mock.img")

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("ch2_mock/data/calibrated/mock.xml", xml_content)
        z.writestr("ch2_mock/data/calibrated/mock.img", img_bytes)

    # 2. Run ingestion
    product = ingest_product(zip_path)

    # 3. Assertions
    assert product.product_id == "urn:isro:isda:ch2_cho.ohr:data_calibrated:ch2_ohr_ncp_mock"
    assert product.dimensions is not None
    assert product.dimensions.width_px == 8
    assert product.dimensions.height_px == 8
    assert product.valid_pixel_ratio == 63.0 / 64.0


def test_missing_metadata(tmp_path: Path) -> None:
    product_dir = tmp_path / "ch2_mock_missing"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_bytes = bytes([1] * 64)
    # Minimal XML missing most parameters
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
    with open(data_dir / "mock.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
    with open(data_dir / "mock.img", "wb") as f:
        f.write(img_bytes)

    product = ingest_product(product_dir)

    assert product.product_id == "urn:isro:isda:ch2_cho.ohr:data_calibrated:mock_missing"
    # instrument defaults to OHRC in our fallback
    assert product.instrument == "OHRC"
    assert product.mission is None
    assert product.gsd_meters is None
    assert product.coordinates is None


def test_malformed_failures(tmp_path: Path) -> None:
    product_dir = tmp_path / "ch2_mock_malformed"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    # 1. Test missing file
    with pytest.raises(FileNotFoundError):
        ingest_from_pds(product_dir)

    # 2. XML exists but image is truncated
    xml_content = _make_mock_xml(img_filename="mock.img", lines=100, samples=100)
    with open(data_dir / "mock.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
    # image has only 10 bytes instead of 10000
    with open(data_dir / "mock.img", "wb") as f:
        f.write(bytes([1] * 10))

    with pytest.raises(ValueError, match="Unexpected End of File"):
        ingest_product(product_dir)


def test_manifest_generated(tmp_path: Path) -> None:
    product_dir = tmp_path / "ch2_mock_manifest"
    product_dir.mkdir()
    data_dir = product_dir / "data" / "calibrated"
    data_dir.mkdir(parents=True)

    img_bytes = bytes([1] * 64)
    xml_content = _make_mock_xml(img_filename="mock.img")
    with open(data_dir / "mock.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
    with open(data_dir / "mock.img", "wb") as f:
        f.write(img_bytes)

    product = ingest_product(product_dir)

    sanitized_id = sanitize_filename(product.product_id)
    manifest_path = tmp_path / f"{sanitized_id}.json"

    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data["product"]["product_id"] == product.product_id
    assert manifest_data["source_path"] == str(product_dir.resolve())
    assert manifest_data["raster_path"] == product.raster_uri
    assert manifest_data["mask_path"] == product.mask_uri
    assert manifest_data["processing_state"] == "ingested"
