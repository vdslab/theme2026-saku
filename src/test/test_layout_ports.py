"""Check port parity and isolation from legacy layout modules."""

from dataclasses import fields, is_dataclass
import importlib
import os
from pathlib import Path
import subprocess
import sys

import matplotlib.pyplot as plt
import pytest


def normalize(value):
    # The ports intentionally have their own dataclass identities.
    if is_dataclass(value):
        return tuple((field.name, normalize(getattr(value, field.name))) for field in fields(value))
    if isinstance(value, dict):
        return {normalize(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(normalize(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(normalize(item) for item in value)
    return value


def run_layout(package, kind, nodes, edges, output):
    def module(name):
        return importlib.import_module(f"{package}.{name}")

    acyclic = module("cycle_removal").remove_cycles(nodes, edges)
    ranks = module("layer_assignment").assign_layers(acyclic.nodes, acyclic.edges)
    hierarchy = module("dummy_insertion").insert_dummy_nodes(acyclic.nodes, acyclic.edges, ranks)
    crossing = module("crossing_reduction")
    reduced = crossing.reduce_crossings(hierarchy.layers, hierarchy.edges)
    if kind == "radial":
        coordinates = module("coordinate_assignment").assign_coordinates(reduced.order)
        figure = module("drawing").create_radial_figure(
            acyclic.nodes, edges, coordinates.cartesian, coordinates.polar,
            coordinates.radii, hierarchy.chains, reduced.winding, acyclic.reversed_edges,
        )
        assert reduced.crossings <= crossing.count_crossings(hierarchy.layers, hierarchy.edges)
    else:
        coordinates = module("coordinate_assignment").assign_coordinates(
            reduced, hierarchy.edges, dummy_nodes=hierarchy.dummy_nodes,
        )
        figure = module("drawing").create_hierarchical_figure(
            acyclic.nodes, edges, coordinates, hierarchy.chains, acyclic.reversed_edges,
        )
        assert crossing.count_crossings(reduced, hierarchy.edges) <= crossing.count_crossings(hierarchy.layers, hierarchy.edges)
    try:
        figure.savefig(output)
    finally:
        plt.close(figure)
    assert output.stat().st_size > 1000
    return normalize((acyclic, ranks, hierarchy, reduced, coordinates))


@pytest.mark.parametrize("kind", ["radial"])
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_port_preserves_layout_and_drawing(kind, seed, tmp_path):
    generator = importlib.import_module(f"{kind}_layout.random_graph")
    nodes, edges = generator.generate_watts_strogatz_digraph(size=10, seed=seed)
    original = run_layout(f"examples.{kind}", kind, nodes, edges, tmp_path / "original.png")
    ported = run_layout(f"{kind}_layout", kind, nodes, edges, tmp_path / "ported.png")
    assert ported == original
    assert (tmp_path / "ported.png").read_bytes() == (tmp_path / "original.png").read_bytes()


@pytest.mark.parametrize("package", ["radial_layout"])
def test_import_and_cli_with_only_src_on_path(package, tmp_path):
    src = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(src), "MPLBACKEND": "Agg"}
    result = subprocess.run(
        [sys.executable, "-c", f"import {package}.main; import sys; "
         "assert not any(name.split('.')[0] in "
         "{'examples', 'main', 'torus_layout', 'coordinate_assignment', "
         "'crossing_reduction', 'layer_assignment', 'drawing', 'gurobipy'} "
         "for name in sys.modules)"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [sys.executable, "-m", package, "--size", "6", "--seed", "7"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
