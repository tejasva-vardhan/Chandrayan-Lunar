import { describe, expect, it } from "vitest";
import {
  baselineResultsView,
  deriveResultStatus,
  fromRegistrationResult,
} from "./resultsView";
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
    candidate_correspondences: 36,
    verified_inliers: 4,
    rejected_correspondences: 32,
    correspondences: [],
    inliers: [],
    control_points: [
      { source_xy: [10, 20], reference_xy: [30, 40], residual: 1.2e-3, uncertainty: null },
    ],
    metrics: {
      verification_residual_rmse: 1.2e-3,
      verification_residual_rmse_label: "Verification residual RMSE",
      inlier_count: 4,
      inlier_ratio: 0.111,
      spatial_coverage: 0.232,
      control_point_count: 4,
      independent_accuracy_claim: "Not independently validated",
    },
    transformation: { model_name: "projective_2d_baseline", parameters: {} },
    registered_source_uri: null,
    registered_artifact_available: false,
    quality_flags: ["registration_output_too_large", "not_independently_validated"],
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
  it("labels baseline RMSE as verification residual and keeps fixture non-live", () => {
    const view = baselineResultsView();
    expect(view.rmseLabel).toBe("Verification residual RMSE");
    expect(view.isLive).toBe(false);
    expect(view.resultStatus).toBe("COMPLETED WITH LIMITATIONS");
    expect(view.rawMatches).toBe(36);
    expect(view.verified).toBe(4);
    expect(view.inlierRatio).toBe("11.1%");
    expect(view.controlPointCount).toBe(4);
    expect(view.coverage).toBe("23.2%");
    expect(view.fullRasterBlocked).toBe(true);
  });

  it("maps successful live results with isLive true", () => {
    const view = fromRegistrationResult(sampleResult(), {
      jobId: "job-9",
      artifactUrl: null,
    });
    expect(view.isLive).toBe(true);
    expect(view.rawMatches).toBe(36);
    expect(view.verified).toBe(4);
    expect(view.inlierRatio).toBe("11.1%");
    expect(view.coverage).toBe("23.2%");
    expect(view.controlPointCount).toBe(4);
    expect(view.rmseLabel).toBe("Verification residual RMSE");
    expect(view.rmseLabel.toLowerCase()).not.toContain("accuracy");
    expect(view.resultStatus).toBe("COMPLETED WITH LIMITATIONS");
    expect(view.fullRasterBlocked).toBe(true);
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
    expect(view.resultStatus).toBe("FAILED");
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
    expect(view.resultStatus).toBe("FAILED");
  });

  it("derives status labels from backend confidence_class and flags only", () => {
    expect(deriveResultStatus({ confidenceClass: "SUCCESS", flags: [] })).toBe("COMPLETED");
    expect(
      deriveResultStatus({
        confidenceClass: "SUCCESS",
        flags: ["registration_output_too_large"],
      }),
    ).toBe("COMPLETED WITH LIMITATIONS");
    expect(deriveResultStatus({ confidenceClass: "LOW_CONFIDENCE", flags: [] })).toBe(
      "LOW CONFIDENCE",
    );
    expect(deriveResultStatus({ confidenceClass: "FAILED", flags: [] })).toBe("FAILED");
  });
});
