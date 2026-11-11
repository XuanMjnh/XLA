"""Periodic alignment of Python and imported Fiji histograms."""

import csv
import hashlib
from pathlib import Path

import numpy as np
from scipy.spatial.distance import jensenshannon

from .analysis import axial_error, histogram_statistics


def read_histogram(path, xkey="angle_deg", ykey="weight"):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or xkey not in reader.fieldnames or ykey not in reader.fieldnames:
            raise ValueError(f"CSV thiếu cột {xkey} hoặc {ykey}.")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV không có dữ liệu.")
    angles = np.array([float(row[xkey]) for row in rows])
    weights = np.array([float(row[ykey]) for row in rows])
    if (
        not np.all(np.isfinite(angles))
        or not np.all(np.isfinite(weights))
        or np.any(weights < 0)
        or weights.sum() <= 0
    ):
        raise ValueError("Histogram không hợp lệ hoặc không có tín hiệu.")
    angles %= 180
    order = np.argsort(angles)
    angles, weights = angles[order], weights[order]
    # Directionality exports both 0 and 180 degrees. Combine the same axial bin.
    unique, inverse = np.unique(np.round(angles, 9), return_inverse=True)
    if len(unique) != len(angles):
        weights = np.bincount(inverse, weights=weights)
        angles = unique
    return angles, weights / weights.sum()


def compare_histograms(python_csv, fiji_csv, method):
    if method not in ("spatial", "fourier"):
        raise ValueError("Phương pháp không hợp lệ.")
    angles, hp = read_histogram(python_csv, ykey=method + "_raw")
    if not np.allclose(angles, np.arange(len(angles)) * 180 / len(angles)):
        raise ValueError("Lưới góc Python phải đều và bắt đầu tại 0°.")
    af, hf = read_histogram(fiji_csv)
    if len(af) < 3:
        raise ValueError("Histogram Fiji cần ít nhất 3 góc.")
    hf = np.interp(angles, af, hf, period=180)
    hf /= hf.sum()
    sp, sf = histogram_statistics(hp), histogram_statistics(hf)
    result = {
        "method": method,
        "python": sp,
        "fiji": sf,
        "peak_difference_deg": axial_error(sp["peak_angle_deg"], sf["peak_angle_deg"]),
        "jensen_shannon_divergence_base2": float(jensenshannon(hp, hf, base=2) ** 2),
        "histogram_mae": float(np.mean(np.abs(hp - hf))),
        "fiji_source_file": Path(fiji_csv).name,
        "fiji_source_sha256": hashlib.sha256(Path(fiji_csv).read_bytes()).hexdigest(),
        "alignment": "merge equivalent endpoint bins; periodic linear interpolation; modulo 180 degrees",
        "comparison": "Python raw histogram versus imported Fiji CSV",
    }
    return result, angles, hp, hf
