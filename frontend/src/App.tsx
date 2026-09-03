import { useEffect, useState, type ReactNode } from "react";
import { motion, useScroll, useSpring, useTransform } from "framer-motion";
import { A618OrbiterLayer } from "./components/A618OrbiterLayer";
import { CesiumMoon } from "./components/CesiumMoon";
import { MoonScene } from "./components/MoonScene";
import { SolarSystemEntrance } from "./components/SolarSystemEntrance";
import { RegistrationWorkspace } from "./components/workspace/RegistrationWorkspace";
import { OverlayViewer } from "./components/workspace/OverlayViewer";
import { baselineResultsView, type ResultsViewModel } from "./api/resultsView";
import type { DisplayPoint } from "./api/resultsView";

const stages = [
  "Deep space", "Equatorial approach", "OHRC strip scan", "Control points", "Quality certificate", "Audit trail",
];

const CP_POINTS = [
  { lon: 23.42, lat: 0.83 },
  { lon: 23.39, lat: 0.55 },
  { lon: 23.46, lat: 0.62 },
  { lon: 23.44, lat: 0.38 },
];

function Raster({
  label,
  points,
  reference = false,
  onHoverPoint,
}: {
  label: string;
  points: DisplayPoint[];
  reference?: boolean;
  onHoverPoint?: (index: number | null) => void;
}) {
  return (
    <figure className={`raster ${reference ? "reference" : "source"}`}>
      <div className="raster-grid" aria-hidden="true" />
      {points.map((point, index) => (
        <i
          className="raster-point"
          key={index}
          style={{ left: `${reference ? point.rx : point.x}%`, top: `${reference ? point.ry : point.y}%` }}
          onMouseEnter={() => onHoverPoint?.(index)}
          onMouseLeave={() => onHoverPoint?.(null)}
          title={`Verified Inlier 0${index + 1}: ${point.residual} residual`}
        />
      ))}
      <figcaption>{label}<span>Illustrative viewing layer</span></figcaption>
    </figure>
  );
}

function useMoonOrbit() {
  const { scrollYProgress } = useScroll();
  const smoothed = useSpring(scrollYProgress, { stiffness: 38, damping: 20, mass: 0.65, restDelta: 0.0004 });

  const x = useTransform(
    smoothed,
    [0.0, 0.18, 0.34, 0.52, 0.74, 0.88, 1.0],
    ["50vw", "60vw", "64vw", "50vw", "42vw", "50vw", "50vw"]
  );

  const y = useTransform(
    smoothed,
    [0.0, 0.18, 0.34, 0.52, 0.74, 0.88, 1.0],
    ["45vh", "47vh", "49vh", "48vh", "50vh", "52vh", "52vh"]
  );

  const scale = useTransform(
    smoothed,
    [0.0,  0.16, 0.30, 0.44, 0.54, 0.66, 0.78, 0.90, 1.0],
    [1.16, 1.00, 1.15, 1.68, 1.90, 1.72, 1.42, 1.06, 0.94]
  );

  const opacity = useTransform(
    smoothed,
    [0.0, 0.88, 1.0],
    [1.0, 0.95, 0.84]
  );

  return { smoothed, x, y, scale, opacity };
}

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
      initial={{ opacity: 0, y: 32 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}

function formatDims(width: number | null, height: number | null): string {
  if (width == null || height == null) return "dimensions unavailable";
  return `${width.toLocaleString()} × ${height.toLocaleString()} px`;
}

function App() {
  const [viewMode, setViewMode]         = useState<"solar" | "mission">("solar");
  const [progress, setProgress]         = useState(0.0);
  const [showRejected, setShowRejected] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [focusedTarget, setFocusedTarget] = useState<{ lon: number; lat: number; zoomMultiplier?: number } | null>(null);
  const [results, setResults] = useState<ResultsViewModel>(() => baselineResultsView());
  const [showOverlay, setShowOverlay] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const { scrollYProgress } = useScroll();
  useEffect(() => {
    return scrollYProgress.on("change", (v) => setProgress(v));
  }, [scrollYProgress]);

  const orbit = useMoonOrbit();
  const activeStage = Math.min(stages.length - 1, Math.floor(progress * stages.length));

  let hudTitle = "DEEP SPACE // LUNAR DISC";
  let hudCoords = "LAT 0.65°N · LON 23.43°E";
  let hudStatus = "1.0× DISC";
  let hudIsExpanded = false;

  if (focusedTarget) {
    hudTitle = "TARGET LOCKED // CUSTOM FEATURE";
    hudCoords = `LAT ${Math.abs(focusedTarget.lat).toFixed(2)}°${focusedTarget.lat >= 0 ? "N" : "S"} · LON ${Math.abs(focusedTarget.lon).toFixed(2)}°${focusedTarget.lon >= 0 ? "E" : "W"}`;
    hudStatus = "3.2× TARGET LOCK";
    hudIsExpanded = true;
  } else if (progress < 0.18) {
    hudTitle = "DEEP SPACE // GLOBAL VIEW";
    hudCoords = "LAT 0.65°N · LON 23.43°E";
    hudStatus = "1.0× DISC";
  } else if (progress < 0.38) {
    hudTitle = "ORBITAL TRANSIT // EQUATORIAL VECTOR";
    hudCoords = "LAT 8.00°N · LON 23.43°E";
    hudStatus = "1.2× APPROACH";
  } else if (progress < 0.68) {
    hudTitle = results.isLive ? "LIVE SCAN FIELD // PIPELINE RESULT" : "EXP-000 SCAN FIELD // EQUATORIAL INLIERS";
    hudCoords = "LAT 0.65°N · LON 23.43°E";
    hudStatus = "2.8× EXPANDED (SURFACE FOCUS)";
    hudIsExpanded = true;
  } else if (progress < 0.86) {
    hudTitle = "SOUTH POLAR BASIN // COLD TRAPS";
    hudCoords = "LAT 84.90°S · LON 25.24°E";
    hudStatus = "2.2× POLAR EXPANSION";
    hudIsExpanded = true;
  } else {
    hudTitle = "SYNTHESIS // SCIENTIFIC AUDIT";
    hudCoords = "LAT 0.65°N · LON 23.43°E";
    hudStatus = "1.0× GLOBAL AUDIT";
  }

  const failureFlags = results.flags.filter((f) =>
    [
      "no_correspondences",
      "insufficient_verified_matches",
      "insufficient_control_points",
      "degenerate_control_points",
      "invalid_transformation",
      "warp_failed",
    ].includes(f),
  );
  const isNoMatch = results.rawMatches === 0 || results.verified === 0;

  return (
    <>
      {viewMode === "solar" && (
        <SolarSystemEntrance
          onEnterLunarMission={() => setViewMode("mission")}
          reducedMotion={reducedMotion}
        />
      )}

      <motion.main
        className="app-shell"
        initial={{ opacity: 0 }}
        animate={{ opacity: viewMode === "mission" ? 1 : 0 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        style={{ pointerEvents: viewMode === "mission" ? "auto" : "none" }}
      >
        <div className="ambient-stars" aria-hidden="true" />
        <div className="nebula-field"  aria-hidden="true" />

        <div className="moon-layer" aria-hidden="true">
          <motion.div
            className="moon-orbit-wrap"
            style={
              reducedMotion
                ? undefined
                : {
                    x: orbit.x,
                    y: orbit.y,
                    scale: orbit.scale,
                    opacity: orbit.opacity,
                  }
            }
          >
            <CesiumMoon progress={progress} reducedMotion={reducedMotion}>
              <MoonScene
                progress={progress}
                reducedMotion={reducedMotion}
                focusedTarget={focusedTarget}
              />
            </CesiumMoon>
            <A618OrbiterLayer reducedMotion={reducedMotion} />
          </motion.div>
        </div>

        <aside className="moon-telemetry-hud" aria-label="Lunar telemetry and targeting coordinates">
          <div className="telemetry-badge">
            <span className="telemetry-dot" />
            <span className="telemetry-title">{hudTitle}</span>
          </div>
          <div className="telemetry-coords">
            <span>{hudCoords}</span>
            <span className={`telemetry-zoom ${hudIsExpanded ? "is-expanded" : ""}`}>
              {hudStatus}
            </span>
          </div>
        </aside>

        <nav className="top-nav" aria-label="Primary navigation">
          <a className="brand" href="#mission">field<span>SPACE</span></a>
          <div className="top-nav-links">
            <a href="#run">Run</a>
            <a href="#results">{results.isLive ? "Live result" : "EXP-000"}</a>
            <a href="#quality">Quality</a>
            <a href="#report">Report</a>
          </div>
          <div className="nav-actions">
            <button
              className="orbit-switch-btn"
              onClick={() => setViewMode("solar")}
              title="Return to Solar System overview"
            >
              ↺ Solar View
            </button>
          </div>
        </nav>

        <section className="hero" id="mission">
          <div className="hero-content-left">
            <p className="eyebrow">SIH26166 / MULTIMODAL LUNAR CORRESPONDENCE</p>
            <h1>Follow the signal.<br /><em>Inspect the evidence.</em></h1>
            <p className="hero-lede">
              A cinematic, scroll-driven mission view that resolves into an auditable
              OHRC × LRO NAC image-correspondence experiment — now wired to the live
              scientific pipeline API.
            </p>
            <a className="primary-button" href="#run">Run registration <span>↓</span></a>
          </div>

          <aside className="mission-control" aria-label="Mission timeline">
            <p>MISSION TIMELINE</p>
            <strong>0{activeStage + 1} / 0{stages.length}</strong>
            <span>{stages[activeStage]}</span>
            <input
              aria-label="Mission timeline scrubber"
              type="range" min="0" max="100"
              value={Math.round(progress * 100)}
              onChange={(e) => setProgress(Number(e.target.value) / 100)}
            />
          </aside>
        </section>

        {/* ── WORKSPACE ── */}
        <RegistrationWorkspace 
          onResults={(view) => {
            setResults(view);
            setShowRejected(false);
            if (view.isLive) {
              document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
            }
          }} 
        />

        <section className="results-shell" id="results">
          <Reveal className="glass-panel panel-left" reducedMotion={reducedMotion}>
            <header className="section-header">
              <div>
                <p className="eyebrow">
                  {results.isLive ? "LIVE PIPELINE RESULT / " : "REAL-DATA BASELINE / "}
                  {results.id}
                </p>
                <h2>The scientific view</h2>
              </div>
              <span className="state-pill">
                {results.isLive ? "LIVE · NOT INDEPENDENTLY VALIDATED" : "NOT INDEPENDENTLY VALIDATED"}
              </span>
            </header>

            {isNoMatch && results.isLive && (
              <div className="run-error" role="status">
                <b>{results.rawMatches === 0 ? "No correspondences" : "Insufficient verified matches"}</b>
                <span>
                  {results.rawMatches === 0
                    ? "The matcher returned an empty correspondence set for this pair."
                    : `Candidates: ${results.rawMatches}; verified inliers: ${results.verified}.`}
                </span>
              </div>
            )}

            {failureFlags.length > 0 && results.isLive && (
              <div className="rejected-note">
                Quality flags: {failureFlags.join(", ")}
              </div>
            )}

            <div className="metric-strip">
              <div title="Total features matched before geometric filtering.">
                <b>{results.rawMatches}</b><span>candidate correspondences</span>
              </div>
              <div title="Correspondences surviving geometric verification.">
                <b>{results.verified}</b><span>geometric inliers</span>
              </div>
              <div title="Ratio of inliers to total candidates.">
                <b>{results.inlierRatio}</b><span>inlier ratio</span>
              </div>
              <div title="Proportion of the image area bounded by control points.">
                <b>{results.coverage}</b><span>spatial coverage</span>
              </div>
              <div title="Verification residual RMSE is a geometric-verification fit diagnostic, not independent registration accuracy.">
                <b className="metric-val-formatted">{results.rmse}</b>
                <span>{results.rmseLabel}</span>
              </div>
              <div title="Total execution time for the pipeline.">
                <b>
                  {results.runtimeSeconds != null
                    ? `${results.runtimeSeconds.toFixed(1)} s`
                    : "—"}
                </b>
                <span>pipeline runtime</span>
              </div>
            </div>

          <div className="dims-strip">
            <div>
              <span className="chip chip-ohrc">{results.source}</span>
              <span>
                {formatDims(results.sourceDims.width, results.sourceDims.height)}
                {results.sourceDims.gsd ? ` — ${results.sourceDims.gsd}` : ""}
              </span>
            </div>
            <div>
              <span className="chip chip-lro">{results.reference}</span>
              <span>{formatDims(results.referenceDims.width, results.referenceDims.height)}</span>
            </div>
            {results.region && (
              <div
                className="chip-interactive"
                onMouseEnter={() => setFocusedTarget({ lon: 23.43, lat: 0.65, zoomMultiplier: 0.88 })}
                onMouseLeave={() => setFocusedTarget(null)}
                onClick={() => setFocusedTarget({ lon: 23.43, lat: 0.65, zoomMultiplier: 0.88 })}
                role="button"
                tabIndex={0}
                title="Focus Moon camera directly on Equatorial OHRC scan field"
              >
                <span className="chip chip-region">Focus Scan Field ⊕</span>
                <span>
                  {results.region.label} · lat {results.region.lat[0]}–{results.region.lat[1]}° · lon{" "}
                  {results.region.lon[0]}–{results.region.lon[1]}°
                </span>
              </div>
            )}
            {results.registeredArtifactUrl && (
              <div>
                <span className="chip chip-region">Registered artifact</span>
                <a href={results.registeredArtifactUrl} target="_blank" rel="noreferrer">
                  Download registered source
                </a>
              </div>
            )}
          </div>

          <div className="view-toggle-controls" style={{ display: "flex", gap: "12px", justifyContent: "center", marginBottom: "24px" }}>
            <button 
              className={`secondary-button ${!showOverlay ? "active" : ""}`} 
              onClick={() => setShowOverlay(false)}
              style={!showOverlay ? { borderColor: "var(--signal)", color: "var(--signal)", background: "rgba(56, 189, 248, 0.1)" } : {}}
            >
              Split Correspondences
            </button>
            <button 
              className={`secondary-button ${showOverlay ? "active" : ""}`} 
              onClick={() => setShowOverlay(true)}
              style={showOverlay ? { borderColor: "var(--signal)", color: "var(--signal)", background: "rgba(56, 189, 248, 0.1)" } : {}}
            >
              Registration Overlay
            </button>
          </div>

          {!showOverlay ? (
            <div className="evidence-grid">
              <Raster
                label={results.source}
                points={results.points}
                onHoverPoint={(index) => {
                  if (index !== null && CP_POINTS[index]) {
                    setFocusedTarget({ lon: CP_POINTS[index].lon, lat: CP_POINTS[index].lat, zoomMultiplier: 0.82 });
                  } else {
                    setFocusedTarget(null);
                  }
                }}
              />
              <div className="correspondence-rail" aria-label="Verified correspondences">
                <p>VERIFIED<br />CORRESPONDENCES</p>
                {results.points.slice(0, 4).map((_, item) => (
                  <span
                    key={item}
                    style={{ top: `${22 + item * 16}%` }}
                    onMouseEnter={() => {
                      if (CP_POINTS[item]) {
                        setFocusedTarget({ lon: CP_POINTS[item].lon, lat: CP_POINTS[item].lat, zoomMultiplier: 0.82 });
                      }
                    }}
                    onMouseLeave={() => setFocusedTarget(null)}
                    title={`Inspect Verified Point CP-0${item + 1}`}
                  />
                ))}
              </div>
              <Raster
                label={results.reference}
                points={results.points}
                reference
                onHoverPoint={(index) => {
                  if (index !== null && CP_POINTS[index]) {
                    setFocusedTarget({ lon: CP_POINTS[index].lon, lat: CP_POINTS[index].lat, zoomMultiplier: 0.82 });
                  } else {
                    setFocusedTarget(null);
                  }
                }}
              />
            </div>
          ) : (
            <OverlayViewer />
          )}

          <div className="explorer-controls">
            <div>
              <b>Correspondence explorer</b>
              <span>
                {results.verified} inliers survived geometric verification
                ({results.rejected} rejected).
              </span>
            </div>
            <button
              className={showRejected ? "active" : ""}
              onClick={() => setShowRejected((v) => !v)}
            >
              {showRejected ? "Hide" : "Show"} {results.rejected} rejected
            </button>
          </div>
          {showRejected && (
            <div className="rejected-note">
              Rejected correspondences are retained for inspection but are not control points and do not enter registration.
            </div>
          )}
        </Reveal>
      </section>

      <section className="quality" id="quality">
        <Reveal className="quality-copy glass-panel panel-right" reducedMotion={reducedMotion}>
          <p className="eyebrow">QUALITY CERTIFICATE</p>
          <h2>Clear about what exists.<br />Clear about what does not.</h2>
          <p>
            {results.isLive
              ? "This live run shows the real pipeline path and controlled failure reporting. It does not establish independent registration accuracy."
              : "EXP-000 demonstrates a real product path and controlled failure reporting. It does not establish independent registration accuracy."}
          </p>
          <div
            className="geographic-target-card"
            onMouseEnter={() => setFocusedTarget({ lon: 25.24, lat: -84.9, zoomMultiplier: 0.88 })}
            onMouseLeave={() => setFocusedTarget(null)}
            onClick={() => setFocusedTarget({ lon: 25.24, lat: -84.9, zoomMultiplier: 0.88 })}
            role="button"
            tabIndex={0}
            title="Focus Moon camera directly on South Polar crater basin"
          >
            <div className="target-card-header">
              <span className="target-tag">South Polar Cold Trap</span>
              <span className="target-coords">84.90°S · 25.24°E</span>
            </div>
            <div className="target-card-action">
              Focus camera on polar region ↗
            </div>
          </div>
        </Reveal>
        <Reveal className="glass-panel panel-right" delay={0.1} reducedMotion={reducedMotion}>
          <dl className="certificate">
            <div><dt>Source / reference</dt><dd>{results.source} / {results.reference}</dd></div>
            <div><dt>Source acquisition</dt><dd>{results.acquisitionTimeSource}</dd></div>
            <div><dt>Reference acquisition</dt><dd>{results.acquisitionTimeReference}</dd></div>
            <div><dt>Matching view stride</dt><dd>Source {results.sourceStride}, Reference {results.referenceStride}</dd></div>
            <div><dt>Refinement</dt><dd>{results.refinement}</dd></div>
            <div><dt>Registration</dt><dd>{results.registration}</dd></div>
            <div><dt>Independent accuracy</dt><dd>{results.independentAccuracy}</dd></div>
          </dl>
        </Reveal>
      </section>

      <section className="report" id="report">
        <Reveal reducedMotion={reducedMotion}>
          <p className="eyebrow">EXPORT / AUDIT TRAIL</p>
          <h2>Built for a judge,<br />honest for a scientist.</h2>
        </Reveal>
        <Reveal className="report-card glass-panel panel-left" delay={0.1} reducedMotion={reducedMotion}>
          <span className="report-mark">↗</span>
          <b>{results.isLive ? "Live registration report" : "EXP-000 registration report"}</b>
          <p>Metrics, transformation, selected points, quality flags, and the limitations of this baseline.</p>
          <button onClick={() => window.print()}>Print / save report</button>
        </Reveal>
        <Reveal className="technical glass-panel panel-left" delay={0.15} reducedMotion={reducedMotion}>
          <b>Technical details</b>
          <p>{results.sourceProduct}</p>
          <p>{results.referenceProduct}</p>
          <p>{results.residualNote}</p>
          {results.flags.length > 0 && <p>Flags: {results.flags.join(", ")}</p>}
          {results.jobId && <p>API job: {results.jobId}</p>}
        </Reveal>
      </section>

      <footer>
        <span>fieldSPACE / SIH26166</span>
        <span>
          {results.isLive
            ? "Scientific interface. Live pipeline result values."
            : "Scientific interface. Real EXP-000 result values."}
        </span>
      </footer>
    </motion.main>
    </>
  );
}

export default App;
