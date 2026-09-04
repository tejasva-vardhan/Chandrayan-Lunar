import type {
  ApiErrorBody,
  CatalogStatusResponse,
  CreateJobRequest,
  Exp000PairResponse,
  JobResultResponse,
  JobStatusResponse,
  ProductSummary,
  ProductUploadResponse,
} from "./types";
import { ApiClientError } from "./types";

/**
 * Production (Vercel): set VITE_API_BASE_URL at build time to the Render API origin.
 * Local development: leave unset so requests stay same-origin and Vite proxies to :8000.
 */
export function resolveApiBaseUrl(
  env: { VITE_API_BASE_URL?: string } = import.meta.env,
): string {
  const configured = env.VITE_API_BASE_URL;
  if (typeof configured === "string" && configured.trim()) {
    return configured.trim().replace(/\/$/, "");
  }
  return "";
}

async function parseError(response: Response): Promise<ApiClientError> {
  let body: ApiErrorBody = {
    code: "request_failure",
    message: `Request failed (${response.status})`,
  };
  try {
    const json = (await response.json()) as Partial<ApiErrorBody>;
    body = {
      code: json.code ?? body.code,
      message: json.message ?? body.message,
      details: json.details,
    };
  } catch {
    /* keep default */
  }
  return new ApiClientError(response.status, body);
}

export function createApiClient(baseUrl: string = resolveApiBaseUrl()) {
  const root = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${root}${path}`, init);
    } catch (err) {
      throw new ApiClientError(0, {
        code: "request_failure",
        message: err instanceof Error ? err.message : "Network request failed",
      });
    }
    if (!response.ok) {
      throw await parseError(response);
    }
    return (await response.json()) as T;
  }

  return {
    health: () => request<{ status: string }>("/health"),

    uploadProduct: async (file: File): Promise<ProductUploadResponse> => {
      const form = new FormData();
      form.append("file", file);
      return request<ProductUploadResponse>("/products", {
        method: "POST",
        body: form,
      });
    },

    listProducts: () => request<ProductSummary[]>("/products"),

    listCatalog: () => request<CatalogStatusResponse>("/products/catalog"),

    getExp000Pair: () => request<Exp000PairResponse>("/products/exp000"),

    createJob: (body: CreateJobRequest) =>
      request<JobStatusResponse>("/registration/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    getJob: (jobId: string) =>
      request<JobStatusResponse>(`/registration/jobs/${encodeURIComponent(jobId)}`),

    getResult: (jobId: string) =>
      request<JobResultResponse>(
        `/registration/jobs/${encodeURIComponent(jobId)}/result`,
      ),

    artifactUrl: (jobId: string, name: string) =>
      `${root}/registration/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(name)}`,
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

export const api = createApiClient();
