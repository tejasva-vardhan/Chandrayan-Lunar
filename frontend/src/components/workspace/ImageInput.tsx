import React from "react";

export type ImageState = "empty" | "selected" | "loading" | "invalid";

interface ImageInputProps {
  label: string;
  description: string;
  state: ImageState;
  filename?: string;
  dimensions?: string;
  sensor?: string;
  onSelect: () => void;
  onClear: () => void;
}

export function ImageInput({
  label,
  description,
  state,
  filename,
  dimensions,
  sensor,
  onSelect,
  onClear,
}: ImageInputProps) {
  return (
    <div className={`workspace-card image-input-card state-${state}`}>
      <div className="card-header">
        <div className="card-header-left">
          <span className="card-dot" />
          <span className="card-title">{label}</span>
        </div>
        {sensor && <span className={`chip chip-${sensor.toLowerCase()}`}>{sensor}</span>}
      </div>
      
      <p className="card-desc">{description}</p>

      <div className="input-dropzone">
        {state === "empty" && (
          <div className="empty-state">
            <span className="state-icon">⏏</span>
            <p>No product selected</p>
            <button className="secondary-button" onClick={onSelect}>Select Product</button>
          </div>
        )}

        {state === "loading" && (
          <div className="loading-state">
            <span className="spinner" />
            <p>Ingesting product...</p>
          </div>
        )}

        {state === "invalid" && (
          <div className="invalid-state">
            <span className="state-icon warning-icon">!</span>
            <p>Product format unrecognized or corrupted.</p>
            <button className="secondary-button" onClick={onClear}>Clear & Retry</button>
          </div>
        )}

        {state === "selected" && (
          <div className="selected-state">
            <div className="selected-meta">
              <span className="file-icon">📄</span>
              <div className="file-info">
                <span className="filename">{filename}</span>
                <span className="dimensions">{dimensions}</span>
              </div>
            </div>
            <button className="icon-button" onClick={onClear} title="Remove image" aria-label="Remove image">
              ×
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
