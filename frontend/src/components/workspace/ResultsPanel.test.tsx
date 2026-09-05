import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import {
  baselineResultsView,
  fromRegistrationResult,
} from "../../api/resultsView";
import type { RegistrationResultDTO } from "../../api/types";
import { ResultsPanel } from "./ResultsPanel";

/** Distinct from static EXP-000 fixture (36 / 4 / 11.1% / 4 / 23.2%). */
function liveSampleResult(overrides: Partial<RegistrationResultDTO> = {}): RegistrationResultDTO {
  return {
    pair_id: "pair-live-demo",
    source: {
      product_id: "ch2_ohr_ncp_20210402T0546284043_d_img_d18",
      instrument: "Chandrayaan-2 OHRC",
      mission: "Chandrayaan-2",
      width_px: 12000,
      height_px: 78175,
      gsd_meters: 0.26,
      acquisition_time: "2021-04-02T05:46:28Z",
      sun_azimuth: 120.5,
      sun_incidence: 45.2,
      raster_uri: null,
    },
    reference: {
      product_id: "M150368601RC",
      instrument: "LRO NAC",
      mission: "LRO",
      width_px: 5064,
      height_px: 52224,
      gsd_meters: null,
      acquisition_time: "2011-01-22T20:48:53Z",
      sun_azimuth: null,
      sun_incidence: null,
      raster_uri: null,
    },
    candidate_correspondences: 919,
    verified_inliers: 25,
    rejected_correspondences: 894,
    correspondences: [
      {
        source_xy: [100, 200],
        reference_xy: [300, 400],
        confidence: 0.91,
        residual: 0.12,
        status: "inlier",
      },
      {
        source_xy: [500, 600],
        reference_xy: [700, 800],
        confidence: null,
        residual: null,
        status: "candidate",
      },
      {
        source_xy: [50, 60],
        reference_xy: [70, 80],
        confidence: null,
        residual: null,
        status: "rejected",
      },
    ],
    inliers: [
      {
        source_xy: [100, 200],
        reference_xy: [300, 400],
        confidence: 0.91,
        residual: 0.12,
        status: "inlier",
      },
    ],
    control_points: [
      { source_xy: [100, 200], reference_xy: [300, 400], residual: 1.2e-3, uncertainty: null },
      { source_xy: [250, 300], reference_xy: [450, 500], residual: null, uncertainty: null },
      { source_xy: [400, 550], reference_xy: [600, 700], residual: null, uncertainty: null },
      { source_xy: [700, 150], reference_xy: [550, 520], residual: null, uncertainty: null },
      { source_xy: [900, 800], reference_xy: [200, 300], residual: null, uncertainty: null },
      { source_xy: [1100, 900], reference_xy: [800, 100], residual: null, uncertainty: null },
      { source_xy: [2000, 1000], reference_xy: [900, 200], residual: null, uncertainty: null },
      { source_xy: [3000, 2000], reference_xy: [1000, 400], residual: null, uncertainty: null },
      { source_xy: [4000, 3000], reference_xy: [1200, 600], residual: null, uncertainty: null },
      { source_xy: [5000, 4000], reference_xy: [1400, 800], residual: null, uncertainty: null },
      { source_xy: [6000, 5000], reference_xy: [1600, 1000], residual: null, uncertainty: null },
    ],
    metrics: {
      verification_residual_rmse: 1.2e-3,
      verification_residual_rmse_label: "Verification residual RMSE",
      inlier_count: 25,
      inlier_ratio: 0.027,
      spatial_coverage: 0.506,
      control_point_count: 11,
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
    runtime_seconds: 42.1,
    export_manifest: null,
    preview_available: false,
    preview_mode: null,
    preview_note: null,
    ...overrides,
  };
}

describe("ResultsPanel UX", () => {
  it("renders live metrics from the live result and never substitutes fixture values", () => {
    const view = fromRegistrationResult(liveSampleResult(), {
      jobId: "job-live",
      artifactUrl: null,
    });
    render(<ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />);

    expect(screen.getAllByText("LIVE RESULT").length).toBeGreaterThan(0);
    expect(screen.getAllByText("919").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("25").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("2.7%").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("11").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("50.6%").length).toBeGreaterThanOrEqual(2);

    // Static EXP-000 fixture values must not appear on a live run.
    expect(screen.queryByText("11.1%")).not.toBeInTheDocument();
    expect(screen.queryByText("23.2%")).not.toBeInTheDocument();
    expect(screen.queryByText(/STATIC EXP-000 FIXTURE/i)).not.toBeInTheDocument();
  });

  it("uses the same live correspondence and control-point data across evidence and spatial views", () => {
    const view = fromRegistrationResult(liveSampleResult(), {
      jobId: "job-live",
      artifactUrl: null,
    });
    const { container } = render(
      <ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />,
    );

    const correspondence = container.querySelector(".correspondence-evidence");
    const spatial = container.querySelector(".spatial-distribution");
    expect(correspondence).toBeTruthy();
    expect(spatial).toBeTruthy();
    expect(correspondence?.contains(spatial)).toBe(false);

    // Control points from live result appear in spatial occupancy.
    expect(within(spatial as HTMLElement).getByText(/Control points plotted: 11/i)).toBeInTheDocument();
    expect(spatial?.querySelector(".occupancy-grid")).toBeTruthy();
    expect(correspondence?.querySelector(".occupancy-grid")).toBeFalsy();

    // Quality certificate uses the same live values.
    const quality = container.querySelector("#quality");
    expect(quality).toBeTruthy();
    expect(within(quality as HTMLElement).getByText("919")).toBeInTheDocument();
    expect(within(quality as HTMLElement).getByText("25")).toBeInTheDocument();
    expect(within(quality as HTMLElement).getByText("2.7%")).toBeInTheDocument();
    expect(within(quality as HTMLElement).getByText("50.6%")).toBeInTheDocument();
  });

  it("labels static fixture distinctly and keeps isLive false", () => {
    const view = baselineResultsView();
    expect(view.isLive).toBe(false);
    render(<ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />);
    expect(screen.getAllByText(/STATIC EXP-000 FIXTURE/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/LIVE RESULT · isLive: true/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("36").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("11.1%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("23.2%").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("919")).not.toBeInTheDocument();
    expect(screen.queryByText("2.7%")).not.toBeInTheDocument();
  });

  it("handles missing live result cleanly", () => {
    render(<ResultsPanel results={null} reducedMotion onFocusRegion={() => undefined} />);
    expect(screen.getByText(/No live registration result is available yet/i)).toBeInTheDocument();
    expect(screen.getByText(/NO LIVE RESULT/i)).toBeInTheDocument();
    expect(screen.queryByText("919")).not.toBeInTheDocument();
    expect(screen.queryByText("36")).not.toBeInTheDocument();
    expect(document.getElementById("correspondence")).toBeTruthy();
    expect(document.getElementById("spatial")).toBeTruthy();
    expect(document.getElementById("quality")).toBeTruthy();
  });

  it("surfaces last registration error when no live result exists", () => {
    render(
      <ResultsPanel
        results={null}
        lastError="OSError: [Errno 28] No space left on device"
        reducedMotion
        onFocusRegion={() => undefined}
      />,
    );
    expect(screen.getByText(/Last registration did not produce a result/i)).toBeInTheDocument();
    expect(screen.getByText(/No space left on device/i)).toBeInTheDocument();
  });

  it("handles missing image preview honestly without fake imagery", () => {
    const view = fromRegistrationResult(liveSampleResult({ preview_available: false }), {
      jobId: "job-noprev",
      artifactUrl: null,
    });
    render(<ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />);
    expect(screen.getAllByText(/Image evidence unavailable for this run/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Registered full-raster output unavailable for this run/i).length,
    ).toBeGreaterThan(0);
    expect(document.querySelector(".viewport-canvas.is-fallback")).toBeFalsy();
  });

  it("renders failed / low-confidence statuses from backend fields", () => {
    const failed = fromRegistrationResult(
      liveSampleResult({
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
      liveSampleResult({
        confidence_class: "LOW_CONFIDENCE",
        quality_flags: [],
      }),
      { jobId: "j-low", artifactUrl: null },
    );
    rerender(<ResultsPanel results={low} reducedMotion onFocusRegion={() => undefined} />);
    expect(screen.getAllByText("LOW CONFIDENCE").length).toBeGreaterThan(0);
  });

  it("synchronizes point selection and shows acceptance path from backend status", () => {
    const view = fromRegistrationResult(liveSampleResult(), {
      jobId: "job-sync",
      artifactUrl: null,
    });
    render(<ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />);

    const evidence = screen.getByRole("heading", { name: "Correspondence Evidence" }).closest(
      "section",
    ) as HTMLElement;
    const markers = within(evidence).getAllByRole("button", {
      name: /^(Candidate|Verified|Control) /i,
    });
    expect(markers.length).toBeGreaterThan(0);
    fireEvent.click(markers[0]);
    const selected = within(evidence).getAllByRole("button", { pressed: true });
    expect(selected.length).toBe(2);
    expect(within(evidence).getByText(/Why was this match accepted/i)).toBeInTheDocument();
    const inspector = evidence.querySelector(".point-inspector") as HTMLElement;
    expect(within(inspector).getByText("Selected control point")).toBeInTheDocument();
    expect(within(inspector).getByText(/Awaiting|Geometric verification/i)).toBeInTheDocument();
  });

  it("never labels verification residual RMSE as accuracy", () => {
    const view = fromRegistrationResult(liveSampleResult(), {
      jobId: "job-rmse",
      artifactUrl: null,
    });
    const { container } = render(
      <ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />,
    );
    const labels = Array.from(
      container.querySelectorAll(".metric-kicker, .certificate dt, .residual-honesty b"),
    );
    const rmseLabels = labels.filter((el) =>
      /verification residual rmse/i.test(el.textContent ?? ""),
    );
    expect(rmseLabels.length).toBeGreaterThan(0);
    rmseLabels.forEach((el) => {
      expect(el.textContent?.toLowerCase()).not.toContain("accuracy");
    });
    expect(
      screen.getAllByText(/does not establish independent registration accuracy/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/Not independently validated/i).length).toBeGreaterThan(0);
  });

  it("keeps document-flow sections and demo path anchors", () => {
    const view = fromRegistrationResult(liveSampleResult(), {
      jobId: "job-layout",
      artifactUrl: null,
    });
    const { container } = render(
      <ResultsPanel results={view} reducedMotion onFocusRegion={() => undefined} />,
    );
    expect(container.querySelector("#correspondence")).toBeTruthy();
    expect(container.querySelector("#spatial")).toBeTruthy();
    expect(container.querySelector("#results-summary")).toBeTruthy();
    expect(container.querySelector("#quality")).toBeTruthy();
    expect(container.querySelector(".pair-characterization")).toBeTruthy();
    expect(container.querySelector(".image-comparison")).toBeTruthy();
    expect(container.querySelector(".refinement-panel")).toBeTruthy();
    expect(container.querySelector(".heatmap-grid-layout")).toBeFalsy();
  });
});
