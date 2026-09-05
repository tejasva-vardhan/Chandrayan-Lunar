/**
 * Technical vision / capability roadmap.
 * LIVE rows reflect implemented pipeline paths.
 * Planned cards show intended sensors/architecture only — never fake evidence.
 */

export type CapabilityStatus =
  | "LIVE"
  | "Pending validation"
  | "Planned / simulated"
  | "Interface prepared / pending integration"
  | "Pending";

export type CapabilityRow = {
  capability: string;
  status: CapabilityStatus;
  tone: "live" | "pending" | "planned";
};

export type PlannedSensorCard = {
  id: string;
  sensor: string;
  badge: string;
  summary: string;
  metadata: { label: string; value: string }[];
  workflow: string[];
  boundary: string;
};

export const CAPABILITY_ROWS: CapabilityRow[] = [
  { capability: "OHRC ↔ LRO correspondence", status: "LIVE", tone: "live" },
  { capability: "Registration pipeline", status: "LIVE", tone: "live" },
  { capability: "Control-point selection", status: "LIVE", tone: "live" },
  { capability: "Sub-pixel refinement", status: "Pending validation", tone: "pending" },
  { capability: "TMC-2 support", status: "Planned / simulated", tone: "planned" },
  { capability: "IIRS support", status: "Planned / simulated", tone: "planned" },
  {
    capability: "SPICE geometry",
    status: "Interface prepared / pending integration",
    tone: "planned",
  },
  { capability: "Independent accuracy", status: "Pending", tone: "pending" },
];

export const PLANNED_SENSOR_CARDS: PlannedSensorCard[] = [
  {
    id: "iirs",
    sensor: "IIRS",
    badge: "PLANNED / SIMULATED",
    summary:
      "Intended multispectral / hyperspectral path for Chandrayaan-2 IIRS — UI and architecture only.",
    metadata: [
      { label: "Sensor", value: "IIRS" },
      { label: "Spectral range", value: "0.8–5.0 µm (intended)" },
      { label: "GSD", value: "~80 m (typical product class)" },
      { label: "Processing concept", value: "Multispectral/hyperspectral representation → feature extraction → matching" },
    ],
    workflow: [
      "Product metadata (SIMULATED)",
      "Spectral representation",
      "Feature extraction",
      "Cross-sensor matching",
    ],
    boundary:
      "IIRS integration: Planned / simulated. No fake matching accuracy, correspondence counts, or residuals.",
  },
  {
    id: "tmc2",
    sensor: "TMC-2",
    badge: "PLANNED / SIMULATED",
    summary:
      "Intended stereo geometry path for Chandrayaan-2 TMC-2 Fore / Nadir / Aft — concept cards only.",
    metadata: [
      { label: "Sensor", value: "TMC-2" },
      { label: "Stereo configuration", value: "Fore / Nadir / Aft (intended)" },
      { label: "Geometric handling", value: "Stereo viewpoint / scale normalization concept" },
      { label: "Example inputs", value: "SIMULATED — not a live product run" },
    ],
    workflow: [
      "Stereo triplet metadata (SIMULATED)",
      "Scale / viewpoint normalization",
      "Correspondence candidates",
      "Geometric consistency checks",
    ],
    boundary:
      "TMC-2 integration: Planned / simulated. No fake verified-match counts or registration metrics.",
  },
  {
    id: "spice",
    sensor: "SPICE",
    badge: "INTERFACE PREPARED",
    summary:
      "Geometry / time / frame integration skeleton. Live SPICE computation is not claimed.",
    metadata: [
      { label: "Role", value: "Product metadata → SPICE geometry → camera/view geometry → normalization → correspondence" },
      { label: "Status", value: "Interface prepared; live computation pending" },
      { label: "Example inputs", value: "SIMULATED placeholders only" },
    ],
    workflow: [
      "Product metadata",
      "SPICE geometry",
      "Camera / view geometry",
      "Normalization",
      "Correspondence",
    ],
    boundary:
      "SPICE geometry integration: Interface prepared; live computation pending. No invented spacecraft positions, attitudes, Sun angles, or geometric residuals.",
  },
];

export function CapabilityRoadmap() {
  return (
    <section className="results-shell capability-roadmap" id="roadmap" aria-labelledby="roadmap-title">
      <div className="glass-panel panel-left capability-roadmap-panel">
        <header className="section-header results-header">
          <div>
            <p className="eyebrow">TECHNICAL / EXPERIMENT VISION</p>
            <h2 id="roadmap-title">Capability status</h2>
            <p className="results-status-sentence">
              Complete architecture vision with an unambiguous boundary between LIVE pipeline
              evidence and Planned / simulated sensor paths.
            </p>
          </div>
          <span className="provenance-badge is-fixture">LIVE ≠ SIMULATED</span>
        </header>

        <p className="what-you-see">
          <span>What you&apos;re seeing</span>
          Status of implemented science versus planned multimodal expansion. Dummy metadata and
          workflow cards are allowed; fabricated scientific evidence is not.
        </p>

        <div className="capability-table-wrap" role="region" aria-label="Capability status table">
          <table className="capability-table">
            <thead>
              <tr>
                <th scope="col">Capability</th>
                <th scope="col">Current status</th>
              </tr>
            </thead>
            <tbody>
              {CAPABILITY_ROWS.map((row) => (
                <tr key={row.capability}>
                  <td>{row.capability}</td>
                  <td>
                    <span className={`capability-status tone-${row.tone}`}>{row.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <header className="results-block-header capability-cards-header">
          <div>
            <h3>Planned / simulated sensor paths</h3>
            <p className="results-block-subtitle">
              Intended metadata and processing concepts only — disabled for live evidence.
            </p>
          </div>
        </header>

        <div className="planned-sensor-grid">
          {PLANNED_SENSOR_CARDS.map((card) => (
            <article key={card.id} className="planned-sensor-card" aria-labelledby={`planned-${card.id}`}>
              <div className="planned-sensor-card-top">
                <h4 id={`planned-${card.id}`}>{card.sensor}</h4>
                <span className="provenance-badge is-fixture">{card.badge}</span>
              </div>
              <p className="planned-sensor-summary">{card.summary}</p>
              <dl className="pair-char-grid planned-meta-grid">
                {card.metadata.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
              <ol className="planned-workflow" aria-label={`${card.sensor} intended workflow`}>
                {card.workflow.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <p className="planned-boundary">{card.boundary}</p>
              <button type="button" className="planned-disabled-cta" disabled>
                Not in this demo run
              </button>
            </article>
          ))}
        </div>

        <div className="capability-honesty" role="note">
          <b>Evidence boundary</b>
          <span>
            UI and workflow simulation is allowed. Scientific evidence is not: no fake IIRS
            accuracy, TMC-2 match counts, SPICE geometry, sub-pixel error, or independent
            validation numbers.
          </span>
        </div>
      </div>
    </section>
  );
}
