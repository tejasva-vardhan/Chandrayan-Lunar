import { afterEach, describe, expect, it, vi } from "vitest";
import { createApiClient, resolveApiBaseUrl } from "../api/client";
import { ApiClientError } from "../api/types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("resolves empty base URL when VITE_API_BASE_URL is unset", () => {
    expect(resolveApiBaseUrl({})).toBe("");
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: "   " })).toBe("");
  });

  it("trims trailing slash from VITE_API_BASE_URL", () => {
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: "https://api.example.com/" })).toBe(
      "https://api.example.com",
    );
  });

  it("posts registration jobs and parses responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: "job-1",
        status: "queued",
        current_stage: null,
        completed_stages: [],
        stages: ["ingest_product"],
        error: null,
        created_at: "t0",
        updated_at: "t0",
        runtime_seconds: null,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("http://api.test");
    const job = await client.createJob({
      source_path: "/tmp/a",
      reference_path: "/tmp/b",
    });
    expect(job.job_id).toBe("job-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/registration/jobs",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("maps HTTP error bodies to ApiClientError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({
          code: "unsupported_product",
          message: "Unsupported lunar product",
        }),
      }),
    );
    const client = createApiClient();
    await expect(client.getJob("job-x")).rejects.toMatchObject({
      code: "unsupported_product",
      status: 400,
    });
  });

  it("shows FastAPI validation details instead of a generic status error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({
          detail: [
            {
              loc: ["body", "source_product_id"],
              msg: "Field required",
            },
          ],
        }),
      }),
    );
    const client = createApiClient();
    await expect(client.createJob({})).rejects.toMatchObject({
      code: "request_failure",
      message: "source_product_id: Field required",
      status: 400,
    });
  });

  it("maps network failures without stack traces", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    const client = createApiClient();
    await expect(client.health()).rejects.toBeInstanceOf(ApiClientError);
  });
});
