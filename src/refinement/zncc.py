"""Zero-mean normalized cross-correlation with continuous peak estimation.

SAME-MODALITY / SOFTWARE BASELINE.

This method estimates a continuous local translation of the reference
coordinate given a source template. It is appropriate as a software
baseline because:

- the objective is a standard, intensity-affine-invariant local similarity
  measure (ZNCC), so a constant gain/bias between images does not by itself
  move the peak;
- a discrete integer-lag search locates the coarse correlation maximum;
- ZNCC is then re-evaluated on a fractional-lag grid around that peak, so
  the continuous displacement is obtained from image evidence rather than
  from an arbitrary decimal offset;
- a 2-D quadratic fit of the fine-grid 3x3 supplies a continuous vertex
  (with the fine-grid argmax as fallback);
- it needs only NumPy.

It is NOT:

- a multimodal refinement solution (OHRC ↔ IIRS, OHRC ↔ TMC-2, etc.)
- a phase-correlation / ISIS-style method
- proof of lunar sub-pixel accuracy (D-006)
- a claim that decimal coordinates equal sub-pixel accuracy

Raw SSD/MSE is intentionally not used as the objective.
"""

from __future__ import annotations

import math

import numpy as np

from src.models.registration_result import ControlPoint
from src.refinement.methods import RefinementMethod
from src.refinement.peak import discrete_peak_index, quadratic_offset_2d
from src.refinement.settings import RefinementSettings
from src.refinement.window import extract_search_stack, extract_window, has_intensity_structure

# Engineering floor. Not a scientific texture threshold.
_VARIANCE_FLOOR = 1e-12


class ZnccParabolicBaseline(RefinementMethod):
    method_id = "zncc_parabolic_baseline"
    role = "same_modality_software_baseline"
    requires_rasters = True

    def refine_point(
        self,
        source: np.ndarray | None,
        reference: np.ndarray | None,
        point: ControlPoint,
        settings: RefinementSettings,
    ) -> ControlPoint | None:
        if source is None or reference is None:
            return None
        estimate = estimate_zncc_displacement(
            source,
            reference,
            point.source_xy,
            point.reference_xy,
            settings,
        )
        if estimate is None:
            return None
        dx, dy = estimate
        refined_x = point.reference_xy[0] + dx
        refined_y = point.reference_xy[1] + dy
        if not math.isfinite(refined_x) or not math.isfinite(refined_y):
            return None
        return ControlPoint(
            source_xy=point.source_xy,
            reference_xy=(float(refined_x), float(refined_y)),
            residual=point.residual,
            uncertainty=None,
        )


def estimate_zncc_displacement(
    source: np.ndarray,
    reference: np.ndarray,
    source_xy: tuple[float, float],
    reference_xy: tuple[float, float],
    settings: RefinementSettings,
) -> tuple[float, float] | None:
    """Estimate (dx, dy) to add to reference_xy.

    The source template is held at source_xy. Integer-lag ZNCC is evaluated
    in the reference image around reference_xy. Around the discrete peak,
    ZNCC is re-evaluated on a fractional-lag grid (image windows sampled at
    non-integer centres). A 2-D quadratic of the fine 3x3, or the fine-grid
    argmax if that fit is invalid, supplies the continuous offset.

    Returns None when the estimate is not supported by image evidence.
    Does not rematch to a different correspondence.
    """

    sx, sy = source_xy
    rx, ry = reference_xy
    if not _finite_xy(sx, sy) or not _finite_xy(rx, ry):
        return None
    if source.ndim != 2 or reference.ndim != 2:
        return None

    window_radius = settings.window_radius
    search_radius = settings.search_radius
    template = extract_window(source, sx, sy, window_radius)
    if template is None:
        return None
    min_valid = _min_valid_pixels(template.size, settings.min_valid_pixel_fraction)
    if not has_intensity_structure(template, min_valid):
        return None

    stack = extract_search_stack(reference, rx, ry, window_radius, search_radius)
    if stack is None:
        return None

    n_lags = 2 * search_radius + 1
    surface = np.full((n_lags, n_lags), np.nan, dtype=float)
    for dv in range(n_lags):
        for du in range(n_lags):
            score = zncc(template, stack[dv, du], min_valid)
            if score is not None:
                surface[dv, du] = score

    peak = discrete_peak_index(surface)
    if peak is None:
        return None
    peak_row, peak_col = peak
    peak_value = float(surface[peak_row, peak_col])
    if not math.isfinite(peak_value) or peak_value < settings.min_peak_zncc:
        return None
    if peak_row <= 0 or peak_row >= n_lags - 1 or peak_col <= 0 or peak_col >= n_lags - 1:
        return None

    du_int = peak_col - search_radius
    dv_int = peak_row - search_radius
    fractional = _fractional_zncc_offset(
        template,
        reference,
        rx,
        ry,
        du_int,
        dv_int,
        window_radius,
        min_valid,
        settings,
    )
    if fractional is None:
        return None
    du = du_int + fractional[0]
    dv = dv_int + fractional[1]
    if not math.isfinite(du) or not math.isfinite(dv):
        return None
    return float(du), float(dv)


def _fractional_zncc_offset(
    template: np.ndarray,
    reference: np.ndarray,
    reference_x: float,
    reference_y: float,
    du_int: int,
    dv_int: int,
    window_radius: int,
    min_valid: int,
    settings: RefinementSettings,
) -> tuple[float, float] | None:
    """Re-evaluate ZNCC on a fractional-lag grid around the integer peak.

    This is the continuous-displacement step: windows are sampled at
    non-integer centres, so the peak is estimated from image evidence.
    """

    step = settings.fine_step
    n_steps = int(round(settings.fine_half_width / step))
    if n_steps < 1:
        return None
    offsets = step * np.arange(-n_steps, n_steps + 1, dtype=float)
    n = offsets.size
    fine = np.full((n, n), np.nan, dtype=float)
    for row, fy in enumerate(offsets):
        for col, fx in enumerate(offsets):
            patch = extract_window(
                reference,
                reference_x + du_int + float(fx),
                reference_y + dv_int + float(fy),
                window_radius,
            )
            if patch is None:
                continue
            score = zncc(template, patch, min_valid)
            if score is not None:
                fine[row, col] = score

    peak = discrete_peak_index(fine)
    if peak is None:
        return None
    peak_row, peak_col = peak
    peak_value = float(fine[peak_row, peak_col])
    if not math.isfinite(peak_value) or peak_value < settings.min_peak_zncc:
        return None

    fx = float(offsets[peak_col])
    fy = float(offsets[peak_row])
    if 0 < peak_row < n - 1 and 0 < peak_col < n - 1:
        quadratic = quadratic_offset_2d(
            fine[peak_row - 1 : peak_row + 2, peak_col - 1 : peak_col + 2]
        )
        if quadratic is not None:
            fx += quadratic[0] * step
            fy += quadratic[1] * step
    if not math.isfinite(fx) or not math.isfinite(fy):
        return None
    return fx, fy


def zncc(template: np.ndarray, patch: np.ndarray, min_valid: int) -> float | None:
    """Zero-mean normalized cross-correlation over co-valid finite pixels.

    zncc = sum((T-μT)(P-μP)) / (||T-μT|| ||P-μP||)

    Undefined (returns None) when there are too few valid pixels or either
    masked vector has near-zero variance. This is the SAME-MODALITY software
    objective, not a multimodal descriptor distance.
    """

    valid = np.isfinite(template) & np.isfinite(patch)
    if int(np.count_nonzero(valid)) < min_valid:
        return None
    t = template[valid].astype(float, copy=False)
    p = patch[valid].astype(float, copy=False)
    t = t - t.mean()
    p = p - p.mean()
    t_norm = math.sqrt(float(np.dot(t, t)))
    p_norm = math.sqrt(float(np.dot(p, p)))
    if t_norm <= math.sqrt(_VARIANCE_FLOOR) or p_norm <= math.sqrt(_VARIANCE_FLOOR):
        return None
    value = float(np.dot(t, p) / (t_norm * p_norm))
    if not math.isfinite(value):
        return None
    return max(-1.0, min(1.0, value))


def _min_valid_pixels(window_size: int, fraction: float) -> int:
    required = int(math.ceil(fraction * window_size))
    return max(4, required)


def _finite_xy(x: float, y: float) -> bool:
    return math.isfinite(x) and math.isfinite(y)
