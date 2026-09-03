import { useEffect, useState, type ReactNode } from "react";
import { motion, useScroll, useSpring, useTransform } from "framer-motion";
import { CesiumMoon } from "./components/CesiumMoon";
import { MoonScene } from "./components/MoonScene";
import { exp000 } from "./data/exp000";

const stages = [
  "Deep space", "Chandrayaan approach", "Lunar orbit", "Region scan", "Correspondence", "Quality",
];

function Raster({ label, reference = false }: { label: string; reference?: boolean }) {
  return (
    <figure className={`raster ${reference ? "reference" : "source"}`}>
      <div className="raster-grid" aria-hidden="true" />
      {exp000.points.map((point, index) => (
        <i
          className="raster-point"
          key={index}
          style={{ left: `${reference ? point.rx : point.x}%`, top: `${reference ? point.ry : point.y}%` }}
        />
      ))}
      <figcaption>{label}<span>Illustrative viewing layer</span></figcaption>
    </figure>
  );
}

function ScrollSatellite({ reducedMotion }: { reducedMotion: boolean }) {
  const { scrollY } = useScroll();
  // The craft stays in the right-side orbit corridor, away from readable content.
  const x = useTransform(scrollY, [0, 520, 1050], ["0vw", "8vw", "22vw"]);
  const y = useTransform(scrollY, [0, 520, 1050], ["0vh", "24vh", "57vh"]);
  const rotate = useTransform(scrollY, [0, 1050], [-18, 27]);
  const scale = useTransform(scrollY, [0, 660, 1050], [1, 0.86, 0.35]);
  const opacity = useTransform(scrollY, [0, 760, 1050], [1, 1, 0]);

  return (
    <motion.div
      className="scroll-satellite"
      aria-hidden="true"
      style={reducedMotion ? undefined : { x, y, rotate, scale, opacity }}
    >
      <span className="satellite-trail" />
      <span className="satellite-panel panel-left" />
      <span className="satellite-body"><i /></span>
      <span className="satellite-panel panel-right" />
      <span className="satellite-dish" />
    </motion.div>
  );
}

/**
 * The moon is pinned to the viewport (position: fixed) and traces a slow
 * elliptical arc — from upper-right, bulging left, down to lower-center —
 * driven entirely by how far the visitor has scrolled through the *whole*
 * document. Only `x`/`y`/`scale`/`opacity` (all GPU-composited transform
 * properties) ever change; nothing here touches layout, which is what
 * keeps it smooth even on a fast trackpad fling.
 *
 * A spring sits between the raw scroll value and the ellipse so the moon
 * glides and settles instead of snapping to the scrollbar 1:1.
 */
function useMoonOrbit() {
  const { scrollYProgress } = useScroll();
  const smoothed = useSpring(scrollYProgress, {
    stiffness: 45,
    damping: 20,
    mass: 0.6,
    restDelta: 0.0008,
  });

  const angle = useTransform(smoothed, (p) => p * Math.PI); // 0 -> π, a half ellipse
  const x = useTransform(angle, (a) => `${70 - 18 * Math.sin(a)}vw`);
  const y = useTransform(angle, (a) => `${34 + 29 * (1 - Math.cos(a))}vh`);
  const scale = useTransform(smoothed, [0, 0.5, 1], [1, 0.84, 0.6]);
  const opacity = useTransform(smoothed, [0, 0.85, 1], [1, 1, 0.5]);

  return { x, y, scale, opacity };
}

/**
 * A single, restrained "float into view" moment per section — not per
 * card. Keeps the page feeling like content drifting into frame against
 * the starfield, rather than a checklist of triggered animations.
 */
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
  if (reducedMotion) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}

function App() {
  const [progress, setProgress] = useState(0.22);
  const [showRejected, setShowRejected] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const orbit = useMoonOrbit();
  const activeStage = Math.min(stages.length - 1, Math.floor(progress * stages.length));

  return (
    <main className="app-shell">
      <div className="ambient-stars" aria-hidden="true" />
      <div className="nebula-field" aria-hidden="true" />

      <div className="moon-layer" aria-hidden="true">
        <motion.div
          className="moon-orbit-wrap"
          style={
            reducedMotion
              ? { left: "44vw", top: "8vh" }
              : { x: orbit.x, y: orbit.y, scale: orbit.scale, opacity: orbit.opacity }
          }
        >
          <CesiumMoon reducedMotion={reducedMotion}>
            <MoonScene progress={progress} reducedMotion={reducedMotion} />
          </CesiumMoon>
        </motion.div>
      </div>

      <ScrollSatellite reducedMotion={reducedMotion} />

      <section className="hero" id="mission">
        <nav className="top-nav" aria-label="Primary navigation">
          <a className="brand" href="#mission">field<span>SPACE</span></a>
          <div><a href="#results">EXP-000</a><a href="#quality">Quality</a><a href="#report">Report</a></div>
          <span className="nav-status">BASELINE REPLAY</span>
        </nav>
        <div className="orbital-path" aria-hidden="true"><span className="satellite">✦</span><b /></div>
        <div className="hero-copy">
          <p className="eyebrow">SIH26166 / MULTI-MODAL LUNAR CORRESPONDENCE</p>
          <h1>Follow the signal.<br /><em>Inspect the evidence.</em></h1>
          <p className="hero-lede">A cinematic mission view that resolves into an auditable image-correspondence experiment.</p>
          <a className="primary-button" href="#results">Explore EXP-000 <span>↓</span></a>
        </div>
        <aside className="mission-control">
          <p>MISSION TIMELINE</p>
          <strong>0{activeStage + 1} / 0{stages.length}</strong>
          <span>{stages[activeStage]}</span>
          <input aria-label="Mission timeline" type="range" min="0" max="100" value={Math.round(progress * 100)} onChange={(event) => setProgress(Number(event.target.value) / 100)} />
        </aside>
      </section>

      <section className="bridge" aria-label="Scientific workflow">
        <Reveal className="glass-panel" reducedMotion={reducedMotion}>
          <p className="eyebrow">FROM ORBIT TO EVIDENCE</p>
          <div className="workflow">
            {["OHRC observation", "LRO reference", "Feature correspondences", "Geometric verification", "Registration quality"].map((item, index) => <div key={item}><b>0{index + 1}</b><span>{item}</span></div>)}
          </div>
        </Reveal>
      </section>

      <section className="results-shell" id="results">
        <Reveal className="glass-panel" reducedMotion={reducedMotion}>
          <header className="section-header">
            <div><p className="eyebrow">REAL-DATA BASELINE / {exp000.id}</p><h2>The scientific view</h2></div>
            <span className="state-pill">NOT INDEPENDENTLY VALIDATED</span>
          </header>
          <div className="metric-strip">
            <div><b>{exp000.rawMatches}</b><span>candidate correspondences</span></div>
            <div><b>{exp000.verified}</b><span>geometrically consistent</span></div>
            <div><b>{exp000.inlierRatio}</b><span>survived verification</span></div>
            <div><b>{exp000.coverage}</b><span>spatial coverage</span></div>
          </div>
          <div className="evidence-grid">
            <Raster label={exp000.source} />
            <div className="correspondence-rail" aria-label="Four verified correspondences">
              <p>VERIFIED<br />CORRESPONDENCES</p>
              {[0, 1, 2, 3].map((item) => <span key={item} style={{ top: `${25 + item * 15}%` }} />)}
            </div>
            <Raster label={exp000.reference} reference />
          </div>
          <div className="explorer-controls">
            <div><b>Correspondence explorer</b><span>These correspondences survived the geometric consistency check.</span></div>
            <button className={showRejected ? "active" : ""} onClick={() => setShowRejected((value) => !value)}>{showRejected ? "Hide" : "Show"} {exp000.rejected} rejected</button>
          </div>
          {showRejected && <div className="rejected-note">Rejected correspondences are retained for inspection but are not control points and do not enter registration.</div>}
        </Reveal>
      </section>

      <section className="quality" id="quality">
        <Reveal className="quality-copy glass-panel" reducedMotion={reducedMotion}>
          <p className="eyebrow">QUALITY CERTIFICATE</p><h2>Clear about what exists.<br />Clear about what does not.</h2><p>EXP-000 demonstrates a real product path and controlled failure reporting. It does not establish independent registration accuracy.</p>
        </Reveal>
        <Reveal className="glass-panel" delay={0.1} reducedMotion={reducedMotion}>
          <dl className="certificate">
            <div><dt>Source / reference</dt><dd>{exp000.source} / {exp000.reference}</dd></div>
            <div><dt>Refinement</dt><dd>{exp000.refinement}</dd></div>
            <div><dt>Registration</dt><dd>{exp000.registration}</dd></div>
            <div><dt>Independent accuracy</dt><dd>{exp000.independentAccuracy}</dd></div>
          </dl>
        </Reveal>
      </section>

      <section className="report" id="report">
        <Reveal reducedMotion={reducedMotion}>
          <p className="eyebrow">EXPORT / AUDIT TRAIL</p><h2>Built for a judge,<br />honest for a scientist.</h2>
        </Reveal>
        <Reveal className="report-card glass-panel" delay={0.1} reducedMotion={reducedMotion}>
          <span className="report-mark">↗</span><b>EXP-000 registration report</b><p>Metrics, transformation, selected points, quality flags, and the limitations of this baseline.</p><button onClick={() => window.print()}>Print / save report</button>
        </Reveal>
        <Reveal className="technical glass-panel" delay={0.15} reducedMotion={reducedMotion}>
          <b>Technical details</b><p>{exp000.sourceProduct}</p><p>{exp000.referenceProduct}</p><p>{exp000.residualNote}</p>
        </Reveal>
      </section>
      <footer><span>fieldSPACE / SIH26166</span><span>Scientific interface. Decorative orbit, real result state.</span></footer>
    </main>
  );
}

export default App;
