"""Replaceable geometric models for correspondence verification.

None of these is the selected lunar transformation (D-010). Each entry is a
software baseline so robust verification can run on synthetic correspondences
and so a later benchmark can swap the model without changing verify_matches.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from src.verification.residuals import image_space_transfer_error

# Numerical degeneracy floors. These are linear-algebra safeguards, not
# inlier thresholds and not lunar accuracy criteria.
_RANK_FLOOR = 1e-10
_MATRIX_NORM_FLOOR = 1e-12


class GeometricModel(ABC):
    """Algebraic mapping from source_xy to reference_xy."""

    model_id: str
    min_samples: int
    role: str

    @abstractmethod
    def fit(self, source_xy: np.ndarray, reference_xy: np.ndarray) -> np.ndarray | None:
        """Return a 3x3 matrix or None when the sample is degenerate."""

    def residuals(
        self, source_xy: np.ndarray, reference_xy: np.ndarray, matrix: np.ndarray
    ) -> np.ndarray:
        return image_space_transfer_error(source_xy, reference_xy, matrix)


class Affine2DBaseline(GeometricModel):
    """Six-parameter affine map. TEST/BASELINE MODEL, not a lunar model.

    x' = a00 x + a01 y + a02
    y' = a10 x + a11 y + a12
    Stored as [[a00, a01, a02], [a10, a11, a12], [0, 0, 1]].
    """

    model_id = "affine_2d_baseline"
    min_samples = 3
    role = "test_generating_or_software_baseline"

    def fit(self, source_xy: np.ndarray, reference_xy: np.ndarray) -> np.ndarray | None:
        if source_xy.shape[0] < self.min_samples:
            return None
        if _planar_rank_deficient(source_xy):
            return None
        n = source_xy.shape[0]
        design = np.zeros((2 * n, 6), dtype=float)
        observation = np.zeros(2 * n, dtype=float)
        design[0::2, 0] = source_xy[:, 0]
        design[0::2, 1] = source_xy[:, 1]
        design[0::2, 2] = 1.0
        design[1::2, 3] = source_xy[:, 0]
        design[1::2, 4] = source_xy[:, 1]
        design[1::2, 5] = 1.0
        observation[0::2] = reference_xy[:, 0]
        observation[1::2] = reference_xy[:, 1]
        try:
            params, _, _, _ = np.linalg.lstsq(design, observation, rcond=None)
        except np.linalg.LinAlgError:
            return None
        if not np.all(np.isfinite(params)):
            return None
        matrix = np.array(
            [
                [params[0], params[1], params[2]],
                [params[3], params[4], params[5]],
                [0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        if np.linalg.norm(matrix[:2, :2]) < _MATRIX_NORM_FLOOR:
            return None
        return matrix


class Projective2DBaseline(GeometricModel):
    """Eight-dof 2D projective map (homography) via normalized DLT.

    TEST/BASELINE MODEL, not a universal lunar model (D-010). Terrain relief,
    pushbroom geometry, and DEM-assisted models are out of scope here.
    """

    model_id = "projective_2d_baseline"
    min_samples = 4
    role = "test_generating_or_software_baseline"

    def fit(self, source_xy: np.ndarray, reference_xy: np.ndarray) -> np.ndarray | None:
        if source_xy.shape[0] < self.min_samples:
            return None
        if _planar_rank_deficient(source_xy) or _planar_rank_deficient(reference_xy):
            return None
        src_n, t_src = _similarity_normalize(source_xy)
        dst_n, t_dst = _similarity_normalize(reference_xy)
        if src_n is None or dst_n is None or t_src is None or t_dst is None:
            return None
        h_norm = _dlt_homography(src_n, dst_n)
        if h_norm is None:
            return None
        try:
            t_dst_inv = np.linalg.inv(t_dst)
        except np.linalg.LinAlgError:
            return None
        matrix = t_dst_inv @ h_norm @ t_src
        if not np.all(np.isfinite(matrix)):
            return None
        if abs(matrix[2, 2]) > _MATRIX_NORM_FLOOR:
            matrix = matrix / matrix[2, 2]
        if np.linalg.norm(matrix) < _MATRIX_NORM_FLOOR:
            return None
        return matrix


def get_geometric_model(model_id: str) -> GeometricModel:
    registry: dict[str, type[GeometricModel]] = {
        Affine2DBaseline.model_id: Affine2DBaseline,
        Projective2DBaseline.model_id: Projective2DBaseline,
    }
    try:
        cls = registry[model_id]
    except KeyError as exc:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown geometric model_id={model_id!r}; known: {known}") from exc
    return cls()


def _planar_rank_deficient(points: np.ndarray) -> bool:
    """True when points are numerically identical or collinear."""

    unique = np.unique(points, axis=0)
    if unique.shape[0] < 3:
        return True
    centered = unique - unique.mean(axis=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    return bool(
        singular[0] < _RANK_FLOOR or singular[-1] <= _RANK_FLOOR * (singular[0] + _RANK_FLOOR)
    )


def _similarity_normalize(points: np.ndarray) -> tuple[np.ndarray | None, np.ndarray | None]:
    centroid = points.mean(axis=0)
    centered = points - centroid
    rms = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
    if rms < _RANK_FLOOR:
        return None, None
    scale = np.sqrt(2.0) / rms
    transform = np.array(
        [
            [scale, 0.0, -scale * centroid[0]],
            [0.0, scale, -scale * centroid[1]],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    ones = np.ones((points.shape[0], 1), dtype=float)
    normalized = (transform @ np.concatenate([points, ones], axis=1).T).T[:, :2]
    return normalized, transform


def _dlt_homography(source_xy: np.ndarray, reference_xy: np.ndarray) -> np.ndarray | None:
    n = source_xy.shape[0]
    design = np.zeros((2 * n, 9), dtype=float)
    x = source_xy[:, 0]
    y = source_xy[:, 1]
    xp = reference_xy[:, 0]
    yp = reference_xy[:, 1]
    design[0::2, 0] = -x
    design[0::2, 1] = -y
    design[0::2, 2] = -1.0
    design[0::2, 6] = x * xp
    design[0::2, 7] = y * xp
    design[0::2, 8] = xp
    design[1::2, 3] = -x
    design[1::2, 4] = -y
    design[1::2, 5] = -1.0
    design[1::2, 6] = x * yp
    design[1::2, 7] = y * yp
    design[1::2, 8] = yp
    try:
        _, _, vh = np.linalg.svd(design)
    except np.linalg.LinAlgError:
        return None
    homography = vh[-1].reshape(3, 3)
    if not np.all(np.isfinite(homography)):
        return None
    return homography
