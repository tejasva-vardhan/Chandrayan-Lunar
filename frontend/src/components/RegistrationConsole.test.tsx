import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RegistrationConsole } from "../components/RegistrationConsole";
import type { ApiClient } from "../api/client";
import { baselineResultsView } from "../api/resultsView";
import { ApiClientError } from "../api/types";

afterEach(() => {
  cleanup();
});

function mockClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    health: vi.fn(),
    uploadProduct: vi.fn(),
    listProducts: vi.fn().mockResolvedValue([]),
    listCatalog: vi.fn().mockResolvedValue({
      data_root_configured: false,
      data_root_env: "CHANDRAYAN_DATA_ROOT",
      product_count: 0,
      products: [],
      message: "unset",
    }),
    getExp000Pair: vi.fn().mockResolvedValue({
      available: false,
      pair_id: "pair_01_equatorial",
      experiment_id: "EXP-000",
      source: null,
      reference: null,
      message: "unset",
    }),
    createJob: vi.fn(),
    getJob: vi.fn(),
    getResult: vi.fn(),
    artifactUrl: vi.fn((jobId: string, name: string) => `/registration/jobs/${jobId}/artifacts/${name}`),
    ...overrides,
  } as ApiClient;
}

describe("RegistrationConsole", () => {
  it("shows loading/running state then success results", async () => {
    const onResults = vi.fn();
    const client = mockClient({
      createJob: vi.fn().mockResolvedValue({
        job_id: "job-ok",
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
          job_id: "job-ok",
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
          job_id: "job-ok",
          status: "completed",
          current_stage: null,
          completed_stages: ["ingest_product", "match", "export_result"],
          stages: ["ingest_product", "match", "export_result"],
          error: null,
          created_at: "t0",
          updated_at: "t2",
          runtime_seconds: 1.5,
        }),
      getResult: vi.fn().mockResolvedValue({
        job_id: "job-ok",
        status: "completed",
        error: null,
        result: {
          pair_id: "pair",
          source: {
            product_id: "s",
            instrument: "OHRC",
            mission: null,
            width_px: 10,
            height_px: 10,
            gsd_meters: null,
            acquisition_time: null,
            sun_azimuth: null,
            sun_incidence: null,
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
            sun_azimuth: null,
            sun_incidence: null,
            raster_uri: null,
          },
          candidate_correspondences: 5,
          verified_inliers: 3,
          rejected_correspondences: 2,
          correspondences: [],
          inliers: [],
          control_points: [],
          metrics: {
            verification_residual_rmse: 0.1,
            verification_residual_rmse_label: "Verification residual RMSE",
            inlier_count: 3,
            inlier_ratio: 0.6,
            spatial_coverage: 0.2,
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
          runtime_seconds: 1.5,
          export_manifest: null,
        },
      }),
    });

    render(<RegistrationConsole client={client} onResults={onResults} pollIntervalMs={20} />);
    fireEvent.change(screen.getByPlaceholderText(/ohrc_product/i), {
      target: { value: "C:/data/source" },
    });
    fireEvent.change(screen.getByPlaceholderText(/M150368601RC/i), {
      target: { value: "C:/data/reference.IMG" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start registration/i }));

    expect(await screen.findByText(/running/i)).toBeTruthy();
    await waitFor(() => expect(onResults).toHaveBeenCalled());
    expect(onResults.mock.calls[0][0].isLive).toBe(true);
    expect(onResults.mock.calls[0][0].verified).toBe(3);
  });

  it("renders failure message from API", async () => {
    const client = mockClient({
      createJob: vi.fn().mockRejectedValue(
        new ApiClientError(400, {
          code: "unsupported_product",
          message: "Unsupported or unrecognised lunar product",
        }),
      ),
    });
    render(<RegistrationConsole client={client} onResults={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/ohrc_product/i), {
      target: { value: "C:/bad/source" },
    });
    fireEvent.change(screen.getByPlaceholderText(/M150368601RC/i), {
      target: { value: "C:/bad/reference" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start registration/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/unrecognised lunar product/i);
  });

  it("can restore EXP-000 baseline view", () => {
    const onResults = vi.fn();
    render(<RegistrationConsole client={mockClient()} onResults={onResults} />);
    fireEvent.click(screen.getByRole("button", { name: /show static exp-000 fixture/i }));
    expect(onResults).toHaveBeenCalledWith(baselineResultsView());
  });
});
