import React from "react";

export type RunState = "idle" | "disabled" | "running" | "completed" | "failed";

interface RunActionProps {
  state: RunState;
  onRun: () => void;
  onReset: () => void;
}

export function RunAction({ state, onRun, onReset }: RunActionProps) {
  return (
    <div className="workspace-card run-card">
      <div className="run-content">
        <div className="run-info">
          <h3>EXECUTE REGISTRATION</h3>
          <p>
            {state === "idle" && "Ready to run baseline pipeline."}
            {state === "disabled" && "Awaiting valid Source and Reference images."}
            {state === "running" && "Pipeline is actively executing..."}
            {state === "completed" && "Execution completed successfully. Results available."}
            {state === "failed" && "Execution failed. See logs for details."}
          </p>
        </div>
        
        <div className="run-actions">
          {state === "completed" || state === "failed" ? (
            <button className="secondary-button" onClick={onReset}>
              Reset Workspace
            </button>
          ) : null}

          <button
            className={`primary-button run-button state-${state}`}
            disabled={state === "disabled" || state === "running"}
            onClick={onRun}
          >
            {state === "running" && <span className="spinner" />}
            {state === "running" ? "RUNNING..." : "RUN PIPELINE"}
            {state !== "running" && <span>→</span>}
          </button>
        </div>
      </div>
    </div>
  );
}
