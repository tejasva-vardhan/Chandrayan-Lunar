import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../../api/client";
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
          path: "/data/ohrc",
          origin: "data_root",
          filename: "ohrc.zip",
          logical_id: "ohrc",
          instrument_hint: "OHRC",
        },
        {
          product_id: "catalog-lroc",
          path: "/data/lroc",
          origin: "data_root",
          filename: "lroc.IMG",
          logical_id: "lroc",
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
        path: "/data/ohrc",
        origin: "data_root",
        filename: "ohrc.zip",
        logical_id: "ohrc",
        instrument_hint: "OHRC",
      },
      reference: {
        product_id: "catalog-lroc",
        path: "/data/lroc",
        origin: "data_root",
        filename: "lroc.IMG",
        logical_id: "lroc",
        instrument_hint: "LRO_NAC",
      },
      message: null,
    }),
    createJob: vi.fn(),
    getJob: vi.fn(),
    getResult: vi.fn(),
    artifactUrl: vi.fn(
      (jobId: string, name: string) => `/registration/jobs/${jobId}/artifacts/${name}`,
    ),
    ...overrides,
  } as ApiClient;
}

function liveResultPayload(jobId: string) {
  return {
    job_id: jobId,
    status: "completed" as const,
    error: null,
    result: {
      pair_id: "pair-live",
      source: {
        product_id: "s",
        instrument: "Chandrayaan-2 OHRC",
        mission: null,
        width_px: 100,
        height_px: 100,
        gsd_meters: 0.25,
        acquisition_time: null,
        sun_azimuth: null,
        sun_incidence: null,
        raster_uri: null,
      },
      reference: {
        product_id: "r",
        instrument: "LRO NAC",
        mission: null,
        width_px: 100,
        height_px: 100,
        gsd_meters: null,
        acquisition_time: null,
        sun_azimuth: null,
        sun_incidence: null,
        raster_uri: null,
      },
      candidate_correspondences: 919,
      verified_inliers: 25,
      rejected_correspondences: 894,
      correspondences: [],
      inliers: [],
      control_points: [
        { source_xy: [10, 20], reference_xy: [30, 40], residual: null, uncertainty: null },
      ],
      metrics: {
        verification_residual_rmse: 0.01,
        verification_residual_rmse_label: "Verification residual RMSE",
        inlier_count: 25,
        inlier_ratio: 0.027,
        spatial_coverage: 0.506,
        control_point_count: 1,
        independent_accuracy_claim: "Not independently validated",
      },
      transformation: { model_name: "projective_2d_baseline", parameters: {} },
      registered_source_uri: null,
      registered_artifact_available: false,
      quality_flags: ["registration_output_too_large", "not_independently_validated"],
      confidence_class: null,
      refinement_note: "indeterminate",
      residual_note: "fit residual",
      evaluation_limitation: null,
      runtime_seconds: 1.2,
      export_manifest: null,
      preview_available: true,
      preview_mode: "diagnostic_crop",
      preview_note: "test preview",
    },
  };
}

describe("RegistrationWorkspace flow", () => {
  it("publishes live results after a completed job", async () => {
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
      getResult: vi.fn().mockResolvedValue(liveResultPayload("job-ok")),
    });

    render(<RegistrationWorkspace client={client} onResults={onResults} pollIntervalMs={20} />);
    fireEvent.click(await screen.findByRole("button", { name: /load exp-000 real pair/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /run registration/i })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: /run registration/i }));

    await waitFor(
      () => {
        expect(onResults.mock.calls.some((c) => c[0]?.isLive === true)).toBe(true);
      },
      { timeout: 5000 },
    );
    const published = onResults.mock.calls.find((c) => c[0]?.isLive)?.[0];
    expect(published.rawMatches).toBe(919);
    expect(published.verified).toBe(25);
    expect(await screen.findByRole("button", { name: /view live results/i })).toBeInTheDocument();
  });

  it("clears results and reports backend failure at ingest", async () => {
    const onResults = vi.fn();
    const onRunError = vi.fn();
    const client = mockClient({
      createJob: vi.fn().mockResolvedValue({
        job_id: "job-fail",
        status: "running",
        current_stage: "ingest_product",
        completed_stages: [],
        stages: ["ingest_product", "match", "export_result"],
        error: null,
        created_at: "t0",
        updated_at: "t1",
        runtime_seconds: null,
      }),
      getJob: vi.fn().mockResolvedValue({
        job_id: "job-fail",
        status: "failed",
        current_stage: "ingest_product",
        completed_stages: [],
        stages: ["ingest_product", "match", "export_result"],
        error: { message: "OSError: [Errno 28] No space left on device" },
        created_at: "t0",
        updated_at: "t2",
        runtime_seconds: 0.2,
      }),
      getResult: vi.fn().mockResolvedValue({
        job_id: "job-fail",
        status: "failed",
        result: null,
        error: {
          code: "backend_exception",
          message: "OSError: [Errno 28] No space left on device",
          failed_stage: "ingest_product",
        },
      }),
    });

    render(
      <RegistrationWorkspace
        client={client}
        onResults={onResults}
        onRunError={onRunError}
        pollIntervalMs={20}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /load exp-000 real pair/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /run registration/i })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: /run registration/i }));

    await waitFor(() =>
      expect(onRunError).toHaveBeenCalledWith(
        expect.stringMatching(/No space left on device/i),
      ),
    );
    expect(onResults).toHaveBeenCalledWith(null);
    expect(await screen.findByRole("alert")).toHaveTextContent(/No space left on device/i);
  });

  it("surfaces upload API failures instead of silent break", async () => {
    const onResults = vi.fn();
    const client = mockClient({
      uploadProduct: vi.fn().mockRejectedValue(
        new ApiClientError(400, {
          code: "storage_full",
          message: "Upload failed: no space left on the API work disk.",
        }),
      ),
    });

    render(<RegistrationWorkspace client={client} onResults={onResults} />);
    const file = new File([new Uint8Array([1, 2, 3])], "ch2_ohr_demo.zip", {
      type: "application/zip",
    });
    const inputs = document.querySelectorAll('input[type="file"]');
    fireEvent.change(inputs[0], { target: { files: [file] } });
    fireEvent.change(inputs[1], {
      target: {
        files: [new File([new Uint8Array([4, 5, 6])], "M150368601RC.IMG", { type: "application/octet-stream" })],
      },
    });
    await waitFor(() => expect(screen.getByRole("button", { name: /run registration/i })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: /run registration/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no space left/i);
  });
});
