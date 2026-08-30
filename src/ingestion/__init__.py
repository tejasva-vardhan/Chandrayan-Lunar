"""PDS/data ingestion. Owned by Haruto.

Pipeline import surface: ingest_product(path) -> LunarProduct.

Replace this stub with a real reader. Do not change the signature.
Pair-aware resampling and orientation belong in preprocessing, not here.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.manifest import save_manifest
from src.ingestion.pds_reader import ingest_from_pds
from src.models.lunar_product import LunarProduct


def ingest_product(source: Path) -> LunarProduct:
    """Load, decode, basic-validate, mask, and extract metadata."""
    product = ingest_from_pds(source)
    save_manifest(product, source)
    return product


__all__ = ["ingest_product"]
