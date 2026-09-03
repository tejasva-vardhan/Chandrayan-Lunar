import { useEffect, useRef, useState } from "react";
import { api, type ApiClient } from "../api/client";
import { baselineResultsView, fromRegistrationResult, type ResultsViewModel } from "../api/resultsView";
import { ApiClientError, type JobStatusResponse } from "../api/types";

type RunPhase = "idle" | "uploading" | "starting" | "running" | "success" | "failure";

export type RegistrationConsoleProps = {
  onResults: (view: ResultsViewModel) => void;
  onStatus?: (status: JobStatusResponse | null) => void;
  client?: ApiClient;
  pollIntervalMs?: number;
};

export function RegistrationConsole({
  onResults,
  onStatus,
  client = api,
  pollIntervalMs = 750,
}: RegistrationConsoleProps) {
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [sourcePath, setSourcePath] = useState("");
  const [referencePath, setReferencePath] = useState("");
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current != null) window.clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    onStatus?.(job);
  }, [job, onStatus]);

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
            setPhase("failure");
            setError(
              payload.error?.message ??
                "Registration failed. Check product format and metadata.",
            );
            return;
          }
          if (!payload.result) {
            setPhase("failure");
            setError("Result unavailable after a completed job.");
            return;
          }
          const artifactUrl = payload.result.registered_artifact_available
            ? client.artifactUrl(jobId, "registered_source")
            : null;
          onResults(
            fromRegistrationResult(payload.result, { jobId, artifactUrl }),
          );
          setPhase("success");
        }
      } catch (err) {
        if (pollRef.current != null) window.clearInterval(pollRef.current);
        pollRef.current = null;
        setPhase("failure");
        setError(err instanceof ApiClientError ? err.message : "Polling failed.");
      }
    };
    await tick();
    pollRef.current = window.setInterval(() => {
      void tick();
    }, pollIntervalMs);
  }

  async function onRun() {
    setError(null);
    setJob(null);
    try {
      let sourceProductId: string | undefined;
      let referenceProductId: string | undefined;
      const body: {
        source_product_id?: string;
        reference_product_id?: string;
        source_path?: string;
        reference_path?: string;
      } = {};

      if (sourceFile || referenceFile) {
        setPhase("uploading");
        if (sourceFile) {
          const uploaded = await client.uploadProduct(sourceFile);
          sourceProductId = uploaded.product_id;
          body.source_product_id = sourceProductId;
        }
        if (referenceFile) {
          const uploaded = await client.uploadProduct(referenceFile);
          referenceProductId = uploaded.product_id;
          body.reference_product_id = referenceProductId;
        }
      }

      if (!body.source_product_id) {
        if (!sourcePath.trim()) {
          throw new ApiClientError(400, {
            code: "invalid_input",
            message: "Provide a source file upload or a local source path.",
          });
        }
        body.source_path = sourcePath.trim();
      }
      if (!body.reference_product_id) {
        if (!referencePath.trim()) {
          throw new ApiClientError(400, {
            code: "invalid_input",
            message: "Provide a reference file upload or a local reference path.",
          });
        }
        body.reference_path = referencePath.trim();
      }

      setPhase("starting");
      const created = await client.createJob(body);
      setJob(created);
      setPhase("running");
      await pollUntilDone(created.job_id);
    } catch (err) {
      setPhase("failure");
      setError(err instanceof ApiClientError ? err.message : "Registration request failed.");
    }
  }

  function onResetBaseline() {
    setPhase("idle");
    setError(null);
    setJob(null);
    onResults(baselineResultsView());
  }

  const busy = phase === "uploading" || phase === "starting" || phase === "running";
  const progressLabel =
    phase === "uploading"
      ? "Uploading products…"
      : phase === "starting"
        ? "Starting registration job…"
        : phase === "running"
          ? `Running${job?.current_stage ? ` · ${job.current_stage}` : ""}…`
          : null;

  return (
    <div className="registration-console" id="run">
      <header className="section-header">
        <div>
          <p className="eyebrow">LIVE PIPELINE / API</p>
          <h2>Run registration</h2>
        </div>
        <span className={`state-pill ${phase === "success" ? "state-ok" : ""}`}>
          {phase === "success"
            ? "LIVE RESULT"
            : phase === "failure"
              ? "FAILED"
              : busy
                ? "RUNNING"
                : "AWAITING INPUT"}
        </span>
      </header>

      <p className="console-lede">
        Upload supported PDS products (OHRC PDS4 / LROC PDS3) or provide local server paths.
        Unsupported formats return a clear backend error — mock data is never substituted.
      </p>

      <div className="console-grid">
        <label>
          <span>Source product file</span>
          <input
            type="file"
            disabled={busy}
            onChange={(e) => setSourceFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          <span>Reference product file</span>
          <input
            type="file"
            disabled={busy}
            onChange={(e) => setReferenceFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          <span>Or source path (local API host)</span>
          <input
            type="text"
            placeholder="D:/data/.../ohrc_product"
            disabled={busy}
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
          />
        </label>
        <label>
          <span>Or reference path (local API host)</span>
          <input
            type="text"
            placeholder="D:/data/.../M150368601RC.IMG"
            disabled={busy}
            value={referencePath}
            onChange={(e) => setReferencePath(e.target.value)}
          />
        </label>
      </div>

      <div className="console-actions">
        <button type="button" className="primary-button" disabled={busy} onClick={() => void onRun()}>
          {busy ? "Working…" : "Start registration"} <span>→</span>
        </button>
        <button type="button" className="ghost-button" disabled={busy} onClick={onResetBaseline}>
          Show EXP-000 baseline
        </button>
      </div>

      {progressLabel && (
        <div className="run-status" role="status" aria-live="polite">
          <b>{progressLabel}</b>
          {job && (
            <span>
              {job.completed_stages.length}/{job.stages.length} stages · job {job.job_id}
            </span>
          )}
          {job && (
            <ol className="stage-list">
              {job.stages.map((stage) => {
                const done = job.completed_stages.includes(stage);
                const current = job.current_stage === stage;
                return (
                  <li key={stage} className={done ? "done" : current ? "current" : ""}>
                    {stage}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}

      {error && (
        <div className="run-error" role="alert">
          <b>Registration error</b>
          <span>{error}</span>
        </div>
      )}

      {phase === "success" && job && (
        <div className="run-success" role="status">
          Completed in {job.runtime_seconds != null ? `${job.runtime_seconds.toFixed(1)} s` : "—"}.
          Scroll to results for live metrics.
        </div>
      )}
    </div>
  );
}
