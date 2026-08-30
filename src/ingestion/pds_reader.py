"""PDS4 Observational Product Reader for Chandrayaan-2 OHRC image datasets."""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np

from src.models.common import Coordinates, ImageDimensions, Provenance
from src.models.lunar_product import LunarProduct

_NAMESPACES = {
    "pds": "http://pds.nasa.gov/pds4/pds/v1",
    "isda": "https://isda.issdc.gov.in/pds4/isda/v1",
}


def sanitize_filename(name: str) -> str:
    """Sanitize product ID to be a valid Windows/Unix filename."""
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    return name


def get_output_dir() -> Path:
    """Retrieve the configurable processed output directory."""
    env_dir = os.environ.get("LUNAR_OUTPUT_DIR") or os.environ.get("LUNAR_PROCESSED_DIR")
    if env_dir:
        return Path(env_dir)
    # Default to data/processed relative to repo root
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / "data" / "processed"


def get_git_commit() -> str | None:
    """Get the current Git commit hash if available."""
    import subprocess

    try:
        repo_dir = Path(__file__).resolve().parent.parent.parent
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return None


def parse_date_time(dt_str: str | None) -> datetime | None:
    """Safely parse ISO acquisition timestamp from XML."""
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
    return None


def extract_bbox(root: ET.Element) -> tuple[float, float, float, float] | None:
    """Extract coordinates bounding box (min_lon, min_lat, max_lon, max_lat) from corners."""
    coords_node = root.find(
        ".//isda:Geometry_Parameters/isda:Refined_Corner_Coordinates", _NAMESPACES
    )
    if coords_node is None:
        coords_node = root.find(
            ".//isda:Geometry_Parameters/isda:System_Level_Coordinates", _NAMESPACES
        )
    if coords_node is None:
        return None

    lats = []
    lons = []
    for prefix in ("upper_left", "upper_right", "lower_left", "lower_right"):
        lat_node = coords_node.find(f"isda:{prefix}_latitude", _NAMESPACES)
        lon_node = coords_node.find(f"isda:{prefix}_longitude", _NAMESPACES)
        if lat_node is not None and lat_node.text:
            try:
                lats.append(float(lat_node.text))
            except ValueError:
                pass
        if lon_node is not None and lon_node.text:
            try:
                lons.append(float(lon_node.text))
            except ValueError:
                pass

    if len(lats) == 4 and len(lons) == 4:
        return (min(lons), min(lats), max(lons), max(lats))
    return None


def parse_metadata_from_xml(xml_content: bytes) -> dict:
    """Parse metadata from PDS4 XML label bytes."""
    root = ET.fromstring(xml_content)

    # logical_identifier (Product ID)
    lid_node = root.find(".//pds:Identification_Area/pds:logical_identifier", _NAMESPACES)
    product_id = lid_node.text.strip() if lid_node is not None and lid_node.text else "unknown"

    # Mission
    mission_node = root.find(".//pds:Investigation_Area/pds:name", _NAMESPACES)
    mission = mission_node.text.strip() if mission_node is not None and mission_node.text else None

    # Instrument
    instrument = None
    components = root.findall(".//pds:Observing_System/pds:Observing_System_Component", _NAMESPACES)
    for comp in components:
        type_node = comp.find("pds:type", _NAMESPACES)
        name_node = comp.find("pds:name", _NAMESPACES)
        is_instrument = (
            type_node is not None
            and type_node.text
            and type_node.text.strip().lower() == "instrument"
        )
        if is_instrument:
            if name_node is not None and name_node.text:
                # Standardize name (e.g. "orbiter high resolution camera" -> "OHRC")
                raw_name = name_node.text.strip()
                if "high resolution camera" in raw_name.lower() or "ohrc" in raw_name.lower():
                    instrument = "OHRC"
                else:
                    instrument = raw_name
                break

    # If instrument is still not found, fallback to searching for isda parameters
    if not instrument:
        instrument = "OHRC"  # default to OHRC for this project context

    # Acquisition Time
    time_node = root.find(".//pds:Time_Coordinates/pds:start_date_time", _NAMESPACES)
    acquisition_time = parse_date_time(time_node.text) if time_node is not None else None

    # Processing Level (Radiometric State)
    proc_node = root.find(".//pds:Primary_Result_Summary/pds:processing_level", _NAMESPACES)
    radiometric_state = proc_node.text.strip() if proc_node is not None and proc_node.text else None

    # GSD
    gsd_node = root.find(".//isda:Product_Parameters/isda:pixel_resolution", _NAMESPACES)
    gsd_meters = None
    if gsd_node is not None and gsd_node.text:
        try:
            gsd_meters = float(gsd_node.text)
        except ValueError:
            pass

    # Dimensions
    width = None
    height = None
    array_node = root.find(".//pds:Array_2D_Image", _NAMESPACES)
    if array_node is not None:
        axis_arrays = array_node.findall("pds:Axis_Array", _NAMESPACES)
        for axis in axis_arrays:
            name_node = axis.find("pds:axis_name", _NAMESPACES)
            elem_node = axis.find("pds:elements", _NAMESPACES)
            has_name_and_elem = (
                name_node is not None
                and elem_node is not None
                and name_node.text
                and elem_node.text
            )
            if has_name_and_elem:
                axis_name = name_node.text.strip()
                elements = int(elem_node.text.strip())
                if axis_name.lower() == "line":
                    height = elements
                elif axis_name.lower() == "sample":
                    width = elements

    dimensions = None
    if width is not None and height is not None:
        dimensions = ImageDimensions(width_px=width, height_px=height, band_count=1)

    # Coordinates
    proj_node = root.find(".//isda:Product_Parameters/isda:projection", _NAMESPACES)
    crs = proj_node.text.strip() if proj_node is not None and proj_node.text else None
    bbox = extract_bbox(root)
    coordinates = None
    if crs or bbox:
        coordinates = Coordinates(crs=crs, bbox=bbox)

    # Binary file name and checksum inside XML
    img_filename = None
    expected_md5 = None
    file_node = root.find(".//pds:File_Area_Observational/pds:File", _NAMESPACES)
    if file_node is not None:
        name_node = file_node.find("pds:file_name", _NAMESPACES)
        md5_node = file_node.find("pds:md5_checksum", _NAMESPACES)
        if name_node is not None and name_node.text:
            img_filename = name_node.text.strip()
        if md5_node is not None and md5_node.text:
            expected_md5 = md5_node.text.strip()

    return {
        "product_id": product_id,
        "instrument": instrument,
        "mission": mission,
        "dimensions": dimensions,
        "gsd_meters": gsd_meters,
        "acquisition_time": acquisition_time,
        "radiometric_state": radiometric_state,
        "coordinates": coordinates,
        "img_filename": img_filename,
        "expected_md5": expected_md5,
    }


def parse_metadata_file(xml_path: Path) -> dict:
    """Read and parse XML label file."""
    with open(xml_path, "rb") as f:
        return parse_metadata_from_xml(f.read())


def ingest_from_pds(source: Path) -> LunarProduct:
    """Main implementation of PDS/DISC real product ingestion."""
    if not source.exists():
        raise FileNotFoundError(f"Source path does not exist: {source}")

    xml_content = None
    img_stream_factory = None
    source_filename = source.name

    # Determine if source is ZIP or directory
    if source.is_file() and source.suffix.lower() == ".zip":
        # ZIP file ingestion
        z = zipfile.ZipFile(source, "r")
        # Locate data XML and image files inside ZIP
        xml_name = None
        for name in z.namelist():
            name_lower = name.lower()
            if (
                name.endswith(".xml")
                and "/data/" in name_lower
                and "browse" not in name_lower
                and "geometry" not in name_lower
            ):
                xml_name = name
                break
        if xml_name is None:
            for name in z.namelist():
                name_lower = name.lower()
                if (
                    name.endswith(".xml")
                    and "_d_" in name_lower
                    and "browse" not in name_lower
                    and "geometry" not in name_lower
                ):
                    xml_name = name
                    break
        if xml_name is None:
            # Fallback to any xml in zip
            for name in z.namelist():
                if name.endswith(".xml"):
                    xml_name = name
                    break
        if xml_name is None:
            z.close()
            raise FileNotFoundError(f"No XML label file found in ZIP archive: {source}")

        xml_content = z.read(xml_name)
        metadata = parse_metadata_from_xml(xml_content)
        img_filename = metadata.get("img_filename")

        # Find img path inside ZIP
        img_zip_path = None
        if img_filename:
            for name in z.namelist():
                if name.endswith(img_filename):
                    img_zip_path = name
                    break
        if img_zip_path is None:
            for name in z.namelist():
                if name.endswith(".img"):
                    img_zip_path = name
                    break
        if img_zip_path is None:
            z.close()
            raise FileNotFoundError(f"No IMG data file found in ZIP archive: {source}")

        def img_stream_factory():
            return z.open(img_zip_path)
    elif source.is_dir():
        # Directory ingestion
        # Find XML file
        xml_paths = list(source.rglob("*.xml"))
        # Filter for those under a 'data' directory and avoid browse/geometry files
        data_xml_paths = []
        for p in xml_paths:
            parts_lower = [part.lower() for part in p.parts]
            is_data_file = (
                "data" in parts_lower
                and "browse" not in parts_lower
                and "geometry" not in parts_lower
            )
            if is_data_file:
                data_xml_paths.append(p)
        if not data_xml_paths:
            for p in xml_paths:
                parts_lower = [part.lower() for part in p.parts]
                is_calibrated = (
                    "calibrated" in parts_lower
                    and "browse" not in parts_lower
                    and "geometry" not in parts_lower
                )
                if is_calibrated:
                    data_xml_paths.append(p)
        if not data_xml_paths:
            for p in xml_paths:
                is_data_name = (
                    "_d_" in p.name.lower()
                    and "browse" not in p.name.lower()
                    and "geometry" not in p.name.lower()
                )
                if is_data_name:
                    data_xml_paths.append(p)

        if data_xml_paths:
            xml_path = data_xml_paths[0]
        elif xml_paths:
            xml_path = xml_paths[0]
        else:
            raise FileNotFoundError(f"No XML label file found in directory: {source}")

        with open(xml_path, "rb") as f:
            xml_content = f.read()

        metadata = parse_metadata_from_xml(xml_content)
        img_filename = metadata.get("img_filename")

        # Locate img file
        img_path = None
        if img_filename:
            # Try exact path relative to source
            img_path = xml_path.parent / img_filename
            if not img_path.exists():
                # Search rglob
                img_paths = list(source.rglob(img_filename))
                if img_paths:
                    img_path = img_paths[0]
        if img_path is None or not img_path.exists():
            img_paths = list(source.rglob("*.img"))
            if img_paths:
                img_path = img_paths[0]

        if img_path is None or not img_path.exists():
            raise FileNotFoundError(f"No IMG data file found in directory: {source}")

        def img_stream_factory():
            return open(img_path, "rb")
    else:
        # Input is direct XML file
        if source.suffix.lower() == ".xml":
            with open(source, "rb") as f:
                xml_content = f.read()
            metadata = parse_metadata_from_xml(xml_content)
            img_filename = metadata.get("img_filename")
            img_path = source.parent / img_filename if img_filename else None
            if img_path is None or not img_path.exists():
                # Check for same name with .img suffix
                img_path = source.with_suffix(".img")
            if not img_path.exists():
                raise FileNotFoundError(f"Could not locate image file for label: {source}")

            def img_stream_factory():
                return open(img_path, "rb")
        else:
            raise ValueError(f"Unsupported source format: {source}")

    # Build output paths
    product_id = metadata["product_id"]
    sanitized_id = sanitize_filename(product_id)
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    raster_path = output_dir / f"{sanitized_id}_raster.npy"
    mask_path = output_dir / f"{sanitized_id}_mask.npy"

    height = metadata["dimensions"].height_px if metadata["dimensions"] else 0
    width = metadata["dimensions"].width_px if metadata["dimensions"] else 0

    if height <= 0 or width <= 0:
        raise ValueError(f"Parsed invalid dimensions: {height}x{width}")

    # Memory-mapped streaming write
    # Using np.lib.format.open_memmap to write directly to disk with small memory footprint
    out_raster = np.lib.format.open_memmap(
        str(raster_path), mode="w+", dtype=np.uint8, shape=(height, width)
    )
    out_mask = np.lib.format.open_memmap(
        str(mask_path), mode="w+", dtype=bool, shape=(height, width)
    )

    chunk_height = 5000
    valid_pixels = 0
    md5_hash = hashlib.md5()

    with img_stream_factory() as stream:
        for i in range(0, height, chunk_height):
            actual_chunk_height = min(chunk_height, height - i)
            bytes_to_read = actual_chunk_height * width
            data = stream.read(bytes_to_read)
            if len(data) < bytes_to_read:
                raise ValueError(
                    f"Unexpected End of File: read {len(data)} bytes, expected {bytes_to_read}"
                )

            # Update checksum
            md5_hash.update(data)

            # Reshape into numpy chunk
            chunk = np.frombuffer(data, dtype=np.uint8).reshape(actual_chunk_height, width)
            out_raster[i : i + actual_chunk_height, :] = chunk

            # Compute valid mask chunk (zero is padding/NoData)
            mask_chunk = chunk != 0
            out_mask[i : i + actual_chunk_height, :] = mask_chunk
            valid_pixels += int(np.sum(mask_chunk))

    out_raster.flush()
    out_mask.flush()

    # Clean up ZIP if open
    if "z" in locals():
        z.close()

    # Finalize properties
    total_pixels = height * width
    valid_pixel_ratio = float(valid_pixels) / total_pixels
    checksum = md5_hash.hexdigest()

    # Verify MD5 checksum if specified in XML
    expected_md5 = metadata.get("expected_md5")
    if expected_md5 and checksum != expected_md5:
        notes = f"MD5 mismatch: expected {expected_md5}, computed {checksum}"
    else:
        notes = f"Successfully ingested from {source_filename}"

    provenance = Provenance(
        source_uri=str(source.resolve()),
        reader="pds4_stream_reader",
        checksum=checksum,
        software_commit=get_git_commit(),
        notes=notes,
    )

    return LunarProduct(
        product_id=product_id,
        instrument=metadata["instrument"],
        mission=metadata["mission"],
        dimensions=metadata["dimensions"],
        gsd_meters=metadata["gsd_meters"],
        acquisition_time=metadata["acquisition_time"],
        radiometric_state=metadata["radiometric_state"],
        coordinates=metadata["coordinates"],
        valid_pixel_ratio=valid_pixel_ratio,
        raster_uri=str(raster_path.resolve()),
        mask_uri=str(mask_path.resolve()),
        provenance=provenance,
    )
