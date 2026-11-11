"""Run image analysis and export in a Qt worker, reporting results by signals."""

import hashlib
import importlib.metadata
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QThread, Signal

from texture.analysis import analyze
from texture.export import write_export
from texture.io import load_image

VERSION = "2.0.0"


class AnalysisWorker(QThread):
    """Process images sequentially; interruption is checked between images."""

    completed = Signal(object)
    failed = Signal(str, str)
    progress = Signal(int, int)

    def __init__(self, jobs, config, directory, arrays=False):
        super().__init__()
        self.jobs, self.config = jobs, config
        self.directory, self.arrays = directory, arrays

    def run(self):
        for index, (path, roi) in enumerate(self.jobs):
            if self.isInterruptionRequested():
                break
            try:
                start = perf_counter()
                image = load_image(path)
                result = analyze(image, self.config, roi)
                elapsed = (perf_counter() - start) * 1000
                result.metadata.update(
                    {
                        "source_filename": Path(path).name,
                        "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                        "created_utc": datetime.now(timezone.utc).isoformat(),
                        "application_version": VERSION,
                        "elapsed_ms_read_and_analysis": elapsed,
                        "runtime": {
                            "python": platform.python_version(),
                            **{
                                name: importlib.metadata.version(name)
                                for name in (
                                    "numpy",
                                    "scipy",
                                    "opencv-python-headless",
                                    "Pillow",
                                    "PySide6-Essentials",
                                )
                            },
                        },
                    }
                )
                folder = Path(self.directory) / uuid.uuid4().hex
                write_export(result, folder, Path(path).name, arrays=self.arrays)
                self.completed.emit(
                    {
                        "path": path,
                        "directory": str(folder),
                        "summary": result.summary(),
                        "elapsed_ms": elapsed,
                        "roi": roi,
                    }
                )
                del image, result
            except Exception as exc:
                self.failed.emit(path, str(exc))
            self.progress.emit(index + 1, len(self.jobs))
