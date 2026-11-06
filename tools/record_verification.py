"""Record actual JUnit results and installed runtime versions for the report."""
from datetime import datetime, timezone, timedelta
import importlib.metadata
import json
from pathlib import Path
import platform
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
base = ROOT/'results/windows'
suites = ET.parse(base/'tests.xml').getroot().findall('testsuite')
tests = sum(int(s.get('tests', 0)) for s in suites)
failed = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
skipped = sum(int(s.get('skipped', 0)) for s in suites)
if not suites or failed: raise RuntimeError('Missing or failed JUnit verification')
packages = ['numpy', 'scipy', 'opencv-python-headless', 'matplotlib', 'Pillow', 'PySide6-Essentials', 'shiboken6', 'pytest']
versions = {name: importlib.metadata.version(name) for name in packages}
(ROOT/'requirements-windows-lock.txt').write_text(''.join(f'{name}=={v}\n' for name,v in versions.items()), encoding='utf-8')
environment = {'python': platform.python_version(), 'platform': platform.platform(),
               'cpu': platform.processor(), 'packages': versions}
(base/'environment.json').write_text(json.dumps(environment, indent=2), encoding='utf-8')
verification = {'date': datetime.now(timezone(timedelta(hours=7))).date().isoformat(),
                'executed_utc': datetime.now(timezone.utc).isoformat(),
                'python': platform.python_version(), 'platform': platform.platform(),
                'tests': tests, 'skipped': skipped, 'test_status': 'passed', 'qt': 'windows',
                'reference_plugin': 'Directionality 2.3.0', 'imagej': '1.54p',
                'reference_images': 15, 'windows_execution': 'tested', 'macos_execution': 'not_tested',
                'evidence': 'results/windows/tests.xml; results/windows/fiji/run_manifest.json',
                'scope': 'Synthetic ground truth. No claim of accuracy on natural images. GUI evidence rendered from actual Qt/ImageJ/plugin components.'}
(base/'verification.json').write_text(json.dumps(verification, indent=2), encoding='utf-8')
old = ROOT/'results/verification.json'
if old.exists():
    record = json.loads(old.read_text(encoding='utf-8'))
    if record.get('windows_execution') == 'not_tested':
        (ROOT/'results/verification_linux_2026-11-02.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
old.write_text(json.dumps(verification, indent=2), encoding='utf-8')
print(f'Recorded {tests} tests, {skipped} skipped; actual runtime lock saved.')
