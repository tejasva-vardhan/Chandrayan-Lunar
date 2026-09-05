import React, { useEffect, useState } from "react";

interface OverlayViewerProps {
  referenceUrl?: string | null;
  registeredUrl?: string | null;
  available?: boolean;
  note?: string | null;
  mode?: string | null;
  isLive?: boolean;
}

export function OverlayViewer({
  referenceUrl,
  registeredUrl,
  available = false,
  note,
  mode,
  isLive = false,
}: OverlayViewerProps) {
  const [opacity, setOpacity] = useState(55);
  const [refFailed, setRefFailed] = useState(false);
  const [regFailed, setRegFailed] = useState(false);
  const [refLoaded, setRefLoaded] = useState(false);
  const [regLoaded, setRegLoaded] = useState(false);

  useEffect(() => {
    setRefFailed(false);
    setRegFailed(false);
    setRefLoaded(false);
    setRegLoaded(false);
  }, [referenceUrl, registeredUrl, available]);

  const urlsReady = Boolean(available && referenceUrl && registeredUrl);
  const loadFailed = refFailed || regFailed;
  const canShow = urlsReady && !loadFailed;
  const loading = urlsReady && !loadFailed && !(refLoaded && regLoaded);

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
            ? "AFTER (diagnostic preview): fade the warped source crop over the reference window. Labeled diagnostic/preview — not a full registered product."
            : "AFTER: fade registered source over reference. Opacity / blink-style comparison of a genuine pipeline artifact."
          : isLive
            ? "Registered full-raster output / diagnostic crop unavailable for this run. No fake after-image is shown."
            : "No diagnostic overlay for the static fixture. Run a live registration to generate a bounded preview when available."}
      </p>

      <div className="overlay-container">
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
              onLoad={() => setRefLoaded(true)}
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
