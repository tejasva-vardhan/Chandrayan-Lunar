import React, { useState, useEffect } from "react";
import { ImageInput, ImageState } from "./ImageInput";
import { PairConfiguration } from "./PairConfiguration";
import { PipelineVisualization, PipelineStageName } from "./PipelineVisualization";
import { RunAction, RunState } from "./RunAction";

interface RegistrationWorkspaceProps {
  onComplete: () => void;
}

export function RegistrationWorkspace({ onComplete }: RegistrationWorkspaceProps) {
  const [sourceState, setSourceState] = useState<ImageState>("empty");
  const [refState, setRefState] = useState<ImageState>("empty");
  const [runState, setRunState] = useState<RunState>("disabled");
  const [activeStage, setActiveStage] = useState<PipelineStageName | null>(null);

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

  const handleSourceSelect = () => {
    setSourceState("loading");
    setTimeout(() => {
      setSourceState("selected");
    }, 800);
  };

  const handleRefSelect = () => {
    setRefState("loading");
    setTimeout(() => {
      setRefState("selected");
    }, 800);
  };

  const handleRun = () => {
    setRunState("running");
    
    // Mock pipeline execution for UI/UX demonstration
    const stages: PipelineStageName[] = [
      "INGEST", "CHARACTERIZE", "PREPROCESS", "REPRESENT", 
      "MATCH", "VERIFY", "CONTROL POINTS", "SUBPIXEL", 
      "REGISTER", "EVALUATE"
    ];
    
    let step = 0;
    setActiveStage(stages[0]);

    const interval = setInterval(() => {
      step++;
      if (step < stages.length) {
        setActiveStage(stages[step]);
      } else {
        clearInterval(interval);
        setRunState("completed");
        setActiveStage(null);
        setTimeout(() => {
          onComplete(); // Scroll to results
        }, 500);
      }
    }, 600); // 600ms per stage for the demo
  };

  const handleReset = () => {
    setSourceState("empty");
    setRefState("empty");
    setRunState("disabled");
    setActiveStage(null);
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
            filename="ch2_ohr_ncp_20210402T0546284043_d_img_d18"
            dimensions="12,000 × 78,175 px"
            sensor="OHRC"
            onSelect={handleSourceSelect}
            onClear={() => setSourceState("empty")}
          />
          <ImageInput
            label="REFERENCE IMAGE"
            description="Select the LRO NAC basemap."
            state={refState}
            filename="M150368601RC.IMG"
            dimensions="5,064 × 52,224 px"
            sensor="LRO NAC"
            onSelect={handleRefSelect}
            onClear={() => setRefState("empty")}
          />
        </div>

        <div className="workspace-column right-column">
          <PairConfiguration />
          <PipelineVisualization 
            status={runState === "idle" || runState === "disabled" ? "idle" : runState}
            currentStage={activeStage} 
          />
        </div>
      </div>

      <div className="workspace-footer">
        <RunAction state={runState} onRun={handleRun} onReset={handleReset} />
      </div>
    </section>
  );
}
