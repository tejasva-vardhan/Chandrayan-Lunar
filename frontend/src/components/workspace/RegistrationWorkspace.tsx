import React, { useState, useEffect, useRef } from "react";
import { ImageInput, ImageState } from "./ImageInput";
import { PairConfiguration } from "./PairConfiguration";
import { PipelineVisualization } from "./PipelineVisualization";
import { RunAction, RunState } from "./RunAction";
import { api as client } from "../../api/client";
import { ApiClientError } from "../../api/types";
import { ResultsViewModel, fromRegistrationResult } from "../../api/resultsView";

interface RegistrationWorkspaceProps {
  onResults: (results: ResultsViewModel) => void;
}

export function RegistrationWorkspace({ onResults }: RegistrationWorkspaceProps) {
  const [sourceState, setSourceState] = useState<ImageState>("empty");
  const [refState, setRefState] = useState<ImageState>("empty");
  
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [refFile, setRefFile] = useState<File | null>(null);

  const [runState, setRunState] = useState<RunState>("disabled");
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [allStages, setAllStages] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);

  // Derive disabled state based on inputs
  useEffect(() => {
    if (runState === "idle" || runState === "disabled") {
      if (sourceState === "selected" && refState === "selected") {
        setRunState("idle");
      } else {
        setRunState("disabled");
      }
    }
  }, [sourceState, refState, runState]);

  const handleSourceSelect = (file: File) => {
    setSourceFile(file);
    setSourceState("selected");
  };

  const handleRefSelect = (file: File) => {
    setRefFile(file);
    setRefState("selected");
  };

  const pollUntilDone = async (jobId: string) => {
    const pollIntervalMs = 800;
    const tick = async () => {
      try {
        const status = await client.getJob(jobId);
        if (status.current_stage) {
          setActiveStage(status.current_stage);
        }
        if (status.stages) {
          setAllStages(status.stages);
        }
        if (status.completed_stages) {
          setCompletedStages(status.completed_stages);
        }

        if (status.status === "completed" || status.status === "failed") {
          if (pollRef.current != null) window.clearInterval(pollRef.current);
          pollRef.current = null;
          
          if (status.status === "failed" || status.error) {
            setRunState("disabled");
            setErrorMsg(status.error?.message ?? "Registration failed. Check product format.");
            setActiveStage(null);
            return;
          }

          const payload = await client.getResult(jobId);
          if (!payload.result) {
            setRunState("disabled");
            setErrorMsg("Result unavailable after a completed job.");
            setActiveStage(null);
            return;
          }

          const artifactUrl = payload.result.registered_artifact_available
            ? client.artifactUrl(jobId, "registered_source")
            : null;

          const viewData = fromRegistrationResult(payload.result, { jobId, artifactUrl });
          
          setRunState("completed");
          setActiveStage(null);
          onResults(viewData);
        }
      } catch (err) {
        if (pollRef.current != null) window.clearInterval(pollRef.current);
        pollRef.current = null;
        setRunState("disabled");
        setErrorMsg(err instanceof ApiClientError ? err.message : "Polling failed.");
        setActiveStage(null);
      }
    };
    
    await tick();
    pollRef.current = window.setInterval(() => {
      void tick();
    }, pollIntervalMs);
  };

  const handleRun = async () => {
    setRunState("running");
    setErrorMsg(null);
    setActiveStage("ingest_product");
    setCompletedStages([]);
    
    try {
      let sourceProductId: string | undefined;
      let referenceProductId: string | undefined;
      const body: { source_product_id?: string; reference_product_id?: string } = {};

      if (sourceFile) {
        const uploaded = await client.uploadProduct(sourceFile);
        sourceProductId = uploaded.product_id;
        body.source_product_id = sourceProductId;
      }
      if (refFile) {
        const uploaded = await client.uploadProduct(refFile);
        referenceProductId = uploaded.product_id;
        body.reference_product_id = referenceProductId;
      }

      if (!body.source_product_id || !body.reference_product_id) {
        throw new Error("Both source and reference files are required.");
      }

      const created = await client.createJob(body);
      
      await pollUntilDone(created.job_id);
    } catch (err) {
      setRunState("disabled");
      setErrorMsg(err instanceof ApiClientError ? err.message : (err as Error).message);
      setActiveStage(null);
    }
  };

  const handleReset = () => {
    setSourceState("empty");
    setRefState("empty");
    setSourceFile(null);
    setRefFile(null);
    setRunState("disabled");
    setActiveStage(null);
    setCompletedStages([]);
    setErrorMsg(null);
  };

  return (
    <section className="registration-workspace glass-panel">
      <header className="workspace-header">
        <p className="eyebrow">WORKSPACE / SETUP</p>
        <h2>Registration Pipeline</h2>
      </header>

      <div className="workspace-grid">
        <div className="workspace-column left-column">
          <ImageInput
            label="SOURCE IMAGE"
            description="Select the OHRC product to be registered."
            state={sourceState}
            filename={sourceFile?.name || "ch2_ohr_ncp_..."}
            dimensions="12,000 × 78,175 px"
            sensor="OHRC"
            onSelect={handleSourceSelect}
            onClear={() => { setSourceState("empty"); setSourceFile(null); }}
          />
          <ImageInput
            label="REFERENCE IMAGE"
            description="Select the LRO NAC basemap."
            state={refState}
            filename={refFile?.name || "M150368601RC.IMG"}
            dimensions="5,064 × 52,224 px"
            sensor="LRO NAC"
            onSelect={handleRefSelect}
            onClear={() => { setRefState("empty"); setRefFile(null); }}
          />
        </div>

        <div className="workspace-column right-column">
          <PairConfiguration />
          <PipelineVisualization 
            status={runState === "idle" || runState === "disabled" ? "idle" : runState}
            currentStage={activeStage} 
            stages={allStages.length > 0 ? allStages : ["ingest_product", "characterize_pair", "preprocess", "generate_representation", "match", "verify_matches", "select_control_points", "refine_points", "register", "evaluate"]}
            completedStages={completedStages}
          />
          {errorMsg && (
            <div style={{ marginTop: "16px", padding: "12px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "4px", color: "var(--critical)", fontSize: "13px", fontFamily: "var(--mono)" }}>
              ⚠️ {errorMsg}
            </div>
          )}
        </div>
      </div>

      <div className="workspace-footer">
        <RunAction state={runState} onRun={handleRun} onReset={handleReset} />
      </div>
    </section>
  );
}
