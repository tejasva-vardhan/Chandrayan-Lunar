import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { DisplayPoint } from "../../api/resultsView";
import { ContainedImageFrame } from "./ContainedImageFrame";

interface OverlayViewerProps {
  referenceUrl?: string | null;
  registeredUrl?: string | null;
  available?: boolean;
  note?: string | null;
  mode?: string | null;
  isLive?: boolean;
  /** Reference-space points (rx/ry) for the diagnostic crop. */
  points?: DisplayPoint[];
}

/**
 * Alignment diagnostic: reference crop under registered crop.
 * Container aspect follows the preview strip so portrait NAC windows are not
 * crushed into a landscape 4:3 letterbox.
 */
export function OverlayViewer({
  referenceUrl,
  registeredUrl,
  available = false,
  note,
  mode,
  isLive = false,
  points = [],
}: OverlayViewerProps) {
  const [opacity, setOpacity] = useState(55);
  const [refFailed, setRefFailed] = useState(false);
  const [regFailed, setRegFailed] = useState(false);
  const [refLoaded, setRefLoaded] = useState(false);
  const [regLoaded, setRegLoaded] = useState(false);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    setRefFailed(false);
    setRegFailed(false);
    setRefLoaded(false);
    setRegLoaded(false);
    setNatural(null);
  }, [referenceUrl, registeredUrl, available]);

  const urlsReady = Boolean(available && referenceUrl && registeredUrl);
  const loadFailed = refFailed || regFailed;
  const canShow = urlsReady && !loadFailed;
  const loading = urlsReady && !loadFailed && !(refLoaded && regLoaded);

  const plotPoints = useMemo(
    () =>
      points.filter(
        (p) =>
          p.inReferencePreview &&
          (p.status === "control" || p.status === "inlier"),
      ),
    [points],
  );

  const containerStyle: CSSProperties | undefined =
    natural && natural.w > 0 && natural.h > 0
      ? {
          aspectRatio: `${natural.w} / ${natural.h}`,
          maxHeight: natural.h >= natural.w ? "min(78vh, 920px)" : "min(62vh, 640px)",
        }
      : undefined;

  return (
    <div className="workspace-card overlay-viewer-card">
      <div className="card-header">
        <div className="card-header-left">
          <span className="card-dot" />
          <span className="card-title">ALIGNMENT DIAGNOSTIC</span>
        </div>
        {mode && (
          <span className={`chip ${canShow ? "chip-region" : ""}`}>
            {mode.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <p className="card-desc">
        {canShow
          ? mode === "diagnostic_crop"
            ? "AFTER (diagnostic preview): fade the warped source crop over the reference window. Verified/control points are drawn on the strip — not a full registered product."
            : "AFTER: fade registered source over reference. Opacity comparison of a genuine pipeline artifact."
          : isLive
            ? "Registered full-raster output / diagnostic crop unavailable for this run. No fake after-image is shown."
            : "No diagnostic overlay for the static fixture. Run a live registration to generate a bounded preview when available."}
      </p>

      <div
        className={`overlay-container${natural && natural.h > natural.w ? " is-portrait" : ""}${natural && natural.w > natural.h ? " is-landscape" : ""}`}
        style={containerStyle}
      >
        {canShow ? (
          <>
            {loading && (
              <div className="overlay-loading" role="status">
                Loading diagnostic crop…
              </div>
            )}
            <img
              key={`ref-${referenceUrl}`}
              src={referenceUrl!}
              alt="Before registration — reference diagnostic crop"
              className="overlay-base"
              onLoad={(e) => {
                const img = e.currentTarget;
                setRefLoaded(true);
                if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                  setNatural({ w: img.naturalWidth, h: img.naturalHeight });
                }
              }}
              onError={() => setRefFailed(true)}
            />
            <img
              key={`reg-${registeredUrl}`}
              src={registeredUrl!}
              alt="Alignment diagnostic — registered source crop"
              className="overlay-top"
              style={{ opacity: opacity / 100 }}
              onLoad={() => setRegLoaded(true)}
              onError={() => setRegFailed(true)}
            />
            {plotPoints.length > 0 && (
              <ContainedImageFrame
                className="overlay-points-frame"
                imageUrl={referenceUrl!}
                onImageError={() => undefined}
              >
                {plotPoints.map((point) => (
                  <span
                    key={point.id}
                    className={`evidence-point status-${point.status} overlay-point`}
                    style={{ left: `${point.rx}%`, top: `${point.ry}%` }}
                    title={`${point.id} · (${point.referencePixel})`}
                  >
                    <span className="evidence-point-label" style={{ opacity: 1 }}>
                      {point.id.replace(/^(M|I|CP)-/, "")}
                    </span>
                  </span>
                ))}
              </ContainedImageFrame>
            )}
          </>
        ) : (
          <div className="overlay-empty" role="status">
            <p>
              {loadFailed
                ? "Diagnostic images failed to load"
                : "Diagnostic artifact not available"}
            </p>
            <span>
              {loadFailed
                ? "The preview URLs returned an error. Re-run registration with the API still running."
                : note ||
                  "Full-strip warp may be blocked by the output-size safety limit. A bounded diagnostic crop is shown only when the backend provides one."}
            </span>
          </div>
        )}
      </div>

      {canShow && plotPoints.length > 0 && (
        <p className="compare-hint">
          Showing {plotPoints.length} verified/control point(s) on the reference strip
          (crop-aligned).
        </p>
      )}

      <div className="overlay-controls">
        <span className="control-label">BEFORE / REFERENCE</span>
        <input
          type="range"
          min="0"
          max="100"
          value={opacity}
          disabled={!canShow}
          onChange={(e) => setOpacity(Number(e.target.value))}
          className="opacity-slider"
          aria-label="Overlay Opacity"
        />
        <span className="control-label">REGISTERED</span>
      </div>

      <div className="opacity-readout">
        {canShow
          ? `Registered crop opacity: ${opacity}% · drag toward BEFORE / REFERENCE to compare`
          : "Slider inactive until a diagnostic preview exists"}
      </div>
      {canShow && note && <p className="overlay-note">{note}</p>}
    </div>
  );
}
