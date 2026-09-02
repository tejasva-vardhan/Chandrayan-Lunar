"""Log-Gabor phase congruency and Maximum Index Map.

Support code for the RIFT adapter. Phase congruency is a contrast- and
brightness-invariant measure of feature significance, so it is the standard
front end for radiation-insensitive multi-modal matching.

This is an in-repository implementation over numpy + scipy, both already
project dependencies. No RIFT or phase-congruency package exists on PyPI that
is both maintained and compatible with this environment (the PyPI project
named ``rift`` is unrelated LIGO gravitational-wave software), so adding one
would have been a fragile dependency rather than a reliable implementation.

Algorithm
---------
1. Build a bank of log-Gabor filters over ``n_scale`` scales and ``n_orient``
   orientations in the frequency domain.
2. Convolve the image with every filter via FFT to obtain the even/odd
   quadrature responses ``EO[s, o]``.
3. Per orientation, accumulate phase congruency energy with Kovesi's noise
   compensation and frequency-spread weighting.
4. Combine the per-orientation phase congruency into maximum/minimum moment
   maps, which behave like edge and corner strength maps.
5. Build the Maximum Index Map (MIM): the index of the orientation whose
   summed amplitude is largest at each pixel. The MIM is what RIFT describes
   instead of the raw gradient, and is why RIFT tolerates radiation change.

References
----------
- Kovesi, P. (1999). Image features from phase congruency. Videre 1(3).
- Kovesi, P. (2003). Phase congruency detects corners and edges. DICTA.
- Li, J., Hu, Q., Ai, M. (2020). RIFT: Multi-modal image matching based on
  radiation-variation insensitive feature transform. IEEE TIP 29, 3296-3310.

Numerical notes
---------------
- FFTs run in ``complex64``. The matching views in this project are large
  (millions of pixels) and ``complex128`` would multiply peak memory by two
  for no measurable benefit at the precision phase congruency needs.
- Inputs are symmetrically padded to a fast FFT length and cropped back.
  Without padding, prime-factor shapes such as 5212 fall back to Bluestein's
  algorithm and dominate runtime. Symmetric padding also suppresses the
  wrap-around edge response of a circular convolution.
- Only one orientation's per-scale responses are held at a time so peak memory
  stays proportional to ``n_scale`` rather than ``n_scale * n_orient``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import fft as scipy_fft

_EPSILON = 1e-8

# Kovesi's empirical rescaling of the Rayleigh noise threshold. Not a tuned
# project parameter; it is part of the published phase-congruency method.
_NOISE_THRESHOLD_SCALE = 1.7


@dataclass(frozen=True, slots=True)
class LogGaborSettings:
    """Log-Gabor / phase-congruency parameters.

    These are the published defaults from Kovesi's phase congruency and from
    the RIFT paper. They are recorded so the experiment is reproducible; they
    are not SIH thresholds and are not lunar-validated parameters.

    n_scale
        Number of log-Gabor radial scales.
    n_orient
        Number of orientations spanning 0..180 degrees. Also the number of
        MIM index values and therefore the RIFT descriptor's channel count.
    min_wavelength
        Wavelength of the smallest scale filter, in pixels.
    mult
        Geometric scaling factor between successive filter wavelengths.
    sigma_on_f
        Ratio of the log-Gabor bandwidth to its centre frequency. Smaller is
        a wider bandwidth.
    k_noise
        Number of noise standard deviations subtracted from the energy.
    cut_off
        Fraction of the filter bank that must be active before the frequency
        spread weight approaches one.
    gain
        Sharpness of the frequency spread sigmoid.
    low_pass_cutoff, low_pass_order
        Butterworth low-pass applied to every filter to suppress the highest
        representable frequencies.
    """

    n_scale: int = 4
    n_orient: int = 6
    min_wavelength: float = 3.0
    mult: float = 1.6
    sigma_on_f: float = 0.75
    k_noise: float = 2.0
    cut_off: float = 0.5
    gain: float = 10.0
    low_pass_cutoff: float = 0.45
    low_pass_order: int = 15

    def __post_init__(self) -> None:
        if self.n_scale < 2:
            raise ValueError("n_scale must be >= 2")
        if self.n_orient < 2:
            raise ValueError("n_orient must be >= 2")
        if self.min_wavelength <= 0.0:
            raise ValueError("min_wavelength must be > 0")
        if self.mult <= 1.0:
            raise ValueError("mult must be > 1")
        if not 0.0 < self.sigma_on_f < 1.0:
            raise ValueError("sigma_on_f must be in (0, 1)")
        if not 0.0 < self.low_pass_cutoff <= 0.5:
            raise ValueError("low_pass_cutoff must be in (0, 0.5]")
        if self.low_pass_order < 1:
            raise ValueError("low_pass_order must be >= 1")


@dataclass(frozen=True, slots=True)
class PhaseCongruencyResult:
    """Phase congruency products consumed by the RIFT adapter.

    max_moment
        Maximum moment of the phase congruency covariance. Behaves as an
        edge-strength map.
    min_moment
        Minimum moment. Behaves as a corner-strength map.
    maximum_index_map
        Per-pixel index of the orientation with the largest summed amplitude,
        in ``[0, n_orient)``. This is RIFT's MIM.
    n_orient
        Number of MIM channels, copied for downstream convenience.
    """

    max_moment: np.ndarray
    min_moment: np.ndarray
    maximum_index_map: np.ndarray
    n_orient: int


def phase_congruency(image: np.ndarray, settings: LogGaborSettings) -> PhaseCongruencyResult:
    """Compute phase congruency moment maps and the Maximum Index Map."""

    array = np.asarray(image, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError(f"phase congruency requires a 2-D image, got shape {array.shape}")
    rows, cols = array.shape
    if rows < 8 or cols < 8:
        raise ValueError(f"image is too small for phase congruency: shape {array.shape}")

    padded, crop = _pad_to_fast_length(array)
    spectrum = scipy_fft.fft2(padded.astype(np.complex64), workers=-1)
    del padded

    radial = _radial_filters(spectrum.shape, settings)
    sin_theta, cos_theta = _angular_grids(spectrum.shape)

    height, width = spectrum.shape
    orientation_amplitude = np.zeros((settings.n_orient, height, width), dtype=np.float32)
    covariance_xx = np.zeros((height, width), dtype=np.float32)
    covariance_yy = np.zeros((height, width), dtype=np.float32)
    covariance_xy = np.zeros((height, width), dtype=np.float32)

    for orientation in range(settings.n_orient):
        angle = orientation * np.pi / settings.n_orient
        spread = _angular_spread(sin_theta, cos_theta, angle, settings.n_orient)
        congruency, summed_amplitude = _orientation_congruency(
            spectrum, radial, spread, settings
        )
        orientation_amplitude[orientation] = summed_amplitude
        component_x = congruency * np.float32(np.cos(angle))
        component_y = congruency * np.float32(np.sin(angle))
        covariance_xx += component_x * component_x
        covariance_yy += component_y * component_y
        covariance_xy += component_x * component_y

    del spectrum, radial, sin_theta, cos_theta

    covariance_xx *= np.float32(2.0 / settings.n_orient)
    covariance_yy *= np.float32(2.0 / settings.n_orient)
    covariance_xy *= np.float32(4.0 / settings.n_orient)
    spread_term = np.sqrt(
        covariance_xy * covariance_xy + (covariance_xx - covariance_yy) ** 2
    ) + np.float32(_EPSILON)
    max_moment = (covariance_yy + covariance_xx + spread_term) * np.float32(0.5)
    min_moment = (covariance_yy + covariance_xx - spread_term) * np.float32(0.5)

    index_map = np.argmax(orientation_amplitude, axis=0).astype(np.uint8)
    del orientation_amplitude

    row_slice, col_slice = crop
    return PhaseCongruencyResult(
        max_moment=np.ascontiguousarray(max_moment[row_slice, col_slice]),
        min_moment=np.ascontiguousarray(min_moment[row_slice, col_slice]),
        maximum_index_map=np.ascontiguousarray(index_map[row_slice, col_slice]),
        n_orient=settings.n_orient,
    )


def _orientation_congruency(
    spectrum: np.ndarray,
    radial: list[np.ndarray],
    spread: np.ndarray,
    settings: LogGaborSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Phase congruency and summed amplitude for one orientation."""

    responses: list[np.ndarray] = []
    summed_amplitude = np.zeros(spectrum.shape, dtype=np.float32)
    summed_even = np.zeros(spectrum.shape, dtype=np.float32)
    summed_odd = np.zeros(spectrum.shape, dtype=np.float32)
    max_amplitude = np.zeros(spectrum.shape, dtype=np.float32)
    smallest_scale_amplitude: np.ndarray | None = None
    filter_energy = 0.0
    filter_bank: list[np.ndarray] = []

    for scale in range(settings.n_scale):
        transfer = radial[scale] * spread
        filter_bank.append(transfer)
        response = scipy_fft.ifft2(spectrum * transfer, workers=-1).astype(np.complex64)
        amplitude = np.abs(response).astype(np.float32)
        summed_amplitude += amplitude
        summed_even += response.real
        summed_odd += response.imag
        np.maximum(max_amplitude, amplitude, out=max_amplitude)
        if scale == 0:
            smallest_scale_amplitude = amplitude
            filter_energy = float(np.sum(transfer.astype(np.float64) ** 2))
        responses.append(response)

    total_energy = np.sqrt(summed_even * summed_even + summed_odd * summed_odd) + np.float32(
        _EPSILON
    )
    mean_even = summed_even / total_energy
    mean_odd = summed_odd / total_energy
    del summed_even, summed_odd, total_energy

    energy = np.zeros(spectrum.shape, dtype=np.float32)
    for response in responses:
        even = response.real
        odd = response.imag
        energy += even * mean_even + odd * mean_odd
        energy -= np.abs(even * mean_odd - odd * mean_even)
    del responses, mean_even, mean_odd

    assert smallest_scale_amplitude is not None
    threshold = _noise_threshold(
        smallest_scale_amplitude, filter_bank, filter_energy, settings
    )
    del smallest_scale_amplitude, filter_bank

    np.subtract(energy, np.float32(threshold), out=energy)
    np.maximum(energy, np.float32(0.0), out=energy)

    width = (summed_amplitude / (max_amplitude + np.float32(_EPSILON)) - np.float32(1.0)) / (
        settings.n_scale - 1
    )
    weight = np.float32(1.0) / (
        np.float32(1.0) + np.exp((np.float32(settings.cut_off) - width) * settings.gain)
    )
    congruency = weight * energy / (summed_amplitude + np.float32(_EPSILON))
    return congruency.astype(np.float32), summed_amplitude


def _noise_threshold(
    smallest_scale_amplitude: np.ndarray,
    filter_bank: list[np.ndarray],
    filter_energy: float,
    settings: LogGaborSettings,
) -> float:
    """Kovesi's Rayleigh noise energy threshold for one orientation."""

    median_squared = float(np.median(smallest_scale_amplitude.astype(np.float64) ** 2))
    if median_squared <= 0.0 or filter_energy <= 0.0:
        return 0.0
    mean_squared_noise = -median_squared / np.log(0.5)
    noise_power = mean_squared_noise / filter_energy

    sum_squared = 0.0
    for transfer in filter_bank:
        sum_squared += float(np.sum(transfer.astype(np.float64) ** 2))
    sum_cross = 0.0
    for first in range(len(filter_bank) - 1):
        for second in range(first + 1, len(filter_bank)):
            sum_cross += float(
                np.sum(
                    filter_bank[first].astype(np.float64) * filter_bank[second].astype(np.float64)
                )
            )

    noise_energy_squared = 2.0 * noise_power * sum_squared + 4.0 * noise_power * sum_cross
    if noise_energy_squared <= 0.0:
        return 0.0
    tau = np.sqrt(noise_energy_squared / 2.0)
    expected = tau * np.sqrt(np.pi / 2.0)
    deviation = np.sqrt((2.0 - np.pi / 2.0) * tau * tau)
    return float((expected + settings.k_noise * deviation) / _NOISE_THRESHOLD_SCALE)


def _radial_filters(shape: tuple[int, int], settings: LogGaborSettings) -> list[np.ndarray]:
    """Log-Gabor radial transfer functions, low-pass limited."""

    rows, cols = shape
    radius = _frequency_radius(rows, cols)
    low_pass = _butterworth_low_pass(radius, settings.low_pass_cutoff, settings.low_pass_order)
    log_sigma_squared = 2.0 * np.log(settings.sigma_on_f) ** 2

    filters: list[np.ndarray] = []
    for scale in range(settings.n_scale):
        wavelength = settings.min_wavelength * settings.mult**scale
        centre_frequency = 1.0 / wavelength
        transfer = np.exp(-((np.log(radius / centre_frequency)) ** 2) / log_sigma_squared)
        transfer = (transfer * low_pass).astype(np.float32)
        transfer[0, 0] = 0.0
        filters.append(transfer)
    return filters


def _frequency_radius(rows: int, cols: int) -> np.ndarray:
    """Normalised frequency radius, origin-shifted, with a non-zero DC entry."""

    x = _frequency_axis(cols)
    y = _frequency_axis(rows)
    grid_x, grid_y = np.meshgrid(x, y)
    radius = np.sqrt(grid_x * grid_x + grid_y * grid_y)
    radius = np.fft.ifftshift(radius)
    # log(radius) at DC is undefined; the filters zero this entry afterwards.
    radius[0, 0] = 1.0
    return radius.astype(np.float64)


def _angular_grids(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = shape
    x = _frequency_axis(cols)
    y = _frequency_axis(rows)
    grid_x, grid_y = np.meshgrid(x, y)
    theta = np.arctan2(-grid_y, grid_x)
    theta = np.fft.ifftshift(theta)
    return np.sin(theta).astype(np.float32), np.cos(theta).astype(np.float32)


def _frequency_axis(length: int) -> np.ndarray:
    if length % 2:
        return np.arange(-(length - 1) / 2.0, (length - 1) / 2.0 + 1.0) / float(length - 1)
    return np.arange(-length / 2.0, length / 2.0) / float(length)


def _angular_spread(
    sin_theta: np.ndarray, cos_theta: np.ndarray, angle: float, n_orient: int
) -> np.ndarray:
    """Cosine angular spread function centred on ``angle``."""

    delta_sin = sin_theta * np.float32(np.cos(angle)) - cos_theta * np.float32(np.sin(angle))
    delta_cos = cos_theta * np.float32(np.cos(angle)) + sin_theta * np.float32(np.sin(angle))
    delta_theta = np.abs(np.arctan2(delta_sin, delta_cos))
    np.minimum(delta_theta * (n_orient / 2.0), np.float32(np.pi), out=delta_theta)
    return ((np.cos(delta_theta) + np.float32(1.0)) * np.float32(0.5)).astype(np.float32)


def _butterworth_low_pass(radius: np.ndarray, cutoff: float, order: int) -> np.ndarray:
    return 1.0 / (1.0 + (radius / cutoff) ** (2 * order))


def _pad_to_fast_length(
    array: np.ndarray,
) -> tuple[np.ndarray, tuple[slice, slice]]:
    """Symmetrically pad to a fast FFT shape and return the crop that undoes it."""

    rows, cols = array.shape
    fast_rows = int(scipy_fft.next_fast_len(rows))
    fast_cols = int(scipy_fft.next_fast_len(cols))
    if fast_rows == rows and fast_cols == cols:
        return array, (slice(0, rows), slice(0, cols))

    pad_rows = fast_rows - rows
    pad_cols = fast_cols - cols
    top = pad_rows // 2
    left = pad_cols // 2
    padded = np.pad(
        array,
        ((top, pad_rows - top), (left, pad_cols - left)),
        mode="symmetric",
    )
    return padded, (slice(top, top + rows), slice(left, left + cols))


__all__ = [
    "LogGaborSettings",
    "PhaseCongruencyResult",
    "phase_congruency",
]
