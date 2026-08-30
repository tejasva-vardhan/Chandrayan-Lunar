"""Manifest generator for tracking and reproducing raw product ingestion."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.ingestion.pds_reader import sanitize_filename
from src.models.lunar_product import LunarProduct


class IngestionManifest(BaseModel):
    """Manifest tracking an ingested LunarProduct and its raw source references."""

    model_config = ConfigDict(extra="forbid")

    product: LunarProduct
    source_path: str
    raster_path: str
    mask_path: str
    processing_state: str = "ingested"


def save_manifest(product: LunarProduct, source_path: Path) -> Path:
    """Serialize the ingestion manifest to data/manifests/{product_id}.json."""
    import os

    env_dir = os.environ.get("LUNAR_MANIFEST_DIR")
    if env_dir:
        manifest_dir = Path(env_dir)
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent
        manifest_dir = repo_root / "data" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    sanitized_id = sanitize_filename(product.product_id)
    manifest_path = manifest_dir / f"{sanitized_id}.json"

    manifest = IngestionManifest(
        product=product,
        source_path=str(source_path.resolve()),
        raster_path=product.raster_uri or "",
        mask_path=product.mask_uri or "",
    )

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest.model_dump_json(indent=2))

    return manifest_path
