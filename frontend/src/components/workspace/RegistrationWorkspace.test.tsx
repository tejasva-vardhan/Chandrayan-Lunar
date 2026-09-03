import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../../api/client";
import { baselineResultsView } from "../../api/resultsView";
import { ApiClientError } from "../../api/types";
import { RegistrationWorkspace } from "./RegistrationWorkspace";

afterEach(() => {
  cleanup();
});

function mockClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    health: vi.fn(),
    uploadProduct: vi.fn(),
    listProducts: vi.fn().mockResolvedValue([]),
    listCatalog: vi.fn().mockResolvedValue({
      data_root_configured: true,
      data_root_env: "CHANDRAYAN_DATA_ROOT",
      product_count: 2,
      products: [
        {
          product_id: "catalog-ohrc",
          path: "<CHANDRAYAN_DATA_ROOT>/ohrc",
          origin: "data_root",
          filename: "ohrc",
          logical_id: "ch2_ohr_demo",
          instrument_hint: "OHRC",
        },
        {
          product_id: "catalog-lroc",
          path: "<CHANDRAYAN_DATA_ROOT>/lroc.IMG",
          origin: "data_root",
          filename: "lroc.IMG",
          logical_id: "M150368601RC",
          instrument_hint: "LRO_NAC",
        },
      ],
      message: null,
    }),
    getExp000Pair: vi.fn().mockResolvedValue({
      available: true,
      pair_id: "pair_01_equatorial",
      experiment_id: "EXP-000",
      source: {
        product_id: "catalog-ohrc",
        path: "<CHANDRAYAN_DATA_ROOT>/ohrc",
        origin: "data_root",
        filename: "ohrc",
        logical_id: "ch2_ohr_demo",
        instrument_hint: "OHRC",
      },
      reference: {
        product_id: "catalog-lroc",
        path: "<CHANDRAYAN_DATA_ROOT>/lroc.IMG",
        origin: "data_root",
        filename: "lroc.IMG",
        logical_id: "M150368601RC",
        instrument_hint: "LRO_NAC",
      },
      message: null,
    }),
    createJob: vi.fn(),
    getJob: vi.fn(),
    getResult: vi.fn(),
    artifactUrl: vi.fn((jobId: string, name: string) => `/registration/jobs/${jobId}/artifacts/${name}`),
    ...overrides,
  } as ApiClient;
}

function liveResult(verified = 3) {
  return {
    job_id: "job-live",
    status: "completed" as const,
    error: null,
    result: {
      pair_id: "pair-live",
      source: {
        product_id: "s",
        instrument: "OHRC",
        mission: null,
        width_px: 10,
        height_px: 10,
        gsd_meters: null,
        acquisition_time: null,
        raster_uri: null,
      },
      reference: {
        product_id: "r",
        instrument: "LRO_NAC",
        mission: null,
        width_px: 10,
        height_px: 10,
        gsd_meters: null,
        acquisition_time: null,
        raster_uri: null,
      },
      candidate_correspondences: 7,
      verified_inliers: verified,
      rejected_correspondences: 4,
      correspondences: [],
      inliers: [],
      control_points: [],
      metrics: {
        verification_residual_rmse: 0.42,
        verification_residual_rmse_label: "Verification residual RMSE",
        inlier_count: verified,
        inlier_ratio: verified / 7,
        spatial_coverage: 0.18,
        control_point_count: 0,
        independent_accuracy_claim: "Not independently validated",
      },
      transformation: null,
      registered_source_uri: null,
      registered_artifact_available: false,
      quality_flags: [],
      confidence_class: null,
      refinement_note: null,
      residual_note: "note",
      evaluation_limitation: null,
      runtime_seconds: 2.2,
      export_manifest: null,
    },
  };
}

describe("RegistrationWorkspace", () => {
  it("blocks RUN REGISTRATION when source or reference is missing", async () => {
    render(<RegistrationWorkspace client={mockClient()} onResults={vi.fn()} />);
    const run = await screen.findByRole("button", { name: /run registration/i });
    expect(run).toBeDisabled();
    expect(screen.getByText(/select both source and reference/i)).toBeTruthy();
  });

  it("rejects invalid upload and keeps run disabled", async () => {
    const client = mockClient({
      uploadProduct: vi.fn().mockRejectedValue(
        new ApiClientError(400, {
          code: "unsupported_product",
          message: "Unsupported upload extension '.png'.",
        }),
      ),
    });
    const { container } = render(<RegistrationWorkspace client={client} onResults={vi.fn()} />);
    const fileInputs = container.querySelectorAll('input[type="file"]');
    const file = new File([new Uint8Array([1, 2, 3])], "photo.png", { type: "image/png" });
    fireEvent.change(fileInputs[0], { target: { files: [file] } });
    expect(await screen.findByText(/unsupported upload extension/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /run registration/i })).toBeDisabled();
  });

  it("creates a job when both uploads succeed and shows live API metrics", async () => {
    const onResults = vi.fn();
    const client = mockClient({
      uploadProduct: vi
        .fn()
        .mockResolvedValueOnce({
          product_id: "upload-src",
          stored_path: "<upload>/source.IMG",
          filename: "source.IMG",
          bytes: 12,
        })
        .mockResolvedValueOnce({
          product_id: "upload-ref",
          stored_path: "<upload>/reference.IMG",
          filename: "reference.IMG",
          bytes: 14,
        }),
      createJob: vi.fn().mockResolvedValue({
        job_id: "job-live",
        status: "running",
        current_stage: "match",
        completed_stages: ["ingest_product"],
        stages: ["ingest_product", "match", "export_result"],
        error: null,
        created_at: "t0",
        updated_at: "t1",
        runtime_seconds: null,
      }),
      getJob: vi
        .fn()
        .mockResolvedValueOnce({
          job_id: "job-live",
          status: "running",
          current_stage: "match",
          completed_stages: ["ingest_product"],
          stages: ["ingest_product", "match", "export_result"],
          error: null,
          created_at: "t0",
          updated_at: "t1",
          runtime_seconds: null,
        })
        .mockResolvedValue({
          job_id: "job-live",
          status: "completed",
          current_stage: null,
          completed_stages: ["ingest_product", "match", "export_result"],
          stages: ["ingest_product", "match", "export_result"],
          error: null,
          created_at: "t0",
          updated_at: "t2",
          runtime_seconds: 2.2,
        }),
      getResult: vi.fn().mockResolvedValue(liveResult(3)),
    });

    const { container } = render(
      <RegistrationWorkspace client={client} onResults={onResults} pollIntervalMs={20} />,
    );
    const fileInputs = container.querySelectorAll('input[type="file"]');
    fireEvent.change(fileInputs[0], {
      target: { files: [new File([new Uint8Array([1])], "source.IMG")] },
    });
    fireEvent.change(fileInputs[1], {
      target: { files: [new File([new Uint8Array([2])], "reference.IMG")] },
    });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /run registration/i })).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: /run registration/i }));

    await waitFor(() => expect(onResults).toHaveBeenCalled());
    const view = onResults.mock.calls[0][0];
    expect(view.isLive).toBe(true);
    expect(view.verified).toBe(3);
    expect(view.rawMatches).toBe(7);
    // Must not use hardcoded EXP-000 fixture metrics for live results.
    const fixture = baselineResultsView();
    expect(view.verified).not.toBe(fixture.verified);
    expect(view.rawMatches).not.toBe(fixture.rawMatches);
    expect(client.createJob).toHaveBeenCalledWith({
      source_product_id: "upload-src",
      reference_product_id: "upload-ref",
    });
  });

  it("displays backend failure messages", async () => {
    const client = mockClient({
      getExp000Pair: vi.fn().mockResolvedValue({
        available: true,
        pair_id: "pair_01_equatorial",
        experiment_id: "EXP-000",
        source: {
          product_id: "catalog-ohrc",
          path: "<CHANDRAYAN_DATA_ROOT>/ohrc",
          origin: "data_root",
          filename: "ohrc",
          logical_id: "ch2_ohr_demo",
          instrument_hint: "OHRC",
        },
        reference: {
          product_id: "catalog-lroc",
          path: "<CHANDRAYAN_DATA_ROOT>/lroc.IMG",
          origin: "data_root",
          filename: "lroc.IMG",
          logical_id: "M150368601RC",
          instrument_hint: "LRO_NAC",
        },
        message: null,
      }),
      createJob: vi.fn().mockRejectedValue(
        new ApiClientError(500, {
          code: "backend_exception",
          message: "Pipeline worker crashed",
        }),
      ),
    });
    render(<RegistrationWorkspace client={client} onResults={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /load exp-000 real pair/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /run registration/i })).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: /run registration/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/pipeline worker crashed/i);
  });

  it("loads the static fixture without treating it as a live result", async () => {
    const onResults = vi.fn();
    render(<RegistrationWorkspace client={mockClient()} onResults={onResults} />);
    fireEvent.click(screen.getByRole("button", { name: /show static exp-000 fixture/i }));
    expect(onResults).toHaveBeenCalledWith(baselineResultsView());
    expect(onResults.mock.calls[0][0].isLive).toBe(false);
  });
});
