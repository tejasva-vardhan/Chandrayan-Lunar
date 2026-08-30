"""Canonical registration-result contract (Shaiz produces this interface)."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.common import ConfidenceClass, Provenance
from src.models.correspondence_set import Correspondence, CorrespondenceSet


class TransformationModel(BaseModel):
    """Named transform plus parameters.

    model_name is an unconstrained label. This contract does not assume a global
    homography (D-010) or any other specific model.

    parameters must be JSON-serializable (objects, arrays, strings, numbers,
    booleans, null). Do not store numpy arrays or other non-JSON values.
    """

    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(min_length=1)
    parameters: dict[str, object] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def parameters_must_be_json_serializable(cls, value: dict[str, object]) -> dict[str, object]:
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("parameters must be JSON serializable") from exc
        return value


class ControlPoint(BaseModel):
    """Spatially selected control point.

    source_xy and reference_xy are image pixel coordinates. Pixel-centre versus
    pixel-corner origin is owned by ingestion/geometry and is not defined here.

    uncertainty is optional and has no canonical unit yet. Leave None until
    refinement computes a real value.
    """

    model_config = ConfigDict(extra="forbid")

    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]
    residual: float | None = None
    uncertainty: float | None = None


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
    """Registration and evaluation outcome.

    CorrespondenceSet.matches is the canonical correspondence collection.
    inliers is a convenience snapshot/subset. If inliers is non-empty, each
    inlier must appear in correspondences.matches by (source_xy, reference_xy).
    Do not invent inliers, counts, metrics, or transformations.
    """

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

    @model_validator(mode="after")
    def inliers_must_be_snapshot_of_matches(self) -> RegistrationResult:
        if not self.inliers:
            return self
        if self.correspondences is None:
            raise ValueError(
                "inliers requires correspondences; CorrespondenceSet.matches is the source of truth"
            )
        known = {(item.source_xy, item.reference_xy) for item in self.correspondences.matches}
        for inlier in self.inliers:
            if (inlier.source_xy, inlier.reference_xy) not in known:
                raise ValueError(
                    "inliers must be a subset of correspondences.matches (source of truth)"
                )
        return self
