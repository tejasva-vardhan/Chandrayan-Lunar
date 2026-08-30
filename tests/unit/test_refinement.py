"""Unit tests for sub-pixel control-point refinement. Not lunar accuracy evidence."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.models import ControlPoint, LunarProduct, RegistrationPair
from src.pipeline.operations import refine_points as pipeline_refine
from src.refinement import (
    RefinementSettings,
    refine_points,
    refine_points_with_settings,
    unvalidated_software_defaults,
)
from src.refinement.peak import parabolic_offset, quadratic_offset_2d, refine_peak_subpixel
from src.refinement.zncc import estimate_zncc_displacement


def _settings(**overrides: object) -> RefinementSettings:
    base: dict[str, object] = dict(
        method_id="zncc_parabolic_baseline",
        window_radius=5,
        search_radius=2,
        min_valid_pixel_fraction=0.75,
        min_peak_zncc=0.25,
        fine_half_width=1.0,
        fine_step=0.1,
    )
    base.update(overrides)
    return RefinementSettings(**base)  # type: ignore[arg-type]


def _texture(height: int, width: int) -> np.ndarray:
    y = np.arange(height, dtype=float)[:, None]
    x = np.arange(width, dtype=float)[None, :]
    return (
        np.sin(0.31 * x)
        + 0.8 * np.sin(0.23 * y)
        + 0.35 * np.sin(0.17 * x + 0.19 * y)
        + 0.2 * np.sin(0.41 * x) * np.cos(0.29 * y)
    )


def _pair(
    tmp_path: Path,
    source: np.ndarray | None = None,
    reference: np.ndarray | None = None,
    *,
    source_name: str = "source.npy",
    reference_name: str = "reference.npy",
    source_uri: str | None | bool = True,
    reference_uri: str | None | bool = True,
) -> RegistrationPair:
    source_path: str | None
    reference_path: str | None
    if source_uri is True:
        if source is None:
            raise ValueError("source array required when writing a raster")
        source_path = str(tmp_path / source_name)
        np.save(source_path, source)
    elif source_uri is False:
        source_path = None
    else:
        source_path = source_uri
    if reference_uri is True:
        if reference is None:
            raise ValueError("reference array required when writing a raster")
        reference_path = str(tmp_path / reference_name)
        np.save(reference_path, reference)
    elif reference_uri is False:
        reference_path = None
    else:
        reference_path = reference_uri
    return RegistrationPair(
        pair_id="pair-refine",
        source=LunarProduct(product_id="src-001", instrument="OHRC", raster_uri=source_path),
        reference=LunarProduct(
            product_id="ref-001", instrument="LRO_NAC", raster_uri=reference_path
        ),
    )


def _cp(
    source_xy: tuple[float, float],
    reference_xy: tuple[float, float],
    *,
    residual: float | None = 0.4,
    uncertainty: float | None = None,
) -> ControlPoint:
    return ControlPoint(
        source_xy=source_xy,
        reference_xy=reference_xy,
        residual=residual,
        uncertainty=uncertainty,
    )


def test_refine_points_is_the_frozen_pipeline_callable() -> None:
    assert pipeline_refine is refine_points


def test_empty_input_returns_empty(registration_pair: RegistrationPair) -> None:
    assert refine_points([], registration_pair) == []


def test_missing_rasters_preserve_original_points(
    registration_pair: RegistrationPair,
) -> None:
    point = _cp((12.0, 14.0), (13.0, 15.0), residual=0.25)
    result = refine_points([point], registration_pair)
    assert len(result) == 1
    assert result[0].source_xy == point.source_xy
    assert result[0].reference_xy == point.reference_xy
    assert result[0].residual == point.residual
    assert result[0].uncertainty is None
    assert result[0] is not point


def test_unsupported_raster_encoding_preserves_points(tmp_path: Path) -> None:
    bogus = tmp_path / "source.png"
    bogus.write_bytes(b"not-a-raster")
    pair = RegistrationPair(
        pair_id="pair-refine",
        source=LunarProduct(product_id="src", instrument="OHRC", raster_uri=str(bogus)),
        reference=LunarProduct(
            product_id="ref", instrument="LRO_NAC", raster_uri=str(bogus)
        ),
    )
    point = _cp((8.0, 8.0), (8.0, 8.0))
    result = refine_points([point], pair)
    assert result[0].source_xy == point.source_xy
    assert result[0].reference_xy == point.reference_xy


def test_missing_raster_file_preserves_points(tmp_path: Path) -> None:
    missing = str(tmp_path / "absent.npy")
    pair = _pair(tmp_path, source_uri=missing, reference_uri=missing)
    point = _cp((8.0, 8.0), (9.0, 9.0))
    result = refine_points([point], pair)
    assert result[0].reference_xy == point.reference_xy


def test_identity_method_is_passthrough_without_rasters(
    registration_pair: RegistrationPair,
) -> None:
    point = _cp((3.0, 4.0), (5.0, 6.0), residual=1.2)
    result = refine_points_with_settings(
        [point], registration_pair, _settings(method_id="identity_passthrough")
    )
    assert result[0].source_xy == point.source_xy
    assert result[0].reference_xy == point.reference_xy
    assert result[0].residual == point.residual


def test_identity_method_does_not_use_image_evidence(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    point = _cp((20.0, 20.0), (22.0, 19.0), residual=0.7)
    result = refine_points_with_settings(
        [point], pair, _settings(method_id="identity_passthrough")
    )
    assert result[0].source_xy == (20.0, 20.0)
    assert result[0].reference_xy == (22.0, 19.0)
    assert result[0].residual == 0.7


def test_unknown_method_id_is_configuration_error(
    tmp_path: Path,
) -> None:
    image = _texture(32, 32)
    pair = _pair(tmp_path, image, image)
    with pytest.raises(ValueError, match="unknown refinement method_id"):
        refine_points_with_settings(
            [_cp((10.0, 10.0), (10.0, 10.0))],
            pair,
            _settings(method_id="not-a-method"),
        )


def test_invalid_settings_are_rejected() -> None:
    with pytest.raises(ValueError):
        _settings(window_radius=0)
    with pytest.raises(ValueError):
        _settings(search_radius=0)
    with pytest.raises(ValueError):
        _settings(min_valid_pixel_fraction=0.0)
    with pytest.raises(ValueError):
        _settings(min_peak_zncc=1.5)
    with pytest.raises(ValueError):
        _settings(fine_step=0.0)
    with pytest.raises(ValueError):
        _settings(fine_half_width=0.05, fine_step=0.1)


def test_unvalidated_software_defaults_are_labelled_engineering() -> None:
    defaults = unvalidated_software_defaults()
    assert defaults.method_id == "zncc_parabolic_baseline"
    assert defaults.window_radius == 7
    assert defaults.search_radius == 3
    assert defaults.fine_half_width == 1.0
    assert defaults.fine_step == 0.1


def test_parabolic_offset_recovers_known_vertex() -> None:
    # f(x) = 1 - 0.5 * (x - 0.3)^2  at x = -1, 0, 1. Not image data.
    left = 1.0 - 0.5 * (-1.0 - 0.3) ** 2
    peak = 1.0 - 0.5 * (0.0 - 0.3) ** 2
    right = 1.0 - 0.5 * (1.0 - 0.3) ** 2
    offset = parabolic_offset(left, peak, right)
    assert offset is not None
    assert offset == pytest.approx(0.3, abs=1e-12)


def test_parabolic_offset_rejects_flat_or_minimum() -> None:
    assert parabolic_offset(1.0, 1.0, 1.0) is None
    assert parabolic_offset(1.0, 0.0, 1.0) is None
    assert parabolic_offset(float("nan"), 1.0, 0.9) is None


def test_quadratic_offset_2d_recovers_known_vertex() -> None:
    # f(x, y) = 1 - 0.5*(x-0.3)^2 - 0.4*(y+0.2)^2 on {-1,0,1}^2. Not image data.
    ys, xs = np.mgrid[-1:2, -1:2]
    surface = 1.0 - 0.5 * (xs - 0.3) ** 2 - 0.4 * (ys + 0.2) ** 2
    offset = quadratic_offset_2d(surface)
    assert offset is not None
    assert offset[0] == pytest.approx(0.3, abs=1e-8)
    assert offset[1] == pytest.approx(-0.2, abs=1e-8)


def test_border_peak_is_not_interpolated() -> None:
    surface = np.array([[0.9, 1.0, 0.8], [0.1, 0.2, 0.1]], dtype=float)
    assert refine_peak_subpixel(surface, 0, 1) is None


def test_non_finite_coordinates_are_not_fabricated(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    points = [
        _cp((float("nan"), 20.0), (20.0, 20.0)),
        _cp((20.0, 20.0), (float("inf"), 20.0)),
        _cp((20.0, float("-inf")), (20.0, 20.0)),
    ]
    result = refine_points_with_settings(points, pair, _settings())
    assert len(result) == 3
    for original, refined in zip(points, result, strict=True):
        assert np.array_equal(
            np.array(refined.source_xy, dtype=float),
            np.array(original.source_xy, dtype=float),
            equal_nan=True,
        )
        assert np.array_equal(
            np.array(refined.reference_xy, dtype=float),
            np.array(original.reference_xy, dtype=float),
            equal_nan=True,
        )


def test_boundary_point_is_not_refined(tmp_path: Path) -> None:
    image = _texture(40, 40)
    pair = _pair(tmp_path, image, image)
    # window_radius=5, search_radius=2 → reference needs 7 px margin.
    interior = _cp((20.0, 20.0), (20.0, 20.0), residual=0.11)
    edge = _cp((2.0, 2.0), (2.0, 2.0), residual=0.11)
    result = refine_points_with_settings([interior, edge], pair, _settings())
    assert result[1].source_xy == (2.0, 2.0)
    assert result[1].reference_xy == (2.0, 2.0)
    assert result[1].residual == 0.11
    assert result[0].residual == 0.11
    assert result[0].source_xy == (20.0, 20.0)
    assert math.isfinite(result[0].reference_xy[0])
    assert math.isfinite(result[0].reference_xy[1])


def test_nan_and_inf_regions_fail_closed(tmp_path: Path) -> None:
    image = _texture(48, 48)
    poisoned = image.copy()
    poisoned[16:25, 16:25] = np.nan
    infested = image.copy()
    infested[16:25, 16:25] = np.inf
    pair_nan = _pair(
        tmp_path, poisoned, poisoned, source_name="nan_s.npy", reference_name="nan_r.npy"
    )
    pair_inf = _pair(
        tmp_path, infested, infested, source_name="inf_s.npy", reference_name="inf_r.npy"
    )
    point = _cp((20.0, 20.0), (20.0, 20.0), residual=0.3)
    for pair in (pair_nan, pair_inf):
        result = refine_points_with_settings([point], pair, _settings())
        assert result[0].source_xy == point.source_xy
        assert result[0].reference_xy == point.reference_xy
        assert result[0].residual == 0.3
        assert result[0].uncertainty is None


def test_insufficient_valid_pixels_preserves_coordinates(tmp_path: Path) -> None:
    image = _texture(48, 48)
    image[15:26, 15:26] = np.nan
    pair = _pair(tmp_path, image, image)
    point = _cp((20.0, 20.0), (20.0, 20.0))
    result = refine_points_with_settings(
        [point], pair, _settings(min_valid_pixel_fraction=0.95)
    )
    assert result[0].reference_xy == (20.0, 20.0)


def test_uncorrelated_noise_does_not_fabricate_a_peak(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    source = rng.normal(size=(48, 48))
    reference = rng.normal(size=(48, 48))
    pair = _pair(tmp_path, source, reference)
    point = _cp((20.0, 20.0), (20.0, 20.0), residual=0.5)
    result = refine_points_with_settings([point], pair, _settings(min_peak_zncc=0.5))
    assert result[0].source_xy == (20.0, 20.0)
    assert result[0].reference_xy == (20.0, 20.0)
    assert result[0].residual == 0.5
    assert result[0].uncertainty is None


def test_constant_image_does_not_fabricate_displacement(tmp_path: Path) -> None:
    image = np.ones((40, 40), dtype=float)
    pair = _pair(tmp_path, image, image)
    point = _cp((20.0, 20.0), (20.0, 20.0))
    result = refine_points_with_settings([point], pair, _settings())
    assert result[0].reference_xy == (20.0, 20.0)


def test_zero_displacement_stays_near_identity(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    point = _cp((24.0, 22.0), (24.0, 22.0), residual=0.08)
    result = refine_points_with_settings([point], pair, _settings())
    dx = result[0].reference_xy[0] - 24.0
    dy = result[0].reference_xy[1] - 22.0
    assert result[0].source_xy == (24.0, 22.0)
    assert result[0].residual == 0.08
    assert math.hypot(dx, dy) < 0.05
    assert result[0].uncertainty is None


def test_correspondence_identity_and_population_are_preserved(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    points = [
        _cp((18.0, 18.0), (18.0, 18.0), residual=0.1),
        _cp((30.0, 18.0), (30.0, 18.0), residual=0.2),
        _cp((18.0, 30.0), (18.0, 30.0), residual=None),
    ]
    result = refine_points_with_settings(points, pair, _settings())
    assert len(result) == 3
    assert [item.residual for item in result] == [0.1, 0.2, None]
    assert [item.source_xy for item in result] == [item.source_xy for item in points]


def test_no_fabricated_points_and_input_not_mutated(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    original = _cp((20.0, 21.0), (20.0, 21.0), residual=0.9)
    points = [original]
    result = refine_points_with_settings(points, pair, _settings())
    assert len(result) == 1
    assert points[0] is original
    assert original.reference_xy == (20.0, 21.0)
    assert original.residual == 0.9
    assert math.isfinite(result[0].reference_xy[0])
    assert math.isfinite(result[0].reference_xy[1])


def test_deterministic_repeatability(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    points = [_cp((20.0, 20.0), (20.0, 20.0)), _cp((28.0, 24.0), (28.0, 24.0))]
    first = refine_points_with_settings(points, pair, _settings())
    second = refine_points_with_settings(points, pair, _settings())
    assert [(p.source_xy, p.reference_xy) for p in first] == [
        (p.source_xy, p.reference_xy) for p in second
    ]


def test_uncertainty_is_not_fabricated(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    success_point = _cp((20.0, 20.0), (20.0, 20.0), uncertainty=None)
    failed_point = _cp((float("nan"), 20.0), (20.0, 20.0), uncertainty=None)
    stale = _cp((2.0, 2.0), (2.0, 2.0), uncertainty=1.23)
    result = refine_points_with_settings(
        [success_point, failed_point, stale], pair, _settings()
    )
    assert result[0].uncertainty is None
    assert result[1].uncertainty is None
    assert result[2].uncertainty == 1.23


def test_multiband_software_raster_uses_engineering_mean(tmp_path: Path) -> None:
    plane = _texture(48, 48)
    stacked = np.stack([plane, plane, plane], axis=2)
    pair = _pair(tmp_path, stacked, stacked)
    point = _cp((22.0, 22.0), (22.0, 22.0))
    result = refine_points_with_settings([point], pair, _settings())
    dx = result[0].reference_xy[0] - 22.0
    dy = result[0].reference_xy[1] - 22.0
    assert math.hypot(dx, dy) < 0.05


def test_output_displacement_is_not_a_token_epsilon(tmp_path: Path) -> None:
    image = _texture(48, 48)
    pair = _pair(tmp_path, image, image)
    point = _cp((22.0, 22.0), (22.0, 22.0))
    result = refine_points_with_settings([point], pair, _settings())
    dx = result[0].reference_xy[0] - point.reference_xy[0]
    dy = result[0].reference_xy[1] - point.reference_xy[1]
    assert (dx, dy) != (0.001, 0.001)
    assert math.hypot(dx - 0.001, dy - 0.001) > 0.0


def test_estimate_rejects_mismatched_ndim() -> None:
    source = _texture(32, 32)
    displacement = estimate_zncc_displacement(
        source,
        np.stack([source, source], axis=2),
        (16.0, 16.0),
        (16.0, 16.0),
        _settings(),
    )
    assert displacement is None


def test_refinement_package_does_not_import_registration_or_evaluation() -> None:
    import src.refinement as refinement_pkg
    import src.refinement.refine as refine_mod
    import src.refinement.zncc as zncc_mod

    for module in (refinement_pkg, refine_mod, zncc_mod):
        assert not hasattr(module, "register")
        assert "src.registration" not in getattr(module, "__dict__", {})
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "src.registration" not in source
        assert "src.evaluation" not in source
        assert "src.verification" not in source
        assert "src.control_points" not in source
