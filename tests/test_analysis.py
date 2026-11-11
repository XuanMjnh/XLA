import json

import numpy as np
import pytest

from texture import AnalysisConfig, analyze, axial_error
from texture.analysis import histogram_statistics, normalized_histogram
from texture.export import write_export
from texture.io import load_image, png_bytes
from texture.synthetic import crossing, quantized, stripes


@pytest.mark.parametrize(
    "a,b,expected", [(0, 180, 0), (179, 1, 2), (10, 100, 90), (-10, 170, 0), (359, 1, 2)]
)
def test_axial_error(a, b, expected):
    assert axial_error(a, b) == pytest.approx(expected)


@pytest.mark.parametrize("angle", [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 179])
def test_known_orientations(angle):
    r = analyze(quantized(stripes(angle, noise=0.02, seed=42)))
    assert axial_error(r.spatial_stats["peak_angle_deg"], angle) < 1
    assert axial_error(r.fourier_stats["peak_angle_deg"], angle) < 2
    assert r.spatial_hist.sum() == pytest.approx(1)
    assert r.fourier_hist.sum() == pytest.approx(1)


@pytest.mark.parametrize("shape", [(192, 384), (384, 192), (129, 257)])
def test_rectangular_frequency_coordinates(shape):
    r = analyze(quantized(stripes(35, shape)))
    assert axial_error(r.fourier_stats["peak_angle_deg"], 35) < 2.5


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((10, 10)),
        np.empty((0, 32)),
        np.full((32, 32), np.nan),
        np.full((32, 32), np.inf),
        np.zeros((32, 32, 2)),
    ],
)
def test_invalid_images(bad):
    with pytest.raises(ValueError):
        analyze(bad)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bins": 0},
        {"bins": 180.0},
        {"sobel_size": 4},
        {"sobel_size": 5.0},
        {"gaussian_sigma": -1},
        {"gradient_threshold": 1},
        {"min_frequency": 0.4, "max_frequency": 0.3},
        {"max_frequency": 0.7},
        {"use_hann": "yes"},
        {"histogram_sigma_deg": float("nan")},
        {"gradient_weight": 3},
        {"max_size": 12},
    ],
)
def test_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        AnalysisConfig(**kwargs).validate()


def test_constant_image_no_false_angle():
    r = analyze(np.ones((64, 64)) * 128)
    for s in [r.spatial_stats, r.fourier_stats]:
        assert s["has_signal"] is False
        assert s["peak_angle_deg"] is None
    assert not r.valid_mask.any()
    json.dumps(r.summary(), allow_nan=False)


def test_crossing_is_not_a_single_axis():
    r = analyze(quantized(crossing()))
    assert r.fourier_stats["resultant_length"] < 0.01
    assert len(r.fourier_stats["peaks_deg"]) >= 2
    for target in [30, 120]:
        assert min(axial_error(target, p) for p in r.fourier_stats["peaks_deg"]) < 2
    # The sum of local gradients need not recover the original two populations.
    assert r.spatial_stats["resultant_length"] < 0.02


def test_noise_has_low_resultant():
    r = analyze(np.random.default_rng(2026).uniform(0, 1, (256, 256)))
    for s in [r.spatial_stats, r.fourier_stats]:
        assert s["resultant_length"] < 0.1
        assert s["entropy_normalized"] > 0.98


def test_circular_boundary():
    raw, h = normalized_histogram(np.array([179.0, 1.0]), np.ones(2), 180, 2)
    assert h[0] > h[90]
    assert axial_error(histogram_statistics(h)["peak_angle_deg"], 0) < 0.1
    assert raw.sum() == pytest.approx(1)


def test_inversion_and_rotation():
    image = quantized(stripes(35))
    original = analyze(image)
    inv = analyze(255 - image)
    rot = analyze(np.rot90(image))
    for attr in ["spatial_stats", "fourier_stats"]:
        a = getattr(original, attr)["peak_angle_deg"]
        assert axial_error(a, getattr(inv, attr)["peak_angle_deg"]) < 1e-5
        assert axial_error(a + 90, getattr(rot, attr)["peak_angle_deg"]) < 1e-4


def test_roi_and_resize():
    image = quantized(stripes(45, (256, 512)))
    r = analyze(image, AnalysisConfig(max_size=128), roi=(40, 40, 200, 160))
    assert r.gray.shape == (102, 128)
    assert r.metadata["roi_xywh"] == [40, 40, 200, 160]
    with pytest.raises(ValueError):
        analyze(image, roi=(500, 0, 40, 40))


def test_rgb_and_uint16():
    gray = quantized(stripes(30))
    rgb = np.stack([gray, gray, gray], axis=2)
    a = analyze(gray)
    b = analyze(rgb)
    c = analyze(gray.astype(np.uint16) * 257)
    assert np.allclose(a.spatial_hist, b.spatial_hist)
    assert np.allclose(a.fourier_hist, c.fourier_hist)


def test_image_loader_roundtrip():
    img = quantized(stripes(20))
    assert np.array_equal(load_image(png_bytes(img)), img)
    with pytest.raises(ValueError):
        load_image(b"not an image")


def test_export_contract(tmp_path):
    r = analyze(quantized(stripes(30)))
    write_export(r, tmp_path, arrays=True)
    for name in ["summary.json", "histograms.csv", "report.html", "histogram.png", "arrays.npz"]:
        assert (tmp_path / name).stat().st_size > 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["spatial"]["has_signal"]
    data = np.load(tmp_path / "arrays.npz")
    assert data["valid_mask"].shape == (256, 256)
    assert len((tmp_path / "histograms.csv").read_text(encoding="utf-8-sig").splitlines()) == 181
