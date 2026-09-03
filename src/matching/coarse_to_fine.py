"""Coarse-to-fine tiled multi-scale SIFT. Candidate correspondence path.

This is not wired into frozen match(). Variant A of the PS-closing comparison
keeps match(); variant B calls run_coarse_to_fine_sift.

Coarse matches from the existing matching view are never dropped. Fine tiles
only add candidates. Downstream verify_matches is unchanged.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from src.matching.settings import CoarseToFineSettings, SiftSettings
from src.matching.shared import matching_view_scale, representation_id
from src.matching.sift_adapter import run_sift
from src.models.correspondence_set import Correspondence, CorrespondenceSet
from src.models.registration_pair import RegistrationPair
from src.representation._loader import load_strided_mask_window, load_strided_window
from src.representation._types import RepresentationResult
from src.representation.gradient import build_gradient_array
from src.representation.intensity import build_intensity_array
from src.representation.structural import build_structural_array
from src.verification import verify_matches
from src.verification.geometric_models import get_geometric_model
from src.verification.settings import unvalidated_software_defaults

MATCHER_ID = "sift_coarse_to_fine"
_INLIER = "inlier"
_HOMOGENEOUS_FLOOR = 1e-12


def run_coarse_to_fine_sift(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
    settings: SiftSettings | None = None,
    coarse_to_fine: CoarseToFineSettings | None = None,
    *,
    diagnostics: dict[str, Any] | None = None,
) -> CorrespondenceSet:
    """Return raw correspondences from coarse SIFT plus finer tiled SIFT."""

    sift_cfg = settings or SiftSettings()
    cfg = coarse_to_fine or CoarseToFineSettings()
    coarse = run_sift(pair, representation, settings=sift_cfg)
    _note(
        diagnostics,
        coarse_raw_matches=len(coarse.matches),
        source_coarse_stride=_stride(representation, "source"),
        reference_coarse_stride=_stride(representation, "reference"),
    )

    fine = _fine_matches(pair, representation, coarse, sift_cfg, cfg, diagnostics)
    added = _novel_matches(fine, list(coarse.matches), cfg.dedup_radius_px)
    union = [
        item.model_copy(update={"status": "raw", "residual": None})
        for item in (*coarse.matches, *added)
    ]
    _note(
        diagnostics,
        fine_raw_matches=len(fine),
        fine_matches_added=len(added),
        union_raw_matches=len(union),
    )
    return CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id=MATCHER_ID,
        matches=union,
        representation_id=representation_id(representation),
    )


def _fine_matches(
    pair: RegistrationPair,
    representation: RepresentationResult | None,
    coarse: CorrespondenceSet,
    sift_cfg: SiftSettings,
    cfg: CoarseToFineSettings,
    diagnostics: dict[str, Any] | None,
) -> list[Correspondence]:
    source_uri = pair.source.raster_uri
    reference_uri = pair.reference.raster_uri
    if source_uri is None or reference_uri is None:
        _note(diagnostics, fine_stage="skipped_no_raster_uri")
        return []
    if not source_uri.lower().endswith(".npy") or not reference_uri.lower().endswith(".npy"):
        _note(diagnostics, fine_stage="skipped_non_npy_raster")
        return []

    matrix, inliers = _coarse_prior(coarse, pair)
    _note(diagnostics, coarse_verified_inliers=len(inliers))
    if matrix is None or len(inliers) < cfg.coarse_min_inliers:
        _note(diagnostics, fine_stage="skipped_insufficient_coarse_inliers")
        return []

    src_shape = _product_shape(pair, "source", representation)
    ref_shape = _product_shape(pair, "reference", representation)
    if src_shape is None or ref_shape is None:
        _note(diagnostics, fine_stage="skipped_missing_product_shape")
        return []

    bbox = _expanded_source_bbox(inliers, src_shape, cfg.bbox_expand_fraction)
    if bbox is None:
        _note(diagnostics, fine_stage="skipped_empty_overlap_bbox")
        return []

    src_fine = _fine_stride(_stride(representation, "source"), cfg.fine_stride_factor)
    ref_fine = _fine_stride(_stride(representation, "reference"), cfg.fine_stride_factor)
    windows = _source_windows(bbox, src_fine, cfg)
    _note(
        diagnostics,
        fine_stage="ran",
        source_fine_stride=src_fine,
        reference_fine_stride=ref_fine,
        source_overlap_bbox=list(bbox),
        fine_tiles_planned=len(windows),
    )

    collected: list[Correspondence] = []
    attempted = 0
    for row, col, height, width in windows:
        ref_window = _reference_window(matrix, row, col, height, width, ref_shape, cfg)
        if ref_window is None:
            continue
        ref_row, ref_col, ref_h, ref_w = ref_window
        src_arr, src_mask = _tile_view(
            source_uri,
            pair.source.mask_uri,
            row,
            col,
            height,
            width,
            src_fine,
            representation_id(representation),
        )
        ref_arr, ref_mask = _tile_view(
            reference_uri,
            pair.reference.mask_uri,
            ref_row,
            ref_col,
            ref_h,
            ref_w,
            ref_fine,
            representation_id(representation),
        )
        if src_arr is None or ref_arr is None:
            continue
        if min(src_arr.shape) < cfg.min_tile_matching_side:
            continue
        if min(ref_arr.shape) < cfg.min_tile_matching_side:
            continue
        attempted += 1
        tile_rep = RepresentationResult(
            array=src_arr,
            representation_id=representation_id(representation) or "intensity",
            metadata={
                "reference_array": ref_arr,
                "source_valid_mask": src_mask,
                "reference_valid_mask": ref_mask,
                "source_matching_view": {
                    "stride": src_fine,
                    "x_scale": float(src_fine),
                    "y_scale": float(src_fine),
                },
                "reference_matching_view": {
                    "stride": ref_fine,
                    "x_scale": float(ref_fine),
                    "y_scale": float(ref_fine),
                },
            },
        )
        tile_set = run_sift(pair, tile_rep, settings=sift_cfg)
        offset = _offset_matches(tile_set.matches, col, row, ref_col, ref_row)
        collected.extend(_strongest(offset, cfg.max_matches_per_tile))

    _note(diagnostics, fine_tiles_attempted=attempted)
    return collected


def _coarse_prior(
    coarse: CorrespondenceSet, pair: RegistrationPair
) -> tuple[np.ndarray | None, list[Correspondence]]:
    verified = verify_matches(coarse, pair)
    inliers = [item for item in verified.matches if item.status == _INLIER]
    model = get_geometric_model(unvalidated_software_defaults().model_id)
    if len(inliers) < model.min_samples:
        return None, inliers
    source_xy = np.array([item.source_xy for item in inliers], dtype=float)
    reference_xy = np.array([item.reference_xy for item in inliers], dtype=float)
    matrix = model.fit(source_xy, reference_xy)
    return matrix, inliers


def _fine_stride(coarse_stride: int, factor: float) -> int:
    return max(1, int(round(coarse_stride * factor)))


def _stride(representation: RepresentationResult | None, role: str) -> int:
    scale = matching_view_scale(representation, role)
    return max(1, int(round(scale[0])))


def _product_shape(
    pair: RegistrationPair,
    role: str,
    representation: RepresentationResult | None,
) -> tuple[int, int] | None:
    product = pair.source if role == "source" else pair.reference
    dimensions = product.dimensions
    if dimensions is not None:
        return int(dimensions.height_px), int(dimensions.width_px)
    if not isinstance(representation, RepresentationResult):
        return None
    view = representation.metadata.get(f"{role}_matching_view")
    if not isinstance(view, dict):
        return None
    original = view.get("original_shape")
    if isinstance(original, (list, tuple)) and len(original) == 2:
        return int(original[0]), int(original[1])
    return None


def _expanded_source_bbox(
    inliers: list[Correspondence],
    shape: tuple[int, int],
    fraction: float,
) -> tuple[int, int, int, int] | None:
    xs = [item.source_xy[0] for item in inliers]
    ys = [item.source_xy[1] for item in inliers]
    if not xs:
        return None
    height, width = shape
    pad_x = (max(xs) - min(xs)) * fraction
    pad_y = (max(ys) - min(ys)) * fraction
    x0 = max(0, int(math.floor(min(xs) - pad_x)))
    y0 = max(0, int(math.floor(min(ys) - pad_y)))
    x1 = min(width, int(math.ceil(max(xs) + pad_x)))
    y1 = min(height, int(math.ceil(max(ys) + pad_y)))
    if x1 - x0 < 32 or y1 - y0 < 32:
        return None
    return x0, y0, x1, y1


def _source_windows(
    bbox: tuple[int, int, int, int],
    stride: int,
    cfg: CoarseToFineSettings,
) -> list[tuple[int, int, int, int]]:
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    match_w = max(1, (width + stride - 1) // stride)
    if match_w > cfg.max_pixels_per_tile:
        match_side = max(1, int(math.sqrt(cfg.max_pixels_per_tile)))
        tile_w = min(width, match_side * stride)
        tile_h = min(height, match_side * stride)
        overlap_x = int(tile_w * cfg.tile_overlap_fraction)
        overlap_y = int(tile_h * cfg.tile_overlap_fraction)
        windows: list[tuple[int, int, int, int]] = []
        for row in _axis_starts(y0, height, tile_h, overlap_y):
            for col in _axis_starts(x0, width, tile_w, overlap_x):
                windows.append(
                    (
                        row,
                        col,
                        min(tile_h, y0 + height - row),
                        min(tile_w, x0 + width - col),
                    )
                )
        return _even_sample(windows, cfg.max_fine_tiles)

    match_h_all = max(1, (height + stride - 1) // stride)
    if match_w * match_h_all <= cfg.max_pixels_per_tile:
        return [(y0, x0, height, width)]

    max_match_h = max(1, cfg.max_pixels_per_tile // match_w)
    tile_h = min(height, max_match_h * stride)
    overlap = int(tile_h * cfg.tile_overlap_fraction)
    windows = []
    for row in _axis_starts(y0, height, tile_h, overlap):
        windows.append((row, x0, min(tile_h, y0 + height - row), width))
    return _even_sample(windows, cfg.max_fine_tiles)


def _axis_starts(origin: int, length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [origin]
    step = max(1, tile - overlap)
    starts: list[int] = []
    pos = origin
    end = origin + length
    while pos + tile < end:
        starts.append(pos)
        pos += step
    last = max(origin, end - tile)
    if not starts or last != starts[-1]:
        starts.append(last)
    unique: list[int] = []
    for start in starts:
        if not unique or start != unique[-1]:
            unique.append(start)
    return unique


def _even_sample(
    items: list[tuple[int, int, int, int]], count: int
) -> list[tuple[int, int, int, int]]:
    if count >= len(items):
        return items
    if count <= 0:
        return []
    if count == 1:
        return [items[len(items) // 2]]
    last = len(items) - 1
    chosen: list[tuple[int, int, int, int]] = []
    seen: set[int] = set()
    for index in range(count):
        idx = int(round(index * last / (count - 1)))
        if idx not in seen:
            seen.add(idx)
            chosen.append(items[idx])
    return chosen


def _reference_window(
    matrix: np.ndarray,
    row: int,
    col: int,
    height: int,
    width: int,
    ref_shape: tuple[int, int],
    cfg: CoarseToFineSettings,
) -> tuple[int, int, int, int] | None:
    corners = np.array(
        [
            [col, row],
            [col + width, row],
            [col + width, row + height],
            [col, row + height],
        ],
        dtype=float,
    )
    mapped = _map_points(corners, matrix)
    if not np.all(np.isfinite(mapped)):
        return None
    x0 = float(mapped[:, 0].min())
    x1 = float(mapped[:, 0].max())
    y0 = float(mapped[:, 1].min())
    y1 = float(mapped[:, 1].max())
    span_x = max(1.0, x1 - x0)
    span_y = max(1.0, y1 - y0)
    margin_x = max(cfg.reference_margin_min_px, span_x * cfg.reference_margin_fraction)
    margin_y = max(cfg.reference_margin_min_px, span_y * cfg.reference_margin_fraction)
    ref_h, ref_w = ref_shape
    col0 = max(0, int(math.floor(x0 - margin_x)))
    row0 = max(0, int(math.floor(y0 - margin_y)))
    col1 = min(ref_w, int(math.ceil(x1 + margin_x)))
    row1 = min(ref_h, int(math.ceil(y1 + margin_y)))
    if col1 - col0 < 32 or row1 - row0 < 32:
        return None
    return row0, col0, row1 - row0, col1 - col0


def _map_points(source_xy: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    ones = np.ones((source_xy.shape[0], 1), dtype=float)
    mapped = (matrix @ np.concatenate([source_xy, ones], axis=1).T).T
    scale = mapped[:, 2]
    predicted = np.full((source_xy.shape[0], 2), np.nan, dtype=float)
    usable = np.abs(scale) > _HOMOGENEOUS_FLOOR
    predicted[usable] = mapped[usable, :2] / scale[usable, np.newaxis]
    return predicted


def _tile_view(
    raster_uri: str,
    mask_uri: str | None,
    row: int,
    col: int,
    height: int,
    width: int,
    stride: int,
    rep_id: str | None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    try:
        raw = load_strided_window(
            raster_uri, row=row, col=col, height=height, width=width, stride=stride
        )
    except (ValueError, OSError):
        return None, None
    if raw.size == 0:
        return None, None
    array = _build_representation(raw, rep_id)
    mask = None
    if mask_uri is not None:
        try:
            mask = load_strided_mask_window(
                mask_uri, row=row, col=col, height=height, width=width, stride=stride
            )
            if mask.shape != array.shape:
                mask = None
        except (ValueError, OSError):
            mask = None
    return array, mask


def _build_representation(array: np.ndarray, rep_id: str | None) -> np.ndarray:
    if rep_id == "gradient":
        return build_gradient_array(array)
    if rep_id == "structural":
        return build_structural_array(array)
    return build_intensity_array(array)


def _offset_matches(
    matches: list[Correspondence],
    source_col: int,
    source_row: int,
    reference_col: int,
    reference_row: int,
) -> list[Correspondence]:
    offset: list[Correspondence] = []
    for item in matches:
        offset.append(
            item.model_copy(
                update={
                    "source_xy": (
                        item.source_xy[0] + source_col,
                        item.source_xy[1] + source_row,
                    ),
                    "reference_xy": (
                        item.reference_xy[0] + reference_col,
                        item.reference_xy[1] + reference_row,
                    ),
                    "status": "raw",
                    "residual": None,
                }
            )
        )
    return offset


def _strongest(matches: list[Correspondence], limit: int) -> list[Correspondence]:
    if len(matches) <= limit:
        return matches
    ranked = sorted(
        matches,
        key=lambda item: (-1.0 if item.confidence is None else -float(item.confidence)),
    )
    return ranked[:limit]


def _novel_matches(
    fine: list[Correspondence],
    coarse: list[Correspondence],
    radius: float,
) -> list[Correspondence]:
    kept: list[Correspondence] = []
    radius_sq = radius * radius
    coarse_xy = [item.source_xy for item in coarse]
    accepted_xy = list(coarse_xy)
    for item in fine:
        if _near_any(item.source_xy, accepted_xy, radius_sq):
            continue
        kept.append(item)
        accepted_xy.append(item.source_xy)
    return kept


def _near_any(
    point: tuple[float, float], others: list[tuple[float, float]], radius_sq: float
) -> bool:
    px, py = point
    for qx, qy in others:
        dx = px - qx
        dy = py - qy
        if dx * dx + dy * dy <= radius_sq:
            return True
    return False


def _note(diagnostics: dict[str, Any] | None, **fields: Any) -> None:
    if diagnostics is not None:
        diagnostics.update(fields)


__all__ = ["MATCHER_ID", "run_coarse_to_fine_sift"]
