"""Reproducible generated textures. These are NOT photographs or external data."""
from __future__ import annotations
from pathlib import Path
import json
import math
import numpy as np
from PIL import Image


def stripes(angle: float = 30, shape: tuple[int,int] = (256,256),
            period: float = 16, noise: float = 0, seed: int = 0,
            phase: float = 0.37) -> np.ndarray:
    if len(shape) != 2 or min(shape) < 32 or max(shape) > 4096:
        raise ValueError("Synthetic shape must be between 32 and 4096 on each axis.")
    if not all(math.isfinite(float(x)) for x in (angle, period, noise, phase)) or period < 3 or noise < 0:
        raise ValueError("Finite angle/phase, period>=3 and noise>=0 are required.")
    yy, xx = np.indices(shape, dtype=float)
    theta = np.deg2rad(angle)
    normal = -np.sin(theta)*xx - np.cos(theta)*yy
    arr = 0.5+0.35*np.cos(2*np.pi*normal/period+phase)
    if noise:
        arr += np.random.default_rng(seed).normal(0, noise, size=shape)
    return np.clip(arr, 0, 1)


def crossing(angles=(30.,120.), shape=(256,256), period=16.) -> np.ndarray:
    a = stripes(angles[0], shape, period)
    b = stripes(angles[1], shape, period)
    return (a+b)/2


def quantized(arr: np.ndarray) -> np.ndarray:
    """Quantization used both for saved examples and all accuracy experiments."""
    return np.clip(np.rint(arr*255), 0, 255).astype(np.uint8)


def generate_samples(directory: str | Path) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    samples = {}
    for angle in (0,15,30,45,60,90,120,150,179):
        samples[f"stripes_{angle:03d}.png"] = (stripes(angle), {"kind":"single", "angle":angle})
    samples["stripes_030_noise015.png"] = (stripes(30, noise=.15, seed=2026),
        {"kind":"single", "angle":30, "noise_sigma":.15, "seed":2026})
    samples["crossing_030_120.png"] = (crossing(), {"kind":"crossing", "angles":[30,120]})
    samples["white_noise.png"] = (np.random.default_rng(2026).uniform(0,1,(256,256)),
        {"kind":"noise", "seed":2026})
    samples["constant.png"] = (np.full((256,256),.5), {"kind":"constant"})
    left, right = stripes(20), stripes(70)
    mixed = left.copy(); mixed[:,128:] = right[:,128:]
    samples["two_regions_020_070.png"] = (mixed, {"kind":"nonstationary", "angles":[20,70]})
    samples["rectangular_035.png"] = (stripes(35,(192,384)), {"kind":"single", "angle":35})
    manifest = {"license":"CC0-1.0 for generated sample images", "generator":"texture/synthetic.py",
                "description":"Procedural test images; no natural-image ground truth is claimed.", "images":{}}
    for filename,(arr,meta) in samples.items():
        Image.fromarray(quantized(arr)).save(directory/filename)
        manifest["images"][filename] = meta
    (directory/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest
