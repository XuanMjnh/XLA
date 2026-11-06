"""Build a native application on the target operating system."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parent
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
        '--onedir', '--name', 'TextureLab', '--collect-all', 'matplotlib',
        '--copy-metadata', 'numpy', '--copy-metadata', 'scipy',
        '--copy-metadata', 'opencv-python-headless', '--copy-metadata', 'Pillow',
        '--copy-metadata', 'PySide6-Essentials',
        '--exclude-module', 'PySide6.QtWebEngineCore', '--exclude-module', 'tkinter',
        str(root/'app.py')]
subprocess.run(args, cwd=root, check=True)
