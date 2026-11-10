"""Check standalone layout pipelines and isolation from legacy modules."""

import importlib
import os
from pathlib import Path
import subprocess
import sys

import matplotlib.pyplot as plt
import pytest



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
    node_layers = {
        node: layer for layer, members in hierarchy.layers.items() for node in members
    }
    assert all(node_layers[v] == node_layers[u] + 1 for u, v in hierarchy.edges)
    positions = coordinates.cartesian if kind == "radial" else coordinates
    assert set(positions) == set(acyclic.nodes) | set(hierarchy.dummy_nodes)
    for source, target in acyclic.edges:
        chain = hierarchy.chains[(source, target)]
        assert chain[0] == source and chain[-1] == target
        assert all(edge in hierarchy.edges for edge in zip(chain, chain[1:]))


@pytest.mark.parametrize("kind", ["sugiyama", "radial"])
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_port_pipeline_and_drawing(kind, seed, tmp_path):
    generator = importlib.import_module(f"{kind}_layout.random_graph")
    nodes, edges = generator.generate_watts_strogatz_digraph(size=10, seed=seed)
    run_layout(f"{kind}_layout", kind, nodes, edges, tmp_path / "ported.png")


@pytest.mark.parametrize("package", ["sugiyama_layout", "radial_layout"])
def test_import_and_cli_with_only_src_on_path(package, tmp_path):
    src = Path(__file__).resolve().parents[2]
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
