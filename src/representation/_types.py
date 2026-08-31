"""Internal representation result type. Not part of the frozen pipeline interface.

generate_representation returns Any per interface freeze v1 §8. This dataclass is
the concrete return type used internally. Matchers that consume it should import
this class directly, not depend on the frozen interface knowing about it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RepresentationResult:
    """Holds the processed image array and accompanying metadata.

    array: float32, shape (H, W) or (H, W, C), values in [0, 1] unless the
           representation method documents a different range.
    representation_id: the label identifying which method produced this result.
                       Passed through to CorrespondenceSet.representation_id.
    metadata: open dict for representation-specific values (e.g. clip percentiles).
              Do not encode routing thresholds here.
    """

    array: np.ndarray
    representation_id: str
    metadata: dict[str, object] = field(default_factory=dict)
