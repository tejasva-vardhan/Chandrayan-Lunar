import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import {
  baselineResultsView,
  fromRegistrationResult,
} from "../../api/resultsView";
import type { RegistrationResultDTO } from "../../api/types";
import { ResultsPanel } from "./ResultsPanel";

function sampleResult(overrides: Partial<RegistrationResultDTO> = {}): RegistrationResultDTO {
  return {
    pair_id: "pair-live",
    source: {
      product_id: "ch2_ohr_ncp_20210402T0546284043_d_img_d18",
      instrument: "Chandrayaan-2 OHRC",
      mission: null,
      width_px: 100,
      height_px: 100,
      gsd_meters: 0.25,
      acquisition_time: null,
      raster_uri: null,
    },
    reference: {
      product_id: "M150368601RC",
      instrument: "LRO NAC",
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
    correspondences: [
      {
        source_xy: [10, 20],
        reference_xy: [30, 40],
        confidence: null,
        residual: 0.1,
        status: "inlier",
      },
      {
        source_xy: [50, 60],
        reference_xy: [70, 80],
        confidence: null,
        residual: null,
        status: "candidate",
      },
    ],
    inliers: [
      {
        source_xy: [10, 20],
        reference_xy: [30, 40],
        confidence: null,
        residual: 0.1,
        status: "inlier",
      },
    ],
    control_points: [
      { source_xy: [10, 20], reference_xy: [30, 40], residual: 1.2e-3, uncertainty: null },
      { source_xy: [25, 30], reference_xy: [45, 50], residual: null, uncertainty: null },
      { source_xy: [40, 55], reference_xy: [60, 70], residual: null, uncertainty: null },
      { source_xy: [70, 15], reference_xy: [55, 52], residual: null, uncertainty: null },
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

describe("ResultsPanel UX", () => {
  it("renders live header state and separates correspondence from spatial distribution", () => {
    const view = fromRegistrationResult(sampleResult(), {
      jobId: "job-live",
      artifactUrl: null,
    });
    const { container } = render(
      <ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />,
    );

    expect(screen.getAllByText("COMPLETED WITH LIMITATIONS").length).toBeGreaterThan(0);
    expect(screen.getByText(/EXP-000 Real-data Run/i)).toBeInTheDocument();
    expect(screen.getByText(/Live result · isLive: true/i)).toBeInTheDocument();

    expect(screen.getAllByRole("heading", { name: "Correspondence Evidence" }).length).toBe(1);
    expect(screen.getAllByRole("heading", { name: "Spatial Distribution" }).length).toBe(1);
    expect(screen.getAllByRole("heading", { name: "Registration Diagnostic" }).length).toBe(1);

    const correspondence = container.querySelector(".correspondence-evidence");
    const spatial = container.querySelector(".spatial-distribution");
    expect(correspondence).toBeTruthy();
    expect(spatial).toBeTruthy();
    expect(correspondence?.contains(spatial)).toBe(false);
    expect(spatial?.querySelector(".occupancy-grid")).toBeTruthy();
    expect(correspondence?.querySelector(".occupancy-grid")).toBeFalsy();
    expect(correspondence?.querySelector(".heatmap-panel")).toBeFalsy();

    expect(screen.getAllByText("36").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("4").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("11.1%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("23.2%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Indeterminate/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Not independently validated/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Full registered raster unavailable/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/output-size safety limit/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Diagnostic artifact not available/i)).toBeInTheDocument();

    const rmseBits = screen.getAllByText(/Verification residual RMSE/i);
    expect(rmseBits.length).toBeGreaterThan(0);
    rmseBits.forEach((el) => {
      expect(el.textContent?.toLowerCase()).not.toContain("accuracy");
    });

    expect(screen.getByText("SOURCE")).toBeInTheDocument();
    expect(screen.getByText("REFERENCE")).toBeInTheDocument();
    expect(
      screen.getByText("ch2_ohr_ncp_20210402T0546284043_d_img_d18"),
    ).toBeInTheDocument();
    expect(screen.getByText("M150368601RC")).toBeInTheDocument();
  });

  it("labels static fixture distinctly and keeps isLive false", () => {
    const view = baselineResultsView();
    expect(view.isLive).toBe(false);
    render(<ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />);
    expect(screen.getAllByText(/Static EXP-000 fixture/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Live result · isLive: true/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("36").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("11.1%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("23.2%").length).toBeGreaterThanOrEqual(1);
  });

  it("renders failed / low-confidence statuses from backend fields", () => {
    const failed = fromRegistrationResult(
      sampleResult({
        confidence_class: "FAILED",
        quality_flags: ["warp_failed"],
      }),
      { jobId: "j-fail", artifactUrl: null },
    );
    const { rerender } = render(
      <ResultsPanel results={failed} reducedMotion onFocusRegion={() => undefined} />,
    );
    expect(screen.getAllByText("FAILED").length).toBeGreaterThan(0);

    const low = fromRegistrationResult(
      sampleResult({
        confidence_class: "LOW_CONFIDENCE",
        quality_flags: [],
      }),
      { jobId: "j-low", artifactUrl: null },
    );
    rerender(<ResultsPanel results={low} reducedMotion onFocusRegion={() => undefined} />);
    expect(screen.getAllByText("LOW CONFIDENCE").length).toBeGreaterThan(0);
  });

  it("synchronizes point selection across source and reference viewports", () => {
    const view = fromRegistrationResult(sampleResult(), {
      jobId: "job-sync",
      artifactUrl: null,
    });
    render(<ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />);

    const evidence = screen.getByRole("heading", { name: "Correspondence Evidence" }).closest(
      "section",
    ) as HTMLElement;
    const buttons = within(evidence).getAllByRole("button", { pressed: false });
    expect(buttons.length).toBeGreaterThan(0);
    fireEvent.click(buttons[0]);
    const selected = within(evidence).getAllByRole("button", { pressed: true });
    expect(selected.length).toBe(2);
    expect(within(evidence).getByText(/Source coordinate/i)).toBeInTheDocument();
  });

  it("uses document-flow sections without absolute overlap wrappers", () => {
    const view = fromRegistrationResult(sampleResult(), {
      jobId: "job-layout",
      artifactUrl: null,
    });
    const { container } = render(
      <ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />,
    );
    expect(container.querySelector(".evidence-viewports")).toBeTruthy();
    expect(container.querySelector(".spatial-distribution")).toBeTruthy();
    expect(container.querySelector(".registration-diagnostic")).toBeTruthy();
    expect(container.querySelector(".heatmap-grid-layout")).toBeFalsy();
    expect(container.querySelector(".view-toggle-controls")).toBeFalsy();
  });
});
