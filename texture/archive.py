"""Atomic file writes and ZIP packaging for desktop analysis sessions."""

import csv
import os
import uuid
import zipfile
from pathlib import Path


def atomic_bytes(path, data):
    path = Path(path)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def package_records(records, destination):
    """Atomic export with distinct directories for duplicate basenames."""
    destination = Path(destination)
    temporary = destination.with_name("." + destination.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
            rows = []
            for index, record in enumerate(records, 1):
                prefix = f"{index:03d}_{Path(record['path']).stem}" if len(records) > 1 else ""
                for file in sorted(Path(record["directory"]).iterdir()):
                    if file.is_file():
                        z.write(file, str(Path(prefix) / file.name))
                row = {"file": Path(record["path"]).name, "elapsed_ms": record["elapsed_ms"]}
                for method in ("spatial", "fourier"):
                    for key in ("peak_angle_deg", "resultant_length", "entropy_normalized"):
                        row[f"{method}_{key}"] = record["summary"][method][key]
                rows.append(row)
            if len(rows) > 1:
                from io import StringIO

                buffer = StringIO(newline="")
                writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
                z.writestr("batch_summary.csv", buffer.getvalue().encode("utf-8-sig"))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
