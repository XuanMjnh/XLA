from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from fiji.run_reference import fiji_runtime
from texture.analysis import normalized_histogram
from tools.benchmark_voting import add_at_baseline


def test_reference_help_does_not_download(tmp_path):
    script = Path(__file__).resolve().parents[1]/'fiji/run_reference.py'
    result = subprocess.run([sys.executable, str(script), '--help'], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and '--fiji-home' in result.stdout
    assert not list(tmp_path.iterdir())


def test_fiji_runtime_uses_bundled_jdk_and_checks_ambiguity(tmp_path):
    jdk = tmp_path/'java/win64/test/bin'; jdk.mkdir(parents=True)
    for file in ('java.exe', 'javac.exe'): (jdk/file).touch()
    (tmp_path/'jars').mkdir(); (tmp_path/'plugins').mkdir()
    for folder, filename in [('jars','ij-1.54p.jar'), ('plugins','Directionality_-2.3.0.jar'),
                              ('jars','jfreechart-1.5.5.jar'), ('jars','jcommon-1.0.24.jar')]:
        (tmp_path/folder/filename).touch()
    java, jars = fiji_runtime(tmp_path)
    assert java == jdk/'java.exe' and len(jars) == 4
    (tmp_path/'plugins/Directionality_-old.jar').touch()
    with pytest.raises(ValueError, match='exactly one'): fiji_runtime(tmp_path)


@pytest.mark.parametrize('angles,weights', [
    ([0.,179.9,180.,-1.,90.], [1.,2.,3.,4.,5.]),
    ([np.nan,20.,30.,np.inf], [1.,-1.,2.,3.]),
    ([0.,90.], [0.,0.]),
])
def test_optimization_baseline_preserves_periodic_votes(angles, weights):
    expected = add_at_baseline(angles, weights, 180)
    actual = normalized_histogram(angles, weights, 180, 0)
    assert np.allclose(actual, expected, atol=1e-14, rtol=1e-12)
