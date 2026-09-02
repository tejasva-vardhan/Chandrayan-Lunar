from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from src.ingestion import (
    LrocPds3Error,
    ingest_lroc_pds3_product,
    ingest_product,
    load_lroc_pds3_raster,
    read_lroc_pds3_label,
)


def _write_synthetic_pds3(
    path: Path,
    array: np.ndarray,
    *,
    record_bytes: int,
    label_records: int,
    file_records: int | None = None,
    sample_bits: int = 16,
    sample_type: str = "LSB_INTEGER",
    image_pointer: int | str | None = None,
    null_value: int = -32768,
    valid_minimum: int = -32752,
    low_saturation: int = -32767,
    high_saturation: int = 32767,
    low_instr_saturation: int = -32766,
    high_instr_saturation: int = -32765,
    start_time: str | None = "2026-08-31T00:00:00Z",
    stop_time: str | None = "2026-08-31T00:10:00Z",
) -> Path:
    if array.dtype != np.int16:
        raise AssertionError("synthetic PDS3 builder expects int16 input")
    if image_pointer is None:
        image_pointer = label_records + 1
    lines, line_samples = array.shape
    label_lines = [
        "PDS_VERSION_ID = PDS3",
        f"RECORD_BYTES = {record_bytes}",
        f"FILE_RECORDS = {file_records}",
        f"LABEL_RECORDS = {label_records}",
        f"^IMAGE = {image_pointer}",
        f"LINES = {lines}",
        f"LINE_SAMPLES = {line_samples}",
        f"SAMPLE_BITS = {sample_bits}",
        f'SAMPLE_TYPE = "{sample_type}"',
        "SCALING_FACTOR = 3.05185094759972e-05",
        f"VALID_MINIMUM = {valid_minimum}",
        f"NULL = {null_value}",
        f"LOW_REPR_SATURATION = {low_saturation}",
        f"HIGH_REPR_SATURATION = {high_saturation}",
        f"LOW_INSTR_SATURATION = {low_instr_saturation}",
        f"HIGH_INSTR_SATURATION = {high_instr_saturation}",
        'UNIT = "Scaled I/F"',
        'TARGET_NAME = "MOON"',
        'INSTRUMENT_NAME = "LUNAR RECONNAISSANCE ORBITER CAMERA"',
    ]
    if start_time is not None:
        label_lines.append(f'START_TIME = "{start_time}"')
    if stop_time is not None:
        label_lines.append(f'STOP_TIME = "{stop_time}"')
    label_lines.append("END")
    label_text = "\n".join(label_lines) + "\n"
    label_bytes = label_text.encode("latin-1")
    padded_label_size = record_bytes * label_records
    if len(label_bytes) > padded_label_size:
        record_bytes = (len(label_bytes) + label_records - 1) // label_records
        label_lines[1] = f"RECORD_BYTES = {record_bytes}"
        label_text = "\n".join(label_lines) + "\n"
        label_bytes = label_text.encode("latin-1")
        padded_label_size = record_bytes * label_records
    if len(label_bytes) > padded_label_size:
        raise AssertionError("label text does not fit into declared label records")
    label_bytes = label_bytes + (b" " * (padded_label_size - len(label_bytes)))

    image_bytes = array.astype("<i2", copy=False).tobytes(order="C")
    image_padding = (-len(image_bytes)) % record_bytes
    padded_image_bytes = image_bytes + (b"\x00" * image_padding)
    image_record_count = len(padded_image_bytes) // record_bytes
    if file_records is None:
        file_records = label_records + image_record_count

    label_lines[2] = f"FILE_RECORDS = {file_records}"
    label_text = "\n".join(label_lines) + "\n"
    label_bytes = label_text.encode("latin-1")
    if len(label_bytes) > padded_label_size:
        raise AssertionError("label text does not fit into declared label records")
    label_bytes = label_bytes + (b" " * (padded_label_size - len(label_bytes)))

    with path.open("wb") as handle:
        handle.write(label_bytes)
        handle.write(padded_image_bytes)
    return path


def test_reads_one_record_embedded_label_and_decodes_int16(tmp_path: Path) -> None:
    array = np.array([[1, 2, -3, 0], [-32768, 100, -32767, 32767]], dtype=np.int16)
    path = _write_synthetic_pds3(
        tmp_path / "one_record.IMG", array, record_bytes=512, label_records=1
    )

    label = read_lroc_pds3_label(path)
    raster, valid_mask = load_lroc_pds3_raster(path, label)

    assert label.label_records == 1
    assert label.lines == 2
    assert label.line_samples == 4
    assert label.image_offset_bytes == label.record_bytes * label.label_records
    assert np.array_equal(raster, array)
    assert valid_mask.dtype == bool
    assert valid_mask.tolist() == [[True, True, True, True], [False, True, False, False]]


def test_reads_two_record_embedded_label_from_image_pointer(tmp_path: Path) -> None:
    array = np.arange(12, dtype=np.int16).reshape(3, 4)
    path = _write_synthetic_pds3(
        tmp_path / "two_record.IMG",
        array,
        record_bytes=512,
        label_records=2,
        image_pointer=3,
    )

    label = read_lroc_pds3_label(path)
    raster, valid_mask = load_lroc_pds3_raster(path, label)

    assert label.label_records == 2
    assert label.image_offset_bytes == 1024
    assert np.array_equal(raster, array)
    assert valid_mask.all()


def test_ingest_materializes_lunar_product_and_preserves_metadata(tmp_path: Path) -> None:
    array = np.array([[0, 1, 2, 3], [4, 5, -32768, 6]], dtype=np.int16)
    path = _write_synthetic_pds3(tmp_path / "product.IMG", array, record_bytes=512, label_records=1)

    product = ingest_lroc_pds3_product(path)

    assert product.product_id == "product"
    assert product.instrument == "LRO_NAC"
    assert product.mission == "LRO"
    assert product.dimensions is not None
    assert product.dimensions.width_px == 4
    assert product.dimensions.height_px == 2
    assert product.acquisition_time == datetime(2026, 8, 31, 0, 0, tzinfo=UTC)
    assert product.valid_pixel_ratio == pytest.approx(7 / 8)
    assert product.raster_uri is not None
    assert product.mask_uri is not None
    assert np.array_equal(np.load(product.raster_uri), array)
    assert np.load(product.raster_uri).dtype == np.dtype("<i2")
    assert np.array_equal(
        np.load(product.mask_uri),
        np.array([[True, True, True, True], [True, True, False, True]]),
    )
    assert product.provenance is not None
    assert product.provenance.source_uri == path.name
    assert product.provenance.reader == "lroc_pds3_embedded_label"
    assert product.provenance.notes is not None
    assert "instrument_name=LUNAR RECONNAISSANCE ORBITER CAMERA" in product.provenance.notes


def test_dispatches_lroc_from_embedded_label_not_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The public dispatcher accepts the declared PDS3 identity, not its name."""
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path / "manifests"))
    path = _write_synthetic_pds3(
        tmp_path / "arbitrary-name.IMG",
        np.arange(8, dtype=np.int16).reshape(2, 4),
        record_bytes=512,
        label_records=1,
    )

    product = ingest_product(path)

    assert product.product_id == "arbitrary-name"
    assert product.provenance is not None
    assert product.provenance.reader == "lroc_pds3_embedded_label"


def test_instrument_saturation_sentinels_are_invalid(tmp_path: Path) -> None:
    """Real LROC CDR labels declare instrument saturation sentinels; mask them."""
    array = np.array([[-32766, -32765], [0, 1]], dtype=np.int16)
    path = _write_synthetic_pds3(
        tmp_path / "instr_sat.IMG", array, record_bytes=512, label_records=1
    )

    label = read_lroc_pds3_label(path)
    _raster, valid_mask = load_lroc_pds3_raster(path, label)

    assert -32766 in label.saturation_values
    assert -32765 in label.saturation_values
    assert valid_mask.tolist() == [[False, False], [True, True]]


def test_zero_is_not_treated_as_invalid(tmp_path: Path) -> None:
    array = np.array([[0, 0], [1, -32768]], dtype=np.int16)
    path = _write_synthetic_pds3(tmp_path / "zeros.IMG", array, record_bytes=512, label_records=1)

    _raster, valid_mask = load_lroc_pds3_raster(path)

    assert valid_mask.tolist() == [[True, True], [True, False]]


def test_rejects_wrong_sample_bits(tmp_path: Path) -> None:
    array = np.arange(8, dtype=np.int16).reshape(2, 4)
    path = _write_synthetic_pds3(
        tmp_path / "bad_bits.IMG",
        array,
        record_bytes=512,
        label_records=1,
        sample_bits=8,
    )

    with pytest.raises(LrocPds3Error, match="SAMPLE_BITS"):
        read_lroc_pds3_label(path)


def test_rejects_wrong_sample_type(tmp_path: Path) -> None:
    array = np.arange(8, dtype=np.int16).reshape(2, 4)
    path = _write_synthetic_pds3(
        tmp_path / "bad_type.IMG",
        array,
        record_bytes=512,
        label_records=1,
        sample_type="MSB_INTEGER",
    )

    with pytest.raises(LrocPds3Error, match="SAMPLE_TYPE"):
        read_lroc_pds3_label(path)


def test_rejects_file_size_mismatch(tmp_path: Path) -> None:
    array = np.arange(8, dtype=np.int16).reshape(2, 4)
    path = _write_synthetic_pds3(
        tmp_path / "bad_size.IMG",
        array,
        record_bytes=512,
        label_records=1,
        file_records=99,
    )

    with pytest.raises(LrocPds3Error, match="file size mismatch"):
        read_lroc_pds3_label(path)


def test_rejects_truncated_file(tmp_path: Path) -> None:
    array = np.arange(8, dtype=np.int16).reshape(2, 4)
    path = _write_synthetic_pds3(
        tmp_path / "truncated.IMG", array, record_bytes=512, label_records=1
    )
    data = path.read_bytes()[:-2]
    path.write_bytes(data)

    with pytest.raises(LrocPds3Error, match="file size mismatch|declared image extent exceeds"):
        read_lroc_pds3_label(path)


def test_repeated_reads_are_deterministic(tmp_path: Path) -> None:
    array = np.arange(12, dtype=np.int16).reshape(3, 4)
    path = _write_synthetic_pds3(tmp_path / "repeat.IMG", array, record_bytes=512, label_records=1)

    first_raster, first_mask = load_lroc_pds3_raster(path)
    second_raster, second_mask = load_lroc_pds3_raster(path)

    assert np.array_equal(first_raster, second_raster)
    assert np.array_equal(first_mask, second_mask)


def test_uses_memmap_for_raster_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    array = np.arange(8, dtype=np.int16).reshape(2, 4)
    path = _write_synthetic_pds3(tmp_path / "memmap.IMG", array, record_bytes=512, label_records=1)
    called: dict[str, object] = {}
    real_memmap = np.memmap

    def tracking_memmap(*args: object, **kwargs: object) -> np.memmap:
        called["used"] = True
        return real_memmap(*args, **kwargs)

    monkeypatch.setattr(np, "memmap", tracking_memmap)
    raster, _mask = load_lroc_pds3_raster(path)

    assert called["used"] is True
    assert np.array_equal(raster, array)


def test_ingest_streams_raster_in_row_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.ingestion.lroc_pds3._MATERIALIZE_CHUNK_ROWS", 1)
    array = np.arange(12, dtype=np.int16).reshape(3, 4)
    path = _write_synthetic_pds3(tmp_path / "chunked.IMG", array, record_bytes=512, label_records=1)

    product = ingest_lroc_pds3_product(path)
    written = np.load(product.raster_uri)

    assert written.dtype == np.dtype("<i2")
    assert np.array_equal(written, array)


def test_missing_optional_timestamps_stay_unset(tmp_path: Path) -> None:
    array = np.arange(8, dtype=np.int16).reshape(2, 4)
    path = _write_synthetic_pds3(
        tmp_path / "no_time.IMG",
        array,
        record_bytes=512,
        label_records=1,
        start_time=None,
        stop_time=None,
    )

    label = read_lroc_pds3_label(path)
    product = ingest_lroc_pds3_product(path)

    assert label.start_time is None
    assert label.stop_time is None
    assert product.acquisition_time is None
