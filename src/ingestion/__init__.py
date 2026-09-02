"""PDS/data ingestion dispatch for supported lunar image products."""

from __future__ import annotations

import zipfile
from pathlib import Path

from src.ingestion.lroc_pds3 import (
    LrocPds3Error,
    LrocPds3Label,
    ingest_lroc_pds3_product,
    load_lroc_pds3_raster,
    read_lroc_pds3_label,
)
from src.ingestion.manifest import save_manifest
from src.ingestion.pds_reader import ingest_from_pds, parse_metadata_from_xml
from src.models.lunar_product import LunarProduct


def ingest_product(source: Path) -> LunarProduct:
    """Dispatch a declared supported product format, then save its manifest.

    LROC products identify themselves through their embedded PDS3 labels.
    Chandrayaan-2 OHRC products identify themselves through PDS4 label
    metadata. Unknown formats are rejected rather than guessed from a
    filename.
    """

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Source path does not exist: {path}")
    if _is_lroc_pds3(path):
        product = ingest_lroc_pds3_product(path)
    elif _is_ohrc_pds4(path):
        product = ingest_from_pds(path)
    else:
        raise ValueError(f"Unsupported or unrecognised lunar product: {path}")

    save_manifest(product, path)
    return product


def _is_lroc_pds3(path: Path) -> bool:
    """Return whether a standalone image declares the supported LROC PDS3 format."""

    if not path.is_file() or path.suffix.lower() != ".img":
        return False
    try:
        label = read_lroc_pds3_label(path)
    except LrocPds3Error:
        return False
    return (
        label.target_name == "MOON"
        and label.instrument_name == "LUNAR RECONNAISSANCE ORBITER CAMERA"
    )


def _is_ohrc_pds4(path: Path) -> bool:
    """Return whether an input's declared PDS4 metadata identifies OHRC."""

    xml_content = _find_pds4_label(path)
    if xml_content is None:
        return False
    try:
        metadata = parse_metadata_from_xml(xml_content)
    except ValueError:
        return False
    product_id = str(metadata["product_id"]).lower()
    return metadata["instrument"] == "OHRC" or "ch2_cho.ohr" in product_id


def _find_pds4_label(path: Path) -> bytes | None:
    """Find the observational XML label without relying on source filenames."""

    if path.is_file() and path.suffix.lower() == ".xml":
        return path.read_bytes()
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            labels = sorted(name for name in archive.namelist() if name.lower().endswith(".xml"))
            for name in labels:
                lower_name = name.lower()
                if "browse" not in lower_name and "geometry" not in lower_name:
                    return archive.read(name)
        return None
    if not path.is_dir():
        return None

    labels = sorted(path.rglob("*.xml"))
    for label in labels:
        parts = {part.lower() for part in label.parts}
        if "browse" not in parts and "geometry" not in parts:
            return label.read_bytes()
    return None


__all__ = [
    "LrocPds3Error",
    "LrocPds3Label",
    "ingest_lroc_pds3_product",
    "ingest_product",
    "load_lroc_pds3_raster",
    "read_lroc_pds3_label",
]
