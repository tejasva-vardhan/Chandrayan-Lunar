import React, { useRef } from "react";
import type { ProductSummary } from "../../api/types";

export type ImageState = "empty" | "selected" | "loading" | "invalid";

export type SelectedProduct = {
  productId: string;
  filename: string;
  origin: "upload" | "data_root" | "path";
  bytes?: number;
  instrumentHint?: string | null;
  detail?: string;
};

interface ImageInputProps {
  label: string;
  description: string;
  state: ImageState;
  selected: SelectedProduct | null;
  errorMessage?: string | null;
  catalog: ProductSummary[];
  catalogMessage?: string | null;
  catalogConfigured: boolean;
  disabled?: boolean;
  onUpload: (file: File) => void;
  onSelectExisting: (product: ProductSummary) => void;
  onClear: () => void;
}

const ACCEPT = ".img,.IMG,.zip,.ZIP,.xml,.XML";

export function ImageInput({
  label,
  description,
  state,
  selected,
  errorMessage,
  catalog,
  catalogMessage,
  catalogConfigured,
  disabled = false,
  onUpload,
  onSelectExisting,
  onClear,
}: ImageInputProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const sensor = selected?.instrumentHint ?? undefined;

  return (
    <div className={`workspace-card image-input-card state-${state}`}>
      <div className="card-header">
        <div className="card-header-left">
          <span className="card-dot" />
          <span className="card-title">{label}</span>
        </div>
        {sensor && sensor !== "UNKNOWN" && (
          <span className={`chip chip-${sensor.toLowerCase().replace("_", "-")}`}>{sensor}</span>
        )}
      </div>

      <p className="card-desc">{description}</p>

      <div className="input-dropzone">
        {state === "empty" && (
          <div className="empty-state">
            <span className="state-icon">⏏</span>
            <p>No product selected</p>
            <div className="input-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={disabled}
                onClick={() => fileRef.current?.click()}
              >
                Upload Image
              </button>
              <label className="select-existing">
                <span className="secondary-button select-existing-label">Select Existing</span>
                <select
                  aria-label={`Select existing ${label}`}
                  disabled={disabled || !catalogConfigured || catalog.length === 0}
                  defaultValue=""
                  onChange={(e) => {
                    const id = e.target.value;
                    const product = catalog.find((item) => item.product_id === id);
                    if (product) onSelectExisting(product);
                    e.target.value = "";
                  }}
                >
                  <option value="" disabled>
                    {catalogConfigured
                      ? catalog.length
                        ? "Choose catalog product…"
                        : "No catalog products found"
                      : "Data root not configured"}
                  </option>
                  {catalog.map((item) => (
                    <option key={item.product_id} value={item.product_id}>
                      {(item.logical_id || item.filename || item.product_id) +
                        (item.instrument_hint ? ` · ${item.instrument_hint}` : "")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="format-hint">
              Accepted: OHRC PDS4 (.zip / .xml) · LROC PDS3 (.IMG). PNG/JPEG are not supported.
            </p>
            {catalogMessage && <p className="catalog-hint">{catalogMessage}</p>}
          </div>
        )}

        {state === "loading" && (
          <div className="loading-state">
            <span className="spinner" />
            <p>Uploading product…</p>
          </div>
        )}

        {state === "invalid" && (
          <div className="invalid-state">
            <span className="state-icon warning-icon">!</span>
            <p>{errorMessage || "Product format unrecognized or corrupted."}</p>
            <button type="button" className="secondary-button" onClick={onClear}>
              Clear & Retry
            </button>
          </div>
        )}

        {state === "selected" && selected && (
          <div className="selected-state">
            <div className="selected-meta">
              <span className="file-icon">📄</span>
              <div className="file-info">
                <span className="filename">{selected.filename}</span>
                <span className="dimensions">
                  {selected.origin === "upload"
                    ? `Upload${selected.bytes != null ? ` · ${(selected.bytes / (1024 * 1024)).toFixed(1)} MB` : ""}`
                    : selected.origin === "data_root"
                      ? "Catalog product · CHANDRAYAN_DATA_ROOT"
                      : "Local path product"}
                  {selected.detail ? ` · ${selected.detail}` : ""}
                </span>
              </div>
            </div>
            <div className="selected-actions">
              <button
                type="button"
                className="ghost-button replace-button"
                disabled={disabled}
                onClick={() => fileRef.current?.click()}
              >
                Replace
              </button>
              <button
                type="button"
                className="icon-button"
                onClick={onClear}
                title="Remove image"
                aria-label="Remove image"
                disabled={disabled}
              >
                ×
              </button>
            </div>
          </div>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept={ACCEPT}
        hidden
        disabled={disabled}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onUpload(file);
        }}
      />
    </div>
  );
}
