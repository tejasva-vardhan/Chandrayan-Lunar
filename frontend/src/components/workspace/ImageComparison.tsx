import { useEffect, useRef, useState, type PointerEvent, type WheelEvent } from "react";

export type ImageComparisonProps = {
  sourceLabel: string;
  referenceLabel: string;
  sourceProduct: string;
  referenceProduct: string;
  sourceDims: { width: number | null; height: number | null; gsd: string };
  referenceDims: { width: number | null; height: number | null };
  acquisitionTimeSource: string;
  acquisitionTimeReference: string;
  sourceUrl?: string | null;
  referenceUrl?: string | null;
  previewNote?: string | null;
};

function formatDims(width: number | null, height: number | null): string {
  if (width == null || height == null) return "dimensions unavailable";
  return `${width.toLocaleString()} × ${height.toLocaleString()} px`;
}

type CompareMode = "side-by-side" | "blink" | "opacity";

/**
 * Source vs reference image comparison using backend preview URLs only.
 * Does not invent imagery when previews are unavailable.
 */
export function ImageComparison({
  sourceLabel,
  referenceLabel,
  sourceProduct,
  referenceProduct,
  sourceDims,
  referenceDims,
  acquisitionTimeSource,
  acquisitionTimeReference,
  sourceUrl,
  referenceUrl,
  previewNote,
}: ImageComparisonProps) {
  const [mode, setMode] = useState<CompareMode>("side-by-side");
  const [opacity, setOpacity] = useState(50);
  const [blinkShowSource, setBlinkShowSource] = useState(true);
  const [sourceFailed, setSourceFailed] = useState(false);
  const [refFailed, setRefFailed] = useState(false);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoomEnabled, setZoomEnabled] = useState(false);
  const dragRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

  useEffect(() => {
    setSourceFailed(false);
    setRefFailed(false);
    setScale(1);
    setPan({ x: 0, y: 0 });
    setZoomEnabled(false);
  }, [sourceUrl, referenceUrl]);

  useEffect(() => {
    if (mode !== "blink") return;
    const id = window.setInterval(() => setBlinkShowSource((v) => !v), 700);
    return () => window.clearInterval(id);
  }, [mode]);

  const sourceReady = Boolean(sourceUrl) && !sourceFailed;
  const refReady = Boolean(referenceUrl) && !refFailed;
  const anyImage = sourceReady || refReady;
  const bothImages = sourceReady && refReady;

  function onWheel(e: WheelEvent) {
    if (!zoomEnabled) return;
    e.preventDefault();
    setScale((s) => Math.min(6, Math.max(1, s * (e.deltaY < 0 ? 1.12 : 0.9))));
  }

  function onPointerDown(e: PointerEvent) {
    if (!zoomEnabled) return;
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
    <section className="results-block image-comparison" aria-labelledby="image-compare-title">
      <header className="results-block-header">
        <div>
          <h3 id="image-compare-title">Image Comparison</h3>
          <p className="results-block-subtitle">
            What two images are being compared in this registration run.
          </p>
        </div>
      </header>

      <div className="input-pair-cards">
        <article className="input-pair-card">
          <span className="chip chip-ohrc">SOURCE</span>
          <strong>{sourceLabel}</strong>
          <span className="product-id">{sourceProduct}</span>
          <span className="dims-line">
            {formatDims(sourceDims.width, sourceDims.height)}
            {sourceDims.gsd ? ` — ${sourceDims.gsd}` : ""}
          </span>
          <span className="dims-line">Acquired: {acquisitionTimeSource}</span>
        </article>
        <article className="input-pair-card">
          <span className="chip chip-lro">REFERENCE</span>
          <strong>{referenceLabel}</strong>
          <span className="product-id">{referenceProduct}</span>
          <span className="dims-line">
            {formatDims(referenceDims.width, referenceDims.height)}
          </span>
          <span className="dims-line">Acquired: {acquisitionTimeReference}</span>
        </article>
      </div>

      {!anyImage ? (
        <div className="image-unavailable" role="status">
          <b>Image evidence unavailable for this run</b>
          <span>
            {previewNote ||
              "No source/reference preview artifacts were returned by the pipeline for this job. Point coordinates below still come from the live result when present."}
          </span>
        </div>
      ) : (
        <>
          <div className="compare-controls" role="toolbar" aria-label="Comparison controls">
            <button
              type="button"
              className={mode === "side-by-side" ? "active" : ""}
              onClick={() => setMode("side-by-side")}
            >
              Side-by-side
            </button>
            <button
              type="button"
              className={mode === "blink" ? "active" : ""}
              onClick={() => setMode("blink")}
              disabled={!bothImages}
            >
              Blink
            </button>
            <button
              type="button"
              className={mode === "opacity" ? "active" : ""}
              onClick={() => setMode("opacity")}
              disabled={!bothImages}
            >
              Opacity
            </button>
            <button
              type="button"
              className={zoomEnabled ? "active" : ""}
              aria-pressed={zoomEnabled}
              onClick={() => setZoomEnabled((v) => !v)}
            >
              {zoomEnabled ? "Scroll zoom: On" : "Enable scroll zoom"}
            </button>
            <button type="button" onClick={() => { setScale(1); setPan({ x: 0, y: 0 }); }}>
              Reset view
            </button>
            {mode === "opacity" && (
              <label className="compare-opacity">
                Opacity
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={opacity}
                  onChange={(e) => setOpacity(Number(e.target.value))}
                />
              </label>
            )}
          </div>

          {mode === "side-by-side" ? (
            <div className="evidence-viewports compare-viewports">
              <figure className="evidence-viewport source">
                <header className="viewport-header">
                  <span className="viewport-role">SOURCE</span>
                  <strong>{sourceLabel}</strong>
                </header>
                <div
                  className={`viewport-canvas compare-canvas${zoomEnabled ? " zoom-enabled" : ""}`}
                  onWheel={onWheel}
                  onPointerDown={onPointerDown}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                >
                  {sourceReady ? (
                    <img
                      className="viewport-image compare-layer"
                      src={sourceUrl!}
                      alt={`Source — ${sourceLabel}`}
                      style={{ transform }}
                      onError={() => setSourceFailed(true)}
                      draggable={false}
                    />
                  ) : (
                    <div className="viewport-missing">Source preview unavailable</div>
                  )}
                </div>
              </figure>
              <figure className="evidence-viewport reference">
                <header className="viewport-header">
                  <span className="viewport-role">REFERENCE</span>
                  <strong>{referenceLabel}</strong>
                </header>
                <div
                  className={`viewport-canvas compare-canvas${zoomEnabled ? " zoom-enabled" : ""}`}
                  onWheel={onWheel}
                  onPointerDown={onPointerDown}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                >
                  {refReady ? (
                    <img
                      className="viewport-image compare-layer"
                      src={referenceUrl!}
                      alt={`Reference — ${referenceLabel}`}
                      style={{ transform }}
                      onError={() => setRefFailed(true)}
                      draggable={false}
                    />
                  ) : (
                    <div className="viewport-missing">Reference preview unavailable</div>
                  )}
                </div>
              </figure>
            </div>
          ) : (
            <div className="compare-stack">
              <header className="viewport-header">
                <span className="viewport-role">
                  {mode === "blink"
                    ? blinkShowSource
                      ? "SOURCE"
                      : "REFERENCE"
                    : "OVERLAY"}
                </span>
                <strong>
                  {mode === "blink"
                    ? blinkShowSource
                      ? sourceLabel
                      : referenceLabel
                    : `${sourceLabel} ↔ ${referenceLabel}`}
                </strong>
              </header>
              <div
                className={`viewport-canvas compare-canvas compare-stack-canvas${zoomEnabled ? " zoom-enabled" : ""}`}
                onWheel={onWheel}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
              >
                {mode === "blink" ? (
                  <img
                    className="viewport-image compare-layer"
                    src={(blinkShowSource ? sourceUrl : referenceUrl)!}
                    alt={blinkShowSource ? sourceLabel : referenceLabel}
                    style={{ transform }}
                    draggable={false}
                  />
                ) : (
                  <>
                    <img
                      className="viewport-image compare-layer"
                      src={referenceUrl!}
                      alt={referenceLabel}
                      style={{ transform }}
                      draggable={false}
                    />
                    <img
                      className="viewport-image compare-layer"
                      src={sourceUrl!}
                      alt={sourceLabel}
                      style={{ transform, opacity: opacity / 100 }}
                      draggable={false}
                    />
                  </>
                )}
              </div>
            </div>
          )}
          <p className="compare-hint">
            {zoomEnabled
              ? "Synchronized zoom/pan · scroll to zoom · drag to pan."
              : "Page scroll is free until you enable scroll zoom."}{" "}
            This is an image comparison aid, not a registered overlay claim.
          </p>
        </>
      )}
    </section>
  );
}
