import type { RegistrationResultDTO } from "../api/types";
import { exp000 } from "../data/exp000";

export type DisplayPoint = {
  id: string;
  x: number;
  y: number;
  rx: number;
  ry: number;
  residual: string;
  residualValue: number | null;
  confidence: string;
  status: "inlier" | "rejected" | "control" | "candidate";
  sourcePixel: string;
  referencePixel: string;
};

/** Presentation status derived only from backend confidence_class / quality_flags. */
export type ResultStatusLabel =
  | "COMPLETED"
  | "COMPLETED WITH LIMITATIONS"
  | "LOW CONFIDENCE"
  | "FAILED";

export type ResultsViewModel = {
  id: string;
  source: string;
  reference: string;
  sourceProduct: string;
  referenceProduct: string;
  acquisitionTimeSource: string;
  acquisitionTimeReference: string;
  sunAzimuth: number | null;
  sunIncidence: number | null;
  region: { lat: readonly [number, number]; lon: readonly [number, number]; label: string } | null;
  sourceDims: { width: number | null; height: number | null; gsd: string };
  referenceDims: { width: number | null; height: number | null };
  sourceStride: string;
  referenceStride: string;
  rawMatches: number;
  verified: number;
  rejected: number;
  controlPointCount: number;
  inlierRatio: string;
  coverage: string;
  rmse: string;
  rmseLabel: string;
  runtimeSeconds: number | null;
  refinement: string;
  registration: string;
  independentAccuracy: string;
  residualNote: string;
  evaluationLimitation: string | null;
  flags: string[];
  confidenceClass: string | null;
  resultStatus: ResultStatusLabel;
  fullRasterBlocked: boolean;
  points: DisplayPoint[];
  mapPoints: DisplayPoint[];
  registeredArtifactUrl: string | null;
  previewSourceUrl: string | null;
  previewReferenceUrl: string | null;
  previewRegisteredUrl: string | null;
  previewAvailable: boolean;
  previewMode: string | null;
  previewNote: string | null;
  transformationModel: string | null;
  isLive: boolean;
  jobId: string | null;
};

const FAILURE_FLAGS = new Set([
  "no_correspondences",
  "insufficient_verified_matches",
  "insufficient_control_points",
  "degenerate_control_points",
  "invalid_transformation",
  "warp_failed",
]);

const LIMITATION_FLAGS = new Set([
  "registration_output_too_large",
  "not_independently_validated",
  "preprocess_identity_passthrough_oversized_raster",
]);

export function deriveResultStatus(input: {
  confidenceClass: string | null | undefined;
  flags: string[];
}): ResultStatusLabel {
  const { confidenceClass, flags } = input;
  if (confidenceClass === "FAILED" || flags.some((f) => FAILURE_FLAGS.has(f))) {
    return "FAILED";
  }
  if (confidenceClass === "LOW_CONFIDENCE") {
    return "LOW CONFIDENCE";
  }
  const hasLimitations = flags.some((f) => LIMITATION_FLAGS.has(f));
  if (confidenceClass === "SUCCESS") {
    return hasLimitations ? "COMPLETED WITH LIMITATIONS" : "COMPLETED";
  }
  // confidence_class commonly unset — map from quality_flags only.
  if (hasLimitations) {
    return "COMPLETED WITH LIMITATIONS";
  }
  return "COMPLETED";
}

function formatScientific(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "Not available";
  if (value === 0) return "0";
  const match = /^(-?\d+(?:\.\d+)?)e([+-]?\d+)$/.exec(value.toExponential(2));
  if (!match) return value.toExponential(2);
  const coeff = match[1];
  const power = Number(match[2]);
  const sign = power < 0 ? "⁻" : "";
  const digits = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  const powerText = `${sign}${Math.abs(power)
    .toString()
    .split("")
    .map((d) => digits[Number(d)])
    .join("")}`;
  return `${coeff} × 10${powerText}`;
}

function formatConfidence(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "Not available";
  return value.toFixed(3);
}

function formatPixel(xy: [number, number] | null | undefined): string {
  if (!xy) return "Not available";
  return `${xy[0].toFixed(1)}, ${xy[1].toFixed(1)}`;
}

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function toPercent(xy: [number, number], width: number | null, height: number | null): { x: number; y: number } {
  if (!width || !height || width <= 1 || height <= 1) {
    return { x: 50, y: 50 };
  }
  return {
    x: (xy[0] / (width - 1)) * 100,
    y: (xy[1] / (height - 1)) * 100,
  };
}

function registrationSummary(result: RegistrationResultDTO): string {
  if (result.registered_artifact_available) {
    const model = result.transformation?.model_name ?? "transform";
    return `Registered (${model})`;
  }
  if (result.quality_flags.includes("registration_output_too_large")) {
    return "Blocked by output-size cap (full-raster warp skipped)";
  }
  if (result.quality_flags.includes("insufficient_control_points")) {
    return "Registration skipped — insufficient control points";
  }
  if (result.quality_flags.includes("no_correspondences")) {
    return "Registration skipped — no correspondences";
  }
  if (result.quality_flags.includes("insufficient_verified_matches")) {
    return "Registration skipped — insufficient verified matches";
  }
  if (result.transformation) {
    return `${result.transformation.model_name} estimated; registered raster unavailable`;
  }
  return "Registration did not produce a registered raster";
}

function makeDisplayPoint(
  item: {
    source_xy: [number, number];
    reference_xy: [number, number];
    residual?: number | null;
    confidence?: number | null;
  },
  status: DisplayPoint["status"],
  id: string,
  sw: number | null,
  sh: number | null,
  rw: number | null,
  rh: number | null,
): DisplayPoint {
  const s = toPercent(item.source_xy, sw, sh);
  const r = toPercent(item.reference_xy, rw, rh);
  return {
    id,
    x: s.x,
    y: s.y,
    rx: r.x,
    ry: r.y,
    residual: formatScientific(item.residual ?? null),
    residualValue: item.residual ?? null,
    confidence: formatConfidence(item.confidence ?? null),
    status,
    sourcePixel: formatPixel(item.source_xy),
    referencePixel: formatPixel(item.reference_xy),
  };
}

export function baselineResultsView(): ResultsViewModel {
  const flags = [...exp000.flags];
  const points: DisplayPoint[] = exp000.points.map((p, i) => ({
    id: `CP-${i + 1}`,
    x: p.x,
    y: p.y,
    rx: p.rx,
    ry: p.ry,
    residual: p.residual,
    residualValue: null,
    confidence: "Not available",
    status: "control" as const,
    sourcePixel: "Not available",
    referencePixel: "Not available",
  }));

  return {
    id: exp000.id,
    source: exp000.source,
    reference: exp000.reference,
    sourceProduct: exp000.sourceProduct,
    referenceProduct: exp000.referenceProduct,
    acquisitionTimeSource: exp000.acquisitionTimeSource,
    acquisitionTimeReference: exp000.acquisitionTimeReference,
    sunAzimuth: null,
    sunIncidence: null,
    region: exp000.region,
    sourceDims: {
      width: exp000.sourceDims.width,
      height: exp000.sourceDims.height,
      gsd: exp000.sourceDims.gsd,
    },
    referenceDims: {
      width: exp000.referenceDims.width,
      height: exp000.referenceDims.height,
    },
    sourceStride: `×${exp000.sourceStride}`,
    referenceStride: `×${exp000.referenceStride}`,
    rawMatches: exp000.rawMatches,
    verified: exp000.verified,
    rejected: exp000.rejected,
    controlPointCount: exp000.points.length,
    inlierRatio: exp000.inlierRatio,
    coverage: exp000.coverage,
    rmse: exp000.rmse,
    rmseLabel: "Verification residual RMSE",
    runtimeSeconds: exp000.runtimeSeconds,
    refinement: exp000.refinement,
    registration: exp000.registration,
    independentAccuracy: exp000.independentAccuracy,
    residualNote: exp000.residualNote,
    evaluationLimitation: null,
    flags,
    confidenceClass: null,
    resultStatus: deriveResultStatus({
      confidenceClass: null,
      flags,
    }),
    fullRasterBlocked: flags.includes("registration_output_too_large"),
    points,
    mapPoints: points,
    registeredArtifactUrl: null,
    previewSourceUrl: null,
    previewReferenceUrl: null,
    previewRegisteredUrl: null,
    previewAvailable: false,
    previewMode: null,
    previewNote: "Static fixture has no live overlay preview.",
    transformationModel: null,
    isLive: false,
    jobId: null,
  };
}

export function fromRegistrationResult(
  result: RegistrationResultDTO,
  options: { jobId: string; artifactUrl: string | null },
): ResultsViewModel {
  const { jobId, artifactUrl } = options;
  const sw = result.source.width_px;
  const sh = result.source.height_px;
  const rw = result.reference.width_px;
  const rh = result.reference.height_px;
  const pointsSource = result.control_points.length
    ? result.control_points
    : result.inliers;
  const points: DisplayPoint[] = pointsSource.slice(0, 12).map((item, i) =>
    makeDisplayPoint(item, "control", `CP-${i + 1}`, sw, sh, rw, rh),
  );

  const mapPoints: DisplayPoint[] = [];
  const pushMapPoint = (
    item: {
      source_xy: [number, number];
      reference_xy: [number, number];
      residual?: number | null;
      confidence?: number | null;
      status?: string;
    },
    status: DisplayPoint["status"],
    id: string,
  ) => {
    mapPoints.push(makeDisplayPoint(item, status, id, sw, sh, rw, rh));
  };

  result.correspondences.forEach((item, i) => {
    const status =
      item.status === "inlier"
        ? "inlier"
        : item.status === "rejected"
          ? "rejected"
          : "candidate";
    pushMapPoint(item, status, `M-${i + 1}`);
  });
  if (mapPoints.length === 0) {
    result.inliers.forEach((item, i) => pushMapPoint(item, "inlier", `I-${i + 1}`));
  }
  result.control_points.forEach((item, i) => {
    const s = toPercent(item.source_xy, sw, sh);
    const existing = mapPoints.find(
      (p) => Math.abs(p.x - s.x) < 0.05 && Math.abs(p.y - s.y) < 0.05,
    );
    if (existing) {
      existing.status = "control";
      existing.id = `CP-${i + 1}`;
    } else {
      pushMapPoint(item, "control", `CP-${i + 1}`);
    }
  });

  const gsd =
    result.source.gsd_meters != null ? `${result.source.gsd_meters} m/px` : "GSD unavailable";

  const previewAvailable = Boolean(result.preview_available);
  const previewQuery = previewAvailable ? `?v=${encodeURIComponent(jobId)}` : "";
  const previewSourceUrl =
    previewAvailable && jobId
      ? `/registration/jobs/${encodeURIComponent(jobId)}/artifacts/preview_source${previewQuery}`
      : null;
  const previewReferenceUrl =
    previewAvailable && jobId
      ? `/registration/jobs/${encodeURIComponent(jobId)}/artifacts/preview_reference${previewQuery}`
      : null;
  const previewRegisteredUrl =
    previewAvailable && jobId
      ? `/registration/jobs/${encodeURIComponent(jobId)}/artifacts/preview_registered${previewQuery}`
      : null;

  const flags = result.quality_flags;
  const controlPointCount =
    result.metrics?.control_point_count ?? result.control_points.length;

  return {
    id: result.pair_id,
    source: result.source.instrument,
    reference: result.reference.instrument,
    sourceProduct: result.source.product_id,
    referenceProduct: result.reference.product_id,
    acquisitionTimeSource: result.source.acquisition_time ?? "Unavailable",
    acquisitionTimeReference: result.reference.acquisition_time ?? "Unavailable",
    sunAzimuth: result.source.sun_azimuth ?? null,
    sunIncidence: result.source.sun_incidence ?? null,
    region: null,
    sourceDims: {
      width: sw,
      height: sh,
      gsd,
    },
    referenceDims: {
      width: rw,
      height: rh,
    },
    sourceStride: "from pipeline",
    referenceStride: "from pipeline",
    rawMatches: result.candidate_correspondences,
    verified: result.verified_inliers,
    rejected: result.rejected_correspondences,
    controlPointCount,
    inlierRatio: pct(result.metrics?.inlier_ratio),
    coverage: pct(result.metrics?.spatial_coverage),
    rmse: formatScientific(result.metrics?.verification_residual_rmse),
    rmseLabel: result.metrics?.verification_residual_rmse_label ?? "Verification residual RMSE",
    runtimeSeconds: result.runtime_seconds,
    refinement: result.refinement_note ?? "Refinement status unavailable",
    registration: registrationSummary(result),
    independentAccuracy:
      result.metrics?.independent_accuracy_claim ?? "Not independently validated",
    residualNote: result.residual_note,
    evaluationLimitation: result.evaluation_limitation ?? null,
    flags,
    confidenceClass: result.confidence_class,
    resultStatus: deriveResultStatus({
      confidenceClass: result.confidence_class,
      flags,
    }),
    fullRasterBlocked: flags.includes("registration_output_too_large"),
    points,
    mapPoints,
    registeredArtifactUrl: artifactUrl,
    previewSourceUrl,
    previewReferenceUrl,
    previewRegisteredUrl,
    previewAvailable,
    previewMode: result.preview_mode ?? null,
    previewNote: result.preview_note ?? null,
    transformationModel: result.transformation?.model_name ?? null,
    isLive: true,
    jobId,
  };
}
