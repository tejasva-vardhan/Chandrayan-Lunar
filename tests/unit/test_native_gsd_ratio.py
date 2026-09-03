"""Unit tests for native GSD ratio helper."""

from __future__ import annotations

from src.io.ps_scale_multimodal.config import (
    PAIR_02_LROC_CATALOG_GSD_METERS,
    PAIR_02_OHRC_GSD_METERS,
)
from src.io.ps_scale_multimodal.decision import native_gsd_ratio


def test_native_gsd_ratio_pair_02_expected() -> None:
    ratio = native_gsd_ratio(PAIR_02_OHRC_GSD_METERS, PAIR_02_LROC_CATALOG_GSD_METERS)
    assert ratio is not None
    assert abs(ratio - 0.56) < 1e-9


def test_native_gsd_ratio_rejects_missing_or_nonpositive() -> None:
    assert native_gsd_ratio(None, 0.5) is None
    assert native_gsd_ratio(0.28, None) is None
    assert native_gsd_ratio(0.0, 0.5) is None
    assert native_gsd_ratio(0.28, -1.0) is None
