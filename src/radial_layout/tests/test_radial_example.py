import math

import matplotlib.pyplot as plt

from radial_layout.coordinate_assignment import assign_coordinates
from radial_layout.crossing_reduction import count_crossings, reduce_crossings
from radial_layout.cycle_removal import remove_cycles
from radial_layout.drawing import create_radial_figure
from radial_layout.dummy_insertion import DummyNode, insert_dummy_nodes
from radial_layout.layer_assignment import assign_layers


def test_radial_pipeline_creates_proper_outward_hierarchy():
    nodes = (0, 1, 2, 3, 4)
    edges = ((0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (1, 4))

    acyclic = remove_cycles(nodes, edges)
    ranks = assign_layers(acyclic.nodes, acyclic.edges)
    hierarchy = insert_dummy_nodes(acyclic.nodes, acyclic.edges, ranks)
    embedding = reduce_crossings(hierarchy.layers, hierarchy.edges, rounds=2)
    coordinates = assign_coordinates(embedding.order)

    node_layers = {
        node: layer for layer, layer_nodes in hierarchy.layers.items() for node in layer_nodes
    }
    assert all(node_layers[target] == node_layers[source] + 1 for source, target in hierarchy.edges)
    assert set(embedding.winding.values()) <= {-1, 0, 1}
    assert embedding.crossings <= count_crossings(hierarchy.layers, hierarchy.edges)
    assert all(
        math.isclose(math.hypot(*coordinates.cartesian[node]), coordinates.polar[node][0])
        for node in coordinates.cartesian
    )


def test_long_edges_are_split_into_hidden_dummy_bends():
    hierarchy = insert_dummy_nodes(
        nodes=(0, 1, 2),
        edges=((0, 2), (0, 1), (1, 2)),
        ranks={0: 0, 1: 1, 2: 2},
    )

    assert len(hierarchy.chains[(0, 2)]) == 3
    assert isinstance(hierarchy.chains[(0, 2)][1], DummyNode)
    assert all(
        target.layer == source.layer + 1
        if isinstance(source, DummyNode) and isinstance(target, DummyNode)
        else True
        for source, target in hierarchy.edges
    )


def test_radial_figure_can_be_saved(tmp_path):
    nodes = (0, 1, 2, 3)
    edges = ((0, 1), (0, 2), (1, 3), (2, 3))
    ranks = assign_layers(nodes, edges)
    hierarchy = insert_dummy_nodes(nodes, edges, ranks)
    embedding = reduce_crossings(hierarchy.layers, hierarchy.edges, rounds=1)
    coordinates = assign_coordinates(embedding.order)
    figure = create_radial_figure(
        nodes,
        edges,
        coordinates.cartesian,
        coordinates.polar,
        coordinates.radii,
        hierarchy.chains,
        embedding.winding,
        frozenset(),
    )
    output = tmp_path / "radial.svg"
    figure.savefig(output)
    plt.close(figure)

    assert output.stat().st_size > 1_000
