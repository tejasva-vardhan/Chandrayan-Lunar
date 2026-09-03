import { useEffect, useState, type ReactNode } from "react";
import { motion, useScroll, useSpring, useTransform } from "framer-motion";
import { A618OrbiterLayer } from "./components/A618OrbiterLayer";
import { CesiumMoon } from "./components/CesiumMoon";
import { MoonScene } from "./components/MoonScene";
import { SolarSystemEntrance } from "./components/SolarSystemEntrance";
import { RegistrationWorkspace } from "./components/workspace/RegistrationWorkspace";
import { exp000 } from "./data/exp000";

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
  reference = false,
  onHoverPoint,
}: {
  label: string;
  reference?: boolean;
  onHoverPoint?: (index: number | null) => void;
}) {
  return (
    <figure className={`raster ${reference ? "reference" : "source"}`}>
      <div className="raster-grid" aria-hidden="true" />
      {exp000.points.map((point, index) => (
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

import { A618Satellite } from "./components/A618Satellite";

/** Fixed 3D A-618 Satellite HUD that remains pinned on screen across all scroll sections */
function ScrollOrbital({ reducedMotion }: { reducedMotion: boolean }) {
  const { scrollYProgress } = useScroll();
  const rotate = useTransform(scrollYProgress, [0, 1], [0, 90]);
  const scale = useTransform(scrollYProgress, [0, 0.5, 1], [1, 0.95, 0.92]);

  return (
    <motion.div
      className="scroll-orbital"
      aria-label="A-618 Lunar Orbiter Spacecraft"
      style={reducedMotion ? undefined : { rotate, scale }}
    >
      <div className="a618-tag">
        <span className="a618-dot" />
        <span>A-618 ORBITER</span>
      </div>
      <A618Satellite reducedMotion={reducedMotion} />
    </motion.div>
  );
}

/** Spring-smoothed scroll progress drives the moon movement and expansion */
function useMoonOrbit() {
  const { scrollYProgress } = useScroll();
  const smoothed = useSpring(scrollYProgress, { stiffness: 38, damping: 20, mass: 0.65, restDelta: 0.0004 });

  // The Moon is NOT fixed on the side — it moves across the viewport with the scroll:
  // - Hero: Centered at 50vw, 45vh (commanding celestial view)
  // - Workflow: Drifts to 64vw to complement left-aligned stages
  // - Results / Inliers Field: Centered at 50vw and EXPANDS dramatically over the crater field!
  // - Quality / South Pole: Glides to 42vw, expanded for polar cold traps
  // - Report / Audit: 50vw global audit view
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

  // Dynamic Expansion:
  // - Starts at 1.16 in Hero
  // - EXPANDS massively up to 1.90x as we approach the scientific results & crater control points field!
  // - Stays expanded (1.42x) for South Pole exploration
  // - Pulls back smoothly to 0.94x for the final report
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

function App() {
  const [viewMode, setViewMode]         = useState<"solar" | "mission">("solar");
  const [progress, setProgress]         = useState(0.0);
  const [showRejected, setShowRejected] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [focusedTarget, setFocusedTarget] = useState<{ lon: number; lat: number; zoomMultiplier?: number } | null>(null);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  // Drive progress from scroll position for the moon camera
  const { scrollYProgress } = useScroll();
  useEffect(() => {
    return scrollYProgress.on("change", (v) => setProgress(v));
  }, [scrollYProgress]);

  const orbit = useMoonOrbit();
  const activeStage = Math.min(stages.length - 1, Math.floor(progress * stages.length));

  // Determine current telemetry readout and expansion status
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
    hudTitle = "EXP-000 SCAN FIELD // EQUATORIAL INLIERS";
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

        {/* Dynamic scroll-driven Moon: moves with the page and expands into specific lunar fields */}
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
            {/* 3D A-618 Spacecraft actively hovering and orbiting the Moon */}
            <A618OrbiterLayer reducedMotion={reducedMotion} />
          </motion.div>
        </div>

        {/* Lunar Telemetry HUD Overlay */}
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

        {/* Pinned Top Navigation across all sections */}
        <nav className="top-nav" aria-label="Primary navigation">
          <a className="brand" href="#mission">field<span>SPACE</span></a>
          <div className="top-nav-links">
            <a href="#results">EXP-000</a>
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

        {/* ── HERO ── */}
        <section className="hero" id="mission">
          <div className="hero-content-left">
            <p className="eyebrow">SIH26166 / MULTIMODAL LUNAR CORRESPONDENCE</p>
            <h1>Follow the signal.<br /><em>Inspect the evidence.</em></h1>
            <p className="hero-lede">
              A cinematic, scroll-driven mission view that resolves into an auditable
              OHRC × LRO NAC image-correspondence experiment.
            </p>
            <a className="primary-button" href="#results">Explore EXP-000 <span>↓</span></a>
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
        <RegistrationWorkspace onComplete={() => {
          document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' });
        }} />

        {/* ── RESULTS ── */}
        <section className="results-shell" id="results">
          <Reveal className="glass-panel panel-left" reducedMotion={reducedMotion}>
            <header className="section-header">
              <div>
                <p className="eyebrow">REAL-DATA BASELINE / {exp000.id}</p>
                <h2>The scientific view</h2>
              </div>
              <span className="state-pill">NOT INDEPENDENTLY VALIDATED</span>
            </header>

            <div className="metric-strip">
              <div title="Total features matched before geometric filtering.">
                <b>{exp000.rawMatches}</b><span>candidate correspondences</span>
              </div>
              <div title="Correspondences surviving geometric verification via RANSAC.">
                <b>{exp000.verified}</b><span>geometric inliers</span>
              </div>
              <div title="Ratio of inliers to total candidates.">
                <b>{exp000.inlierRatio}</b><span>inlier ratio</span>
              </div>
              <div title="Proportion of the image area bounded by control points.">
                <b>{exp000.coverage}</b><span>spatial coverage</span>
              </div>
              <div title="⚠️ Verification RMSE is NOT independent registration accuracy. Fit residuals on 4 points will naturally approach zero.">
                <b className="metric-val-formatted">
                  9.41 × 10<sup>-10</sup> <span className="metric-unit">px</span>
                </b>
                <span style={{ color: "var(--danger)", fontWeight: 500 }}>verification RMSE ⚠️</span>
              </div>
              <div title="Total execution time for the pipeline.">
                <b>{exp000.runtimeSeconds.toFixed(1)} s</b><span>pipeline runtime</span>
              </div>
            </div>

          {/* Image dimensions */}
          <div className="dims-strip">
            <div>
              <span className="chip chip-ohrc">OHRC</span>
              <span>{exp000.sourceDims.width.toLocaleString()} × {exp000.sourceDims.height.toLocaleString()} px — {exp000.sourceDims.gsd}</span>
            </div>
            <div>
              <span className="chip chip-lro">LRO NAC</span>
              <span>{exp000.referenceDims.width.toLocaleString()} × {exp000.referenceDims.height.toLocaleString()} px</span>
            </div>
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
              <span>{exp000.region.label} · lat {exp000.region.lat[0]}–{exp000.region.lat[1]}° · lon {exp000.region.lon[0]}–{exp000.region.lon[1]}°</span>
            </div>
          </div>

          <div className="evidence-grid">
            <Raster
              label={exp000.source}
              onHoverPoint={(index) => {
                if (index !== null && CP_POINTS[index]) {
                  setFocusedTarget({ lon: CP_POINTS[index].lon, lat: CP_POINTS[index].lat, zoomMultiplier: 0.82 });
                } else {
                  setFocusedTarget(null);
                }
              }}
            />
            <div className="correspondence-rail" aria-label="Four verified correspondences">
              <p>VERIFIED<br />CORRESPONDENCES</p>
              {[0, 1, 2, 3].map((item) => (
                <span
                  key={item}
                  style={{ top: `${22 + item * 16}%` }}
                  onMouseEnter={() => setFocusedTarget({ lon: CP_POINTS[item].lon, lat: CP_POINTS[item].lat, zoomMultiplier: 0.82 })}
                  onMouseLeave={() => setFocusedTarget(null)}
                  title={`Inspect Verified Point CP-0${item + 1} (${CP_POINTS[item].lon}°E, ${CP_POINTS[item].lat}°N)`}
                />
              ))}
            </div>
            <Raster
              label={exp000.reference}
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

          <div className="explorer-controls">
            <div>
              <b>Correspondence explorer</b>
              <span>4 inliers survived RANSAC-style geometric verification (32 rejected).</span>
            </div>
            <button
              className={showRejected ? "active" : ""}
              onClick={() => setShowRejected((v) => !v)}
            >
              {showRejected ? "Hide" : "Show"} {exp000.rejected} rejected
            </button>
          </div>
          {showRejected && (
            <div className="rejected-note">
              Rejected correspondences are retained for inspection but are not control points and do not enter registration.
            </div>
          )}
        </Reveal>
      </section>

      {/* ── QUALITY ── */}
      <section className="quality" id="quality">
        <Reveal className="quality-copy glass-panel panel-right" reducedMotion={reducedMotion}>
          <p className="eyebrow">QUALITY CERTIFICATE</p>
          <h2>Clear about what exists.<br />Clear about what does not.</h2>
          <p>EXP-000 demonstrates a real product path and controlled failure reporting. It does not establish independent registration accuracy.</p>
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
            <div><dt>Source / reference</dt><dd>{exp000.source} / {exp000.reference}</dd></div>
            <div><dt>OHRC acquisition</dt><dd>{exp000.acquisitionTimeSource}</dd></div>
            <div><dt>LRO NAC acquisition</dt><dd>{exp000.acquisitionTimeReference}</dd></div>
            <div><dt>Matching view stride</dt><dd>Source ×{exp000.sourceStride}, Reference ×{exp000.referenceStride}</dd></div>
            <div><dt>Refinement</dt><dd>{exp000.refinement}</dd></div>
            <div><dt>Registration</dt><dd>{exp000.registration}</dd></div>
            <div><dt>Independent accuracy</dt><dd>{exp000.independentAccuracy}</dd></div>
          </dl>
        </Reveal>
      </section>

      {/* ── REPORT ── */}
      <section className="report" id="report">
        <Reveal reducedMotion={reducedMotion}>
          <p className="eyebrow">EXPORT / AUDIT TRAIL</p>
          <h2>Built for a judge,<br />honest for a scientist.</h2>
        </Reveal>
        <Reveal className="report-card glass-panel panel-left" delay={0.1} reducedMotion={reducedMotion}>
          <span className="report-mark">↗</span>
          <b>EXP-000 registration report</b>
          <p>Metrics, transformation, selected points, quality flags, and the limitations of this baseline.</p>
          <button onClick={() => window.print()}>Print / save report</button>
        </Reveal>
        <Reveal className="technical glass-panel panel-left" delay={0.15} reducedMotion={reducedMotion}>
          <b>Technical details</b>
          <p>{exp000.sourceProduct}</p>
          <p>{exp000.referenceProduct}</p>
          <p>{exp000.residualNote}</p>
        </Reveal>
      </section>

      <footer>
        <span>fieldSPACE / SIH26166</span>
        <span>Scientific interface. Real EXP-000 result values.</span>
      </footer>
    </motion.main>
    </>
  );
}

export default App;
