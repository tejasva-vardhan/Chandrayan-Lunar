"""Synthetic sub-pixel refinement tests. Software validation only — not lunar accuracy.

Ground truth is a known global translation of a periodic band-limited texture,
applied with an FFT phase ramp. That generating model is TEST ONLY. It is not
a lunar transformation, not Chandrayaan-2 / LROC accuracy, and not SIH
evaluator evidence (D-006, D-011, D-012).

Decimal coordinates are not treated as proof of sub-pixel accuracy. These
tests compare an estimated displacement (dx_hat, dy_hat) to a known
(dx, dy) and require the Euclidean error to fall within a SOFTWARE TEST
TOLERANCE derived from this construction (FFT shift, ZNCC window, 1-D
parabolic peak interpolation). That tolerance is not a lunar accuracy
claim.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.control_points import ControlPointSettings, select_control_points_with_settings
from src.models import (
    ControlPoint,
    Correspondence,
    CorrespondenceSet,
    LunarProduct,
    RegistrationPair,
)
from src.refinement import RefinementSettings, refine_points, refine_points_with_settings
from src.registration.estimation import eligible_control_points, estimate_matrix
from src.registration.models import Affine2DBaseline

pytestmark = pytest.mark.scientific

# SOFTWARE TEST TOLERANCE. Chosen for this synthetic construction:
# periodic multi-sinusoid texture, FFT phase-shift generating model,
# default/engineering ZNCC window (radius 7), search (radius 3),
# fractional ZNCC grid (half-width 1.0 px, step 0.1 px), and 2-D
# quadratic interpolation of the fine 3x3.
#
# On this construction the observed worst Euclidean error among the
# listed displacements was about 0.05 px. The test bound is 0.15 px:
# three times that observed worst case and 1.5 times the 0.1 px fine-grid
# step. It is not tightened to 0.05 to invent an impressive figure, and
# it is not a lunar sub-pixel accuracy claim.
SOFTWARE_TEST_TOLERANCE_PX = 0.15

SYNTHETIC_DISPLACEMENTS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (0.37, 0.0),
    (0.0, -0.41),
    (0.25, -0.25),
    (-0.45, 0.33),
    (0.12, 0.48),
    (-0.30, -0.20),
    (0.50, -0.50),
    (-0.15, 0.27),
)


def _periodic_texture(height: int, width: int) -> np.ndarray:
    y = np.arange(height, dtype=float)[:, None]
    x = np.arange(width, dtype=float)[None, :]
    return (
        np.sin(2.0 * np.pi * 3.0 * x / width)
        + 0.7 * np.sin(2.0 * np.pi * 5.0 * y / height)
        + 0.45 * np.sin(2.0 * np.pi * (2.0 * x / width + 3.0 * y / height))
        + 0.25 * np.sin(2.0 * np.pi * 7.0 * x / width)
        * np.cos(2.0 * np.pi * 4.0 * y / height)
    )


def _fourier_translate(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Periodic translation: a feature at (x, y) appears at (x+dx, y+dy).

    FFT phase ramp. TEST GENERATING MODEL ONLY — not a lunar model.
    """

    if dx == 0.0 and dy == 0.0:
        return np.array(image, dtype=float, copy=True)
    height, width = image.shape
    fx = np.fft.fftfreq(width)
    fy = np.fft.fftfreq(height)
    freq_x, freq_y = np.meshgrid(fx, fy)
    ramp = np.exp(-2j * np.pi * (freq_x * dx + freq_y * dy))
    shifted = np.fft.ifft2(np.fft.fft2(image) * ramp)
    return np.real(shifted)


def _pair(tmp_path: Path, source: np.ndarray, reference: np.ndarray) -> RegistrationPair:
    source_uri = str(tmp_path / "source.npy")
    reference_uri = str(tmp_path / "reference.npy")
    np.save(source_uri, source)
    np.save(reference_uri, reference)
    return RegistrationPair(
        pair_id="synthetic-refine",
        source=LunarProduct(product_id="src", instrument="OHRC", raster_uri=source_uri),
        reference=LunarProduct(
            product_id="ref", instrument="LRO_NAC", raster_uri=reference_uri
        ),
    )


def _interior_points() -> list[ControlPoint]:
    # Integer coarse locations. Coarse reference equals source (identity),
    # so any recovered offset must come from image evidence of the shift.
    locations = ((32.0, 32.0), (48.0, 32.0), (32.0, 48.0), (56.0, 56.0), (40.0, 44.0))
    return [
        ControlPoint(source_xy=(x, y), reference_xy=(x, y), residual=0.15)
        for x, y in locations
    ]


def _displacement_error(
    refined: ControlPoint, original: ControlPoint, dx: float, dy: float
) -> tuple[float, float, float]:
    dx_hat = refined.reference_xy[0] - original.reference_xy[0]
    dy_hat = refined.reference_xy[1] - original.reference_xy[1]
    error_x = dx_hat - dx
    error_y = dy_hat - dy
    return error_x, error_y, math.hypot(error_x, error_y)


@pytest.mark.parametrize(("dx", "dy"), SYNTHETIC_DISPLACEMENTS)
def test_known_fractional_translation_is_recovered(
    tmp_path: Path, dx: float, dy: float
) -> None:
    # Synthetic generating model (TEST ONLY): global translation (dx, dy).
    source = _periodic_texture(96, 96)
    reference = _fourier_translate(source, dx, dy)
    pair = _pair(tmp_path, source, reference)
    originals = _interior_points()
    refined = refine_points(originals, pair)
    assert len(refined) == len(originals)
    errors = [
        _displacement_error(out, inp, dx, dy)
        for out, inp in zip(refined, originals, strict=True)
    ]
    for out, inp, (error_x, error_y, euclidean) in zip(refined, originals, errors, strict=True):
        assert out.source_xy == inp.source_xy
        assert out.residual == inp.residual
        assert math.isfinite(out.reference_xy[0]) and math.isfinite(out.reference_xy[1])
        assert euclidean <= SOFTWARE_TEST_TOLERANCE_PX, (
            f"dx={dx} dy={dy} error=({error_x:.4f}, {error_y:.4f}) "
            f"euclidean={euclidean:.4f} > software test tolerance "
            f"{SOFTWARE_TEST_TOLERANCE_PX}"
        )


def test_zero_displacement_is_recovered(tmp_path: Path) -> None:
    source = _periodic_texture(96, 96)
    pair = _pair(tmp_path, source, source)
    originals = _interior_points()
    refined = refine_points(originals, pair)
    for out, inp in zip(refined, originals, strict=True):
        _, _, euclidean = _displacement_error(out, inp, 0.0, 0.0)
        assert euclidean <= SOFTWARE_TEST_TOLERANCE_PX
        assert out.uncertainty is None


def test_positive_and_negative_displacements_track_sign(tmp_path: Path) -> None:
    source = _periodic_texture(96, 96)
    originals = _interior_points()
    plus_dir = tmp_path / "plus"
    minus_dir = tmp_path / "minus"
    plus_dir.mkdir()
    minus_dir.mkdir()
    plus = refine_points(
        originals, _pair(plus_dir, source, _fourier_translate(source, 0.35, 0.20))
    )
    minus = refine_points(
        originals, _pair(minus_dir, source, _fourier_translate(source, -0.35, -0.20))
    )
    dx_plus = plus[0].reference_xy[0] - originals[0].reference_xy[0]
    dy_plus = plus[0].reference_xy[1] - originals[0].reference_xy[1]
    dx_minus = minus[0].reference_xy[0] - originals[0].reference_xy[0]
    dy_minus = minus[0].reference_xy[1] - originals[0].reference_xy[1]
    assert dx_plus > 0.0 and dy_plus > 0.0
    assert dx_minus < 0.0 and dy_minus < 0.0


def test_multiple_subpixel_displacements_are_distinct(tmp_path: Path) -> None:
    source = _periodic_texture(96, 96)
    originals = [_interior_points()[0]]
    estimates: list[tuple[float, float]] = []
    for dx, dy in ((0.0, 0.0), (0.3, 0.0), (0.0, 0.3)):
        case_dir = tmp_path / f"{dx}_{dy}"
        case_dir.mkdir()
        refined = refine_points(
            originals, _pair(case_dir, source, _fourier_translate(source, dx, dy))
        )
        estimates.append(
            (
                refined[0].reference_xy[0] - originals[0].reference_xy[0],
                refined[0].reference_xy[1] - originals[0].reference_xy[1],
            )
        )
    assert estimates[0] != estimates[1]
    assert estimates[0] != estimates[2]
    assert estimates[1] != estimates[2]
    assert estimates[1][0] == pytest.approx(0.3, abs=SOFTWARE_TEST_TOLERANCE_PX)
    assert estimates[2][1] == pytest.approx(0.3, abs=SOFTWARE_TEST_TOLERANCE_PX)


def test_estimate_is_derived_from_image_evidence_not_a_token_offset(
    tmp_path: Path,
) -> None:
    source = _periodic_texture(96, 96)
    originals = [_interior_points()[0]]
    shifted = refine_points(
        originals, _pair(tmp_path, source, _fourier_translate(source, 0.4, -0.25))
    )
    dx_hat = shifted[0].reference_xy[0] - originals[0].reference_xy[0]
    dy_hat = shifted[0].reference_xy[1] - originals[0].reference_xy[1]
    assert (dx_hat, dy_hat) != (0.001, 0.001)
    assert (dx_hat, dy_hat) != (0.0, 0.0)
    assert math.hypot(dx_hat - 0.4, dy_hat + 0.25) <= SOFTWARE_TEST_TOLERANCE_PX


def test_already_correct_fractional_correspondence_does_not_walk_away(
    tmp_path: Path,
) -> None:
    dx, dy = 0.31, -0.22
    source = _periodic_texture(96, 96)
    reference = _fourier_translate(source, dx, dy)
    pair = _pair(tmp_path, source, reference)
    originals = [
        ControlPoint(
            source_xy=(40.0, 44.0),
            reference_xy=(40.0 + dx, 44.0 + dy),
            residual=0.05,
        )
    ]
    refined = refine_points(originals, pair)
    extra_x = refined[0].reference_xy[0] - originals[0].reference_xy[0]
    extra_y = refined[0].reference_xy[1] - originals[0].reference_xy[1]
    assert math.hypot(extra_x, extra_y) <= SOFTWARE_TEST_TOLERANCE_PX
    assert refined[0].source_xy == originals[0].source_xy


def test_deterministic_repeatability_on_synthetic_shift(tmp_path: Path) -> None:
    source = _periodic_texture(96, 96)
    reference = _fourier_translate(source, 0.28, -0.17)
    pair = _pair(tmp_path, source, reference)
    originals = _interior_points()
    first = refine_points(originals, pair)
    second = refine_points(originals, pair)
    assert [(p.source_xy, p.reference_xy) for p in first] == [
        (p.source_xy, p.reference_xy) for p in second
    ]


def test_failed_noisy_refinement_preserves_coordinates(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)
    source = rng.normal(size=(96, 96))
    reference = rng.normal(size=(96, 96))
    pair = _pair(tmp_path, source, reference)
    originals = _interior_points()
    refined = refine_points(originals, pair)
    for out, inp in zip(refined, originals, strict=True):
        assert out.source_xy == inp.source_xy
        assert out.reference_xy == inp.reference_xy
        assert out.residual == inp.residual
        assert out.uncertainty is None


def test_no_refinement_ablation_hook_leaves_coarse_points(tmp_path: Path) -> None:
    source = _periodic_texture(96, 96)
    reference = _fourier_translate(source, 0.4, 0.2)
    pair = _pair(tmp_path, source, reference)
    originals = _interior_points()
    settings = RefinementSettings(
        method_id="identity_passthrough",
        window_radius=7,
        search_radius=3,
        min_valid_pixel_fraction=0.75,
        min_peak_zncc=0.25,
        fine_half_width=1.0,
        fine_step=0.1,
    )
    refined = refine_points_with_settings(originals, pair, settings)
    for out, inp in zip(refined, originals, strict=True):
        assert out.source_xy == inp.source_xy
        assert out.reference_xy == inp.reference_xy


def test_output_remains_finite_and_population_is_unchanged(tmp_path: Path) -> None:
    source = _periodic_texture(96, 96)
    reference = _fourier_translate(source, -0.22, 0.41)
    pair = _pair(tmp_path, source, reference)
    originals = _interior_points()
    refined = refine_points(originals, pair)
    assert len(refined) == len(originals)
    for out, inp in zip(refined, originals, strict=True):
        assert math.isfinite(out.source_xy[0]) and math.isfinite(out.source_xy[1])
        assert math.isfinite(out.reference_xy[0]) and math.isfinite(out.reference_xy[1])
        assert out.residual == inp.residual


def _apply_matrix(matrix: np.ndarray, point: tuple[float, float]) -> np.ndarray:
    homogeneous = matrix @ np.array([point[0], point[1], 1.0])
    return homogeneous[:2] / homogeneous[2]


def test_spatial_selection_survives_refinement_and_supports_an_ablation_fit(
    tmp_path: Path,
) -> None:
    """Compare all verified points with the selected subset on known synthetic data.

    This is an engineering ablation utility only. It checks that refinement
    preserves the selected spatial population and that both point populations
    can support a finite affine fit. It does not rank either population or
    claim scientific registration superiority.
    """
    dx, dy = 0.35, -0.25
    source = _periodic_texture(96, 96)
    pair = _pair(tmp_path, source, _fourier_translate(source, dx, dy))
    locations = [(float(x), float(y)) for x in (20, 48, 76) for y in (20, 48, 76)]
    # Extra high-confidence center points exercise the spatial selector's
    # one-point-per-cell limit without changing the known synthetic transform.
    locations.extend([(48.0, 48.0)] * 8)
    correspondences = CorrespondenceSet(
        pair_id=pair.pair_id,
        matcher_id="synthetic",
        matches=[
            Correspondence(
                source_xy=point,
                reference_xy=(point[0] + dx, point[1] + dy),
                confidence=0.99,
                residual=0.1,
                status="inlier",
            )
            for point in locations
        ],
    )
    selected = select_control_points_with_settings(
        correspondences,
        pair,
        ControlPointSettings(
            grid_bins=3,
            max_per_source_cell=1,
            max_per_reference_cell=1,
        ),
    )
    refined = refine_points(selected, pair)

    assert len(selected) == len(refined) == 9
    assert {point.source_xy for point in refined} == {
        (float(x), float(y)) for x in (20, 48, 76) for y in (20, 48, 76)
    }

    all_points = [
        ControlPoint(
            source_xy=item.source_xy,
            reference_xy=item.reference_xy,
            residual=item.residual,
        )
        for item in correspondences.matches
    ]
    model = Affine2DBaseline()
    all_matrix = estimate_matrix(eligible_control_points(all_points), model)
    selected_matrix = estimate_matrix(eligible_control_points(refined), model)

    assert all_matrix is not None
    assert selected_matrix is not None
    expected = np.array([60.0 + dx, 36.0 + dy])
    # Both fits are evaluated against the known synthetic generating model;
    # neither fit is asserted to be better than the other.
    assert np.linalg.norm(_apply_matrix(all_matrix, (60.0, 36.0)) - expected) <= 1e-9
    assert np.linalg.norm(_apply_matrix(selected_matrix, (60.0, 36.0)) - expected) <= (
        SOFTWARE_TEST_TOLERANCE_PX
    )
