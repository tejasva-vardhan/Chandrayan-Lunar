import { useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import type { ResultsViewModel } from "../../api/resultsView";
import { CorrespondenceEvidence } from "./CorrespondenceEvidence";
import { RegistrationDiagnostic } from "./RegistrationDiagnostic";
import { SpatialDistribution } from "./SpatialDistribution";

function Reveal({
  children,
  className = "",
  delay = 0,
  reducedMotion,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  reducedMotion: boolean;
}) {
  if (reducedMotion) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}

function formatDims(width: number | null, height: number | null): string {
  if (width == null || height == null) return "dimensions unavailable";
  return `${width.toLocaleString()} × ${height.toLocaleString()} px`;
}

function statusSummary(results: ResultsViewModel): string {
  if (results.resultStatus === "FAILED") {
    return "Registration did not complete successfully. See quality flags and limitations.";
  }
  if (results.resultStatus === "LOW CONFIDENCE") {
    return "Registration completed at low confidence. See the quality certificate below.";
  }
  if (results.resultStatus === "COMPLETED WITH LIMITATIONS") {
    return "Registration completed with limitations. See the quality certificate below.";
  }
  return "Registration completed. The system found and geometrically verified correspondences between the two lunar images.";
}

function ProcessFlow({ results }: { results: ResultsViewModel }) {
  const failedEarly =
    results.flags.includes("no_correspondences") || results.rawMatches === 0;
  const verifyWeak =
    results.flags.includes("insufficient_verified_matches") || results.verified === 0;
  const balanceWeak =
    results.flags.includes("insufficient_control_points") ||
    results.flags.includes("degenerate_control_points") ||
    results.controlPointCount === 0;
  const registerBlocked = results.fullRasterBlocked || results.flags.includes("warp_failed");

  const steps: { key: string; title: string; detail: string; state: "ok" | "warn" | "fail" }[] = [
    {
      key: "inputs",
      title: "INPUTS",
      detail: "Source image + Reference image",
      state: "ok",
    },
    {
      key: "match",
      title: "MATCH",
      detail: "Find corresponding locations",
      state: failedEarly ? "fail" : "ok",
    },
    {
      key: "verify",
      title: "VERIFY",
      detail: "Keep geometrically consistent matches",
      state: failedEarly ? "fail" : verifyWeak ? "warn" : "ok",
    },
    {
      key: "balance",
      title: "BALANCE",
      detail: "Select spatially distributed control points",
      state: failedEarly || verifyWeak ? "fail" : balanceWeak ? "warn" : "ok",
    },
    {
      key: "register",
      title: "REGISTER",
      detail: "Estimate image alignment",
      state:
        failedEarly || verifyWeak || balanceWeak
          ? "fail"
          : registerBlocked
            ? "warn"
            : "ok",
    },
    {
      key: "check",
      title: "CHECK",
      detail: "Report diagnostics and validation state",
      state: "ok",
    },
  ];

  return (
    <ol className="results-flow" aria-label="Registration process overview">
      {steps.map((step, i) => (
        <li key={step.key} className={`flow-step state-${step.state}`}>
          <b>{step.title}</b>
          <span>{step.detail}</span>
          {i < steps.length - 1 && <span className="flow-arrow" aria-hidden="true">↓</span>}
        </li>
      ))}
    </ol>
  );
}

function Limitations({ results }: { results: ResultsViewModel }) {
  const items: string[] = [];
  if (results.verified > 0 && results.verified < 10) {
    items.push(`Only ${results.verified} matches survived verification.`);
  }
  if (
    results.independentAccuracy.toLowerCase().includes("not") ||
    results.flags.includes("not_independently_validated")
  ) {
    items.push("Independent accuracy has not been established.");
  }
  if (/indeterminate/i.test(results.refinement)) {
    items.push("Sub-pixel refinement is indeterminate.");
  }
  if (results.fullRasterBlocked) {
    items.push(
      "Full-raster output may be unavailable due to the safety/output-size limit.",
    );
  }
  if (results.evaluationLimitation) {
    items.push(results.evaluationLimitation);
  }
  items.push(
    "The current result is a baseline experiment, not final SIH performance.",
  );

  return (
    <section className="results-block limitations-block" aria-labelledby="limitations-title">
      <header className="results-block-header">
        <div>
          <h3 id="limitations-title">Limitations</h3>
          <p className="results-block-subtitle">
            Scientific honesty about what this run does and does not establish.
          </p>
        </div>
      </header>
      <ul className="limitations-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export type ResultsPanelProps = {
  results: ResultsViewModel;
  reducedMotion: boolean;
  onFocusRegion?: (target: { lon: number; lat: number; zoomMultiplier?: number } | null) => void;
};

export function ResultsPanel({ results, reducedMotion, onFocusRegion }: ResultsPanelProps) {
  const [showRejected, setShowRejected] = useState(false);
  const mapPoints = results.mapPoints.length ? results.mapPoints : results.points;
  const isNoMatch = results.rawMatches === 0 || results.verified === 0;
  const statusClass =
    results.resultStatus === "FAILED"
      ? "status-failed"
      : results.resultStatus === "LOW CONFIDENCE"
        ? "status-low"
        : results.resultStatus === "COMPLETED WITH LIMITATIONS"
          ? "status-limited"
          : "status-completed";

  return (
    <>
      <section className="results-shell" id="results">
        <Reveal className="glass-panel panel-left results-panel" reducedMotion={reducedMotion}>
          {/* A. RESULT HEADER */}
          <header className="section-header results-header">
            <div>
              <p className="eyebrow">
                {results.isLive
                  ? "EXP-000 Real-data Run / Live result from the scientific pipeline / "
                  : "STATIC EXP-000 FIXTURE / Regression only / "}
                {results.id}
              </p>
              <h2>Results</h2>
              <p className="results-pair-line">
                {results.source} → {results.reference}
              </p>
              <p className="results-status-sentence">{statusSummary(results)}</p>
            </div>
            <span className={`state-pill result-status-pill ${statusClass}`}>
              {results.resultStatus}
            </span>
          </header>

          {!results.isLive && (
            <div className="fixture-banner" role="note">
              <b>Static EXP-000 fixture</b>
              <span>
                Historical regression values — not a live pipeline run. Use “Load EXP-000 Real Pair”
                then register for a live result.
              </span>
            </div>
          )}

          {results.isLive && (
            <div className="live-banner" role="status">
              <b>Live result · isLive: true</b>
              <span>Values below come from the scientific pipeline API for this job.</span>
            </div>
          )}

          {/* Input continuity cards */}
          <div className="input-pair-cards">
            <article className="input-pair-card">
              <span className="chip chip-ohrc">SOURCE</span>
              <strong>{results.source}</strong>
              <span className="product-id">{results.sourceProduct}</span>
              <span className="dims-line">
                {formatDims(results.sourceDims.width, results.sourceDims.height)}
                {results.sourceDims.gsd ? ` — ${results.sourceDims.gsd}` : ""}
              </span>
            </article>
            <article className="input-pair-card">
              <span className="chip chip-lro">REFERENCE</span>
              <strong>{results.reference}</strong>
              <span className="product-id">{results.referenceProduct}</span>
              <span className="dims-line">
                {formatDims(results.referenceDims.width, results.referenceDims.height)}
              </span>
            </article>
          </div>

          {results.region && (
            <button
              type="button"
              className="chip-interactive region-focus-btn"
              onMouseEnter={() =>
                onFocusRegion?.({ lon: 23.43, lat: 0.65, zoomMultiplier: 0.88 })
              }
              onMouseLeave={() => onFocusRegion?.(null)}
              onClick={() =>
                onFocusRegion?.({ lon: 23.43, lat: 0.65, zoomMultiplier: 0.88 })
              }
              title="Focus Moon camera on equatorial OHRC scan field"
            >
              <span className="chip chip-region">Focus Scan Field ⊕</span>
              <span>
                {results.region.label} · lat {results.region.lat[0]}–{results.region.lat[1]}° · lon{" "}
                {results.region.lon[0]}–{results.region.lon[1]}°
              </span>
            </button>
          )}

          <ProcessFlow results={results} />

          {isNoMatch && results.isLive && (
            <div className="run-error" role="status">
              <b>
                {results.rawMatches === 0
                  ? "No correspondences"
                  : "Insufficient verified matches"}
              </b>
              <span>
                {results.rawMatches === 0
                  ? "The matcher returned an empty correspondence set for this pair."
                  : `Candidates: ${results.rawMatches}; verified inliers: ${results.verified}.`}
              </span>
            </div>
          )}

          {/* Summary metrics — human-readable */}
          <div className="metric-strip metric-strip-readable" aria-label="Result metrics">
            <div>
              <span className="metric-kicker">MATCHES FOUND</span>
              <b>{results.rawMatches}</b>
              <span>Candidate correspondences</span>
            </div>
            <div>
              <span className="metric-kicker">MATCHES VERIFIED</span>
              <b>{results.verified}</b>
              <span>Survived geometric consistency checks</span>
            </div>
            <div>
              <span className="metric-kicker">INLIER RATIO</span>
              <b>{results.inlierRatio}</b>
              <span>Verified / candidate correspondences</span>
            </div>
            <div>
              <span className="metric-kicker">CONTROL POINTS</span>
              <b>{results.controlPointCount}</b>
              <span>Spatially selected points used for registration</span>
            </div>
            <div>
              <span className="metric-kicker">SPATIAL COVERAGE</span>
              <b>{results.coverage}</b>
              <span>Area represented by selected control points</span>
            </div>
            <div title="Verification residual RMSE is a geometric-verification fit diagnostic, not independent registration accuracy.">
              <span className="metric-kicker">{results.rmseLabel.toUpperCase()}</span>
              <b className="metric-val-formatted">{results.rmse}</b>
              <span>Fit residual from the verification model; not independent registration accuracy</span>
            </div>
            <div>
              <span className="metric-kicker">REFINEMENT</span>
              <b className="metric-text">{/indeterminate/i.test(results.refinement) ? "Indeterminate" : results.refinement}</b>
              <span>Sub-pixel refinement state</span>
            </div>
            <div>
              <span className="metric-kicker">INDEPENDENT VALIDATION</span>
              <b className="metric-text">
                {/not independently|unavailable|not available/i.test(results.independentAccuracy)
                  ? "Not available"
                  : results.independentAccuracy}
              </b>
              <span>{results.independentAccuracy}</span>
            </div>
          </div>

          {/* C. Correspondence Evidence */}
          <CorrespondenceEvidence
            sourceLabel={results.source}
            referenceLabel={results.reference}
            points={mapPoints}
            showRejected={showRejected}
          />

          <div className="explorer-controls">
            <div>
              <b>Rejected matches</b>
              <span>
                {results.rejected} candidates did not survive geometric verification. Toggle to
                inspect them; they are not control points.
              </span>
            </div>
            <button
              type="button"
              className={showRejected ? "active" : ""}
              onClick={() => setShowRejected((v) => !v)}
              disabled={results.rejected === 0}
            >
              {showRejected ? "Hide" : "Show"} {results.rejected} rejected
            </button>
          </div>
          {showRejected && (
            <div className="rejected-note">
              Rejected correspondences are retained for inspection but are not control points and do
              not enter registration.
            </div>
          )}

          {/* D. Spatial Distribution — separate from correspondence */}
          <SpatialDistribution points={mapPoints} coverage={results.coverage} />

          {/* E. Registration Diagnostic — separate section */}
          <RegistrationDiagnostic results={results} />
        </Reveal>
      </section>

      {/* F. Quality Certificate */}
      <section className="quality" id="quality">
        <Reveal className="quality-copy glass-panel panel-right" reducedMotion={reducedMotion}>
          <p className="eyebrow">QUALITY CERTIFICATE</p>
          <h2>
            Can I trust this result?
            <br />
            What was actually validated?
          </h2>
          <p>
            {results.isLive
              ? "This live run shows the real pipeline path and controlled failure reporting. It does not establish independent registration accuracy."
              : "This static fixture shows the EXP-000 observation path and controlled failure reporting. It does not establish independent registration accuracy."}
          </p>
          <div
            className="geographic-target-card"
            onMouseEnter={() =>
              onFocusRegion?.({ lon: 25.24, lat: -84.9, zoomMultiplier: 0.88 })
            }
            onMouseLeave={() => onFocusRegion?.(null)}
            onClick={() =>
              onFocusRegion?.({ lon: 25.24, lat: -84.9, zoomMultiplier: 0.88 })
            }
            role="button"
            tabIndex={0}
            title="Focus Moon camera on South Polar crater basin"
          >
            <div className="target-card-header">
              <span className="target-tag">South Polar Cold Trap</span>
              <span className="target-coords">84.90°S · 25.24°E</span>
            </div>
            <div className="target-card-action">Focus camera on polar region ↗</div>
          </div>
        </Reveal>
        <Reveal className="glass-panel panel-right certificate-panel" delay={0.1} reducedMotion={reducedMotion}>
          <div className={`certificate-status ${statusClass}`}>
            <span>Status</span>
            <strong>{results.resultStatus}</strong>
          </div>
          <dl className="certificate">
            <div>
              <dt>Candidates</dt>
              <dd>{results.rawMatches}</dd>
            </div>
            <div>
              <dt>Verified (inliers)</dt>
              <dd>{results.verified}</dd>
            </div>
            <div>
              <dt>Inlier ratio</dt>
              <dd>{results.inlierRatio}</dd>
            </div>
            <div>
              <dt>{results.rmseLabel}</dt>
              <dd>{results.rmse}</dd>
            </div>
            <div>
              <dt>Control points</dt>
              <dd>{results.controlPointCount}</dd>
            </div>
            <div>
              <dt>Spatial coverage</dt>
              <dd>{results.coverage}</dd>
            </div>
            <div>
              <dt>Sub-pixel refinement</dt>
              <dd>{/indeterminate/i.test(results.refinement) ? "Indeterminate" : results.refinement}</dd>
            </div>
            <div>
              <dt>Independent accuracy</dt>
              <dd>Not independently validated</dd>
            </div>
            <div>
              <dt>Full-raster output</dt>
              <dd>
                {results.fullRasterBlocked
                  ? "Blocked by safety limit"
                  : results.registeredArtifactUrl
                    ? "Available"
                    : "Unavailable"}
              </dd>
            </div>
            <div>
              <dt>Source / reference</dt>
              <dd>
                {results.source} / {results.reference}
              </dd>
            </div>
            <div>
              <dt>Provenance</dt>
              <dd>
                {results.isLive
                  ? `Live job ${results.jobId ?? "—"}`
                  : "Static EXP-000 fixture"}
              </dd>
            </div>
            {results.flags.length > 0 && (
              <div>
                <dt>Warning / failure flags</dt>
                <dd>{results.flags.join(", ")}</dd>
              </div>
            )}
            {results.confidenceClass && (
              <div>
                <dt>Backend confidence_class</dt>
                <dd>{results.confidenceClass}</dd>
              </div>
            )}
          </dl>
        </Reveal>
      </section>

      {/* G. Limitations */}
      <section className="results-shell limitations-shell">
        <Reveal className="glass-panel panel-left" reducedMotion={reducedMotion}>
          <Limitations results={results} />
        </Reveal>
      </section>

      {/* H + I. Technical + Export */}
      <section className="report" id="report">
        <Reveal reducedMotion={reducedMotion}>
          <p className="eyebrow">TECHNICAL DETAILS / EXPORT</p>
          <h2>
            Built for a judge,
            <br />
            honest for a scientist.
          </h2>
        </Reveal>
        <Reveal className="report-card glass-panel panel-left" delay={0.1} reducedMotion={reducedMotion}>
          <span className="report-mark">↗</span>
          <b>
            {results.isLive ? "Live registration report" : "Static EXP-000 fixture report"}
          </b>
          <p>
            Metrics, transformation, selected points, quality flags, and the limitations of this
            baseline.
          </p>
          <button type="button" onClick={() => window.print()}>
            Print / save report
          </button>
        </Reveal>
        <Reveal className="technical glass-panel panel-left" delay={0.15} reducedMotion={reducedMotion}>
          <b>Technical details</b>
          <p>Source product: {results.sourceProduct}</p>
          <p>Reference product: {results.referenceProduct}</p>
          <p>Source acquisition: {results.acquisitionTimeSource}</p>
          <p>Reference acquisition: {results.acquisitionTimeReference}</p>
          <p>
            Matching view stride: Source {results.sourceStride}, Reference {results.referenceStride}
          </p>
          <p>Registration: {results.registration}</p>
          {results.transformationModel && (
            <p>Transformation model: {results.transformationModel}</p>
          )}
          <p>{results.residualNote}</p>
          {results.flags.length > 0 && <p>Flags: {results.flags.join(", ")}</p>}
          {results.jobId && <p>API job: {results.jobId}</p>}
          <p>Live result: {results.isLive ? "true" : "false"}</p>
        </Reveal>
      </section>
    </>
  );
}
