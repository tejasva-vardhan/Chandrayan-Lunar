"""PDS/data ingestion. Owned by Haruto.

Pipeline import surface: ingest_product(path) -> LunarProduct.

The frozen pipeline entrypoint remains unimplemented in this foundation.
Format-specific helpers may be added here without changing that public
behavior; callers can use those helpers directly in tests and experiments
until a reviewed ingest dispatcher is introduced.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.lroc_pds3 import (
    LrocPds3Error,
    LrocPds3Label,
    ingest_lroc_pds3_product,
    load_lroc_pds3_raster,
    read_lroc_pds3_label,
)
from src.models.lunar_product import LunarProduct


def ingest_product(source: Path) -> LunarProduct:
    """Load, decode, basic-validate, mask, and extract metadata."""
    raise NotImplementedError(f"ingest_product is not implemented. source={source}")


__all__ = [
    "LrocPds3Error",
    "LrocPds3Label",
    "ingest_lroc_pds3_product",
    "ingest_product",
    "load_lroc_pds3_raster",
    "read_lroc_pds3_label",
]
