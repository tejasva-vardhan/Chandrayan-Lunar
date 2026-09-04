import type { RegistrationResultDTO } from "../api/types";
import { exp000 } from "../data/exp000";

export type DisplayPoint = {
  x: number;
  y: number;
  rx: number;
  ry: number;
  residual: string;
  status: "inlier" | "rejected" | "control" | "candidate";
  residualValue: number | null;
};

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
  inlierRatio: string;
  coverage: string;
  rmse: string;
  rmseLabel: string;
  runtimeSeconds: number | null;
  refinement: string;
  registration: string;
  independentAccuracy: string;
  residualNote: string;
  flags: string[];
  points: DisplayPoint[];
  mapPoints: DisplayPoint[];
  registeredArtifactUrl: string | null;
  previewSourceUrl: string | null;
  previewReferenceUrl: string | null;
  previewRegisteredUrl: string | null;
  previewAvailable: boolean;
  previewMode: string | null;
  previewNote: string | null;
  isLive: boolean;
  jobId: string | null;
};

function formatScientific(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
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

export function baselineResultsView(): ResultsViewModel {
  return {
    id: exp000.id,
    source: exp000.source,
    reference: exp000.reference,
    sourceProduct: exp000.sourceProduct,
    referenceProduct: exp000.referenceProduct,
    acquisitionTimeSource: exp000.acquisitionTimeSource,
    acquisitionTimeReference: exp000.acquisitionTimeReference,
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
    inlierRatio: exp000.inlierRatio,
    coverage: exp000.coverage,
    rmse: exp000.rmse,
    rmseLabel: "Verification residual RMSE",
    runtimeSeconds: exp000.runtimeSeconds,
    refinement: exp000.refinement,
    registration: exp000.registration,
    independentAccuracy: exp000.independentAccuracy,
    residualNote: exp000.residualNote,
    flags: [...exp000.flags],
    points: exp000.points.map((p) => ({
      ...p,
      status: "control" as const,
      residualValue: null,
    })),
    mapPoints: exp000.points.map((p) => ({
      ...p,
      status: "control" as const,
      residualValue: null,
    })),
    registeredArtifactUrl: null,
    previewReferenceUrl: null,
    previewRegisteredUrl: null,
    previewAvailable: false,
    previewMode: null,
    previewNote: "Static fixture has no live overlay preview.",
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
  const points: DisplayPoint[] = pointsSource.slice(0, 12).map((item) => {
    const s = toPercent(item.source_xy, sw, sh);
    const r = toPercent(item.reference_xy, rw, rh);
    return {
      x: s.x,
      y: s.y,
      rx: r.x,
      ry: r.y,
      residual: formatScientific(item.residual),
      status: "control" as const,
      residualValue: item.residual ?? null,
    };
  });

  const mapPoints: DisplayPoint[] = [];
  const pushMapPoint = (
    item: { source_xy: [number, number]; reference_xy: [number, number]; residual?: number | null; status?: string },
    status: DisplayPoint["status"],
  ) => {
    const s = toPercent(item.source_xy, sw, sh);
    const r = toPercent(item.reference_xy, rw, rh);
    mapPoints.push({
      x: s.x,
      y: s.y,
      rx: r.x,
      ry: r.y,
      residual: formatScientific(item.residual ?? null),
      status,
      residualValue: item.residual ?? null,
    });
  };

  for (const item of result.correspondences) {
    const status =
      item.status === "inlier"
        ? "inlier"
        : item.status === "rejected"
          ? "rejected"
          : "candidate";
    pushMapPoint(item, status);
  }
  if (mapPoints.length === 0) {
    for (const item of result.inliers) pushMapPoint(item, "inlier");
  }
  for (const item of result.control_points) {
    // Prefer marking control points distinctly on top of inliers.
    const s = toPercent(item.source_xy, sw, sh);
    const existing = mapPoints.find(
      (p) => Math.abs(p.x - s.x) < 0.05 && Math.abs(p.y - s.y) < 0.05,
    );
    if (existing) existing.status = "control";
    else pushMapPoint(item, "control");
  }

  const gsd =
    result.source.gsd_meters != null ? `${result.source.gsd_meters} m/px` : "GSD unavailable";

  const previewAvailable = Boolean(result.preview_available);
  // Cache-bust so a re-run of the same job id (dev restarts) reloads PNGs.
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
    flags: result.quality_flags,
    points,
    mapPoints,
    registeredArtifactUrl: artifactUrl,
    previewSourceUrl,
    previewReferenceUrl,
    previewRegisteredUrl,
    previewAvailable,
    previewMode: result.preview_mode ?? null,
    previewNote: result.preview_note ?? null,
    isLive: true,
    jobId,
  };
}
