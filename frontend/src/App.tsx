import { useEffect, useState } from "react";
import { motion, useScroll, useSpring, useTransform } from "framer-motion";
import { A618OrbiterLayer } from "./components/A618OrbiterLayer";
import { CesiumMoon } from "./components/CesiumMoon";
import { MoonScene } from "./components/MoonScene";
import { SolarSystemEntrance } from "./components/SolarSystemEntrance";
import { RegistrationWorkspace } from "./components/workspace/RegistrationWorkspace";
import { ResultsPanel } from "./components/workspace/ResultsPanel";
import type { ResultsViewModel } from "./api/resultsView";

const stages = [
  "Deep space", "Equatorial approach", "OHRC strip scan", "Control points", "Quality certificate", "Audit trail",
];

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

function App() {
  const [viewMode, setViewMode]         = useState<"solar" | "mission">("solar");
  const [progress, setProgress]         = useState(0.0);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [focusedTarget, setFocusedTarget] = useState<{ lon: number; lat: number; zoomMultiplier?: number } | null>(null);
  /** Single source of truth for Results → Correspondence → Spatial → Quality. null = no live/fixture yet. */
  const [results, setResults] = useState<ResultsViewModel | null>(null);

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
    hudTitle = results?.isLive
      ? "LIVE SCAN FIELD // PIPELINE RESULT"
      : results
        ? "EXP-000 SCAN FIELD // FIXTURE"
        : "SCAN FIELD // AWAITING LIVE RESULT";
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
          <a className="brand" href="#mission">Selene<span>on</span></a>
          <div className="top-nav-links">
            <a href="#run">Register</a>
            <a href="#results">
              {results?.isLive ? "Live result" : results ? "Fixture" : "Results"}
            </a>
            <a href="#correspondence">Evidence</a>
            <a href="#spatial">Spatial</a>
            <a href="#quality">Quality</a>
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
            <a className="primary-button" href="#run">Open registration pipeline <span>↓</span></a>
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

        <RegistrationWorkspace
          onResults={(view) => {
            setResults(view);
            if (view.isLive) {
              document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
            }
          }}
        />

        <ResultsPanel
          results={results}
          reducedMotion={reducedMotion}
          onFocusRegion={setFocusedTarget}
        />

        <footer>
          <span>Seleneon / SIH26166</span>
          <span>
            {results?.isLive
              ? "Scientific interface. Live pipeline result values."
              : results
                ? "Scientific interface. Static EXP-000 fixture (regression only)."
                : "Scientific interface. No live result yet."}
          </span>
        </footer>
      </motion.main>
    </>
  );
}

export default App;
