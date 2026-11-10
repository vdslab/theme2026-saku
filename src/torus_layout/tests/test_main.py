"""Exercise the full CLI with an explicit, real local Gurobi environment."""

import json
import os
from pathlib import Path
import subprocess

from PIL import Image
import pytest

from torus_layout.main import main
from torus_layout.layering.lib.solver import _local_license


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("entrypoint", ["module", "script"])
def test_entrypoint_runs_full_pipeline_and_saves_comparison(tmp_path, entrypoint):
    environment = dict(os.environ)
    environment.update(PYTHONPATH=str(ROOT / "src"), MPLBACKEND="Agg",
                       MPLCONFIGDIR=str(tmp_path / "mpl"), PYTHONDONTWRITEBYTECODE="1")
    entry = ["-m", "torus_layout"] if entrypoint == "module" else ["src/torus_layout/main.py"]
    if entrypoint == "script":
        environment.pop("PYTHONPATH", None)
    command = [str(ROOT / "theme2026-saku/bin/python"), *entry,
               "--nodes", "12", "--seed", "0", "--rounds", "1",
               "--local-license", "--compare-seams", "--no-show", "--output-dir", str(tmp_path)]
    completed = subprocess.run(command, cwd=ROOT, env=environment,
                               capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads((tmp_path / "result.json").read_text())
    assert payload["status"] == "completed"
    assert payload["settings"]["pipeline"]["optimize_seams"] is True
    assert payload["settings"]["pipeline"]["coordinate_method"] == "brandes_koepf"
    assert payload["settings"]["license_mode"] == "local"
    assert payload["settings"]["drawing"]["tile_surroundings"] is True
    metrics = payload["metrics"]
    assert metrics["original_nodes"] == 12
    assert metrics["seam_segments"] < metrics["seam_segments_before"]
    assert metrics["crossings"] == metrics["crossings_before"]
    assert len(payload["coordinates"]) == metrics["subdivided_nodes"]
    for name in ("layout.png", "before_seam.png"):
        with Image.open(tmp_path / name) as image:
            assert image.width > 0 and image.height > 0
            image.verify()
    assert "境界通過線分数" in completed.stdout


def test_cli_can_disable_dp_and_select_bk(tmp_path, capsys, monkeypatch):
    import matplotlib.pyplot as plt

    def unexpected_show(*args, **kwargs):
        pytest.fail("--no-show must not open a window")

    monkeypatch.setattr(plt, "show", unexpected_show)
    assert main(["--nodes", "6", "--seed", "0", "--rounds", "0",
                 "--local-license", "--no-optimize-seams", "--compare-seams",
                 "--no-tile-surroundings", "--no-show",
                 "--coordinate-method", "brandes_koepf", "--output-dir", str(tmp_path)]) == 0
    payload = json.loads((tmp_path / "result.json").read_text())
    assert payload["settings"]["pipeline"]["optimize_seams"] is False
    assert payload["settings"]["drawing"]["tile_surroundings"] is False
    assert payload["metrics"]["seam_segments"] == payload["metrics"]["seam_segments_before"]
    assert _local_license.get() is False
    capsys.readouterr()


@pytest.mark.parametrize("arguments", [
    ["--nodes", "0"], ["--rounds", "-1"], ["--edge-prob", "1.1"],
    ["--bend-weight", "nan"], ["--coordinate-method", "unknown"],
])
def test_cli_rejects_invalid_parameters_before_solving(arguments):
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_failure_returns_nonzero_and_restores_license_scope(monkeypatch, capsys):
    import torus_layout.main as cli

    def fail(*args, **kwargs):
        assert _local_license.get() is True
        raise RuntimeError("solver failure for test")

    monkeypatch.setattr(cli, "run_pipeline", fail)
    assert main(["--local-license", "--nodes", "6"]) == 1
    assert _local_license.get() is False
    assert "solver failure for test" in capsys.readouterr().err


@pytest.mark.parametrize("compare_seams", [False, True])
def test_default_display_waits_until_all_outputs_are_saved(tmp_path, monkeypatch, capsys, compare_seams):
    import matplotlib.pyplot as plt
    import numpy as np

    before = plt.get_fignums()
    calls = []

    def show(*, block):
        assert block is True
        payload = json.loads((tmp_path / "result.json").read_text())
        assert payload["status"] == "completed"
        if compare_seams:
            assert (tmp_path / "before_seam.png").exists()
        figure = plt.gcf()
        with Image.open(tmp_path / "layout.png") as saved:
            assert np.array_equal(figure.axes[0].images[0].get_array(), np.asarray(saved))
        assert "設定・グラフ・座標・評価値" in capsys.readouterr().out
        calls.append(figure)

    monkeypatch.setattr(plt, "show", show)
    arguments = ["--nodes", "6", "--seed", "0", "--rounds", "0", "--local-license",
                 "--output-dir", str(tmp_path)]
    if compare_seams:
        arguments.append("--compare-seams")
    assert main(arguments) == 0
    assert len(calls) == 1
    assert plt.get_fignums() == before
