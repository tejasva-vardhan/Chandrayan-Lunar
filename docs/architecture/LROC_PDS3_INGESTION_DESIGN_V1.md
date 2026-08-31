# LROC PDS3 Ingestion Design V1

Status: Engineering ingestion adapter
Owner: Haruto / ingestion
Scope: Read embedded-label LROC PDS3 ``.IMG`` products into the frozen ``LunarProduct`` contract

This adapter is an engineering reader for representative LROC demo products. It does not establish registration accuracy, sub-pixel accuracy, or official SIH benchmark performance.

## Supported product shape

The adapter targets LROC PDS3 products whose label is embedded at the front of the same ``.IMG`` file and whose image samples are stored after the label.

Supported encoding in this version:

- single-band image
- ``SAMPLE_BITS = 16``
- ``SAMPLE_TYPE = LSB_INTEGER``

Unsupported encodings are rejected explicitly.

## PDS3 label structure

The reader parses the embedded ASCII label and extracts:

- ``RECORD_BYTES``
- ``FILE_RECORDS``
- ``LABEL_RECORDS``
- ``^IMAGE``
- ``LINES``
- ``LINE_SAMPLES``
- ``SAMPLE_BITS``
- ``SAMPLE_TYPE``
- ``SCALING_FACTOR``
- ``VALID_MINIMUM``
- ``NULL``
- ``UNIT``
- ``TARGET_NAME``
- ``INSTRUMENT_NAME``
- ``START_TIME`` when present
- ``STOP_TIME`` when present

Saturation sentinels are also read when declared through keys such as ``LOW_REPR_SATURATION`` and ``HIGH_REPR_SATURATION``.

## Embedded label handling

The reader performs two label passes:

1. Read a small prefix to recover ``RECORD_BYTES`` and ``LABEL_RECORDS``.
2. Read exactly ``RECORD_BYTES * LABEL_RECORDS`` bytes and parse the full embedded label.

This avoids assuming a fixed label size while still keeping file I/O small.

## IMAGE offset determination

Image-data start is determined from ``^IMAGE``:

- integer record pointer: offset is ``(^IMAGE - 1) * RECORD_BYTES``
- byte pointer syntax ``n<BYTES>``: offset is ``n`` bytes

The adapter validates that the image offset does not point inside the declared label records.

## File-layout validation

Before any raster decode, the adapter checks:

- actual file size equals ``RECORD_BYTES * FILE_RECORDS``
- declared image extent fits inside the file
- declared label extent is not larger than the image offset
- sample encoding is the supported little-endian signed 16-bit layout

Corrupt or truncated products are rejected.

## Raster output representation

The raw image is memory-mapped as little-endian signed ``int16`` and then materialized into a software ``.npy`` raster handle recorded in ``LunarProduct.raster_uri``.

Important:

- numeric sample values are preserved
- no geometric alteration is applied
- no resize, crop, flip, rotate, reprojection, or resampling is applied
- the reader does not convert the raster into physical reflectance units

The label's ``SCALING_FACTOR`` and ``UNIT`` are preserved in provenance notes so later stages can interpret them deliberately if needed.

## NULL and saturation semantics

The reader does not assume zero is invalid.

Invalid-pixel handling is based on the label:

- ``NULL`` samples are invalid
- declared saturation sentinel values are invalid when present
- other numeric values, including zero, remain valid

A derived software mask is written beside the raster and recorded in ``LunarProduct.mask_uri``.

``LunarProduct.valid_pixel_ratio`` is computed from that derived mask.

## Streaming and memory strategy

The raw ``.IMG`` raster is accessed with ``numpy.memmap`` so the adapter does not require the full source file to be copied into Python RAM before decode.

The derived engineering raster and mask are then written as ``.npy`` files beside the source product. This matches the repository's existing software-raster convention used by preprocessing, refinement, and registration.

## Provenance

The adapter records:

- original source path
- reader identifier
- image offset
- sample encoding
- scaling factor
- unit
- NULL value
- saturation sentinels
- target name
- instrument name
- start and stop timestamps when present

No latitude/longitude footprint, GSD, overlap, or geometry is invented.

## Deliberate limitations

This adapter deliberately does not:

- infer geographic overlap from filenames
- infer missing coordinates
- infer missing GSD
- infer registration accuracy
- choose a matcher
- run preprocessing, matching, verification, or registration
- treat representative LROC data as the official SIH dataset

The frozen pipeline ``ingest_product(path) -> LunarProduct`` surface remains unchanged in this repository state. This adapter is exposed as a format-specific helper until a reviewed ingest dispatcher is introduced.

## Real-data validation procedure

Optional integration validation uses the environment variable ``LUNAR_DEMO_DATA_ROOT`` and checks for these filenames when present:

- ``M150368601RC.IMG``
- ``M1504316436RC.IMG``
- ``M106979273RC.IMG``
- ``M175153469LC.IMG``

The normal unit-test suite does not require these large files. If the environment variable is unset or the files are absent, the real-data test is skipped.
