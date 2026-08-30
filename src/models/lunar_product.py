"""Canonical lunar product contract (Haruto consumes this interface)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.common import Coordinates, ImageDimensions, Provenance


class LunarProduct(BaseModel):
    """Scientific product identity and metadata.

    Image arrays are not embedded. Ingestion provides raster/mask URIs when available.
    Optional scientific fields stay unset until a reader actually extracts them.
    """

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    mission: str | None = None
    dimensions: ImageDimensions | None = None
    gsd_meters: float | None = Field(default=None, gt=0)
    acquisition_time: datetime | None = None
    radiometric_state: str | None = None
    coordinates: Coordinates | None = None
    valid_pixel_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Valid-pixel fraction for this product alone. Not pair/overlap-aware. "
            "See PairCharacterization.valid_pixel_ratio for the pair measurement."
        ),
    )
    raster_uri: str | None = None
    mask_uri: str | None = None
    provenance: Provenance | None = None
