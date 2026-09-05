/** API DTOs mirrored from the FastAPI boundary. */

export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface ProductUploadResponse {
  product_id: string;
  stored_path: string;
  filename: string;
  bytes: number;
}

export interface ProductSummary {
  product_id: string;
  path: string;
  origin: "upload" | "path" | "data_root";
  filename: string | null;
  logical_id: string | null;
  instrument_hint: string | null;
}

export interface CatalogStatusResponse {
  data_root_configured: boolean;
  data_root_env: string;
  product_count: number;
  products: ProductSummary[];
  message: string | null;
}

export interface Exp000PairResponse {
  available: boolean;
  pair_id: string;
  experiment_id: string;
  source: ProductSummary | null;
  reference: ProductSummary | null;
  message: string | null;
}

export interface CreateJobRequest {
  source_product_id?: string;
  reference_product_id?: string;
  source_path?: string;
  reference_path?: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  current_stage: string | null;
  completed_stages: string[];
  stages: string[];
  error: {
    code?: string;
    message?: string;
    failed_stage?: string | null;
    details?: Record<string, unknown>;
  } | null;
  created_at: string;
  updated_at: string;
  runtime_seconds: number | null;
}

export interface CorrespondencePoint {
  source_xy: [number, number];
  reference_xy: [number, number];
  confidence: number | null;
  residual: number | null;
  status: string;
}

export interface ControlPoint {
  source_xy: [number, number];
  reference_xy: [number, number];
  residual: number | null;
  uncertainty: number | null;
}

export interface MetricsDTO {
  verification_residual_rmse: number | null;
  verification_residual_rmse_label: string;
  inlier_count: number | null;
  inlier_ratio: number | null;
  spatial_coverage: number | null;
  control_point_count: number | null;
  independent_accuracy_claim: string;
}

export interface ProductInfo {
  product_id: string;
  instrument: string;
  mission: string | null;
  width_px: number | null;
  height_px: number | null;
  gsd_meters: number | null;
  acquisition_time: string | null;
  sun_azimuth: number | null;
  sun_incidence: number | null;
  raster_uri: string | null;
}

export interface RegistrationResultDTO {
  pair_id: string;
  source: ProductInfo;
  reference: ProductInfo;
  candidate_correspondences: number;
  verified_inliers: number;
  rejected_correspondences: number;
  correspondences: CorrespondencePoint[];
  inliers: CorrespondencePoint[];
  control_points: ControlPoint[];
  metrics: MetricsDTO | null;
  transformation: { model_name: string; parameters: Record<string, unknown> } | null;
  registered_source_uri: string | null;
  registered_artifact_available: boolean;
  quality_flags: string[];
  confidence_class: string | null;
  refinement_note: string | null;
  residual_note: string;
  evaluation_limitation: string | null;
  runtime_seconds: number | null;
  export_manifest: Record<string, string | null> | null;
  preview_available?: boolean;
  preview_mode?: string | null;
  preview_note?: string | null;
  preview_source_crop?: PreviewCropDTO | null;
  preview_reference_crop?: PreviewCropDTO | null;
}

export interface PreviewCropDTO {
  row: number;
  col: number;
  height: number;
  width: number;
  display_height?: number | null;
  display_width?: number | null;
  display_scale?: number | null;
}

export interface JobResultResponse {
  job_id: string;
  status: JobStatus;
  result: RegistrationResultDTO | null;
  error: {
    code?: string;
    message?: string;
    failed_stage?: string | null;
    details?: Record<string, unknown>;
  } | null;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiClientError";
    this.code = body.code;
    this.status = status;
    this.details = body.details ?? {};
  }
}
