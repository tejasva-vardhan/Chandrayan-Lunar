import React from "react";

export type RunState = "idle" | "disabled" | "running" | "completed" | "degraded" | "failed";

interface RunActionProps {
  state: RunState;
  onRun: () => void;
  onReset: () => void;
  onViewResults?: () => void;
  validationMessage?: string | null;
  jobId?: string | null;
}

export function RunAction({
  state,
  onRun,
  onReset,
  onViewResults,
  validationMessage,
  jobId,
}: RunActionProps) {
  const canViewResults = state === "completed" || state === "degraded";

  return (
    <div className="workspace-card run-card">
      <div className="run-content">
        <div className="run-info">
          <h3>EXECUTE REGISTRATION</h3>
          <p>
            {state === "idle" && "Ready — both products selected. Runs the live ScientificPipeline."}
            {state === "disabled" && (validationMessage || "Awaiting valid Source and Reference images.")}
            {state === "running" && "Pipeline is executing on the backend…"}
            {state === "completed" && "Execution completed. Open live results below."}
            {state === "degraded" &&
              "Completed with scientific warnings (for example output-size cap). See quality flags."}
            {state === "failed" && "Execution failed. See the error below."}
          </p>
          {jobId && <p className="job-meta">Job {jobId}</p>}
        </div>

        <div className="run-actions">
          {canViewResults && onViewResults ? (
            <button type="button" className="secondary-button" onClick={onViewResults}>
              View live results ↓
            </button>
          ) : null}

          {state === "completed" || state === "failed" || state === "degraded" ? (
            <button type="button" className="secondary-button" onClick={onReset}>
              Reset Workspace
            </button>
          ) : null}

          <button
            type="button"
            className={`primary-button run-button state-${state}`}
            disabled={state === "disabled" || state === "running"}
            onClick={onRun}
          >
            {state === "running" && <span className="spinner" />}
            {state === "running" ? "RUNNING…" : "RUN REGISTRATION"}
            {state !== "running" && <span>→</span>}
          </button>
        </div>
      </div>
    </div>
  );
}
