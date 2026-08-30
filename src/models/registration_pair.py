"""Canonical registration-pair contract (Shashwat populates characterization)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.common import DifficultyClass
from src.models.lunar_product import LunarProduct


class PairCharacterization(BaseModel):
    """Pair descriptors listed in v3 §8.

    Geometry (Shashwat) owns these calculations. This model only stores results.
    All measurements stay None until that layer actually computes them.
    Routing thresholds are experimental and are not encoded here.
    """

    model_config = ConfigDict(extra="forbid")

    sensor_pair: str | None = None
    gsd_ratio: float | None = Field(
        default=None,
        gt=0,
        description=(
            "source GSD / reference GSD when both GSD values are known. "
            "Descriptive measurement, not a routing threshold."
        ),
    )
    acquisition_time_difference_seconds: float | None = None
    sun_angle_difference_degrees: float | None = Field(
        default=None,
        description=(
            "Optional geometry-derived Sun-angle difference. Do not invent an "
            "incidence/azimuth combination until geometry defines one."
        ),
    )
    viewing_geometry_difference: float | None = Field(
        default=None,
        description=(
            "Optional opaque geometry-derived scalar. This contract does not "
            "define its unit or computation. Remain None until geometry defines it."
        ),
    )
    expected_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_pixel_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Pair/overlap-aware validity. Geometry owns the calculation. "
            "Distinct from LunarProduct.valid_pixel_ratio."
        ),
    )
    texture_contrast: float | None = None
    modality: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    difficulty: DifficultyClass | None = None


class RegistrationPair(BaseModel):
    """Source/reference pair plus optional characterization and overlap handle."""

    model_config = ConfigDict(extra="forbid")

    pair_id: str = Field(min_length=1)
    source: LunarProduct
    reference: LunarProduct
    characterization: PairCharacterization | None = None
    overlap_mask_uri: str | None = Field(
        default=None,
        description=(
            "Optional pair-specific overlap / valid correspondence region. "
            "Unset until geometry or preprocessing writes a real mask."
        ),
    )
