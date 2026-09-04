import React from "react";
import type { DisplayPoint } from "../../api/resultsView";

type CorrespondenceMapProps = {
  sourceLabel: string;
  sourceUrl?: string;
  referenceLabel: string;
  referenceUrl?: string;
  points: DisplayPoint[];
  showRejected: boolean;
  rawMatches: number;
  verified: number;
  rejected: number;
  inlierRatio: string;
  onHoverPoint?: (index: number | null) => void;
};

const STATUS_ORDER: DisplayPoint["status"][] = [
  "rejected",
  "candidate",
  "inlier",
  "control",
];

function panelPoints(points: DisplayPoint[], showRejected: boolean) {
  return points
    .filter((p) => showRejected || p.status !== "rejected")
    .sort(
      (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status),
    );
}

function DensityHeatmap({
  title,
  subtitle,
  points,
  reference = false,
  showRejected,
  imageUrl,
  onHoverPoint,
  hoveredIndex,
}: {
  title: string;
  subtitle: string;
  points: DisplayPoint[];
  reference?: boolean;
  showRejected: boolean;
  imageUrl?: string;
  onHoverPoint?: (index: number | null) => void;
  hoveredIndex?: number | null;
}) {
  const visible = panelPoints(points, showRejected);
  const [imageError, setImageError] = React.useState(false);
  const showRadar = !imageUrl || imageError;

  return (
    <figure className={`raster heatmap-panel ${reference ? "reference" : "source"}`}>
      {imageUrl && !imageError && (
        <img 
          src={imageUrl} 
          alt={title} 
          onError={() => setImageError(true)}
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }}
        />
      )}
      {showRadar && (
        <>
          <div className="heatmap-grid" aria-hidden="true" />
          <div className="heatmap-glow" aria-hidden="true" />
        </>
      )}
      {visible.map((point, index) => (
        <i
          key={`${point.status}-${index}`}
          className={`raster-point map-point status-${point.status} ${index === hoveredIndex ? "glowing" : ""}`}
          style={{
            left: `${reference ? point.rx : point.x}%`,
            top: `${reference ? point.ry : point.y}%`,
          }}
          onMouseEnter={() => onHoverPoint?.(index)}
          onMouseLeave={() => onHoverPoint?.(null)}
          title={`${point.status.toUpperCase()} · residual ${point.residual}`}
        />
      ))}
      <figcaption>
        {title}
        <span>{subtitle}</span>
      </figcaption>
    </figure>
  );
}

export function CorrespondenceMap({
  sourceLabel,
  sourceUrl,
  referenceLabel,
  referenceUrl,
  points,
  showRejected,
  rawMatches,
  verified,
  rejected,
  inlierRatio,
  onHoverPoint,
}: CorrespondenceMapProps) {
  const kept = points.filter((p) => p.status === "inlier" || p.status === "control").length;
  const shownRejected = showRejected
    ? points.filter((p) => p.status === "rejected").length
    : 0;

  const [hoveredIndex, setHoveredIndex] = React.useState<number | null>(null);

  const handleHover = React.useCallback((idx: number | null) => {
    setHoveredIndex(idx);
    onHoverPoint?.(idx);
  }, [onHoverPoint]);

  return (
    <div className="correspondence-map">
      <div className="mapping-story">
        <div className="story-step">
          <span className="story-num">1</span>
          <div>
            <b>Detect & match</b>
            <p>
              SIFT finds similar local features in both images →{" "}
              <strong>{rawMatches}</strong> candidate pairs.
            </p>
          </div>
        </div>
        <div className="story-step">
          <span className="story-num">2</span>
          <div>
            <b>Geometric verify</b>
            <p>
              RANSAC keeps only pairs that agree on one projective transform →{" "}
              <strong>{verified}</strong> inliers ({inlierRatio}).
            </p>
          </div>
        </div>
        <div className="story-step">
          <span className="story-num">3</span>
          <div>
            <b>Map & register</b>
            <p>
              Surviving points become control points for the transform. Rejected
              candidates (<strong>{rejected}</strong>) stay for inspection only.
            </p>
          </div>
        </div>
      </div>

      <div className="heatmap-legend" aria-label="Correspondence legend">
        <span className="legend-item status-candidate">
          <i /> Candidates
        </span>
        <span className="legend-item status-inlier">
          <i /> Verified inliers
        </span>
        <span className="legend-item status-control">
          <i /> Control points
        </span>
        <span className="legend-item status-rejected">
          <i /> Rejected
        </span>
      </div>

      <div className="evidence-grid heatmap-grid-layout">
        <DensityHeatmap
          title={sourceLabel}
          subtitle="Source feature locations"
          points={points}
          showRejected={showRejected}
          imageUrl={sourceUrl}
          onHoverPoint={handleHover}
          hoveredIndex={hoveredIndex}
        />
        <div className="correspondence-rail mapping-rail" aria-label="How mapping connects images">
          <p>HOW WE MAP</p>
          <ol>
            <li>Feature match</li>
            <li>Geometry filter</li>
            <li>Shared transform</li>
          </ol>
          <div className="rail-stats">
            <b>{kept}</b>
            <span>kept for mapping</span>
            {showRejected && (
              <>
                <b>{shownRejected}</b>
                <span>rejected shown</span>
              </>
            )}
          </div>
        </div>
        <DensityHeatmap
          title={referenceLabel}
          subtitle="Reference feature locations"
          points={points}
          reference
          showRejected={showRejected}
          imageUrl={referenceUrl}
          onHoverPoint={handleHover}
          hoveredIndex={hoveredIndex}
        />
      </div>

      <p className="heatmap-caption">
        Dot positions are normalized image coordinates from the live API result.
        Brighter / larger markers are verified or control points; dim markers are
        rejected or raw candidates. This is a correspondence map, not a thermal
        sensor heatmap.
      </p>
    </div>
  );
}
