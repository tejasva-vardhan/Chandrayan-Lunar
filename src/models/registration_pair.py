"""Canonical registration-pair contract (Shashwat populates characterization)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.common import DifficultyClass
from src.models.lunar_product import LunarProduct


class PairCharacterization(BaseModel):
    """Pair descriptors listed in v3 §8.

    All measurements are optional until the geometry/pair layer computes them.
    Routing thresholds are experimental and are not encoded here.
    """

    model_config = ConfigDict(extra="forbid")

    sensor_pair: str | None = None
    gsd_ratio: float | None = Field(default=None, gt=0)
    acquisition_time_difference_seconds: float | None = None
    sun_angle_difference_degrees: float | None = None
    viewing_geometry_difference: float | None = None
    expected_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_pixel_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    texture_contrast: float | None = None
    modality: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    difficulty: DifficultyClass | None = None


class RegistrationPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str = Field(min_length=1)
    source: LunarProduct
    reference: LunarProduct
    characterization: PairCharacterization | None = None
