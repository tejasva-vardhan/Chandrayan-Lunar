"""Canonical registration-result contract (Shaiz produces this interface)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.common import ConfidenceClass, Provenance
from src.models.correspondence_set import Correspondence, CorrespondenceSet


class TransformationModel(BaseModel):
    """Named transform plus parameters.

    The model is not assumed to be a global homography (D-010).
    """

    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(min_length=1)
    parameters: dict[str, object] = Field(default_factory=dict)


class ControlPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]
    residual: float | None = None


class RegistrationMetrics(BaseModel):
    """Minimum metrics from v3 §22.

    Fields stay None until evaluation actually computes them. Do not fill placeholders.
    """

    model_config = ConfigDict(extra="forbid")

    rmse: float | None = Field(default=None, ge=0.0)
    inlier_count: int | None = Field(default=None, ge=0)
    inlier_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    spatial_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    control_point_count: int | None = Field(default=None, ge=0)


class RegistrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str = Field(min_length=1)
    correspondences: CorrespondenceSet | None = None
    inliers: list[Correspondence] = Field(default_factory=list)
    control_points: list[ControlPoint] = Field(default_factory=list)
    transformation: TransformationModel | None = None
    registered_source_uri: str | None = None
    metrics: RegistrationMetrics | None = None
    quality_flags: list[str] = Field(default_factory=list)
    confidence_class: ConfidenceClass | None = None
    provenance: Provenance | None = None
