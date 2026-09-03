import React from "react";

/** Backend ScientificPipeline stage names (source of truth). */
export const PIPELINE_STAGE_LABELS: Record<string, string> = {
  ingest_product: "INGEST",
  characterize_pair: "CHARACTERIZE",
  preprocess: "PREPROCESS",
  generate_representation: "REPRESENT",
  match: "MATCH",
  verify_matches: "VERIFY",
  select_control_points: "CONTROL POINTS",
  refine_points: "SUBPIXEL",
  register: "REGISTER",
  evaluate: "EVALUATE",
  export_result: "EXPORT",
};

const FALLBACK_STAGES = Object.keys(PIPELINE_STAGE_LABELS);

interface PipelineVisualizationProps {
  stages: string[];
  completedStages: string[];
  currentStage: string | null;
  status: "idle" | "running" | "completed" | "failed" | "degraded";
}

export function PipelineVisualization({
  stages,
  completedStages,
  currentStage,
  status,
}: PipelineVisualizationProps) {
  const track = stages.length > 0 ? stages : FALLBACK_STAGES;

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
        {track.map((stage, i) => {
          const done = completedStages.includes(stage) || status === "completed" || status === "degraded";
          const current = currentStage === stage && status === "running";
          const failed = status === "failed" && currentStage === stage;
          let stageState = "pending";
          if (done && !current) stageState = "completed";
          else if (failed) stageState = "failed";
          else if (current) stageState = "active";
          else if (status === "failed" && completedStages.includes(stage)) stageState = "completed";

          // When failed, mark stages after the failure as pending; completed list wins.
          if (status === "failed" && !completedStages.includes(stage) && stage !== currentStage) {
            stageState = "pending";
          }
          if (failed) stageState = "failed";
          if (current) stageState = "active";
          if (completedStages.includes(stage) && !current && !failed) stageState = "completed";
          if ((status === "completed" || status === "degraded") && track.indexOf(stage) <= i) {
            // all completed when job finished successfully / degraded
          }
          if (status === "completed" || status === "degraded") {
            stageState = "completed";
          }

          return (
            <div key={stage} className={`pipeline-node state-${stageState}`}>
              <div className="node-indicator">
                {stageState === "completed" && <span className="icon">✓</span>}
                {stageState === "failed" && <span className="icon">!</span>}
                {stageState === "active" && <span className="icon spinner-small" />}
                {stageState === "pending" && <span className="icon number">{i + 1}</span>}
              </div>
              <span className="node-label">{PIPELINE_STAGE_LABELS[stage] ?? stage}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
