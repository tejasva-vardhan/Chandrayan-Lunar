import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import type { DisplayPoint } from "../../api/resultsView";

type CorrespondenceEvidenceProps = {
  sourceLabel: string;
  referenceLabel: string;
  sourceUrl?: string | null;
  referenceUrl?: string | null;
  points: DisplayPoint[];
  showRejected: boolean;
  previewNote?: string | null;
};

const STATUS_LABEL: Record<DisplayPoint["status"], string> = {
  candidate: "Candidate",
  inlier: "Verified",
  control: "Verified",
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

function acceptancePath(point: DisplayPoint): string[] {
  if (point.status === "rejected") {
    return [
      "Candidate match",
      "Geometric verification",
      "Rejected during geometric verification",
    ];
  }
  if (point.status === "candidate") {
    return ["Candidate match", "Awaiting / not verified in this listing"];
  }
  if (point.status === "control") {
    return [
      "Candidate match",
      "Geometric verification",
      "Verified",
      "Selected for registration: Yes",
    ];
  }
  return [
    "Candidate match",
    "Geometric verification",
    "Verified",
    "Selected for registration: No",
  ];
}

function Viewport({
  title,
  role,
  points,
  selectedId,
  onSelect,
  imageUrl,
  reference = false,
  transform,
  onWheel,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: {
  title: string;
  role: string;
  points: DisplayPoint[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  imageUrl?: string | null;
  reference?: boolean;
  transform: string;
  onWheel: (e: WheelEvent) => void;
  onPointerDown: (e: PointerEvent) => void;
  onPointerMove: (e: PointerEvent) => void;
  onPointerUp: () => void;
}) {
  const [imageError, setImageError] = useState(false);
  useEffect(() => {
    setImageError(false);
  }, [imageUrl]);
  const showImage = Boolean(imageUrl) && !imageError;

  return (
    <figure className={`evidence-viewport ${reference ? "reference" : "source"}`}>
      <header className="viewport-header">
        <span className="viewport-role">{role}</span>
        <strong>{title}</strong>
      </header>
      <div
        className={`viewport-canvas${showImage ? "" : " is-empty"}`}
        role="img"
        aria-label={`${role} correspondence points`}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {showImage ? (
          <img
            className="viewport-image compare-layer"
            src={imageUrl!}
            alt={`${role} — ${title}`}
            style={{ transform }}
            onError={() => setImageError(true)}
            draggable={false}
          />
        ) : (
          <div className="viewport-missing">
            <b>Image preview unavailable</b>
            <span>Points use backend coordinates only — not a lunar image substitute.</span>
          </div>
        )}
        <div className="point-layer" style={{ transform }}>
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
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(selected ? null : point.id);
                }}
              >
                <span className="evidence-point-label">
                  {point.id.replace(/^(M|I|CP)-/, "")}
                </span>
              </button>
            );
          })}
        </div>
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
  previewNote,
}: CorrespondenceEvidenceProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

  useEffect(() => {
    setScale(1);
    setPan({ x: 0, y: 0 });
    setSelectedId(null);
  }, [sourceUrl, referenceUrl, points]);

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

  const hasAnyPreview = Boolean(sourceUrl || referenceUrl);

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    setScale((s) => Math.min(6, Math.max(1, s * (e.deltaY < 0 ? 1.12 : 0.9))));
  }

  function onPointerDown(e: PointerEvent) {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.px + (e.clientX - dragRef.current.x),
      y: dragRef.current.py + (e.clientY - dragRef.current.y),
    });
  }

  function onPointerUp() {
    dragRef.current = null;
  }

  const transform = `translate(${pan.x}px, ${pan.y}px) scale(${scale})`;

  return (
    <section
      className="results-block correspondence-evidence"
      id="correspondence"
      aria-labelledby="corr-evidence-title"
    >
      <header className="results-block-header">
        <div>
          <h3 id="corr-evidence-title">Correspondence Evidence</h3>
          <p className="results-block-subtitle">
            Actual correspondences from this run — same match ID on both images.
          </p>
        </div>
      </header>

      <p className="what-you-see">
        <span>What you&apos;re seeing</span>
        SOURCE ({sourceLabel}) versus REFERENCE ({referenceLabel}). Markers share the same match
        ID. Drawing a point does not by itself prove correctness — status comes from geometric
        verification.
      </p>

      {!hasAnyPreview && (
        <div className="image-unavailable" role="status">
          <b>Image evidence unavailable for this run</b>
          <span>
            {previewNote ||
              "Pipeline preview URLs were not provided. Correspondence coordinates below are still from the result object."}
          </span>
        </div>
      )}

      {presentStatuses.length > 0 && (
        <div className="evidence-legend" aria-label="Correspondence legend">
          {presentStatuses.map((status) => (
            <span key={status} className={`legend-item status-${status}`}>
              <i />{" "}
              {status === "candidate"
                ? "Candidate correspondences"
                : status === "inlier"
                  ? "Verified correspondences"
                  : status === "control"
                    ? "Selected control points"
                    : "Rejected"}
            </span>
          ))}
        </div>
      )}

      <div className="compare-controls">
        <button type="button" onClick={() => { setScale(1); setPan({ x: 0, y: 0 }); }}>
          Reset synchronized view
        </button>
      </div>

      <div className="evidence-viewports">
        <Viewport
          role="SOURCE · Chandrayaan-2 OHRC context"
          title={sourceLabel}
          points={visible}
          selectedId={selectedId}
          onSelect={setSelectedId}
          imageUrl={sourceUrl}
          transform={transform}
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        />
        <Viewport
          role="REFERENCE · LRO NAC context"
          title={referenceLabel}
          points={visible}
          selectedId={selectedId}
          onSelect={setSelectedId}
          imageUrl={referenceUrl}
          reference
          transform={transform}
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        />
      </div>

      <aside className="point-inspector" aria-live="polite">
        {selected ? (
          <>
            <b>Match {selected.id}</b>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{STATUS_LABEL[selected.status]}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>({selected.sourcePixel})</dd>
              </div>
              <div>
                <dt>Reference</dt>
                <dd>({selected.referencePixel})</dd>
              </div>
              <div>
                <dt>Selected control point</dt>
                <dd>{selected.status === "control" ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt>Residual</dt>
                <dd>{selected.residual}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{selected.confidence}</dd>
              </div>
            </dl>
            <div className="acceptance-path">
              <b>Why was this match accepted?</b>
              <ol>
                {acceptancePath(selected).map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          </>
        ) : (
          <p>Select a correspondence to inspect backend coordinates, residual, and acceptance path.</p>
        )}
      </aside>
    </section>
  );
}
