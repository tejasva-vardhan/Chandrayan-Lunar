"""PDS/data ingestion. Owned by Haruto.

Pipeline import surface: ingest_product(path) -> LunarProduct.

Replace this stub with a real reader. Do not change the signature.
Pair-aware resampling and orientation belong in preprocessing, not here.
"""

from __future__ import annotations

from pathlib import Path

from src.models.lunar_product import LunarProduct


def ingest_product(source: Path) -> LunarProduct:
    """Load, decode, basic-validate, mask, and extract metadata."""
    raise NotImplementedError(f"ingest_product is not implemented. source={source}")


__all__ = ["ingest_product"]
