import "./MoonScene.css";

interface MoonSceneProps {
  progress: number; // 0..1, drives the mission-timeline scrub
  reducedMotion: boolean;
}

const CRATERS = [
  { cx: 150, cy: 120, r: 34, o: 0.35 },
  { cx: 260, cy: 90, r: 20, o: 0.3 },
  { cx: 90, cy: 230, r: 46, o: 0.3 },
  { cx: 230, cy: 250, r: 16, o: 0.4 },
  { cx: 300, cy: 200, r: 28, o: 0.28 },
  { cx: 170, cy: 300, r: 24, o: 0.3 },
  { cx: 60, cy: 120, r: 14, o: 0.35 },
  { cx: 330, cy: 290, r: 18, o: 0.3 },
  { cx: 130, cy: 60, r: 10, o: 0.4 },
  { cx: 20, cy: 200, r: 22, o: 0.3 },
  { cx: 380, cy: 150, r: 16, o: 0.3 },
  { cx: 220, cy: 40, r: 12, o: 0.35 },
];

export function MoonScene({ progress, reducedMotion }: MoonSceneProps) {
  // Scrubbing the mission timeline still reads as a small "approach"
  // wobble local to the moon body itself — independent of the larger
  // elliptical scroll orbit applied by the parent wrapper in App.tsx.
  const scale = 0.92 + progress * 0.16;
  const shiftX = (0.5 - progress) * 18;

  return (
    <div className="moon-stage" aria-hidden="true">
      <div
        className={`moon-rig${reducedMotion ? " is-still" : ""}`}
        style={{ transform: `translateX(${shiftX}px) scale(${scale})` }}
      >
        <div className="moon-glow" />
        <svg className="moon-svg" viewBox="0 0 400 400">
          <defs>
            <radialGradient id="moonBase" cx="38%" cy="32%" r="75%">
              <stop offset="0%" stopColor="#e9ede4" />
              <stop offset="45%" stopColor="#aab3a6" />
              <stop offset="78%" stopColor="#5d685f" />
              <stop offset="100%" stopColor="#262b26" />
            </radialGradient>
            <radialGradient id="craterShade" cx="40%" cy="35%" r="65%">
              <stop offset="0%" stopColor="rgba(0,0,0,0)" />
              <stop offset="100%" stopColor="rgba(0,0,0,.45)" />
            </radialGradient>
            <clipPath id="moonClip">
              <circle cx="200" cy="200" r="180" />
            </clipPath>
          </defs>
          <circle cx="200" cy="200" r="180" fill="url(#moonBase)" />
          <g clipPath="url(#moonClip)">
            <g className="crater-field">
              {CRATERS.map((c, i) => (
                <circle key={i} cx={c.cx} cy={c.cy} r={c.r} fill="#3c4139" opacity={c.o} />
              ))}
            </g>
            <circle cx="200" cy="200" r="180" fill="url(#craterShade)" />
          </g>
        </svg>
      </div>

      <div className="ring-orbit">
        <svg viewBox="0 0 500 500">
          <circle cx="250" cy="250" r="235" fill="none" stroke="rgba(201,255,94,.22)" strokeWidth="1" />
          <circle
            cx="250"
            cy="250"
            r="235"
            fill="none"
            stroke="rgba(201,255,94,.55)"
            strokeWidth="2"
            strokeDasharray="2 14"
            strokeLinecap="round"
          />
          <circle cx="250" cy="15" r="4" fill="#c9ff5e" style={{ filter: "drop-shadow(0 0 8px #c9ff5e)" }} />
        </svg>
      </div>
    </div>
  );
}