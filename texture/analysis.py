"""Spatial and Fourier texture orientation, with a shared mathematical convention.

Angles describe STRUCTURES, not their gradient normals. 0 deg is horizontal,
90 deg is vertical, positive angles are counter-clockwise, modulo 180 deg.
The implementations are independent of the Fiji Directionality Java plugin.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

EPS = 1e-15


@dataclass(frozen=True)
class AnalysisConfig:
    bins: int = 180
    gaussian_sigma: float = 1.0
    sobel_size: int = 5
    gradient_threshold: float = 0.05
    gradient_weight: int = 2
    histogram_sigma_deg: float = 2.0
    min_frequency: float = 0.02
    max_frequency: float = 0.45
    use_hann: bool = True
    max_size: int = 2048

    def validate(self) -> None:
        if type(self.bins) is not int or not 18 <= self.bins <= 720:
            raise ValueError("bins must be an integer in [18, 720].")
        if type(self.sobel_size) is not int or self.sobel_size not in (3, 5, 7):
            raise ValueError("sobel_size must be 3, 5 or 7.")
        if type(self.gradient_weight) is not int or self.gradient_weight not in (1, 2):
            raise ValueError("gradient_weight must be 1 or 2.")
        numbers = [
            self.gaussian_sigma,
            self.gradient_threshold,
            self.histogram_sigma_deg,
            self.min_frequency,
            self.max_frequency,
        ]
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in numbers):
            raise ValueError("All numeric parameters must be finite.")
        if not 0 <= self.gaussian_sigma <= 5:
            raise ValueError("gaussian_sigma must be in [0, 5].")
        if not 0 <= self.gradient_threshold < 1:
            raise ValueError("gradient_threshold must be in [0, 1).")
        if not 0 <= self.histogram_sigma_deg <= 15:
            raise ValueError("histogram_sigma_deg must be in [0, 15].")
        if not 0 <= self.min_frequency < self.max_frequency <= 0.5:
            raise ValueError("Require 0 <= min_frequency < max_frequency <= 0.5 cycles/pixel.")
        if type(self.use_hann) is not bool:
            raise ValueError("use_hann must be a Boolean.")
        if type(self.max_size) is not int or not 64 <= self.max_size <= 4096:
            raise ValueError("max_size must be an integer in [64, 4096].")


@dataclass
class AnalysisResult:
    config: AnalysisConfig
    metadata: dict[str, Any]
    angles: np.ndarray
    gray: np.ndarray
    processed: np.ndarray
    gx: np.ndarray
    gy: np.ndarray
    magnitude: np.ndarray
    texture_angles: np.ndarray
    valid_mask: np.ndarray
    orientation_rgb: np.ndarray
    fft_power: np.ndarray
    fft_log: np.ndarray
    frequency_mask: np.ndarray
    spatial_raw: np.ndarray
    spatial_hist: np.ndarray
    fourier_raw: np.ndarray
    fourier_hist: np.ndarray
    spatial_stats: dict[str, Any]
    fourier_stats: dict[str, Any]
    warnings: list[str]

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "angle_convention": "structure angle; 0=horizontal; counter-clockwise; modulo 180 degrees",
            "config": asdict(self.config),
            "metadata": self.metadata,
            "spatial": self.spatial_stats,
            "fourier": self.fourier_stats,
            "warnings": self.warnings,
        }


def axial_error(a: float | np.ndarray, b: float | np.ndarray):
    """Smallest angular distance for undirected axes, always in [0, 90]."""
    d = np.abs((np.asarray(a) - np.asarray(b) + 90.0) % 180.0 - 90.0)
    return float(d) if d.ndim == 0 else d


def prepare_image(
    image: np.ndarray, config: AnalysisConfig, roi: tuple[int, int, int, int] | None = None
):
    """Validate, crop, convert RGB to luminance, normalize and resize isotropically.

    Array inputs with three channels are RGB, NOT OpenCV BGR. Inputs must be
    finite real values. Per-image min-max normalization is used, so brightness
    and contrast cannot be compared quantitatively between separate images.
    """
    arr = np.asarray(image)
    if arr.ndim not in (2, 3) or arr.size == 0:
        raise ValueError("Expected a nonempty 2D grayscale or HxWx3 RGB image.")
    if arr.ndim == 3 and arr.shape[2] not in (3, 4):
        raise ValueError("Color images must have three RGB or four RGBA channels.")
    if not (np.issubdtype(arr.dtype, np.number) or arr.dtype == np.bool_):
        raise ValueError("Image pixels must be numeric.")
    if np.iscomplexobj(arr) or not np.all(np.isfinite(arr)):
        raise ValueError("Complex, NaN and infinite image values are not supported.")
    original_shape = list(arr.shape[:2])
    if roi is not None:
        if len(roi) != 4 or any(type(v) is not int for v in roi):
            raise ValueError("ROI must be four integers: x y width height.")
        x, y, w, h = roi
        if min(x, y) < 0 or min(w, h) < 32 or x + w > arr.shape[1] or y + h > arr.shape[0]:
            raise ValueError("ROI must be inside the image and at least 32x32 pixels.")
        arr = arr[y : y + h, x : x + w]
    if min(arr.shape[:2]) < 32:
        raise ValueError("Image must be at least 32x32 pixels.")
    arr = arr.astype(np.float64)
    if arr.ndim == 3:
        if arr.shape[2] == 4:
            alpha = arr[..., 3]
            alpha_max = 255.0 if alpha.max() > 1 else 1.0
            alpha = np.clip(alpha / alpha_max, 0, 1)
            white = 255.0 if arr[..., :3].max() > 1 else 1.0
            arr = arr[..., :3] * alpha[..., None] + white * (1 - alpha[..., None])
        arr = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    lo, hi = float(arr.min()), float(arr.max())
    arr = (arr - lo) / (hi - lo) if hi > lo else np.zeros_like(arr)
    cropped_shape = list(arr.shape)
    scale = min(1.0, config.max_size / max(arr.shape))
    if scale < 1:
        width = max(1, int(round(arr.shape[1] * scale)))
        height = max(1, int(round(arr.shape[0] * scale)))
        arr = cv2.resize(arr, (width, height), interpolation=cv2.INTER_AREA)
        if min(arr.shape) < 32:
            raise ValueError("Aspect ratio is too extreme after downsampling; crop an ROI.")
    processed = arr.copy()
    if config.gaussian_sigma > 0:
        processed = cv2.GaussianBlur(
            processed, (0, 0), config.gaussian_sigma, borderType=cv2.BORDER_REFLECT_101
        )
    meta = {
        "original_shape_hw": original_shape,
        "cropped_shape_hw": cropped_shape,
        "analysis_shape_hw": list(arr.shape),
        "resize_scale": scale,
        "roi_xywh": list(roi) if roi else None,
        "input_min": lo,
        "input_max": hi,
        "normalization": "per-image min-max to [0,1]",
        "pixel_spacing_assumption": "square pixels; frequency in cycles/analysis-pixel",
    }
    return arr, processed, meta


def normalized_histogram(angles: np.ndarray, weights: np.ndarray, bins: int, sigma_deg: float):
    """Circular linear voting to centers 0, step, ..., 180-step degrees."""
    a = np.asarray(angles, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    if a.size != w.size:
        raise ValueError("angles and weights must have identical sizes.")
    good = np.isfinite(a) & np.isfinite(w) & (w > 0)
    a, w = a[good], w[good]
    hist = np.zeros(bins, dtype=np.float64)
    if w.size and float(w.sum()) > EPS:
        u = (a % 180.0) * (bins / 180.0)
        i = np.floor(u).astype(np.int64)
        frac = u - i
        hist += np.bincount(i % bins, weights=w * (1 - frac), minlength=bins)
        hist += np.bincount((i + 1) % bins, weights=w * frac, minlength=bins)
        hist /= hist.sum()
    smooth = hist.copy()
    if sigma_deg > 0 and smooth.sum() > 0:
        smooth = gaussian_filter1d(smooth, sigma_deg * bins / 180.0, mode="wrap")
        smooth /= smooth.sum()
    return hist, smooth


def _refine_peak(hist: np.ndarray, index: int) -> float:
    """Three-bin parabolic interpolation; not a Gaussian fit."""
    left, mid, right = hist[(index - 1) % len(hist)], hist[index], hist[(index + 1) % len(hist)]
    denom = left - 2 * mid + right
    delta = 0.0 if abs(denom) < EPS else float(np.clip(0.5 * (left - right) / denom, -0.5, 0.5))
    return float(((index + delta) * 180.0 / len(hist)) % 180.0)


def histogram_statistics(hist: np.ndarray) -> dict[str, Any]:
    n = len(hist)
    if float(hist.sum()) <= EPS:
        return {
            "has_signal": False,
            "peak_angle_deg": None,
            "mean_angle_deg": None,
            "resultant_length": None,
            "entropy_normalized": None,
            "peak_mass_pm10deg": None,
            "peaks_deg": [],
            "interpretation": "no_signal",
        }
    p = np.asarray(hist, float) / np.sum(hist)
    angles = np.arange(n) * 180.0 / n
    z = np.sum(p * np.exp(2j * np.deg2rad(angles)))
    r = float(np.clip(abs(z), 0, 1))
    mean = float((0.5 * np.rad2deg(np.angle(z))) % 180) if r > 1e-8 else None
    nz = p[p > 0]
    entropy = float(np.clip(-np.sum(nz * np.log(nz)) / np.log(n), 0, 1))
    peak = _refine_peak(p, int(np.argmax(p)))
    mass = float(p[axial_error(angles, peak) <= 10].sum())
    distance = max(1, int(round(10 * n / 180)))
    candidates, properties = find_peaks(
        np.tile(p, 3), prominence=float(0.08 * p.max()), distance=distance
    )
    candidates = candidates[(candidates >= n) & (candidates < 2 * n)] - n
    candidates = sorted(candidates, key=lambda i: p[i], reverse=True)
    peaks = [_refine_peak(p, int(i)) for i in candidates[:3]]
    if not peaks and p.max() - p.min() > 1e-10:
        peaks = [peak]
    if r < 0.45 and len(peaks) >= 2 and mass > 0.18:
        interpretation = "multimodal_or_mixed"
    elif r < 0.15 and entropy > 0.90:
        interpretation = "diffuse_or_weakly_oriented"
    elif r > 0.70:
        interpretation = "strong_single_axis_component"
    else:
        interpretation = "mixed_or_moderately_oriented"
    return {
        "has_signal": True,
        "peak_angle_deg": peak,
        "mean_angle_deg": mean,
        "resultant_length": r,
        "entropy_normalized": entropy,
        "peak_mass_pm10deg": mass,
        "peaks_deg": peaks,
        "interpretation": interpretation,
    }


def _orientation_map(
    gray: np.ndarray, angles: np.ndarray, magnitude: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    hsv = np.zeros((*gray.shape, 3), dtype=np.float32)
    hsv[..., 0] = (angles * 2).astype(np.float32)
    reference = float(np.percentile(magnitude[mask], 95)) if np.any(mask) else 1.0
    hsv[..., 1] = np.where(mask, np.clip(magnitude / max(reference, EPS), 0, 1), 0)
    hsv[..., 2] = 0.2 + 0.8 * gray
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return np.clip(np.rint(rgb * 255), 0, 255).astype(np.uint8)


def analyze(
    image: np.ndarray,
    config: AnalysisConfig | None = None,
    roi: tuple[int, int, int, int] | None = None,
) -> AnalysisResult:
    config = config or AnalysisConfig()
    config.validate()
    gray, processed, meta = prepare_image(image, config, roi)
    h, w = processed.shape
    # Normalize the gain of the separable Sobel derivative. Absolute gain cancels
    # out of a normalized histogram but this keeps exported magnitudes readable.
    gain = 2.0 ** (2 * config.sobel_size - 3)
    gx = cv2.Sobel(
        processed,
        cv2.CV_64F,
        1,
        0,
        ksize=config.sobel_size,
        scale=1 / gain,
        borderType=cv2.BORDER_REFLECT_101,
    )
    gy = cv2.Sobel(
        processed,
        cv2.CV_64F,
        0,
        1,
        ksize=config.sobel_size,
        scale=1 / gain,
        borderType=cv2.BORDER_REFLECT_101,
    )
    magnitude = np.hypot(gx, gy)
    theta = (np.rad2deg(np.arctan2(-gy, gx)) + 90.0) % 180.0
    margin = config.sobel_size // 2 + int(math.ceil(3 * config.gaussian_sigma))
    mask = np.zeros((h, w), dtype=bool)
    if h > 2 * margin and w > 2 * margin:
        mask[margin : h - margin, margin : w - margin] = True
    else:
        raise ValueError("Image/ROI is too small for the selected blur and Sobel support.")
    max_magnitude = float(magnitude[mask].max()) if np.any(mask) else 0
    mask &= magnitude > max(EPS, config.gradient_threshold * max_magnitude)
    spatial_raw, spatial_hist = normalized_histogram(
        theta[mask],
        magnitude[mask] ** config.gradient_weight,
        config.bins,
        config.histogram_sigma_deg,
    )
    centered = processed - float(processed.mean())
    if config.use_hann:
        centered = centered * np.outer(np.hanning(h), np.hanning(w))
    spectrum = np.fft.fftshift(np.fft.fft2(centered))
    power = np.abs(spectrum) ** 2
    # Frequency coordinates MUST be normalized by each image dimension. Raw
    # array indices would give wrong angles for non-square images.
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fxx, fyy = np.meshgrid(fx, fy)
    radius = np.hypot(fxx, fyy)
    frequency_mask = (
        (radius >= config.min_frequency) & (radius <= config.max_frequency) & (radius > 0)
    )
    fourier_angles = (np.rad2deg(np.arctan2(-fyy, fxx)) + 90.0) % 180.0
    fourier_raw, fourier_hist = normalized_histogram(
        fourier_angles[frequency_mask],
        power[frequency_mask],
        config.bins,
        config.histogram_sigma_deg,
    )
    spatial_stats = histogram_statistics(spatial_hist)
    fourier_stats = histogram_statistics(fourier_hist)
    notes = []
    for label, stats in [("Spatial", spatial_stats), ("Fourier", fourier_stats)]:
        if not stats["has_signal"]:
            notes.append(label + ": no usable directional energy; angle is undefined.")
        elif stats["resultant_length"] < 0.15:
            notes.append(
                label
                + ": low axial resultant; inspect the whole histogram for multiple peaks or diffuse content."
            )
    if meta["resize_scale"] < 1:
        notes.append("Image was isotropically downsampled. Frequencies refer to analysis pixels.")
    if spatial_stats["has_signal"] and fourier_stats["has_signal"]:
        delta = axial_error(spatial_stats["peak_angle_deg"], fourier_stats["peak_angle_deg"])
        meta["spatial_fourier_peak_difference_deg"] = delta
        if delta > 10:
            notes.append(
                "Methods disagree by more than 10 degrees: examine multiple scales, peaks, ROI and frequency limits."
            )
    meta.update(
        {
            "excluded_border_pixels": margin,
            "valid_gradient_fraction": float(mask.mean()),
            "frequency_bin_count": int(frequency_mask.sum()),
            "fourier_band_energy": float(power[frequency_mask].sum()),
        }
    )
    return AnalysisResult(
        config,
        meta,
        np.arange(config.bins) * 180.0 / config.bins,
        gray,
        processed,
        gx,
        gy,
        magnitude,
        theta,
        mask,
        _orientation_map(processed, theta, magnitude, mask),
        power,
        np.log1p(power),
        frequency_mask,
        spatial_raw,
        spatial_hist,
        fourier_raw,
        fourier_hist,
        spatial_stats,
        fourier_stats,
        notes,
    )
