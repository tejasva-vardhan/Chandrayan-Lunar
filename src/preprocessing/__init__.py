"""Product preprocessing. Owned by Haruto.

Pipeline import surface: preprocess(pair) -> RegistrationPair.

Owns pair-aware normalization, orientation when required, and scale-aware
resampling when required. This package currently implements a software
baseline: finite-value masking plus optional percentile intensity
normalization. It does not invent thresholds in configs/default.yaml.
Preserve characterization produced by geometry unless a later architecture
decision says otherwise.

SOFTWARE BASELINE only. Not a final Chandrayaan-2 preprocessing pipeline.
"""

from src.preprocessing.preprocess import preprocess, preprocess_with_settings
from src.preprocessing.settings import (
    PreprocessingSettings,
    minimal_preprocessing_defaults,
    unvalidated_software_defaults,
)

__all__ = [
    "PreprocessingSettings",
    "minimal_preprocessing_defaults",
    "preprocess",
    "preprocess_with_settings",
    "unvalidated_software_defaults",
]
