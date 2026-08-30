"""Canonical correspondence contract (Chuba produces this interface)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.common import CorrespondenceStatus


class Correspondence(BaseModel):
    """One image-space correspondence.

    source_xy and reference_xy are image pixel coordinates. Pixel-centre versus
    pixel-corner origin is owned by ingestion/geometry and is not defined here.

    confidence is an optional adapter-normalized value in [0, 1]. It is not the
    raw native score or distance returned by a matcher. Leave None when a
    meaningful normalization has not been defined. Do not add a raw score field
    in this freeze.
    """

    model_config = ConfigDict(extra="forbid")

    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    residual: float | None = None
    status: CorrespondenceStatus = "raw"


class CorrespondenceSet(BaseModel):
    """Canonical correspondence collection for one pair and one matcher identity.

    matches is the source of truth for correspondences. matcher_id is a label
    only; it does not select or endorse a final algorithm.
    """

    model_config = ConfigDict(extra="forbid")

    pair_id: str = Field(min_length=1)
    matcher_id: str = Field(min_length=1)
    matches: list[Correspondence] = Field(default_factory=list)
    representation_id: str | None = None
