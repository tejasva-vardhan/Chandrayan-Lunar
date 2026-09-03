"""EXP-005 diagnostic helpers. Not lunar accuracy evidence."""

from __future__ import annotations

from src.io.exp005.diagnostics import (
    coordinate_displacement_px,
    coordinates_changed,
    displacement_report,
)
from src.models.registration_result import ControlPoint


def _cp(
    source: tuple[float, float], reference: tuple[float, float]
) -> ControlPoint:
    return ControlPoint(source_xy=source, reference_xy=reference, residual=0.5)


def test_displacement_report_counts_reference_shifts_only() -> None:
    original = [_cp((10.0, 20.0), (30.0, 40.0)), _cp((1.0, 2.0), (3.0, 4.0))]
    refined = [_cp((10.0, 20.0), (30.3, 40.4)), _cp((1.0, 2.0), (3.0, 4.0))]

    report = displacement_report(original, refined)

    assert report["coordinates_changed_count"] == 1
    assert report["outcome"] == "COORDINATES_UPDATED"
    import math as _math
    assert _math.isclose(report["mean_displacement_pixels"], 0.25, rel_tol=1e-9)
    assert _math.isclose(report["mean_displacement_among_changed_pixels"], 0.5, rel_tol=1e-9)
    assert _math.isclose(report["max_displacement_pixels"], 0.5, rel_tol=1e-9)
    assert _math.isclose(report["per_point_displacement_pixels"][0], 0.5, rel_tol=1e-9)
    assert report["per_point_displacement_pixels"][1] == 0.0  # exact zero, identity
    limitation_lower = report["limitation"].lower()
    assert "not accuracy" in limitation_lower or "not evidence" in limitation_lower


def test_identity_displacements_are_indeterminate() -> None:
    points = [_cp((5.0, 6.0), (7.0, 8.0))]
    report = displacement_report(points, [_cp((5.0, 6.0), (7.0, 8.0))])
    assert report["coordinates_changed_count"] == 0
    assert report["outcome"] == "INDETERMINATE"
    assert report["mean_displacement_pixels"] == 0.0
    assert report["max_displacement_pixels"] == 0.0


def test_coordinate_helpers_detect_source_or_reference_change() -> None:
    before = _cp((0.0, 0.0), (1.0, 1.0))
    after = _cp((0.0, 0.0), (2.0, 1.0))
    assert coordinates_changed(before, after)
    assert coordinate_displacement_px(before, after) == 1.0
    assert not coordinates_changed(before, before)
    assert coordinate_displacement_px(before, before) == 0.0
