"""HTTP DTOs. Mapped to/from scientific models at the API boundary only."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "running", "completed", "failed"]


class ProductUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    stored_path: str
    filename: str
    bytes: int


class ProductSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    path: str
    origin: Literal["upload", "path", "data_root"]
    filename: str | None = None


class CreateJobRequest(BaseModel):
    """Start a registration job from uploaded product IDs and/or local paths."""

    model_config = ConfigDict(extra="forbid")

    source_product_id: str | None = None
    reference_product_id: str | None = None
    source_path: str | None = None
    reference_path: str | None = None


class CorrespondencePointDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]
    confidence: float | None = None
    residual: float | None = None
    status: str


class ControlPointDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_xy: tuple[float, float]
    reference_xy: tuple[float, float]
    residual: float | None = None
    uncertainty: float | None = None


class MetricsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_residual_rmse: float | None = Field(
        default=None,
        description=(
            "RMSE of geometric-verification transfer residuals. "
            "Not an independent registration-accuracy measurement."
        ),
    )
    verification_residual_rmse_label: str = "Verification residual RMSE"
    inlier_count: int | None = None
    inlier_ratio: float | None = None
    spatial_coverage: float | None = None
    control_point_count: int | None = None
    independent_accuracy_claim: str = "Not independently validated"


class ProductInfoDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    instrument: str
    mission: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    gsd_meters: float | None = None
    acquisition_time: str | None = None
    raster_uri: str | None = None


class TransformationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class RegistrationResultDTO(BaseModel):
    """API view of RegistrationResult + pair context for the UI."""

    model_config = ConfigDict(extra="forbid")

    pair_id: str
    source: ProductInfoDTO
    reference: ProductInfoDTO
    candidate_correspondences: int
    verified_inliers: int
    rejected_correspondences: int
    correspondences: list[CorrespondencePointDTO] = Field(default_factory=list)
    inliers: list[CorrespondencePointDTO] = Field(default_factory=list)
    control_points: list[ControlPointDTO] = Field(default_factory=list)
    metrics: MetricsDTO | None = None
    transformation: TransformationDTO | None = None
    registered_source_uri: str | None = None
    registered_artifact_available: bool = False
    quality_flags: list[str] = Field(default_factory=list)
    confidence_class: str | None = None
    refinement_note: str | None = None
    residual_note: str = (
        "Verification transfer residuals are image-space fit values, not independent "
        "registration accuracy. Do not claim sub-pixel accuracy without independent validation."
    )
    evaluation_limitation: str | None = None
    runtime_seconds: float | None = None
    export_manifest: dict[str, str | None] | None = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus
    current_stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str
    runtime_seconds: float | None = None


class JobResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus
    result: RegistrationResultDTO | None = None
    error: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    service: str = "sih26166-api"
    pipeline_stages: list[str]


class VisualizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_url: str
    registered_source_url: str
