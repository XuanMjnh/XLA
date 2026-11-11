"""Compare every available official plugin result, retaining no-signal cases."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from texture.analysis import AnalysisConfig, analyze, axial_error
from texture.comparison import compare_histograms
from texture.export import write_export
from texture.io import load_image


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=Path("data/samples"))
    parser.add_argument("--reference", type=Path, default=Path("results/windows/fiji"))
    args = parser.parse_args(argv)
    manifest = json.loads((args.images / "manifest.json").read_text(encoding="utf-8"))["images"]
    run_manifest = json.loads((args.reference / "run_manifest.json").read_text(encoding="utf-8"))
    for image in run_manifest["images"]:
        current = hashlib.sha256((args.images / image["filename"]).read_bytes()).hexdigest()
        if current != image["sha256"]:
            raise ValueError("Input changed since the Fiji run: " + image["filename"])
    rows = []
    for filename, label in manifest.items():
        folder = args.reference / Path(filename).stem
        if not folder.is_dir():
            raise ValueError(f"Missing official reference result: {folder}")
        result = analyze(load_image(args.images / filename), AnalysisConfig())
        write_export(result, folder / "python", filename)
        for method, reference_name in [
            ("spatial", "local_gradient"),
            ("fourier", "fourier_components"),
        ]:
            row = {
                "image": filename,
                "kind": label["kind"],
                "method": method,
                "status": "ok",
                "true_angle_deg": label.get("angle"),
                "python_raw_peak_deg": None,
                "fiji_raw_peak_deg": None,
                "python_gt_error_deg": None,
                "fiji_gt_error_deg": None,
                "peak_difference_deg": None,
                "jsd_base2": None,
                "histogram_mae": None,
            }
            if label["kind"] == "constant":
                row["status"] = "no_signal"
                (folder / f"comparison_{method}.json").write_text(
                    json.dumps(
                        {
                            "status": "no_signal",
                            "reason": "constant image has no defined orientation",
                        }
                    ),
                    encoding="utf-8",
                )
            else:
                report, *_ = compare_histograms(
                    folder / "python/histograms.csv", folder / f"{reference_name}.csv", method
                )
                (folder / f"comparison_{method}.json").write_text(
                    json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
                )
                row.update(
                    python_raw_peak_deg=report["python"]["peak_angle_deg"],
                    fiji_raw_peak_deg=report["fiji"]["peak_angle_deg"],
                    peak_difference_deg=report["peak_difference_deg"],
                    jsd_base2=report["jensen_shannon_divergence_base2"],
                    histogram_mae=report["histogram_mae"],
                )
                if label["kind"] == "single":
                    row["python_gt_error_deg"] = axial_error(
                        row["python_raw_peak_deg"], label["angle"]
                    )
                    row["fiji_gt_error_deg"] = axial_error(row["fiji_raw_peak_deg"], label["angle"])
            rows.append(row)
    with (args.reference / "comparison_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"images": len(manifest), "rows": len(rows), "methods": {}}
    for method in ("spatial", "fourier"):
        all_rows = [r for r in rows if r["method"] == method and r["status"] == "ok"]
        single = [r for r in all_rows if r["kind"] == "single"]
        summary["methods"][method] = {
            "valid_images": len(all_rows),
            "single_orientation_images": len(single),
            "mean_jsd_all_valid": float(np.mean([r["jsd_base2"] for r in all_rows])),
            "single_python_raw_mae_deg": float(np.mean([r["python_gt_error_deg"] for r in single])),
            "single_fiji_raw_mae_deg": float(np.mean([r["fiji_gt_error_deg"] for r in single])),
            "single_mean_peak_difference_deg": float(
                np.mean([r["peak_difference_deg"] for r in single])
            ),
        }
    summary["interpretation"] = (
        "Raw aligned histograms. Ground-truth error only for single-orientation images. Multimodal peak differences and noise maxima are not accuracy scores."
    )
    (args.reference / "comparison_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
