import { useMemo } from "react";
import type { DisplayPoint } from "../../api/resultsView";

const GRID = 8;

type SpatialDistributionProps = {
  points: DisplayPoint[];
  coverage: string;
};

/** Presentational 8×8 occupancy from existing point positions — not a scientific coverage algorithm. */
function buildOccupancy(points: DisplayPoint[], axis: "source" | "reference"): number[] {
  const cells = Array.from({ length: GRID * GRID }, () => 0);
  for (const point of points) {
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

export function SpatialDistribution({ points, coverage }: SpatialDistributionProps) {
  const useful = useMemo(
    () => points.filter((p) => p.status === "control" || p.status === "inlier"),
    [points],
  );
  const sourceCells = useMemo(() => buildOccupancy(useful, "source"), [useful]);
  const referenceCells = useMemo(() => buildOccupancy(useful, "reference"), [useful]);
  const occupiedSource = sourceCells.filter((c) => c > 0).length;
  const occupiedReference = referenceCells.filter((c) => c > 0).length;

  return (
    <section className="results-block spatial-distribution" aria-labelledby="spatial-dist-title">
      <header className="results-block-header">
        <div>
          <h3 id="spatial-dist-title">Spatial Distribution</h3>
          <p className="results-block-subtitle">
            Shows where the verified/control points are located across the image.
          </p>
          <p className="results-tech-label">8×8 control-point occupancy</p>
        </div>
      </header>

      <p className="what-you-see">
        <span>What you&apos;re seeing</span>
        This view shows whether selected control points are spread across the image rather than
        concentrated in one region. It is an occupancy map, not a registration-error heatmap.
      </p>

      {useful.length === 0 ? (
        <p className="results-empty">
          No verified or control-point coordinates are available to plot occupancy.
        </p>
      ) : (
        <div className="occupancy-row">
          <OccupancyMap label="Source occupancy" cells={sourceCells} />
          <OccupancyMap label="Reference occupancy" cells={referenceCells} />
        </div>
      )}

      <div className="coverage-readout">
        <div>
          <b>Spatial coverage: {coverage}</b>
          <span>Measures how much of the image area is represented by selected control points.</span>
        </div>
        <div className="occupancy-counts" aria-label="Occupied cells">
          <span>Source cells occupied: {occupiedSource}/{GRID * GRID}</span>
          <span>Reference cells occupied: {occupiedReference}/{GRID * GRID}</span>
        </div>
      </div>
    </section>
  );
}
