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
          <span className="card-title">REGISTRATION OVERLAY EXPLORER</span>
        </div>
        {mode && (
          <span className={`chip ${canShow ? "chip-region" : ""}`}>
            {mode.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <p className="card-desc">
        {canShow
          ? "Fade the warped source crop over the reference window. Alignment is correct when craters and ridges stay locked as you drag the slider."
          : isLive
            ? "This live run has not produced a browser preview crop yet."
            : "Run a live registration in the pipeline above to generate a diagnostic overlay crop."}
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
              alt="Reference diagnostic crop"
              className="overlay-base"
              onLoad={() => setRefLoaded(true)}
              onError={() => setRefFailed(true)}
            />
            <img
              key={`reg-${registeredUrl}`}
              src={registeredUrl!}
              alt="Registered diagnostic crop"
              className="overlay-top"
              style={{ opacity: opacity / 100 }}
              onLoad={() => setRegLoaded(true)}
              onError={() => setRegFailed(true)}
            />
          </>
        ) : (
          <div className="overlay-empty" role="status">
            <p>{loadFailed ? "Preview images failed to load" : "No raster overlay available"}</p>
            <span>
              {loadFailed
                ? "The preview URLs returned an error. Re-run registration with the API still running, then open this tab again."
                : note ||
                  "Full-strip warp may be blocked by the output-size cap. Re-run registration to generate a diagnostic crop preview."}
            </span>
          </div>
        )}
      </div>

      <div className="overlay-controls">
        <span className="control-label">REFERENCE</span>
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
          ? `Registered crop opacity: ${opacity}% · drag toward REFERENCE to compare`
          : "Slider inactive until preview exists"}
      </div>
      {canShow && note && <p className="overlay-note">{note}</p>}
    </div>
  );
}
