"""Parse the public PDS3 label of M150368601RC without the image samples."""

from __future__ import annotations

from pathlib import Path

from src.ingestion.lroc_pds3 import (
    _REQUIRED_KEYS,
    _as_int,
    _as_str,
    _parse_label_text,
    _parse_saturation_values,
)

_LABEL_PATH = Path(__file__).parent / "data" / "M150368601RC_label.txt"


def test_real_m150368601rc_label_has_required_keys() -> None:
    values = _parse_label_text(_LABEL_PATH.read_text(encoding="utf-8"))
    missing = [key for key in _REQUIRED_KEYS if key not in values]
    assert missing == []
    assert _as_int(values["LINES"]) == 52224
    assert _as_int(values["LINE_SAMPLES"]) == 5064
    assert _as_int(values["SAMPLE_BITS"]) == 16
    assert _as_str(values["SAMPLE_TYPE"]) == "LSB_INTEGER"
    assert _as_int(values["NULL"]) == -32768
    assert _as_str(values["UNIT"]) == "Scaled I/F"
    assert _as_str(values["TARGET_NAME"]) == "MOON"
    assert _as_str(values["INSTRUMENT_NAME"]) == "LUNAR RECONNAISSANCE ORBITER CAMERA"
    saturation = _parse_saturation_values(values)
    assert -32767 in saturation
    assert -32766 in saturation
    assert -32765 in saturation
    assert -32764 in saturation
