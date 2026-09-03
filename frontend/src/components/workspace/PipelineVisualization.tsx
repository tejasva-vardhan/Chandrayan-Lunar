import React from "react";

export type PipelineStageName = 
  | "INGEST"
  | "CHARACTERIZE"
  | "PREPROCESS"
  | "REPRESENT"
  | "MATCH"
  | "VERIFY"
  | "CONTROL POINTS"
  | "SUBPIXEL"
  | "REGISTER"
  | "EVALUATE";

const STAGES: PipelineStageName[] = [
  "INGEST",
  "CHARACTERIZE",
  "PREPROCESS",
  "REPRESENT",
  "MATCH",
  "VERIFY",
  "CONTROL POINTS",
  "SUBPIXEL",
  "REGISTER",
  "EVALUATE",
];

interface PipelineVisualizationProps {
  currentStage: PipelineStageName | null;
  status: "idle" | "running" | "completed" | "failed";
}

export function PipelineVisualization({ currentStage, status }: PipelineVisualizationProps) {
  const currentIndex = currentStage ? STAGES.indexOf(currentStage) : -1;

  return (
    <div className="workspace-card pipeline-card">
      <div className="card-header">
        <div className="card-header-left">
          <span className="card-dot" />
          <span className="card-title">EXECUTION PIPELINE</span>
        </div>
        <span className={`pipeline-status-badge status-${status}`}>
          {status.toUpperCase()}
        </span>
      </div>

      <div className="pipeline-track">
        {STAGES.map((stage, i) => {
          let stageState = "pending";
          if (status === "completed") {
            stageState = "completed";
          } else if (i < currentIndex) {
            stageState = "completed";
          } else if (i === currentIndex) {
            stageState = status === "failed" ? "failed" : "active";
          }

          return (
            <div key={stage} className={`pipeline-node state-${stageState}`}>
              <div className="node-indicator">
                {stageState === "completed" && <span className="icon">✓</span>}
                {stageState === "failed" && <span className="icon">!</span>}
                {stageState === "active" && <span className="icon spinner-small" />}
                {stageState === "pending" && <span className="icon number">{i + 1}</span>}
              </div>
              <span className="node-label">{stage}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
