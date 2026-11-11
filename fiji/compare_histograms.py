#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from texture.comparison import compare_histograms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--fiji", required=True, type=Path)
    parser.add_argument("--method", choices=["spatial", "fourier"], required=True)
    parser.add_argument("--out", type=Path, default=Path("comparison.json"))
    args = parser.parse_args()
    try:
        result, *_ = compare_histograms(args.python, args.fiji, args.method)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
