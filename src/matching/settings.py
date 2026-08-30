"""SIFT matcher settings.

Settings are software defaults only. Do not treat these as SIH-validated
or lunar-validated parameters. The controlled benchmark (EXP-000, EXP-001)
will determine whether these defaults are appropriate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SiftSettings:
    """Tunable SIFT parameters.

    nfeatures:
        Maximum number of features to retain per image. 0 = no limit.
        Increase for high-resolution images; decrease for speed.
    n_octave_layers:
        Number of layers per octave in the scale-space pyramid.
        OpenCV default is 3.
    contrast_threshold:
        Filter threshold for weak features in low-contrast regions.
        Lower = more features (noisier). OpenCV default 0.04.
    edge_threshold:
        Filter threshold for edge-like regions.
        Higher = more features retained near edges. OpenCV default 10.
    sigma:
        Gaussian sigma applied to the input image at the first octave.
        OpenCV default 1.6.
    ratio_threshold:
        Lowe's ratio test threshold. Matches where
        best_dist / second_best_dist > ratio_threshold are discarded.
        0.75 is the standard Lowe (2004) value; lower = stricter.
    min_matches:
        Minimum number of raw matches required before returning an empty set.
        If fewer raw matches exist after ratio test, an empty CorrespondenceSet
        is returned with a quality flag.
    """

    nfeatures: int = 0
    n_octave_layers: int = 3
    contrast_threshold: float = 0.04
    edge_threshold: float = 10.0
    sigma: float = 1.6
    ratio_threshold: float = 0.75
    min_matches: int = 4
