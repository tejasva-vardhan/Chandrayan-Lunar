import { useMemo, useState } from "react";
import type { DisplayPoint } from "../../api/resultsView";

type CorrespondenceEvidenceProps = {
  sourceLabel: string;
  referenceLabel: string;
  sourceUrl?: string | null;
  referenceUrl?: string | null;
  points: DisplayPoint[];
  showRejected: boolean;
};

const STATUS_LABEL: Record<DisplayPoint["status"], string> = {
  candidate: "Candidate match",
  inlier: "Verified match",
  control: "Selected control point",
  rejected: "Rejected",
};

const STATUS_ORDER: DisplayPoint["status"][] = [
  "rejected",
  "candidate",
  "inlier",
  "control",
];

function visiblePoints(points: DisplayPoint[], showRejected: boolean) {
  return points
    .filter((p) => showRejected || p.status !== "rejected")
    .sort(
      (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status),
    );
}

function Viewport({
  title,
  role,
  points,
  selectedId,
  onSelect,
  imageUrl,
  reference = false,
}: {
  title: string;
  role: string;
  points: DisplayPoint[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  imageUrl?: string | null;
  reference?: boolean;
}) {
  const [imageError, setImageError] = useState(false);
  const showFallback = !imageUrl || imageError;

  return (
    <figure className={`evidence-viewport ${reference ? "reference" : "source"}`}>
      <header className="viewport-header">
        <span className="viewport-role">{role}</span>
        <strong>{title}</strong>
      </header>
      <div
        className={`viewport-canvas${showFallback ? " is-fallback" : ""}`}
        role="img"
        aria-label={`${role} correspondence points`}
      >
        {imageUrl && !imageError && (
          <img
            className="viewport-image"
            src={imageUrl}
            alt={`${role} — ${title}`}
            onError={() => setImageError(true)}
          />
        )}
        {points.map((point) => {
          const selected = selectedId === point.id;
          return (
            <button
              key={point.id}
              type="button"
              className={`evidence-point status-${point.status}${selected ? " is-selected" : ""}`}
              style={{
                left: `${reference ? point.rx : point.x}%`,
                top: `${reference ? point.ry : point.y}%`,
              }}
              aria-pressed={selected}
              aria-label={`${STATUS_LABEL[point.status]} ${point.id}`}
              onMouseEnter={() => onSelect(point.id)}
              onFocus={() => onSelect(point.id)}
              onClick={() => onSelect(selected ? null : point.id)}
            >
              <span className="evidence-point-label">{point.id.replace(/^(M|I|CP)-/, "")}</span>
            </button>
          );
        })}
      </div>
    </figure>
  );
}

export function CorrespondenceEvidence({
  sourceLabel,
  referenceLabel,
  sourceUrl,
  referenceUrl,
  points,
  showRejected,
}: CorrespondenceEvidenceProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const visible = useMemo(
    () => visiblePoints(points, showRejected),
    [points, showRejected],
  );
  const selected = visible.find((p) => p.id === selectedId) ?? null;

  const presentStatuses = useMemo(() => {
    const set = new Set(visible.map((p) => p.status));
    return (["candidate", "inlier", "control", "rejected"] as const).filter((s) =>
      set.has(s),
    );
  }, [visible]);

  const howToRead = useMemo(() => {
    const parts: string[] = [];
    parts.push(
      "Each pair of markers marks a location the algorithm believes corresponds between the source and reference images.",
    );
    if (presentStatuses.includes("inlier") || presentStatuses.includes("control")) {
      parts.push("Verified matches survived geometric consistency checks.");
    }
    if (presentStatuses.includes("control")) {
      parts.push(
        "Selected control points are the subset used for spatially balanced registration.",
      );
    }
    if (presentStatuses.includes("candidate") && !presentStatuses.includes("inlier")) {
      parts.push("Candidate matches have not yet been geometrically verified in this view.");
    }
    return parts.join(" ");
  }, [presentStatuses]);

  return (
    <section className="results-block correspondence-evidence" aria-labelledby="corr-evidence-title">
      <header className="results-block-header">
        <div>
          <h3 id="corr-evidence-title">Correspondence Evidence</h3>
          <p className="results-block-subtitle">
            Where the system found matching locations between the two images.
          </p>
        </div>
      </header>

      <p className="what-you-see">
        <span>What you&apos;re seeing</span>
        Lines and points connect locations identified as corresponding between the two images.
      </p>

      <div className="how-to-read">
        <b>How to read this</b>
        <p>{howToRead}</p>
      </div>

      {presentStatuses.length > 0 && (
        <div className="evidence-legend" aria-label="Correspondence legend">
          {presentStatuses.map((status) => (
            <span key={status} className={`legend-item status-${status}`}>
              <i />{" "}
              {status === "candidate"
                ? "Candidate matches"
                : status === "inlier"
                  ? "Verified matches"
                  : status === "control"
                    ? "Selected control points"
                    : "Rejected"}
            </span>
          ))}
        </div>
      )}

      <div className="evidence-viewports">
        <Viewport
          role="Source"
          title={sourceLabel}
          points={visible}
          selectedId={selectedId}
          onSelect={setSelectedId}
          imageUrl={sourceUrl}
        />
        <Viewport
          role="Reference"
          title={referenceLabel}
          points={visible}
          selectedId={selectedId}
          onSelect={setSelectedId}
          imageUrl={referenceUrl}
          reference
        />
      </div>

      <aside className="point-inspector" aria-live="polite">
        {selected ? (
          <>
            <b>{selected.id}</b>
            <dl>
              <div>
                <dt>State</dt>
                <dd>{STATUS_LABEL[selected.status]}</dd>
              </div>
              <div>
                <dt>Source coordinate</dt>
                <dd>{selected.sourcePixel}</dd>
              </div>
              <div>
                <dt>Reference coordinate</dt>
                <dd>{selected.referencePixel}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{selected.confidence}</dd>
              </div>
              <div>
                <dt>Geometric residual</dt>
                <dd>{selected.residual}</dd>
              </div>
              <div>
                <dt>Control-point membership</dt>
                <dd>{selected.status === "control" ? "Yes" : "No"}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p>Select a point in either image to highlight its pair and inspect backend values.</p>
        )}
      </aside>
    </section>
  );
}
