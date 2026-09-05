"""Unit checks for diagnostic preview crop metadata."""

from __future__ import annotations

from api.preview import _compute_crop_meta, _crop_dict
from src.io.exp000.diagnostic import DiagnosticWindow
from src.models.common import ImageDimensions
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.models.registration_result import ControlPoint, RegistrationResult


def test_crop_dict_includes_display_scale_when_downsampled() -> None:
    window = DiagnosticWindow(row=10, col=20, height=3000, width=4000)
    meta = _crop_dict(window)
    assert meta["row"] == 10
    assert meta["col"] == 20
    assert meta["height"] == 3000
    assert meta["width"] == 4000
    assert float(meta["display_scale"]) < 1.0
    assert max(int(meta["display_height"]), int(meta["display_width"])) == 1280


def test_compute_crop_meta_covers_control_points() -> None:
    pair = RegistrationPair(
        pair_id="p",
        source=LunarProduct(
            product_id="src",
            instrument="OHRC",
            dimensions=ImageDimensions(width_px=200, height_px=100),
            raster_uri="memory://src",
        ),
        reference=LunarProduct(
            product_id="ref",
            instrument="LRO_NAC",
            dimensions=ImageDimensions(width_px=200, height_px=200),
            raster_uri="memory://ref",
        ),
    )
    result = RegistrationResult(
        pair_id="p",
        control_points=[
            ControlPoint(source_xy=(40.0, 30.0), reference_xy=(50.0, 60.0), residual=0.1),
            ControlPoint(source_xy=(45.0, 35.0), reference_xy=(55.0, 65.0), residual=0.1),
        ],
    )
    meta = _compute_crop_meta(pair, result)
    assert meta["source_crop"] is not None
    assert meta["reference_crop"] is not None
    sc = meta["source_crop"]
    rc = meta["reference_crop"]
    assert sc["col"] <= 40 <= sc["col"] + sc["width"] - 1
    assert sc["row"] <= 30 <= sc["row"] + sc["height"] - 1
    assert rc["col"] <= 50 <= rc["col"] + rc["width"] - 1
    assert rc["row"] <= 60 <= rc["row"] + rc["height"] - 1
