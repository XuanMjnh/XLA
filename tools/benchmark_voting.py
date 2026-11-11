"""Measure equivalent circular voting implementations, excluding all image I/O."""

import argparse
import csv
import json
import platform
import sys
from functools import partial
from pathlib import Path
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from texture.analysis import EPS, normalized_histogram


def add_at_baseline(angles, weights, bins):
    angles = np.asarray(angles, dtype=np.float64).ravel()
    weights = np.asarray(weights, dtype=np.float64).ravel()
    if angles.size != weights.size:
        raise ValueError("angles and weights must have identical sizes")
    good = np.isfinite(angles) & np.isfinite(weights) & (weights > 0)
    angles, weights = angles[good], weights[good]
    hist = np.zeros(bins)
    if not weights.size or float(weights.sum()) <= EPS:
        return hist, hist.copy()
    u = (angles % 180) * (bins / 180)
    index = np.floor(u).astype(np.int64)
    fraction = u - index
    np.add.at(hist, index % bins, weights * (1 - fraction))
    np.add.at(hist, (index + 1) % bins, weights * fraction)
    hist /= hist.sum()
    return hist, hist.copy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results/windows/optimization"))
    parser.add_argument("--runs", type=int, default=15)
    args = parser.parse_args(argv)
    if args.runs < 3:
        parser.error("runs must be >= 3")
    args.out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2026)
    rows = []
    for count in (65536, 262144, 1048576):
        angles = rng.uniform(0, 180, count)
        weights = rng.uniform(0.01, 1, count)
        expected = add_at_baseline(angles, weights, 180)[0]
        actual = normalized_histogram(angles, weights, 180, 0)[0]
        error = float(np.max(np.abs(actual - expected)))
        if not np.allclose(actual, expected, atol=1e-14, rtol=1e-12):
            raise AssertionError("Optimized voting changes the result")
        baseline = []
        optimized = []
        # Alternate execution order to reduce systematic ordering bias.
        for run in range(args.runs):
            jobs = [
                (partial(add_at_baseline, angles, weights, 180), baseline),
                (partial(normalized_histogram, angles, weights, 180, 0), optimized),
            ]
            for function, timings in jobs[:: 1 if run % 2 == 0 else -1]:
                start = perf_counter()
                function()
                timings.append((perf_counter() - start) * 1000)
        bm = float(np.median(baseline))
        om = float(np.median(optimized))
        rows.append(
            {
                "votes": count,
                "bins": 180,
                "runs": args.runs,
                "add_at_median_ms": bm,
                "bincount_median_ms": om,
                "speedup": bm / om,
                "max_abs_histogram_error": error,
            }
        )
    with (args.out / "voting.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "seed": 2026,
        "results": rows,
        "scope": "Microbenchmark only. Both implementations include the same input validation, linear voting, normalization and output copy, with smoothing disabled. No claim of full application or Fiji speedup.",
    }
    (args.out / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
