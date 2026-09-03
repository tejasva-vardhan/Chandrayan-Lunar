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
  onResults: (view: ResultsViewModel) => void;
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
  };
}

export function RegistrationWorkspace({
  onResults,
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

  const busy = runState === "running";

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
    if (runState === "running") {
      return;
    }
    const bothReady = source.state === "selected" && reference.state === "selected";
    if (runState === "completed" || runState === "degraded" || runState === "failed") {
      if (!bothReady) {
        setRunState("disabled");
      }
      return;
    }
    setRunState(bothReady ? "idle" : "disabled");
  }, [source.state, reference.state, runState]);

  async function handleUpload(role: "source" | "reference", file: File) {
    const setSlot = role === "source" ? setSource : setReference;
    setSlot({ state: "loading", selected: null, error: null });
    setError(null);
    try {
      const uploaded = await client.uploadProduct(file);
      setSlot({
        state: "selected",
        selected: {
          productId: uploaded.product_id,
          filename: uploaded.filename,
          origin: "upload",
          bytes: uploaded.bytes,
        },
        error: null,
      });
    } catch (err) {
      setSlot({
        state: "invalid",
        selected: null,
        error: err instanceof ApiClientError ? err.message : "Upload failed.",
      });
    }
  }

  function handleSelectExisting(role: "source" | "reference", product: ProductSummary) {
    const setSlot = role === "source" ? setSource : setReference;
    setSlot({
      state: "selected",
      selected: summaryToSelected(product),
      error: null,
    });
    setError(null);
  }

  async function handleLoadExp000() {
    setExp000Message(null);
    setError(null);
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
        `Loaded real ${pair.experiment_id} / ${pair.pair_id}. Press RUN REGISTRATION to execute the live pipeline.`,
      );
      await refreshCatalog();
    } catch (err) {
      const message = err instanceof ApiClientError ? err.message : "Failed to load EXP-000 pair.";
      setExp000Message(message);
      setSource({ state: "invalid", selected: null, error: message });
      setReference({ state: "invalid", selected: null, error: message });
    }
  }

  async function pollUntilDone(jobId: string) {
    if (pollRef.current != null) window.clearInterval(pollRef.current);

    const tick = async () => {
      try {
        const status = await client.getJob(jobId);
        setJob(status);
        if (status.status === "completed" || status.status === "failed") {
          if (pollRef.current != null) window.clearInterval(pollRef.current);
          pollRef.current = null;
          const payload = await client.getResult(jobId);
          if (payload.status === "failed" || payload.error) {
            setRunState("failed");
            setError(
              payload.error?.message ??
                "Registration failed. Check product format and metadata.",
            );
            return;
          }
          if (!payload.result) {
            setRunState("failed");
            setError("Result unavailable after a completed job.");
            return;
          }
          const artifactUrl = payload.result.registered_artifact_available
            ? client.artifactUrl(jobId, "registered_source")
            : null;
          const view = fromRegistrationResult(payload.result, { jobId, artifactUrl });
          onResults(view);
          const degraded = view.flags.some((flag) => DEGRADED_FLAGS.has(flag));
          setRunState(degraded ? "degraded" : "completed");
        }
      } catch (err) {
        if (pollRef.current != null) window.clearInterval(pollRef.current);
        pollRef.current = null;
        setRunState("failed");
        setError(err instanceof ApiClientError ? err.message : "Polling failed.");
      }
    };

    await tick();
    pollRef.current = window.setInterval(() => {
      void tick();
    }, pollIntervalMs);
  }

  async function handleRun() {
    if (!source.selected || !reference.selected) {
      setError("Both source and reference products are required.");
      setRunState("disabled");
      return;
    }
    setError(null);
    setJob(null);
    setRunState("running");
    try {
      const created = await client.createJob({
        source_product_id: source.selected.productId,
        reference_product_id: reference.selected.productId,
      });
      setJob(created);
      await pollUntilDone(created.job_id);
    } catch (err) {
      setRunState("failed");
      setError(err instanceof ApiClientError ? err.message : "Registration request failed.");
    }
  }

  function handleReset() {
    if (pollRef.current != null) window.clearInterval(pollRef.current);
    pollRef.current = null;
    setSource(emptySlot());
    setReference(emptySlot());
    setRunState("disabled");
    setJob(null);
    setError(null);
    setExp000Message(null);
  }

  function showBaselineFixture() {
    onResults(baselineResultsView());
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
                  : runState === "failed"
                    ? ""
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
          Provide two real lunar products (OHRC PDS4 or LROC PDS3). Metrics shown after a run come
          only from the backend ScientificPipeline — never from the static EXP-000 fixture.
        </p>
        <p className="workspace-lede workspace-note">
          Large full rasters use the existing engineering safeguards: preprocess may
          identity-passthrough when float64 materialization would exceed the 16&nbsp;MP
          cap, matching uses stride-decimated views, and full-raster warp may be skipped.
          Those outcomes appear as quality flags — images are not silently resized.
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
          onClick={showBaselineFixture}
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
            description="Upload or select the OHRC product to be registered."
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
            description="Upload or select the LRO NAC basemap product."
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
