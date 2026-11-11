"""Run the official Directionality plugin using Fiji's bundled JDK or Java 17+."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fiji_runtime(home):
    """Prefer the bundled JDK, so Java does not need to be on PATH."""
    home = Path(home).resolve()
    candidates = sorted(home.glob("java/**/bin/java.exe")) + sorted(home.glob("java/**/bin/java"))
    java = next((p for p in candidates if p.with_name("javac" + p.suffix).is_file()), None)
    if java is None:
        raise ValueError(
            "No bundled JDK found in Fiji. Pass a Fiji installation containing java and javac."
        )
    jars = []
    for folder, pattern in [
        ("jars", "ij-*.jar"),
        ("plugins", "Directionality_*.jar"),
        ("jars", "jfreechart-*.jar"),
        ("jars", "jcommon-*.jar"),
    ]:
        matches = sorted((home / folder).glob(pattern))
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one {pattern} in {home / folder}, found {len(matches)}."
            )
        jars.extend(matches)
    return java, jars


def pinned_jars(root):
    jars = []
    for dependency in json.loads((root / "dependencies.json").read_text(encoding="utf-8")):
        target = root / "lib" / dependency["file"]
        if not target.exists() or sha256(target) != dependency["sha256"]:
            target.parent.mkdir(exist_ok=True)
            with urlopen(dependency["source"], timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != dependency["sha256"]:
                raise ValueError("Dependency checksum mismatch: " + dependency["file"])
            target.write_bytes(data)
        jars.append(target)
    return jars


def main(argv=None):
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--fiji-home",
        type=Path,
        help="Fiji.app directory; uses its JDK and plugin JARs without downloading",
    )
    parser.add_argument(
        "--java", default="java", help="Java 17+ executable when not using --fiji-home"
    )
    parser.add_argument("--sigma", type=float, default=1.0)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Render official plugin windows for the first image (requires a display)",
    )
    args = parser.parse_args(argv)
    if not 0 <= args.sigma <= 5:
        parser.error("sigma must be in [0,5]")
    if not args.input.is_dir() or not list(args.input.glob("*.png")):
        parser.error("input must be a directory containing grayscale PNG images")
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        if args.fiji_home:
            java, jars = fiji_runtime(args.fiji_home)
        else:
            java = Path(shutil.which(args.java) or args.java).resolve()
            jars = pinned_jars(root)
        classpath = os.pathsep.join(str(p) for p in jars)
        logs = []
        with tempfile.TemporaryDirectory(prefix="texturelab_java_") as build:
            source = root / "DirectionalityBatch.java"
            if args.fiji_home:
                compiler = java.with_name("javac" + java.suffix)
                subprocess.run(
                    [
                        str(compiler),
                        "-encoding",
                        "UTF-8",
                        "-cp",
                        classpath,
                        "-d",
                        build,
                        str(source),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                command = [
                    str(java),
                    "-Djava.awt.headless=true",
                    "-cp",
                    build + os.pathsep + classpath,
                    "DirectionalityBatch",
                ]
            else:
                command = [
                    str(java),
                    "-Djava.awt.headless=true",
                    "--class-path",
                    classpath,
                    str(source),
                ]
            command.extend([str(args.input.resolve()), str(args.output.resolve()), str(args.sigma)])
            run = subprocess.run(command, check=True, capture_output=True, text=True)
            logs.append(run.stdout + run.stderr)
            if args.demo:
                compiler = java.with_name("javac" + java.suffix)
                subprocess.run(
                    [
                        str(compiler),
                        "-encoding",
                        "UTF-8",
                        "-cp",
                        classpath,
                        "-d",
                        build,
                        str(root / "DirectionalityDemo.java"),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                sample = args.input / "stripes_030_noise015.png"
                if not sample.is_file():
                    sample = sorted(args.input.glob("*.png"))[0]
                demo = subprocess.run(
                    [
                        str(java),
                        "-cp",
                        build + os.pathsep + classpath,
                        "DirectionalityDemo",
                        str(sample.resolve()),
                        str(args.output.resolve() / "demo"),
                        str(args.sigma),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logs.append(demo.stdout + demo.stderr)
        (args.output / "execution.log").write_text("\n".join(logs), encoding="utf-8")
        version = subprocess.run(
            [str(java), "-version"], capture_output=True, text=True, check=True
        )
        manifest = {
            "executed_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "java_executable": str(java),
            "java_version": (version.stdout + version.stderr).strip(),
            "mode": "official unmodified plugin from local Fiji"
            if args.fiji_home
            else "official pinned plugin JARs",
            "configuration": {"bins": 180, "range_deg": [0, 180], "gaussian_sigma": args.sigma},
            "images": [
                {"filename": p.name, "sha256": sha256(p)} for p in sorted(args.input.glob("*.png"))
            ],
            "jars": [{"file": p.name, "sha256": sha256(p)} for p in jars],
            "source_sha256": sha256(root / "DirectionalityBatch.java"),
            "timing_note": "Plugin single pass includes fit and JIT effects; not a controlled speed comparison with Python.",
        }
        (args.output / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"Executed official Directionality on {len(manifest['images'])} images. Results: {args.output}"
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Error: {getattr(exc, 'stderr', '') or str(exc)}\n")


if __name__ == "__main__":
    main()
