# Representation and Matching Baseline V1

## Scope

This document describes the engineering baseline used by EXP-000 and the
common boundary that EXP-001 candidates use. It is not a matcher-selection
decision and records no scientific performance claim.

The frozen pipeline remains:

```text
preprocess -> generate_representation -> match -> verify_matches
```

`preprocess` returns an updated `RegistrationPair`; its product `raster_uri`
values are the preprocessed inputs consumed by `generate_representation`.
The frozen `generate_representation(pair) -> Any` signature is unchanged.

## Representation

`src.representation.RepresentationResult` is the internal, unfrozen payload.
It contains the source matching-view array, the selected representation ID,
and metadata containing the reference array, optional valid masks, and
matching-view coordinate scales.

The baseline representations are deterministic NumPy `float32` grayscale
arrays. `intensity` is the EXP-000 default; `gradient` and `structural` are
separate experimental representations available through the same payload.
The loader does not silently resize imagery. Matching-view decimation, when
explicitly configured, is recorded with the coordinate scale used to map
matches back to original pixels.

## Matcher

`src.matching.match(pair, representation)` is the frozen matcher boundary.
Its current wired adapter is SIFT with explicit `SiftSettings`, a deterministic
OpenCV feature path where the installed OpenCV implementation permits it, and
Lowe ratio filtering. It returns raw `CorrespondenceSet` items only;
geometric verification owns inlier classification.

The adapter respects source and reference validity masks, returns an empty
`CorrespondenceSet` for missing, empty, or featureless inputs, and rejects
malformed masks or non-finite direct representation arrays before OpenCV is
called. No metadata is fabricated.

## Extension Boundary

Later matchers add an adapter behind `src.matching` and produce the existing
`CorrespondenceSet` contract. They consume the same `RepresentationResult`
and shared helpers for arrays, masks, coordinate mapping, and confidence
normalisation. The pipeline does not import any matcher implementation.

## Limitations

This SIFT baseline is not a final matcher decision, a multimodal method, a
sun-angle-invariant method, or evidence of sub-pixel accuracy. Synthetic tests
only establish software behavior for known images. Real-data experiments and
independent evaluation remain necessary for all scientific claims.
