"""Build a native application on the target operating system."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "TextureLab",
        "--collect-all",
        "matplotlib",
        "--copy-metadata",
        "numpy",
        "--copy-metadata",
        "scipy",
        "--copy-metadata",
        "opencv-python-headless",
        "--copy-metadata",
        "Pillow",
        "--copy-metadata",
        "PySide6-Essentials",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "tkinter",
        str(root / "app.py"),
    ]
    subprocess.run(args, cwd=root, check=True)


if __name__ == "__main__":
    main()
