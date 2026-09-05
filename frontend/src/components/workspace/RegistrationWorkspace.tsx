import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, type ApiClient } from "../../api/client";
import {
  baselineResultsView,
  fromRegistrationResult,
  type ResultsViewModel,
} from "../../api/resultsView";
import { ApiClientError, type JobStatusResponse, type ProductSummary } from "../../api/types";
import { ImageInput, type ImageState, type SelectedProduct } from "./ImageInput";
import { PairConfiguration } from "./PairConfiguration";
import { PipelineVisualization } from "./PipelineVisualization";
import { RunAction, type RunState } from "./RunAction";

const DEGRADED_FLAGS = new Set([
  "registration_output_too_large",
  "preprocess_identity_passthrough_oversized_raster",
  "no_correspondences",
  "insufficient_verified_matches",
  "insufficient_control_points",
  "degenerate_control_points",
  "warp_failed",
]);

export type RegistrationWorkspaceProps = {
  onResults: (view: ResultsViewModel | null) => void;
  onRunError?: (message: string | null) => void;
  client?: ApiClient;
  pollIntervalMs?: number;
};

type Slot = {
  state: ImageState;
  selected: SelectedProduct | null;
  error: string | null;
};

const emptySlot = (): Slot => ({ state: "empty", selected: null, error: null });

function summaryToSelected(product: ProductSummary): SelectedProduct {
  return {
    productId: product.product_id,
    filename: product.logical_id || product.filename || product.product_id,
    origin: product.origin,
    instrumentHint: product.instrument_hint,
    detail: product.path,
    file: null,
  };
}

function hintFromName(name: string): string | null {
  const lower = name.toLowerCase();
  if (lower.includes("ohr") || lower.startsWith("ch2_")) return "OHRC";
  if (lower.startsWith("m") && lower.endsWith(".img")) return "LRO_NAC";
  if (lower.endsWith(".zip")) return "OHRC";
  return null;
}

function sleep(ms: number) {
  return new Promise((r) => window.setTimeout(r, ms));
}

async function fetchResultWithRetry(
  client: ApiClient,
  jobId: string,
  attempts = 4,
): Promise<Awaited<ReturnType<ApiClient["getResult"]>>> {
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await client.getResult(jobId);
    } catch (err) {
      lastErr = err;
      await sleep(400 * (i + 1));
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("Result fetch failed");
}

export function RegistrationWorkspace({
  onResults,
  onRunError,
  client = api,
  pollIntervalMs = 750,
}: RegistrationWorkspaceProps) {
  const [source, setSource] = useState<Slot>(emptySlot);
  const [reference, setReference] = useState<Slot>(emptySlot);
  const [runState, setRunState] = useState<RunState>("disabled");
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ProductSummary[]>([]);
  const [catalogConfigured, setCatalogConfigured] = useState(false);
  const [catalogMessage, setCatalogMessage] = useState<string | null>(null);
  const [exp000Message, setExp000Message] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const settlingRef = useRef(false);
  const runGenRef = useRef(0);

  const busy = runState === "running";

  const reportError = useCallback(
    (message: string | null) => {
      setError(message);
      onRunError?.(message);
    },
    [onRunError],
  );

  const refreshCatalog = useCallback(async () => {
    try {
      const status = await client.listCatalog();
      setCatalogConfigured(status.data_root_configured);
      setCatalog(status.products);
      setCatalogMessage(status.message);
    } catch (err) {
      setCatalogConfigured(false);
      setCatalog([]);
      setCatalogMessage(err instanceof ApiClientError ? err.message : "Catalog unavailable.");
    }
  }, [client]);

  useEffect(() => {
    void refreshCatalog();
  }, [refreshCatalog]);

  useEffect(() => {
    return () => {
      if (pollRef.current != null) window.clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (runState === "running") return;
    const bothReady = source.state === "selected" && reference.state === "selected";
    if (runState === "completed" || runState === "degraded" || runState === "failed") {
      if (!bothReady) setRunState("disabled");
      return;
    }
    setRunState(bothReady ? "idle" : "disabled");
  }, [source.state, reference.state, runState]);

  function validateClientFile(file: File): string | null {
    const suffix = file.name.includes(".")
      ? `.${file.name.split(".").pop()!.toLowerCase()}`
      : "";
    if (![".img", ".zip", ".xml"].includes(suffix)) {
      return `Unsupported extension ${suffix || "(none)"}. Use OHRC .zip/.xml or LROC .IMG.`;
    }
    if (file.size <= 0) return "Uploaded file is empty.";
    return null;
  }

  async function handleUpload(role: "source" | "reference", file: File) {
    const setSlot = role === "source" ? setSource : setReference;
    const invalid = validateClientFile(file);
    if (invalid) {
      setSlot({ state: "invalid", selected: null, error: invalid });
      return;
    }
    setSlot({
      state: "selected",
      selected: {
        filename: file.name,
        origin: "upload",
        bytes: file.size,
        instrumentHint: hintFromName(file.name),
        file,
      },
      error: null,
    });
    reportError(null);
  }

  function handleSelectExisting(role: "source" | "reference", product: ProductSummary) {
    const setSlot = role === "source" ? setSource : setReference;
    setSlot({ state: "selected", selected: summaryToSelected(product), error: null });
    reportError(null);
  }

  async function handleLoadExp000() {
    setExp000Message(null);
    reportError(null);
    setSource({ state: "loading", selected: null, error: null });
    setReference({ state: "loading", selected: null, error: null });
    try {
      const pair = await client.getExp000Pair();
      if (!pair.available || !pair.source || !pair.reference) {
        const message = pair.message || "EXP-000 real pair is unavailable.";
        setExp000Message(message);
        setSource({ state: "invalid", selected: null, error: message });
        setReference({ state: "invalid", selected: null, error: message });
        return;
      }
      setSource({ state: "selected", selected: summaryToSelected(pair.source), error: null });
      setReference({
        state: "selected",
        selected: summaryToSelected(pair.reference),
        error: null,
      });
      setExp000Message(
        `Loaded real ${pair.experiment_id} / ${pair.pair_id}. Press RUN REGISTRATION.`,
      );
      await refreshCatalog();
    } catch (err) {
      const message = err instanceof ApiClientError ? err.message : "Failed to load EXP-000.";
      setExp000Message(message);
      setSource({ state: "invalid", selected: null, error: message });
      setReference({ state: "invalid", selected: null, error: message });
    }
  }

  async function settleJob(jobId: string, gen: number) {
    if (settlingRef.current) return;
    settlingRef.current = true;
    try {
      if (pollRef.current != null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      const payload = await fetchResultWithRetry(client, jobId);
      if (gen !== runGenRef.current) return;

      if (payload.status === "failed" || payload.error) {
        setRunState("failed");
        reportError(payload.error?.message ?? "Registration failed.");
        onResults(null);
        return;
      }
      if (!payload.result) {
        setRunState("failed");
        reportError("Result unavailable after a completed job.");
        onResults(null);
        return;
      }

      const artifactUrl = payload.result.registered_artifact_available
        ? client.artifactUrl(jobId, "registered_source")
        : null;
      let result = payload.result;
      if (!result.preview_available) {
        await sleep(900);
        if (gen !== runGenRef.current) return;
        try {
          const again = await client.getResult(jobId);
          if (again.result?.preview_available) result = again.result;
        } catch {
          /* keep first result */
        }
      }

      const view = fromRegistrationResult(result, { jobId, artifactUrl });
      if (gen !== runGenRef.current) return;
      reportError(null);
      onResults(view);
      const degraded = view.flags.some((flag) => DEGRADED_FLAGS.has(flag));
      setRunState(degraded ? "degraded" : "completed");
    } catch (err) {
      if (gen !== runGenRef.current) return;
      setRunState("failed");
      reportError(err instanceof ApiClientError ? err.message : "Failed to load registration result.");
      onResults(null);
    } finally {
      settlingRef.current = false;
    }
  }

  async function pollUntilDone(jobId: string, gen: number) {
    if (pollRef.current != null) window.clearInterval(pollRef.current);
    let finished = false;
    const tick = async () => {
      if (gen !== runGenRef.current || settlingRef.current || finished) return;
      try {
        const status = await client.getJob(jobId);
        if (gen !== runGenRef.current || finished) return;
        setJob(status);
        if (status.status === "completed" || status.status === "failed") {
          finished = true;
          if (pollRef.current != null) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          await settleJob(jobId, gen);
        }
      } catch (err) {
        if (gen !== runGenRef.current) return;
        finished = true;
        if (pollRef.current != null) window.clearInterval(pollRef.current);
        pollRef.current = null;
        setRunState("failed");
        reportError(err instanceof ApiClientError ? err.message : "Polling failed.");
        onResults(null);
      }
    };
    await tick();
    if (gen !== runGenRef.current || finished) return;
    pollRef.current = window.setInterval(() => {
      void tick();
    }, pollIntervalMs);
  }

  async function handleRun() {
    if (!source.selected || !reference.selected) {
      reportError("Both source and reference products are required.");
      setRunState("disabled");
      return;
    }
    const gen = ++runGenRef.current;
    settlingRef.current = false;
    if (pollRef.current != null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    reportError(null);
    onResults(null);
    setJob(null);
    setRunState("running");
    try {
      const body: {
        source_product_id?: string;
        reference_product_id?: string;
      } = {};

      if (source.selected.file) {
        const uploaded = await client.uploadProduct(source.selected.file);
        if (gen !== runGenRef.current) return;
        body.source_product_id = uploaded.product_id;
        setSource((prev) =>
          prev.selected
            ? {
                ...prev,
                selected: {
                  ...prev.selected,
                  productId: uploaded.product_id,
                  bytes: uploaded.bytes,
                  file: null,
                },
              }
            : prev,
        );
      } else if (source.selected.productId) {
        body.source_product_id = source.selected.productId;
      }

      if (reference.selected.file) {
        const uploaded = await client.uploadProduct(reference.selected.file);
        if (gen !== runGenRef.current) return;
        body.reference_product_id = uploaded.product_id;
        setReference((prev) =>
          prev.selected
            ? {
                ...prev,
                selected: {
                  ...prev.selected,
                  productId: uploaded.product_id,
                  bytes: uploaded.bytes,
                  file: null,
                },
              }
            : prev,
        );
      } else if (reference.selected.productId) {
        body.reference_product_id = reference.selected.productId;
      }

      if (!body.source_product_id || !body.reference_product_id) {
        throw new ApiClientError(400, {
          code: "invalid_input",
          message: "Both source and reference products are required.",
        });
      }

      const created = await client.createJob(body);
      if (gen !== runGenRef.current) return;
      setJob(created);
      await pollUntilDone(created.job_id, gen);
    } catch (err) {
      if (gen !== runGenRef.current) return;
      setRunState("failed");
      reportError(err instanceof ApiClientError ? err.message : "Registration request failed.");
      onResults(null);
    }
  }

  function handleReset() {
    runGenRef.current += 1;
    settlingRef.current = false;
    if (pollRef.current != null) window.clearInterval(pollRef.current);
    pollRef.current = null;
    setSource(emptySlot());
    setReference(emptySlot());
    setRunState("disabled");
    setJob(null);
    reportError(null);
    setExp000Message(null);
    onResults(null);
  }

  function handleViewResults() {
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const validationMessage =
    source.state !== "selected" && reference.state !== "selected"
      ? "Select both SOURCE and REFERENCE products."
      : source.state !== "selected"
        ? "SOURCE image is missing."
        : reference.state !== "selected"
          ? "REFERENCE image is missing."
          : null;

  const pipelineStatus =
    runState === "idle" || runState === "disabled"
      ? "idle"
      : runState === "running"
        ? "running"
        : runState === "failed"
          ? "failed"
          : runState === "degraded"
            ? "degraded"
            : "completed";

  return (
    <section className="registration-workspace glass-panel" id="run">
      <header className="workspace-header">
        <div className="workspace-header-row">
          <div>
            <p className="eyebrow">WORKSPACE / LIVE PIPELINE</p>
            <h2>Registration Pipeline</h2>
          </div>
          <span
            className={`state-pill ${
              runState === "completed"
                ? "state-ok"
                : runState === "degraded"
                  ? "state-warn"
                  : ""
            }`}
          >
            {runState === "running"
              ? "RUNNING"
              : runState === "completed"
                ? "COMPLETED"
                : runState === "degraded"
                  ? "DEGRADED / WARNING"
                  : runState === "failed"
                    ? "FAILED"
                    : runState === "idle"
                      ? "READY"
                      : "AWAITING INPUT"}
          </span>
        </div>
        <p className="workspace-lede">
          Prefer <b>Load EXP-000 Real Pair</b> or catalog Select Existing. Large re-uploads can fail
          when the system disk is full. Results come only from the live ScientificPipeline.
        </p>
      </header>

      <div className="workspace-toolbar">
        <button
          type="button"
          className="secondary-button"
          disabled={busy}
          onClick={() => void handleLoadExp000()}
        >
          Load EXP-000 Real Pair
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={busy}
          onClick={() => {
            reportError(null);
            onResults(baselineResultsView());
          }}
        >
          Show static EXP-000 fixture
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={busy}
          onClick={() => void refreshCatalog()}
        >
          Refresh catalog
        </button>
      </div>
      {exp000Message && <p className="workspace-inline-msg">{exp000Message}</p>}

      <div className="workspace-grid">
        <div className="workspace-column left-column">
          <ImageInput
            label="SOURCE IMAGE"
            description="OHRC product — upload a PDS4 .zip (preferred) or .xml, or select from catalog."
            state={source.state}
            selected={source.selected}
            errorMessage={source.error}
            catalog={catalog}
            catalogConfigured={catalogConfigured}
            catalogMessage={catalogMessage}
            disabled={busy}
            onUpload={(file) => void handleUpload("source", file)}
            onSelectExisting={(product) => handleSelectExisting("source", product)}
            onClear={() => setSource(emptySlot())}
          />
          <ImageInput
            label="REFERENCE IMAGE"
            description="LRO NAC basemap — upload a PDS3 .IMG, or select from catalog."
            state={reference.state}
            selected={reference.selected}
            errorMessage={reference.error}
            catalog={catalog}
            catalogConfigured={catalogConfigured}
            catalogMessage={catalogMessage}
            disabled={busy}
            onUpload={(file) => void handleUpload("reference", file)}
            onSelectExisting={(product) => handleSelectExisting("reference", product)}
            onClear={() => setReference(emptySlot())}
          />
        </div>

        <div className="workspace-column right-column">
          <PairConfiguration />
          <PipelineVisualization
            status={pipelineStatus}
            stages={job?.stages ?? []}
            completedStages={job?.completed_stages ?? []}
            currentStage={job?.current_stage ?? null}
          />
        </div>
      </div>

      <div className="workspace-footer">
        <RunAction
          state={runState}
          onRun={() => void handleRun()}
          onReset={handleReset}
          onViewResults={handleViewResults}
          validationMessage={validationMessage}
          jobId={job?.job_id ?? null}
        />
      </div>

      {error && (
        <div className="run-error" role="alert">
          <b>Registration error</b>
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}
