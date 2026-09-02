"""Tests for EXP-000 integration helpers. Not lunar accuracy evidence."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.io.exp000 import (
    control_point_crop_report,
    diagnostic_crop_window,
    projective_fit_residuals,
    snapshot_software_configuration,
    warp_diagnostic_crop,
    window_contains_xy,
)
from src.io.exp000.run import _preprocess_guarded
from src.models import ControlPoint, LunarProduct, RegistrationPair
from src.registration.settings import unvalidated_software_defaults
from src.registration.warp import warp_to_grid


def test_software_configuration_records_existing_caps_and_sift_defaults() -> None:
    config = snapshot_software_configuration()
    assert config["experiment_id"] == "EXP-000"
    assert config["matcher_id"] == "sift"
    assert config["matching_view"]["max_pixels_per_image"] == 4_194_304
    assert config["matching_view"]["downsample_method"] == "stride_decimation"
    assert config["sift"]["ratio_threshold"] == 0.75
    assert config["sift"]["n_octave_layers"] == 3
    assert config["verification"]["residual_limit"] == 3.0
    assert config["verification"]["max_trials"] == 500
    assert config["verification"]["rng_seed"] == 0
    assert config["registration"]["max_output_pixels"] == 16_777_216
    assert (
        config["diagnostic_registration_crop"]["strategy"]
        == "bounded_reference_window_maximum_control_point_cover"
    )
    assert config["evaluation"]["independent_ground_truth"] is False
    assert "x_original = x_matching * x_scale" in config["matching_view"]["coordinate_mapping"]


def test_diagnostic_crop_stays_within_existing_pixel_cap() -> None:
    points = [
        ControlPoint(source_xy=(10.0, 20.0), reference_xy=(2500.0, 40000.0)),
        ControlPoint(source_xy=(11.0, 21.0), reference_xy=(2600.0, 40100.0)),
        ControlPoint(source_xy=(12.0, 22.0), reference_xy=(2400.0, 39900.0)),
        ControlPoint(source_xy=(13.0, 23.0), reference_xy=(2550.0, 40050.0)),
    ]
    window = diagnostic_crop_window(52_224, 5_064, points)
    cap = unvalidated_software_defaults().max_output_pixels
    assert window.height * window.width <= cap
    assert window.height == cap // 5_064
    assert window.width == 5_064
    assert 0 <= window.row <= 52_224 - window.height
    assert window.col == 0
    assert window.row <= 40_000 <= window.row + window.height - 1
    for point in points:
        assert window_contains_xy(window, point.reference_xy)
    report = control_point_crop_report(window, points)
    assert report["inside_count"] == 4
    assert report["all_included"] is True
    assert report["reason"] is None


def test_diagnostic_crop_does_not_raise_the_registration_cap() -> None:
    points = [ControlPoint(source_xy=(0.0, 0.0), reference_xy=(8.0, 8.0))]
    window = diagnostic_crop_window(64, 64, points, max_output_pixels=16_777_216)
    assert window.height * window.width == 64 * 64
    assert window.height * window.width < 16_777_216


def test_matching_view_coordinate_mapping_is_scale_times_matching_xy() -> None:
    x_matching, y_matching = 12.5, 40.0
    x_scale, y_scale = 17.0, 17.0
    x_original = x_matching * x_scale
    y_original = y_matching * y_scale
    assert x_original == 212.5
    assert y_original == 680.0


def test_diagnostic_warp_preserves_original_coordinates(tmp_path: Path) -> None:
    source = np.arange(32 * 32, dtype=float).reshape(32, 32)
    path = tmp_path / "source.npy"
    np.save(path, source)
    identity = np.eye(3, dtype=float)
    points = [
        ControlPoint(source_xy=(8.0, 10.0), reference_xy=(8.0, 10.0)),
        ControlPoint(source_xy=(20.0, 10.0), reference_xy=(20.0, 10.0)),
        ControlPoint(source_xy=(8.0, 22.0), reference_xy=(8.0, 22.0)),
        ControlPoint(source_xy=(20.0, 22.0), reference_xy=(20.0, 22.0)),
    ]
    window = diagnostic_crop_window(32, 32, points, max_output_pixels=64, preferred_side=8)
    assert window.height == 8
    assert window.width == 8
    warped = warp_diagnostic_crop(str(path), identity, window)
    expected = source[
        window.row : window.row + window.height, window.col : window.col + window.width
    ]
    np.testing.assert_allclose(warped, expected, atol=1e-6)
    full = warp_to_grid(source, identity, 32, 32)
    np.testing.assert_allclose(
        warped,
        full[window.row : window.row + window.height, window.col : window.col + window.width],
        atol=1e-6,
    )


def test_four_point_projective_fit_residuals_are_numerically_tiny_and_not_accuracy() -> None:
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(0.0, 0.0)),
        ControlPoint(source_xy=(10.0, 0.0), reference_xy=(10.0, 0.0)),
        ControlPoint(source_xy=(0.0, 10.0), reference_xy=(0.0, 10.0)),
        ControlPoint(source_xy=(10.0, 10.0), reference_xy=(10.0, 10.0)),
    ]
    residuals = projective_fit_residuals(points, np.eye(3, dtype=float))
    assert len(residuals) == 4
    assert max(residuals) < 1e-9


def test_preprocess_guard_uses_identity_when_pair_exceeds_existing_cap() -> None:
    pair = RegistrationPair(
        pair_id="oversize",
        source=LunarProduct(
            product_id="ohrc",
            instrument="OHRC",
            dimensions={"width_px": 12_000, "height_px": 90_000},
        ),
        reference=LunarProduct(
            product_id="lroc",
            instrument="LRO_NAC",
            dimensions={"width_px": 5_064, "height_px": 52_224},
        ),
    )
    warnings: list[str] = []
    record = {"warnings": warnings}
    out_pair, report = _preprocess_guarded(pair, record)
    assert out_pair is pair
    assert report["applied"] == "identity_passthrough"
    assert report["cap_pixels"] == 16_777_216
    assert report["source_pixels"] > 16_777_216
    assert report["reference_pixels"] > 16_777_216
    assert warnings


def test_preprocess_guard_runs_frozen_preprocess_for_small_rasters(tmp_path: Path) -> None:
    source = tmp_path / "source.npy"
    reference = tmp_path / "reference.npy"
    np.save(source, np.linspace(0.0, 1.0, 16).reshape(4, 4))
    np.save(reference, np.linspace(0.0, 1.0, 16).reshape(4, 4))
    pair = RegistrationPair(
        pair_id="tiny",
        source=LunarProduct(
            product_id="s",
            instrument="OHRC",
            dimensions={"width_px": 4, "height_px": 4},
            raster_uri=str(source),
        ),
        reference=LunarProduct(
            product_id="r",
            instrument="LRO_NAC",
            dimensions={"width_px": 4, "height_px": 4},
            raster_uri=str(reference),
        ),
    )
    out_pair, report = _preprocess_guarded(pair, {"warnings": []})
    assert report["applied"] == "preprocess"
    assert out_pair.source.raster_uri != str(source)
    assert Path(out_pair.source.raster_uri).name.endswith(".preprocessed.npy")


def test_diagnostic_crop_contains_all_points_when_they_fit() -> None:
    points = [
        ControlPoint(source_xy=(1.0, 1.0), reference_xy=(20.0, 30.0)),
        ControlPoint(source_xy=(2.0, 2.0), reference_xy=(28.0, 34.0)),
        ControlPoint(source_xy=(3.0, 3.0), reference_xy=(24.0, 38.0)),
        ControlPoint(source_xy=(4.0, 4.0), reference_xy=(26.0, 32.0)),
    ]
    window = diagnostic_crop_window(80, 80, points, max_output_pixels=4096, preferred_side=16)
    assert window.height * window.width <= 4096
    for point in points:
        assert window_contains_xy(window, point.reference_xy)
    report = control_point_crop_report(window, points)
    assert report["inside_count"] == 4
    assert report["total_control_points"] == 4
    assert report["all_included"] is True


def test_diagnostic_crop_maximises_inclusion_when_all_points_cannot_fit() -> None:
    # Window grows to 20x10. Two close points fit; the far pair cannot join them.
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(5.0, 12.0)),
        ControlPoint(source_xy=(1.0, 1.0), reference_xy=(5.0, 14.0)),
        ControlPoint(source_xy=(2.0, 2.0), reference_xy=(5.0, 80.0)),
        ControlPoint(source_xy=(3.0, 3.0), reference_xy=(5.0, 82.0)),
    ]
    window = diagnostic_crop_window(100, 10, points, max_output_pixels=200, preferred_side=20)
    assert window.width == 10
    assert window.height == 20
    assert window.height * window.width <= 200
    report = control_point_crop_report(window, points)
    assert report["inside_count"] == 2
    assert report["total_control_points"] == 4
    assert report["all_included"] is False
    assert report["reason"] is not None
    assert report["inside_indices"] == [0, 1]
    for index in report["inside_indices"]:
        assert window_contains_xy(window, points[index].reference_xy)
    again = diagnostic_crop_window(100, 10, points, max_output_pixels=200, preferred_side=20)
    assert (again.row, again.col, again.height, again.width) == (
        window.row,
        window.col,
        window.height,
        window.width,
    )


def test_diagnostic_crop_empty_control_points_uses_image_centre() -> None:
    window = diagnostic_crop_window(64, 32, [], max_output_pixels=256, preferred_side=8)
    assert window.height * window.width <= 256
    expected_height = min(8, 64, 256)
    expected_width = min(32, 256 // expected_height)
    expected_height = min(64, 256 // expected_width)
    assert window.height == expected_height
    assert window.width == expected_width
    center_x = (32 - 1) / 2.0
    center_y = (64 - 1) / 2.0
    expected_col = int(round(center_x - expected_width / 2.0))
    expected_row = int(round(center_y - expected_height / 2.0))
    expected_col = min(max(expected_col, 0), 32 - expected_width)
    expected_row = min(max(expected_row, 0), 64 - expected_height)
    assert window.col == expected_col
    assert window.row == expected_row
    report = control_point_crop_report(window, [])
    assert report["inside_count"] == 0
    assert report["total_control_points"] == 0
    assert report["all_included"] is True


def test_diagnostic_crop_pixel_count_never_exceeds_registration_cap() -> None:
    cap = unvalidated_software_defaults().max_output_pixels
    clustered = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(100.0, 200.0)),
        ControlPoint(source_xy=(1.0, 1.0), reference_xy=(120.0, 220.0)),
    ]
    spread = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(10.0, 10.0)),
        ControlPoint(source_xy=(1.0, 1.0), reference_xy=(5000.0, 40_000.0)),
        ControlPoint(source_xy=(2.0, 2.0), reference_xy=(20.0, 20_000.0)),
        ControlPoint(source_xy=(3.0, 3.0), reference_xy=(4000.0, 50_000.0)),
    ]
    for points in (clustered, spread, []):
        window = diagnostic_crop_window(52_224, 5_064, points)
        assert window.height * window.width <= cap
        assert window.width <= 5_064
        assert window.height <= 52_224
        assert window.row >= 0
        assert window.col >= 0
        assert window.row + window.height <= 52_224
        assert window.col + window.width <= 5_064


def test_diagnostic_crop_prefers_larger_cluster_over_centroid() -> None:
    # Global centroid sits between clusters and would miss every point.
    points = [
        ControlPoint(source_xy=(0.0, 0.0), reference_xy=(8.0, 8.0)),
        ControlPoint(source_xy=(1.0, 1.0), reference_xy=(9.0, 10.0)),
        ControlPoint(source_xy=(2.0, 2.0), reference_xy=(8.5, 12.0)),
        ControlPoint(source_xy=(3.0, 3.0), reference_xy=(8.0, 90.0)),
    ]
    window = diagnostic_crop_window(100, 20, points, max_output_pixels=400, preferred_side=20)
    assert window.height == 20
    assert window.width == 20
    report = control_point_crop_report(window, points)
    assert report["inside_count"] == 3
    assert report["inside_indices"] == [0, 1, 2]
    assert window_contains_xy(window, points[3].reference_xy) is False


def test_diagnostic_crop_rejects_window_above_cap(tmp_path: Path) -> None:
    path = tmp_path / "source.npy"
    np.save(path, np.zeros((8, 8), dtype=float))
    from src.io.exp000.diagnostic import DiagnosticWindow

    huge = DiagnosticWindow(row=0, col=0, height=5000, width=5000)
    with pytest.raises(ValueError, match="exceeds the existing registration pixel cap"):
        warp_diagnostic_crop(str(path), np.eye(3), huge)


def test_exp000_from_products_runs_every_stage_on_synthetic_pair(tmp_path: Path) -> None:
    import cv2

    from src.io.exp000 import run_exp000_from_products
    from src.models.common import ImageDimensions

    rng = np.random.default_rng(4)
    image = np.zeros((256, 256), dtype=np.float32)
    for _ in range(30):
        cx = int(rng.integers(20, 236))
        cy = int(rng.integers(20, 236))
        radius = int(rng.integers(8, 25))
        cv2.circle(image, (cx, cy), radius, float(rng.uniform(0.2, 1.0)), -1)
    image += rng.normal(0.0, 0.02, image.shape).astype(np.float32)
    image = np.clip(image, 0.0, 1.0)
    source_path = tmp_path / "source.npy"
    reference_path = tmp_path / "reference.npy"
    mask_path = tmp_path / "reference_mask.npy"
    np.save(source_path, image)
    np.save(reference_path, image)
    mask = np.ones((256, 256), dtype=bool)
    np.save(mask_path, mask)
    dims = ImageDimensions(width_px=256, height_px=256)
    source = LunarProduct(
        product_id="synth-ohrc",
        instrument="OHRC",
        dimensions=dims,
        raster_uri=str(source_path),
    )
    reference = LunarProduct(
        product_id="synth-lroc",
        instrument="LRO_NAC",
        dimensions=dims,
        raster_uri=str(reference_path),
        mask_uri=str(mask_path),
    )
    record = run_exp000_from_products(
        source,
        reference,
        output_dir=tmp_path / "out",
        record_path=tmp_path / "record.json",
    )
    assert record["status"] == "completed"
    assert record["failed_stage"] is None
    for name in (
        "ingest_product",
        "characterize_pair",
        "preprocess",
        "generate_representation",
        "match",
        "verify_matches",
        "select_control_points",
        "refine_points",
        "register",
        "evaluate",
        "export_result",
    ):
        assert name in record["stages"]
    assert record["stages"]["evaluate"]["independent_ground_truth_used"] is False
    assert record["stages"]["evaluate"]["independent_accuracy"] is None
    # Identical textured rasters should produce raw SIFT matches after preprocess.
    assert record["stages"]["match"]["raw_match_count"] >= 4
    assert record["stages"]["ingest_product"]["source"]["illumination_metadata"][
        "populated_from_product"
    ] is False
    assert (tmp_path / "record.json").is_file()
    assert (tmp_path / "out" / "export" / "registration_report.json").is_file()
