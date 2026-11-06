"""Capture the running Qt interface for the report; no synthetic UI mockups."""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app import MainWindow, configure_appearance


def main():
    root = Path(__file__).resolve().parents[1]
    output = root/'results/windows/ui'; output.mkdir(parents=True, exist_ok=True)
    app = QApplication([]); configure_appearance(app)
    window = MainWindow(); geometry = window.settings.value('geometry')
    try:
        window.showNormal(); window.resize(1600, 940)
        for _ in range(3): app.processEvents(); time.sleep(.05)
        window.grab().save(str(output/'desktop_empty.png'))
        window.add_files([str(root/'data/samples/stripes_030_noise015.png')])
        window.analyze_current()
        deadline = time.monotonic() + 60
        while window.worker:
            app.processEvents(); time.sleep(.01)
            if time.monotonic() > deadline: raise TimeoutError('Analysis did not finish')
        app.processEvents(); window.grab().save(str(output/'desktop_analysis.png'))
        window.tabs.setCurrentIndex(0); window.set_roi((32,32,160,160)); app.processEvents()
        window.grab().save(str(output/'desktop_roi.png'))
    finally:
        if window.worker:
            window.cancel()
            while window.worker: app.processEvents(); time.sleep(.01)
        window.close()
        if geometry is not None: window.settings.setValue('geometry', geometry)
    print(output)


if __name__ == '__main__': main()
