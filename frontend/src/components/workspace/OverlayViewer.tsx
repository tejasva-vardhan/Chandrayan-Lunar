import React, { useState } from "react";

interface OverlayViewerProps {
  referenceUrl?: string;
  sourceUrl?: string;
}

export function OverlayViewer({ referenceUrl, sourceUrl }: OverlayViewerProps) {
  const [opacity, setOpacity] = useState(50);

  // Fallback placeholder images if backend hasn't provided real ones yet
  const defaultRef = "data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Crect width='100%25' height='100%25' fill='%230f172a'/%3E%3Cpath d='M0 0l800 600M800 0L0 600' stroke='%23334155' stroke-width='2'/%3E%3Ctext x='400' y='300' fill='%2364748b' font-family='monospace' font-size='24' text-anchor='middle'%3EREFERENCE BASEMAP%3C/text%3E%3C/svg%3E";
  const defaultSrc = "data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Crect width='100%25' height='100%25' fill='transparent'/%3E%3Ccircle cx='400' cy='300' r='200' stroke='%2338bdf8' stroke-width='4' fill='rgba(56,189,248,0.1)'/%3E%3Ctext x='400' y='360' fill='%2338bdf8' font-family='monospace' font-size='24' text-anchor='middle'%3EREGISTERED SOURCE%3C/text%3E%3C/svg%3E";

  const refSrc = referenceUrl || defaultRef;
  const overlaySrc = sourceUrl || defaultSrc;

  return (
    <div className="workspace-card overlay-viewer-card">
      <div className="card-header">
        <div className="card-header-left">
          <span className="card-dot" />
          <span className="card-title">REGISTRATION OVERLAY EXPLORER</span>
        </div>
      </div>
      
      <p className="card-desc">
        Visually verify geometric alignment by fading the warped source image over the reference basemap.
      </p>

      <div className="overlay-container">
        <img src={refSrc} alt="Reference Base" className="overlay-base" />
        <img 
          src={overlaySrc} 
          alt="Registered Source" 
          className="overlay-top" 
          style={{ opacity: opacity / 100 }} 
        />
      </div>

      <div className="overlay-controls">
        <span className="control-label">REFERENCE</span>
        <input 
          type="range" 
          min="0" 
          max="100" 
          value={opacity} 
          onChange={(e) => setOpacity(Number(e.target.value))}
          className="opacity-slider"
          aria-label="Overlay Opacity"
        />
        <span className="control-label">SOURCE</span>
      </div>
      
      <div className="opacity-readout">
        Source Opacity: {opacity}%
      </div>
    </div>
  );
}
