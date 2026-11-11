"""CSV/JSON/PNG/HTML exports shared by CLI and the desktop interface."""

from __future__ import annotations

import base64
import csv
import html
import json
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analysis import AnalysisResult
from .io import png_bytes


def _fig_bytes(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def histogram_plot(
    result: AnalysisResult, title: str = "Structure orientation histograms"
) -> bytes:
    fig, ax = plt.subplots(figsize=(8.2, 3.9))
    # Plot one extra point at 180 degrees to make circular continuity visible.
    angles = np.r_[result.angles, 180]
    for label, hist in [
        ("Sobel gradient", result.spatial_hist),
        ("Fourier spectrum", result.fourier_hist),
    ]:
        ax.plot(angles, 100 * np.r_[hist, hist[0]], label=label, linewidth=1.7)
    ax.set(
        xlim=(0, 180),
        xlabel="Structure angle (degrees; counter-clockwise)",
        ylabel="Normalized weight per bin (%)",
        title=title,
    )
    ax.set_xticks(np.arange(0, 181, 30))
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return _fig_bytes(fig)


def spectrum_plot(result: AnalysisResult) -> bytes:
    h, w = result.fft_log.shape
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    im = ax.imshow(
        result.fft_log,
        origin="upper",
        cmap="gray",
        extent=[fx[0], fx[-1], fy[-1], fy[0]],
        aspect="equal",
    )
    ax.set(
        xlabel="fx (cycles/pixel)",
        ylabel="fy (image-axis cycles/pixel)",
        title="log(1 + Fourier power); display only",
    )
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    fig.tight_layout()
    return _fig_bytes(fig)


def orientation_legend() -> bytes:
    import cv2

    hsv = np.zeros((32, 360, 3), np.float32)
    hsv[..., 0] = np.arange(360)[None, :]
    hsv[..., 1:] = 1
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    fig, ax = plt.subplots(figsize=(7.4, 1.1))
    ax.imshow(rgb, extent=(0, 180, 0, 1), aspect="auto")
    ax.set(yticks=[], xticks=np.arange(0, 181, 30), xlabel="Structure angle (degrees)")
    fig.tight_layout()
    return _fig_bytes(fig)


def result_images(result: AnalysisResult) -> dict[str, bytes]:
    m = result.magnitude
    m = m / max(float(m.max()), 1e-15)
    return {
        "input.png": png_bytes(result.gray),
        "preprocessed.png": png_bytes(result.processed),
        "gradient_magnitude.png": png_bytes(m),
        "orientation_map.png": png_bytes(result.orientation_rgb),
        "orientation_legend.png": orientation_legend(),
        "fft_spectrum.png": spectrum_plot(result),
        "histogram.png": histogram_plot(result),
    }


def csv_bytes(result: AnalysisResult) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        ["angle_deg", "spatial_raw", "spatial_smoothed", "fourier_raw", "fourier_smoothed"]
    )
    writer.writerows(
        zip(
            result.angles,
            result.spatial_raw,
            result.spatial_hist,
            result.fourier_raw,
            result.fourier_hist,
            strict=False,
        )
    )
    return buffer.getvalue().encode("utf-8-sig")


def make_html(
    result: AnalysisResult, images: dict[str, bytes], title="Texture directionality"
) -> bytes:
    def fmt(value):
        return "undefined" if value is None else f"{value:.4f}"

    rows = []
    for label, s in [("Sobel", result.spatial_stats), ("Fourier", result.fourier_stats)]:
        rows.append(
            f"<tr><td>{label}</td><td>{fmt(s['peak_angle_deg'])}</td><td>{fmt(s['resultant_length'])}</td>"
            f"<td>{fmt(s['entropy_normalized'])}</td><td>{html.escape(s['interpretation'])}</td></tr>"
        )
    gallery = []
    captions = {
        "input.png": "Normalized input",
        "preprocessed.png": "Gaussian preprocessed image",
        "gradient_magnitude.png": "Sobel magnitude (display normalized)",
        "orientation_map.png": "Local STRUCTURE orientation; not gradient-normal angle",
        "orientation_legend.png": "Orientation-map color key",
        "fft_spectrum.png": "Fourier log-power spectrum",
        "histogram.png": "Energy-weighted orientation histogram",
    }
    for name, data in images.items():
        b64 = base64.b64encode(data).decode("ascii")
        gallery.append(
            f'<figure><img src="data:image/png;base64,{b64}" alt="{captions[name]}"><figcaption>{captions[name]}</figcaption></figure>'
        )
    warnings = "".join(f"<li>{html.escape(w)}</li>" for w in result.warnings)
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:16px/1.55 system-ui;margin:32px auto;max-width:1050px;padding:0 20px;color:#172231}}
h1{{font-size:28px}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border:1px solid #ccd4db;padding:9px;text-align:left}}
.gallery{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}figure{{margin:0}}img{{width:100%;object-fit:contain;max-height:410px}}
figcaption{{font-size:13px}}pre{{white-space:pre-wrap;font-size:12px}}@media print{{.gallery{{display:block}}figure{{break-inside:avoid}}}}</style>
<h1>{html.escape(title)}</h1>
<table><tr><th>Method</th><th>Peak (deg)</th><th>R</th><th>Entropy</th><th>Interpretation</th></tr>{"".join(rows)}</table>
<ul>{warnings}</ul><div class="gallery">{"".join(gallery)}</div><h2>Reproducibility metadata</h2>
<pre>{html.escape(json.dumps(result.summary(), indent=2, ensure_ascii=False, allow_nan=False))}</pre></html>"""
    return page.encode("utf-8")


def export_files(
    result: AnalysisResult, title="Texture directionality", arrays=False
) -> dict[str, bytes]:
    images = result_images(result)
    files = dict(images)
    files["summary.json"] = json.dumps(
        result.summary(), indent=2, ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    files["histograms.csv"] = csv_bytes(result)
    files["report.html"] = make_html(result, images, title)
    if arrays:
        buf = BytesIO()
        np.savez_compressed(
            buf,
            gx=result.gx,
            gy=result.gy,
            magnitude=result.magnitude,
            texture_angles_deg=result.texture_angles,
            valid_mask=result.valid_mask,
            fft_power=result.fft_power,
            frequency_mask=result.frequency_mask,
        )
        files["arrays.npz"] = buf.getvalue()
    return files


def write_export(
    result: AnalysisResult, directory: str | Path, title="Texture directionality", arrays=False
):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = export_files(result, title, arrays)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return directory


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()
