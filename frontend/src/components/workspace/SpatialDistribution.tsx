import { useMemo, useState, useEffect } from "react";
import type { DisplayPoint } from "../../api/resultsView";
import { ContainedImageFrame } from "./ContainedImageFrame";

const GRID = 8;

type SpatialDistributionProps = {
  points: DisplayPoint[];
  coverage: string;
  sourceLabel: string;
  referenceLabel: string;
  sourceUrl?: string | null;
  referenceUrl?: string | null;
};

/** Presentational 8×8 occupancy from existing point positions — not a scientific coverage algorithm. */
function buildOccupancy(points: DisplayPoint[], axis: "source" | "reference"): number[] {
  const cells = Array.from({ length: GRID * GRID }, () => 0);
  for (const point of points) {
    const inCrop = axis === "source" ? point.inSourcePreview : point.inReferencePreview;
    if (!inCrop) continue;
    const px = axis === "source" ? point.x : point.rx;
    const py = axis === "source" ? point.y : point.ry;
    const col = Math.min(GRID - 1, Math.max(0, Math.floor((px / 100) * GRID)));
    const row = Math.min(GRID - 1, Math.max(0, Math.floor((py / 100) * GRID)));
    cells[row * GRID + col] += 1;
  }
  return cells;
}

function OccupancyMap({
  label,
  cells,
}: {
  label: string;
  cells: number[];
}) {
  const max = Math.max(1, ...cells);
  return (
    <div className="occupancy-map">
      <span className="occupancy-map-label">{label}</span>
      <p className="occupancy-map-note">
        8×8 occupancy map of selected control points — not an accuracy, error, or confidence heatmap.
        Does not prove uniformity.
      </p>
      <div
        className="occupancy-grid"
        role="img"
        aria-label={`${label} 8 by 8 control-point occupancy`}
      >
        {cells.map((count, i) => (
          <div
            key={i}
            className={`occupancy-cell${count > 0 ? " is-occupied" : ""}`}
            style={
              count > 0
                ? { opacity: 0.35 + (0.65 * count) / max }
                : undefined
            }
            title={count > 0 ? `${count} point(s)` : "Empty"}
          />
        ))}
      </div>
    </div>
  );
}

function ControlPointViewport({
  role,
  title,
  points,
  imageUrl,
  reference = false,
}: {
  role: string;
  title: string;
  points: DisplayPoint[];
  imageUrl?: string | null;
  reference?: boolean;
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
        aria-label={`${role} selected control points`}
      >
        {showImage ? (
          <ContainedImageFrame
            imageUrl={imageUrl!}
            onImageError={() => setImageError(true)}
          >
            {points.map((point) => {
              const inCrop = reference ? point.inReferencePreview : point.inSourcePreview;
              if (!inCrop) return null;
              return (
                <span
                  key={point.id}
                  className="evidence-point status-control spatial-cp"
                  style={{
                    left: `${reference ? point.rx : point.x}%`,
                    top: `${reference ? point.ry : point.y}%`,
                  }}
                  title={`${point.id} · (${reference ? point.referencePixel : point.sourcePixel})`}
                >
                  <span className="evidence-point-label" style={{ opacity: 1 }}>
                    {point.id.replace(/^CP-/, "")}
                  </span>
                </span>
              );
            })}
          </ContainedImageFrame>
        ) : (
          <>
            <div className="viewport-missing">
              <b>Image preview unavailable</b>
              <span>Control-point positions use backend coordinates only.</span>
            </div>
            {points.map((point) => (
              <span
                key={point.id}
                className="evidence-point status-control spatial-cp"
                style={{
                  left: `${reference ? point.rx : point.x}%`,
                  top: `${reference ? point.ry : point.y}%`,
                }}
                title={`${point.id} · (${reference ? point.referencePixel : point.sourcePixel})`}
              >
                <span className="evidence-point-label" style={{ opacity: 1 }}>
                  {point.id.replace(/^CP-/, "")}
                </span>
              </span>
            ))}
          </>
        )}
      </div>
    </figure>
  );
}

export function SpatialDistribution({
  points,
  coverage,
  sourceLabel,
  referenceLabel,
  sourceUrl,
  referenceUrl,
}: SpatialDistributionProps) {
  const controlPoints = useMemo(
    () => points.filter((p) => p.status === "control"),
    [points],
  );
  const sourceCells = useMemo(
    () => buildOccupancy(controlPoints, "source"),
    [controlPoints],
  );
  const referenceCells = useMemo(
    () => buildOccupancy(controlPoints, "reference"),
    [controlPoints],
  );
  const occupiedSource = sourceCells.filter((c) => c > 0).length;
  const occupiedReference = referenceCells.filter((c) => c > 0).length;

  return (
    <section
      className="results-block spatial-distribution"
      id="spatial"
      aria-labelledby="spatial-dist-title"
    >
      <header className="results-block-header">
        <div>
          <h3 id="spatial-dist-title">Spatial Coverage</h3>
          <p className="results-block-subtitle">
            Shows the distribution of selected control points across the current image extent.
          </p>
        </div>
      </header>

      <p className="what-you-see">
        <span>What you&apos;re seeing</span>
        Each column pairs the preview image with its 8×8 occupancy map so you can relate cell
        occupancy to the imagery. This is spatial coverage / occupancy — not an accuracy heatmap
        and not proof of uniform distribution.
      </p>

      {controlPoints.length === 0 ? (
        <p className="results-empty">
          No selected control points are available in this result to plot.
        </p>
      ) : (
        <div className="spatial-paired-columns">
          <div className="spatial-pair-column">
            <ControlPointViewport
              role="SOURCE · control points"
              title={sourceLabel}
              points={controlPoints}
              imageUrl={sourceUrl}
            />
            <OccupancyMap label="Source occupancy 8×8" cells={sourceCells} />
          </div>
          <div className="spatial-pair-column">
            <ControlPointViewport
              role="REFERENCE · control points"
              title={referenceLabel}
              points={controlPoints}
              imageUrl={referenceUrl}
              reference
            />
            <OccupancyMap label="Reference occupancy 8×8" cells={referenceCells} />
          </div>
        </div>
      )}

      <div className="coverage-readout">
        <div>
          <b>
            {coverage === "—"
              ? "Spatial coverage: unavailable"
              : `${coverage} spatial coverage according to the current coverage metric.`}
          </b>
          <span>
            Pipeline coverage metric for selected control points on this run — not a claim of
            uniformity.
          </span>
        </div>
        <div className="occupancy-counts" aria-label="Occupied cells">
          <span>Source cells occupied: {occupiedSource}/{GRID * GRID}</span>
          <span>Reference cells occupied: {occupiedReference}/{GRID * GRID}</span>
          <span>Control points plotted: {controlPoints.length}</span>
        </div>
      </div>
    </section>
  );
}
