"""LROC PDS3 ingestion adapter.

Reads embedded-label LROC PDS3 ``.IMG`` products and materializes software
``.npy`` raster/mask handles compatible with the frozen ``LunarProduct``
contract. This adapter does not change geometry, scale, orientation, or units.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from src.ingestion._derived import derived_output_path
from src.models.common import ImageDimensions, Provenance
from src.models.lunar_product import LunarProduct

_READER_ID = "lroc_pds3_embedded_label"
_REQUIRED_KEYS = (
    "RECORD_BYTES",
    "FILE_RECORDS",
    "LABEL_RECORDS",
    "^IMAGE",
    "LINES",
    "LINE_SAMPLES",
    "SAMPLE_BITS",
    "SAMPLE_TYPE",
    "SCALING_FACTOR",
    "VALID_MINIMUM",
    "NULL",
    "UNIT",
    "TARGET_NAME",
    "INSTRUMENT_NAME",
)
_SUPPORTED_SAMPLE_BITS = 16
_SUPPORTED_SAMPLE_TYPE = "LSB_INTEGER"
_SATURATION_KEYS = (
    "LOW_REPR_SATURATION",
    "HIGH_REPR_SATURATION",
    "LOW_INSTR_SATURATION",
    "HIGH_INSTR_SATURATION",
    "CORE_LOW_REPR_SATURATION",
    "CORE_HIGH_REPR_SATURATION",
    "SATURATION_VALUE",
)
_MATERIALIZE_CHUNK_ROWS = 1024


class LrocPds3Error(ValueError):
    """Raised when a product cannot be decoded as a supported LROC PDS3 image."""


@dataclass(frozen=True)
class LrocPds3Label:
    record_bytes: int
    file_records: int
    label_records: int
    image_pointer: int | str
    image_offset_bytes: int
    lines: int
    line_samples: int
    sample_bits: int
    sample_type: str
    scaling_factor: float
    valid_minimum: int
    null_value: int
    unit: str
    target_name: str
    instrument_name: str
    start_time: datetime | None
    stop_time: datetime | None
    saturation_values: tuple[int, ...]


def ingest_lroc_pds3_product(path: Path) -> LunarProduct:
    """Read one LROC PDS3 product and return a compatible LunarProduct."""

    source = Path(path)
    label = read_lroc_pds3_label(source)
    raster_uri = _derived_uri(source, ".lroc.npy")
    mask_uri = _derived_uri(source, ".lroc.mask.npy")
    valid_ratio = _materialize_lroc_handles(source, label, raster_uri, mask_uri)
    acquisition_time = label.start_time if label.start_time is not None else label.stop_time
    notes = (
        f"format=PDS3_embedded_label; "
        f"image_offset_bytes={label.image_offset_bytes}; "
        f"sample_type={label.sample_type}; "
        f"sample_bits={label.sample_bits}; "
        f"unit={label.unit}; "
        f"scaling_factor={label.scaling_factor}; "
        f"null={label.null_value}; "
        f"saturation_values={list(label.saturation_values)}; "
        f"target_name={label.target_name}; "
        f"instrument_name={label.instrument_name}; "
        f"start_time={label.start_time.isoformat() if label.start_time else None}; "
        f"stop_time={label.stop_time.isoformat() if label.stop_time else None}; "
        "raster_values=raw_signed_int16_samples_saved_losslessly_in_numeric_value_space"
    )
    return LunarProduct(
        product_id=source.stem,
        instrument="LRO_NAC",
        mission="LRO",
        dimensions=ImageDimensions(
            width_px=label.line_samples,
            height_px=label.lines,
            band_count=1,
        ),
        acquisition_time=acquisition_time,
        valid_pixel_ratio=valid_ratio,
        raster_uri=raster_uri,
        mask_uri=mask_uri,
        provenance=Provenance(
            source_uri=source.name,
            reader=_READER_ID,
            notes=notes,
        ),
    )


def read_lroc_pds3_label(path: Path) -> LrocPds3Label:
    """Parse the embedded label and validate the declared image layout."""

    source = Path(path)
    first_pass = _read_text_prefix(source, 65536)
    first_values = _parse_label_text(first_pass)
    try:
        record_bytes = _as_int(first_values["RECORD_BYTES"])
        label_records = _as_int(first_values["LABEL_RECORDS"])
    except KeyError as exc:
        raise LrocPds3Error(f"missing required PDS3 label key: {exc.args[0]}") from exc

    label_text = _read_text_prefix(source, record_bytes * label_records)
    values = _parse_label_text(label_text)
    missing = [key for key in _REQUIRED_KEYS if key not in values]
    if missing:
        raise LrocPds3Error(f"missing required PDS3 label keys: {', '.join(missing)}")

    sample_bits = _as_int(values["SAMPLE_BITS"])
    sample_type = _as_str(values["SAMPLE_TYPE"])
    if sample_bits != _SUPPORTED_SAMPLE_BITS:
        raise LrocPds3Error(f"unsupported SAMPLE_BITS={sample_bits}; expected 16")
    if sample_type != _SUPPORTED_SAMPLE_TYPE:
        raise LrocPds3Error(f"unsupported SAMPLE_TYPE={sample_type}; expected LSB_INTEGER")

    image_pointer = _parse_pointer_value(values["^IMAGE"])
    image_offset = _image_offset_bytes(image_pointer, record_bytes)
    label = LrocPds3Label(
        record_bytes=record_bytes,
        file_records=_as_int(values["FILE_RECORDS"]),
        label_records=label_records,
        image_pointer=image_pointer,
        image_offset_bytes=image_offset,
        lines=_as_int(values["LINES"]),
        line_samples=_as_int(values["LINE_SAMPLES"]),
        sample_bits=sample_bits,
        sample_type=sample_type,
        scaling_factor=_as_float(values["SCALING_FACTOR"]),
        valid_minimum=_as_int(values["VALID_MINIMUM"]),
        null_value=_as_int(values["NULL"]),
        unit=_as_str(values["UNIT"]),
        target_name=_as_str(values["TARGET_NAME"]),
        instrument_name=_as_str(values["INSTRUMENT_NAME"]),
        start_time=_parse_datetime(values.get("START_TIME")),
        stop_time=_parse_datetime(values.get("STOP_TIME")),
        saturation_values=_parse_saturation_values(values),
    )
    _validate_layout(source, label)
    return label


def load_lroc_pds3_raster(
    path: Path, label: LrocPds3Label | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Return the decoded raster and a valid-pixel mask."""

    source = Path(path)
    parsed = label or read_lroc_pds3_label(source)
    mmap_raster = _open_source_memmap(source, parsed)
    try:
        values = np.asarray(mmap_raster)
        valid_mask = _valid_mask_for_chunk(values, parsed)
        return values.copy(), valid_mask
    finally:
        del mmap_raster


def _materialize_lroc_handles(
    source: Path,
    label: LrocPds3Label,
    raster_uri: str,
    mask_uri: str,
) -> float:
    """Write derived raster/mask handles in row chunks without a full RAM copy."""

    shape = (label.lines, label.line_samples)
    total = label.lines * label.line_samples
    if total <= 0:
        raise LrocPds3Error(f"invalid LROC image shape {shape}")

    mmap_raster = _open_source_memmap(source, label)
    out_raster = np.lib.format.open_memmap(
        raster_uri, mode="w+", dtype=np.dtype("<i2"), shape=shape
    )
    out_mask = np.lib.format.open_memmap(mask_uri, mode="w+", dtype=bool, shape=shape)
    valid_pixels = 0
    try:
        for row in range(0, label.lines, _MATERIALIZE_CHUNK_ROWS):
            end = min(row + _MATERIALIZE_CHUNK_ROWS, label.lines)
            chunk = np.asarray(mmap_raster[row:end])
            mask_chunk = _valid_mask_for_chunk(chunk, label)
            out_raster[row:end] = chunk
            out_mask[row:end] = mask_chunk
            valid_pixels += int(mask_chunk.sum())
        out_raster.flush()
        out_mask.flush()
    finally:
        del out_raster
        del out_mask
        del mmap_raster
    return float(valid_pixels) / float(total)


def _open_source_memmap(source: Path, label: LrocPds3Label) -> np.memmap:
    return np.memmap(
        source,
        dtype="<i2",
        mode="r",
        offset=label.image_offset_bytes,
        shape=(label.lines, label.line_samples),
        order="C",
    )


def _valid_mask_for_chunk(chunk: np.ndarray, label: LrocPds3Label) -> np.ndarray:
    invalid = chunk == label.null_value
    for saturation in label.saturation_values:
        invalid |= chunk == saturation
    return ~invalid


def _derived_uri(source: Path, suffix: str) -> str:
    return str(derived_output_path(source, suffix))


def _read_text_prefix(path: Path, byte_count: int) -> str:
    try:
        with path.open("rb") as handle:
            data = handle.read(byte_count)
    except OSError as exc:
        raise LrocPds3Error(f"could not read PDS3 label from {path}") from exc
    return data.decode("latin-1", errors="ignore")


def _parse_label_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("/*", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"END", "END_OBJECT", "END_GROUP"}:
            continue
        values[key] = value
    return values


def _parse_pointer_value(value: str) -> int | str:
    stripped = value.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]
    match = re.fullmatch(r"(-?\d+)\s*<BYTES>", stripped, re.IGNORECASE)
    if match:
        return f"{match.group(1)}<BYTES>"
    try:
        return int(stripped)
    except ValueError:
        return stripped


def _image_offset_bytes(pointer: int | str, record_bytes: int) -> int:
    if isinstance(pointer, int):
        if pointer <= 0:
            raise LrocPds3Error("^IMAGE record pointer must be positive")
        return (pointer - 1) * record_bytes
    match = re.fullmatch(r"(-?\d+)<BYTES>", pointer, re.IGNORECASE)
    if match:
        offset = int(match.group(1))
        if offset < 0:
            raise LrocPds3Error("^IMAGE byte pointer must be non-negative")
        return offset
    raise LrocPds3Error(f"unsupported ^IMAGE pointer syntax: {pointer}")


def _validate_layout(path: Path, label: LrocPds3Label) -> None:
    try:
        file_size = path.stat().st_size
    except OSError as exc:
        raise LrocPds3Error(f"could not stat {path}") from exc

    declared_file_size = label.record_bytes * label.file_records
    if declared_file_size != file_size:
        raise LrocPds3Error(
            f"file size mismatch: label declares {declared_file_size} bytes, actual {file_size}"
        )

    bytes_per_sample = label.sample_bits // 8
    image_bytes = label.lines * label.line_samples * bytes_per_sample
    if label.image_offset_bytes < label.record_bytes * label.label_records:
        raise LrocPds3Error("^IMAGE points inside the declared label records")
    if label.image_offset_bytes + image_bytes > file_size:
        raise LrocPds3Error("declared image extent exceeds file size")


def _parse_saturation_values(values: dict[str, str]) -> tuple[int, ...]:
    found: list[int] = []
    for key in _SATURATION_KEYS:
        raw = values.get(key)
        if raw is None:
            continue
        found.append(_as_int(raw))
    return tuple(found)


def _as_str(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]
    return stripped


def _as_int(value: str) -> int:
    return int(_as_str(value))


def _as_float(value: str) -> float:
    return float(_as_str(value))


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = _as_str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise LrocPds3Error(f"could not parse PDS3 timestamp: {value}")
