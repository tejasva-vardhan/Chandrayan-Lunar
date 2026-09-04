"""Write browser-safe diagnostic preview PNGs for the registration overlay UI.

Uses the existing EXP-000 diagnostic crop policy when a full registered raster
is unavailable (registration_output_too_large). This is a viewing aid, not a
claim that the full strip was warped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.ingestion.windows import read_product_window
from src.io.exp000.diagnostic import diagnostic_crop_window, warp_diagnostic_crop
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult

PREVIEW_REFERENCE_NAME = "preview_reference.png"
PREVIEW_REGISTERED_NAME = "preview_registered.png"
_MAX_DISPLAY_SIDE = 1280
_DIAGNOSTIC_NOTE = (
    "Diagnostic crop preview: full-raster warp was blocked by the existing "
    "output-size cap. Overlay shows a control-point–covering window only — "
    "not a complete registered product."
)
_FULL_NOTE = "Preview derived from the registered source artifact."
_UNAVAILABLE_NOTE = (
    "Overlay preview unavailable: missing raster handles, transform, or "
    "control points required to build a diagnostic crop."
)


def ensure_job_previews(
    pair: RegistrationPair,
    result: RegistrationResult,
    output_dir: Path,
) -> dict[str, Any]:
    """Create or reuse preview PNGs under *output_dir*.

    Returns keys: available, mode, note, reference_path, registered_path.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = output_dir / PREVIEW_REFERENCE_NAME
    registered_path = output_dir / PREVIEW_REGISTERED_NAME
    source_path = output_dir / "preview_source.png"

    if reference_path.is_file() and registered_path.is_file():
        mode = (
            "full_registered"
            if result.registered_source_uri
            else "diagnostic_crop"
        )
        return {
            "available": True,
            "mode": mode,
            "note": _FULL_NOTE if mode == "full_registered" else _DIAGNOSTIC_NOTE,
            "reference_path": reference_path,
            "registered_path": registered_path,
            "source_path": source_path if source_path.is_file() else None,
        }

    source_uri = pair.source.raster_uri
    reference_uri = pair.reference.raster_uri
    if not source_uri or not reference_uri:
        return {
            "available": False,
            "mode": "unavailable",
            "note": _UNAVAILABLE_NOTE,
            "reference_path": None,
            "registered_path": None,
        }

    dims = pair.reference.dimensions
    if dims is None:
        return {
            "available": False,
            "mode": "unavailable",
            "note": _UNAVAILABLE_NOTE,
            "reference_path": None,
            "registered_path": None,
        }

    transform = result.transformation
    matrix = None
    if transform is not None:
        raw = transform.parameters.get("matrix")
        if raw is not None:
            matrix = np.asarray(raw, dtype=float)

    if matrix is None or len(result.control_points) < 1:
        return {
            "available": False,
            "mode": "unavailable",
            "note": _UNAVAILABLE_NOTE,
            "reference_path": None,
            "registered_path": None,
        }

    window = diagnostic_crop_window(
        int(dims.height_px),
        int(dims.width_px),
        list(result.control_points),
    )
    reference_crop = read_product_window(
        reference_uri, window.row, window.col, window.height, window.width
    )
    registered_crop = warp_diagnostic_crop(source_uri, matrix, window)

    source_dims = pair.source.dimensions
    source_path_out: Path | None = None
    if source_dims is not None:
        # Place a source-space crop using source_xy as the windowing coordinates.
        source_pts = [
            ControlPoint(source_xy=cp.source_xy, reference_xy=cp.source_xy)
            for cp in result.control_points
        ]
        source_window = diagnostic_crop_window(
            int(source_dims.height_px),
            int(source_dims.width_px),
            source_pts,
        )
        source_crop = read_product_window(
            source_uri,
            source_window.row,
            source_window.col,
            source_window.height,
            source_window.width,
        )
        _write_display_png(source_path, source_crop)
        source_path_out = source_path

    _write_display_png(reference_path, reference_crop)
    _write_display_png(registered_path, registered_crop)

    return {
        "available": True,
        "mode": "diagnostic_crop",
        "note": _DIAGNOSTIC_NOTE,
        "reference_path": reference_path,
        "registered_path": registered_path,
        "source_path": source_path_out,
    }


def _write_display_png(path: Path, array: np.ndarray) -> None:
    display = _to_uint8_display(array)
    if max(display.shape[:2]) > _MAX_DISPLAY_SIDE:
        scale = _MAX_DISPLAY_SIDE / float(max(display.shape[:2]))
        width = max(1, int(round(display.shape[1] * scale)))
        height = max(1, int(round(display.shape[0] * scale)))
        display = cv2.resize(display, (width, height), interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(path), display):
        raise RuntimeError(f"failed to write preview PNG: {path}")


def _to_uint8_display(array: np.ndarray) -> np.ndarray:
    data = np.asarray(array, dtype=np.float64)
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return np.zeros(data.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [2.0, 98.0])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = float(np.min(finite))
        hi = float(np.max(finite))
    if hi <= lo:
        return np.zeros(data.shape, dtype=np.uint8)
    scaled = (np.clip(data, lo, hi) - lo) / (hi - lo)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(np.round(scaled * 255.0), 0, 255).astype(np.uint8)
