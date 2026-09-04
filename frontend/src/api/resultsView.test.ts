import { describe, expect, it } from "vitest";
import { baselineResultsView, fromRegistrationResult } from "./resultsView";
import type { RegistrationResultDTO } from "./types";

function sampleResult(overrides: Partial<RegistrationResultDTO> = {}): RegistrationResultDTO {
  return {
    pair_id: "pair-live",
    source: {
      product_id: "src",
      instrument: "OHRC",
      mission: null,
      width_px: 100,
      height_px: 100,
      gsd_meters: 0.25,
      acquisition_time: null,
      raster_uri: null,
    },
    reference: {
      product_id: "ref",
      instrument: "LRO_NAC",
      mission: null,
      width_px: 100,
      height_px: 100,
      gsd_meters: null,
      acquisition_time: null,
      raster_uri: null,
    },
    candidate_correspondences: 10,
    verified_inliers: 4,
    rejected_correspondences: 6,
    correspondences: [],
    inliers: [],
    control_points: [
      { source_xy: [10, 20], reference_xy: [30, 40], residual: 1.2e-3, uncertainty: null },
    ],
    metrics: {
      verification_residual_rmse: 1.2e-3,
      verification_residual_rmse_label: "Verification residual RMSE",
      inlier_count: 4,
      inlier_ratio: 0.4,
      spatial_coverage: 0.25,
      control_point_count: 1,
      independent_accuracy_claim: "Not independently validated",
    },
    transformation: { model_name: "projective_2d_baseline", parameters: {} },
    registered_source_uri: null,
    registered_artifact_available: false,
    quality_flags: [],
    confidence_class: null,
    refinement_note: "indeterminate",
    residual_note: "Verification transfer residuals are image-space fit values",
    evaluation_limitation: null,
    runtime_seconds: 2.5,
    export_manifest: null,
    preview_available: false,
    preview_mode: null,
    preview_note: null,
    ...overrides,
  };
}

describe("resultsView", () => {
  it("labels baseline RMSE as verification residual", () => {
    const view = baselineResultsView();
    expect(view.rmseLabel).toBe("Verification residual RMSE");
    expect(view.isLive).toBe(false);
  });

  it("maps successful live results", () => {
    const view = fromRegistrationResult(sampleResult(), {
      jobId: "job-9",
      artifactUrl: null,
    });
    expect(view.isLive).toBe(true);
    expect(view.rawMatches).toBe(10);
    expect(view.verified).toBe(4);
    expect(view.rmseLabel).toBe("Verification residual RMSE");
    expect(view.inlierRatio).toBe("40.0%");
    expect(view.points).toHaveLength(1);
  });

  it("builds overlay preview artifact urls when available", () => {
    const view = fromRegistrationResult(
      sampleResult({ preview_available: true, preview_mode: "diagnostic_crop" }),
      { jobId: "job-preview", artifactUrl: null },
    );
    expect(view.previewAvailable).toBe(true);
    expect(view.previewReferenceUrl).toContain(
      "/registration/jobs/job-preview/artifacts/preview_reference",
    );
    expect(view.previewRegisteredUrl).toContain(
      "/registration/jobs/job-preview/artifacts/preview_registered",
    );
  });

  it("maps no-match diagnostics", () => {
    const view = fromRegistrationResult(
      sampleResult({
        candidate_correspondences: 0,
        verified_inliers: 0,
        rejected_correspondences: 0,
        quality_flags: ["no_correspondences"],
        metrics: {
          verification_residual_rmse: null,
          verification_residual_rmse_label: "Verification residual RMSE",
          inlier_count: 0,
          inlier_ratio: null,
          spatial_coverage: null,
          control_point_count: 0,
          independent_accuracy_claim: "Not independently validated",
        },
      }),
      { jobId: "job-0", artifactUrl: null },
    );
    expect(view.rawMatches).toBe(0);
    expect(view.flags).toContain("no_correspondences");
    expect(view.registration.toLowerCase()).toContain("no correspondences");
  });

  it("maps failure-oriented registration summary", () => {
    const view = fromRegistrationResult(
      sampleResult({
        quality_flags: ["insufficient_verified_matches"],
        verified_inliers: 0,
        transformation: null,
      }),
      { jobId: "job-f", artifactUrl: null },
    );
    expect(view.registration.toLowerCase()).toContain("insufficient verified");
  });
});
