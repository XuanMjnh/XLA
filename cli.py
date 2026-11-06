#!/usr/bin/env python3
"""Reproducible command-line interface. Run: python cli.py --help."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
from texture import AnalysisConfig, analyze
from texture.export import write_export
from texture.io import load_image, SUPPORTED_EXTENSIONS
from texture.synthetic import generate_samples


def add_options(p):
    p.add_argument("--bins",type=int,default=180)
    p.add_argument("--sigma",type=float,default=1.0)
    p.add_argument("--sobel",type=int,choices=[3,5,7],default=5)
    p.add_argument("--threshold",type=float,default=.05)
    p.add_argument("--weight",type=int,choices=[1,2],default=2)
    p.add_argument("--hist-sigma",type=float,default=2.0)
    p.add_argument("--rmin",type=float,default=.02)
    p.add_argument("--rmax",type=float,default=.45)
    p.add_argument("--no-hann",action="store_true")
    p.add_argument("--max-size",type=int,default=2048)
    p.add_argument("--roi",type=int,nargs=4,metavar=("X","Y","W","H"))
    p.add_argument("--save-arrays",action="store_true")


def config_from_args(a):
    return AnalysisConfig(bins=a.bins,gaussian_sigma=a.sigma,sobel_size=a.sobel,
        gradient_threshold=a.threshold,gradient_weight=a.weight,histogram_sigma_deg=a.hist_sigma,
        min_frequency=a.rmin,max_frequency=a.rmax,use_hann=not a.no_hann,max_size=a.max_size)


def main(argv=None):
    parser=argparse.ArgumentParser(description="Texture structure orientation: Sobel and Fourier.")
    sub=parser.add_subparsers(dest="command",required=True)
    one=sub.add_parser("analyze",help="Analyze a single image")
    one.add_argument("image",type=Path);one.add_argument("--out",type=Path,default=Path("results/single"));add_options(one)
    batch=sub.add_parser("batch",help="Analyze all supported images in one directory")
    batch.add_argument("directory",type=Path);batch.add_argument("--out",type=Path,default=Path("results/batch"));add_options(batch)
    gen=sub.add_parser("generate",help="Regenerate 15 synthetic demonstration images")
    gen.add_argument("--out",type=Path,default=Path("data/samples"))
    exp=sub.add_parser("experiment",help="Regenerate benchmark CSVs, figures and metric summary")
    exp.add_argument("--out",type=Path,default=Path("results/experiments"))
    args=parser.parse_args(argv)
    try:
        if args.command == "generate":
            manifest=generate_samples(args.out)
            print(f"Generated {len(manifest['images'])} images in {args.out}");return 0
        if args.command == "experiment":
            from texture.experiments import run_experiments
            run_experiments(args.out);return 0
        config=config_from_args(args);config.validate()
        roi=tuple(args.roi) if args.roi else None
        if args.command == "analyze":
            result=analyze(load_image(args.image),config,roi)
            write_export(result,args.out,args.image.name,args.save_arrays)
            print(json.dumps(result.summary(),indent=2,ensure_ascii=False,allow_nan=False))
            print(f"Saved results: {args.out}");return 0
        if not args.directory.is_dir():
            raise ValueError(f"Directory does not exist: {args.directory}")
        paths=sorted(p for p in args.directory.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
        if not paths:
            raise ValueError("No supported image files found in the directory.")
        args.out.mkdir(parents=True,exist_ok=True)
        rows=[];errors=[]
        for index,path in enumerate(paths,1):
            try:
                result=analyze(load_image(path),config,roi)
                # Index and full original name avoid collisions between same-stem files.
                target=args.out/f"{index:03d}_{path.name}"
                write_export(result,target,path.name,args.save_arrays)
                row={"filename":path.name}
                for method,stats in [("spatial",result.spatial_stats),("fourier",result.fourier_stats)]:
                    for key in ("peak_angle_deg","resultant_length","entropy_normalized"):
                        row[f"{method}_{key}"]=stats[key]
                rows.append(row)
                print(f"[{index}/{len(paths)}] OK {path.name}")
            except (ValueError,OSError) as exc:
                errors.append({"filename":path.name,"error":str(exc)})
                print(f"[{index}/{len(paths)}] ERROR {path.name}: {exc}",file=sys.stderr)
        for filename,data in [("batch_summary.csv",rows),("errors.csv",errors)]:
            if data:
                with (args.out/filename).open("w",encoding="utf-8-sig",newline="") as f:
                    writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
        return 1 if errors else 0
    except (ValueError,OSError) as exc:
        print(f"Error: {exc}",file=sys.stderr);return 2

if __name__ == "__main__":
    raise SystemExit(main())
