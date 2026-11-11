import csv
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
)

from app import MainWindow, configure_appearance
from desktop_ui import Section
from texture.archive import package_records
from texture.comparison import compare_histograms
from texture.io import png_bytes
from texture.synthetic import quantized, stripes


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    configure_appearance(app)
    yield app


@pytest.fixture
def window(qt_app):
    w = MainWindow()
    w.show()
    qt_app.processEvents()
    yield w
    if w.worker:
        w.cancel()
        wait_idle(w, qt_app)
    w.close()
    qt_app.processEvents()


def wait_idle(window, app):
    deadline = time.monotonic() + 45
    while window.worker and time.monotonic() < deadline:
        # Release the GIL so the Python worker can render exports on Windows.
        app.processEvents()
        time.sleep(0.01)
    assert window.worker is None
    app.processEvents()


def create_image(path, angle=30):
    path.write_bytes(png_bytes(quantized(stripes(angle, shape=(128, 128)))))
    return str(path.resolve())


@pytest.mark.parametrize("system_scheme", [Qt.ColorScheme.Light, Qt.ColorScheme.Dark])
def test_appearance_independent_of_system_theme(qt_app, system_scheme):
    qt_app.setStyleSheet("")
    qt_app.styleHints().setColorScheme(system_scheme)
    # Reproduce the OS palette that previously leaked into the parameter panel.
    inherited = QPalette()
    inherited.setColor(
        QPalette.ColorRole.Window,
        QColor("#202020" if system_scheme == Qt.ColorScheme.Dark else "#ffffff"),
    )
    inherited.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
    inherited.setColor(QPalette.ColorRole.Base, QColor("#202020"))
    qt_app.setPalette(inherited)
    configure_appearance(qt_app)
    w = MainWindow()
    dialog = QDialog(w)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Thông tin phân tích"))
    editor = QPlainTextEdit("Ghi chú")
    layout.addWidget(editor)
    try:
        w.show()
        dialog.show()
        qt_app.processEvents()
        panel = w.findChild(QScrollArea).widget()
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            assert panel.palette().color(group, QPalette.ColorRole.Window).name() == "#f6f8fb"
            assert panel.palette().color(group, QPalette.ColorRole.WindowText).name() == "#273044"
            assert editor.palette().color(group, QPalette.ColorRole.Base).name() == "#ffffff"
            assert editor.palette().color(group, QPalette.ColorRole.Text).name() == "#273044"
        assert panel.grab().toImage().pixelColor(0, 0).name() == "#f6f8fb"
        assert w.inputs["bins"].palette().color(QPalette.ColorRole.Text).name() == "#273044"
        assert (
            qt_app.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name()
            == "#9aa7b7"
        )
        # A later system preference change must not replace the explicit palette.
        qt_app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
        qt_app.processEvents()
        assert panel.grab().toImage().pixelColor(0, 0).name() == "#f6f8fb"
    finally:
        dialog.close()
        w.close()
        configure_appearance(qt_app)


def test_desktop_analysis_export_invalidation(window, qt_app, tmp_path):
    path = create_image(tmp_path / "vân 30.png")
    window.add_files([path, path])
    assert window.file_list.count() == 1
    assert not window.save_action.isEnabled()
    window.run_button.click()
    assert not window.run_button.isEnabled()
    wait_idle(window, qt_app)
    assert not window.errors
    record = window.records[path]
    assert abs(record["summary"]["spatial"]["peak_angle_deg"] - 30) < 1
    assert window.stats.item(0, 1).text() != "—"
    assert window.table.rowCount() == 180
    assert not window.views["histogram"].pixmap.isNull()
    assert not window.stats.empty.isVisible()
    output = tmp_path / "out.zip"
    package_records([record], output)
    with zipfile.ZipFile(output) as z:
        assert "report.html" in z.namelist()
        assert json.loads(z.read("summary.json"))["metadata"]["source_sha256"]
    window.inputs["bins"].setValue(90)
    assert not window.records and not window.save_action.isEnabled()
    assert window.table.rowCount() == 0
    assert window.stats.empty.isVisible()


def test_empty_state_open_remove_and_compact_layout(window, qt_app, tmp_path, monkeypatch):
    path = create_image(tmp_path / "texture.png")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **k: ([path], ""))
    assert window.file_stack.currentWidget() is window.list_empty
    QTest.mouseClick(window.views["source"].empty.open_button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    assert window.current_path() == path
    assert window.file_stack.currentWidget() is window.file_list
    assert not window.views["source"].empty.isVisible()
    window.showNormal()
    window.resize(1180, 760)
    qt_app.processEvents()
    assert window.run_button.isVisible()
    assert (
        window.run_button.mapTo(window, QPoint(0, 0)).y() + window.run_button.height()
        < window.height()
    )
    section = window.findChildren(Section)[0]
    value = window.inputs["bins"].value()
    QTest.mouseClick(section.toggle, Qt.MouseButton.LeftButton)
    assert not section.body.isVisible()
    QTest.mouseClick(section.toggle, Qt.MouseButton.LeftButton)
    assert section.body.isVisible() and window.inputs["bins"].value() == value
    QTest.mouseClick(window.remove_button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    assert window.file_stack.currentWidget() is window.list_empty
    assert window.views["source"].empty.isVisible()
    assert not window.run_button.isEnabled()


def test_roi_drag_batch_duplicate_names(window, qt_app, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    p1 = create_image(a / "same.png", 20)
    p2 = create_image(b / "same.png", 70)
    window.add_files([p1, p2])
    window.file_list.setCurrentRow(0)
    qt_app.processEvents()
    view = window.views["source"]
    r = view.image_rect()
    start = QPoint(r.left() + r.width() // 8, r.top() + r.height() // 8)
    end = QPoint(r.left() + 7 * r.width() // 8, r.top() + 7 * r.height() // 8)
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view, end)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=end)
    assert p1 in window.rois
    window.batch_button.click()
    wait_idle(window, qt_app)
    assert not window.errors and len(window.records) == 2
    assert window.records[p1]["summary"]["metadata"]["roi_xywh"]
    output = tmp_path / "batch.zip"
    package_records(list(window.records.values()), output)
    with zipfile.ZipFile(output) as z:
        assert "001_same/summary.json" in z.namelist()
        assert "002_same/summary.json" in z.namelist()
        assert "batch_summary.csv" in z.namelist()


def test_bad_file_continues_and_cancellation(window, qt_app, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"bad")
    good = create_image(tmp_path / "good.png")
    errors = []
    window.notify_error = errors.append
    window.add_files([str(bad), good])
    window.analyze_all()
    wait_idle(window, qt_app)
    assert len(errors) == 1 and good in window.records and len(window.errors) == 1
    window.analyze_all()
    window.cancel()
    wait_idle(window, qt_app)
    assert window.run_button.isEnabled()


def test_no_signal(window, qt_app, tmp_path):
    path = tmp_path / "constant.png"
    path.write_bytes(png_bytes(np.zeros((64, 64), np.uint8)))
    window.add_files([str(path)])
    window.analyze_current()
    wait_idle(window, qt_app)
    assert not window.errors
    assert window.stats.item(0, 1).text() == "—" and window.stats.item(1, 1).text() == "—"


def test_comparison(window, qt_app, tmp_path, monkeypatch):
    path = create_image(tmp_path / "texture.png")
    window.add_files([path])
    window.analyze_current()
    wait_idle(window, qt_app)
    folder = Path(window.records[path]["directory"])
    with (folder / "histograms.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    # Fixture validates alignment only. It is not a real Fiji measurement.
    external = tmp_path / "fixture.csv"
    with external.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["angle_deg", "weight"])
        writer.writerows(
            (float(row["angle_deg"]) - 180, float(row["spatial_raw"])) for row in reversed(rows)
        )
    report, *_ = compare_histograms(folder / "histograms.csv", external, "spatial")
    assert (
        report["peak_difference_deg"] < 1e-10 and report["jensen_shannon_divergence_base2"] < 1e-10
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(external), ""))
    window.compare_fiji()
    assert (folder / "fiji_spatial.json").is_file() and not window.comparison_view.pixmap.isNull()
    external.write_text("angle_deg,weight\n0,0\n90,0\n")
    with pytest.raises(ValueError):
        compare_histograms(folder / "histograms.csv", external, "spatial")


def test_cli(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "cli.py"), "generate", "--out", str(tmp_path / "samples")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [
            sys.executable,
            str(root / "cli.py"),
            "analyze",
            str(tmp_path / "samples/stripes_030.png"),
            "--out",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out/summary.json").is_file()


def test_fiji_inclusive_endpoints(tmp_path):
    from texture.comparison import read_histogram

    path = tmp_path / "endpoints.csv"
    path.write_text("angle_deg,weight\n0,2\n90,1\n180,3\n")
    angles, hist = read_histogram(path)
    assert np.allclose(angles, [0, 90])
    assert np.allclose(hist, [5 / 6, 1 / 6])


def test_import_real_directionality_reference():
    root = Path(__file__).resolve().parents[1]
    folder = root / "results/fiji/stripes_030_noise015"
    report, *_ = compare_histograms(
        folder / "python_histograms.csv", folder / "fourier_components.csv", "fourier"
    )
    assert report["peak_difference_deg"] < 0.1
    assert report["jensen_shannon_divergence_base2"] < 0.1
