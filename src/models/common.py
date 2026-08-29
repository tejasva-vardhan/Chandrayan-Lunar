"""Shared contract types used by the four canonical models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DifficultyClass = Literal["easy", "normal", "difficult"]
CorrespondenceStatus = Literal["raw", "filtered", "inlier", "rejected"]
ConfidenceClass = Literal["SUCCESS", "LOW_CONFIDENCE", "FAILED"]


class Provenance(BaseModel):
    """Processing provenance. Values are recorded when known; never invented."""

    model_config = ConfigDict(extra="forbid")

    source_uri: str | None = None
    reader: str | None = None
    checksum: str | None = None
    software_commit: str | None = None
    notes: str | None = None


class ImageDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    band_count: int = Field(default=1, gt=0)


class Coordinates(BaseModel):
    """Coordinate metadata when a product provides it."""

    model_config = ConfigDict(extra="forbid")

    crs: str | None = None
    bbox: tuple[float, float, float, float] | None = None
