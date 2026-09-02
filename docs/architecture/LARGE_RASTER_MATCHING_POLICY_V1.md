# Large Raster Matching Policy v1

Status: Engineering runtime safeguard
Scope: `src/representation/` and `src/matching/` only
Companion: Interface Freeze v1, Master spec v3 §11, §13, §30

## Purpose

Real OHRC and LROC strips can be too large for full-resolution SIFT on a
developer machine. This policy adds an explicit derived matching view so the
software baseline can execute without altering source imagery or changing the
frozen pipeline contracts.

This is a runtime and memory strategy only. It is **not** a scientific claim
that lower-resolution matching improves registration accuracy.

## Policy

- Each product keeps its original ingested raster handle in `LunarProduct.raster_uri`.
- `generate_representation()` may derive a lower-resolution in-memory matching
  view when the original image exceeds the per-image engineering budget.
- Default budget: `4,194,304` pixels per image.
- Deterministic reduction rule:
  `stride = ceil(sqrt(original_pixels / max_pixels_per_image))`
- Reduction method: `stride_decimation`, using `array[::stride, ::stride]`.
- Small images at or below the budget keep full-resolution behavior
  (`stride = 1`).

## Coordinate handling

- Matching runs on the derived view.
- The derived view metadata stores:
  - original shape
  - matching-view shape
  - stride
  - `x_scale` and `y_scale`
- SIFT keypoints are mapped back to original image coordinates using:
  - `x_original = x_matching * x_scale`
  - `y_original = y_matching * y_scale`

Downstream verification, control-point selection, refinement, registration, and
evaluation therefore continue to receive correspondence coordinates in the
original product image coordinate system expected by the frozen contracts.

## Validity masks

When an ingested product supplies a `mask_uri`, its matching view is decimated
with the same stride as the raster and passed to OpenCV as a feature-detection
mask. A mismatched mask/representation shape is an error. Pair overlap masks
are not consumed here because this boundary has no declared mapping from a
pair-level mask into two product pixel grids.

## Safety properties

- Original rasters are never overwritten.
- The representation stage can inspect `.npy` raster shapes via memory mapping
  before deciding whether a derived view is needed.
- For large `.npy` rasters, only the decimated sample grid is materialized into
  the matcher-facing array, avoiding unnecessary full-size copies in Python RAM.
- If the policy cannot determine a raster shape safely, representation
  generation fails closed instead of silently forcing a risky full-resolution
  matching path.
- A large non-`.npy` input also fails closed: decoding it before decimation
  would materialise the full raster and defeat this runtime safeguard.
