"""Canonical correspondence contract (Chuba produces this interface)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.common import CorrespondenceStatus


class Correspondence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    residual: float | None = None
    status: CorrespondenceStatus = "raw"


class CorrespondenceSet(BaseModel):
    """Unordered set of correspondences for one pair and one matcher identity.

    The matcher identity is a label only. It does not select or endorse a final algorithm.
    """

    model_config = ConfigDict(extra="forbid")

    pair_id: str = Field(min_length=1)
    matcher_id: str = Field(min_length=1)
    matches: list[Correspondence] = Field(default_factory=list)
    representation_id: str | None = None
