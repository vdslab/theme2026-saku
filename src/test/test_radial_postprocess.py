import random

from crossing_reduction.radial import (
    _count_all_crossings,
    _postprocess_layer_rotations,
    _rotate_layer_preserving_crossings,
)


def test_postprocess_rotates_by_average_angle_without_changing_crossings():
    order = {0: [0, 1, 2], 1: [3, 4, 5]}
    layers = [0, 1]
    edges = [(0, 4), (1, 5), (2, 3)]
    psi = {(0, 4): 0, (1, 5): 0, (2, 3): 1}
    before = _count_all_crossings(order, psi, layers, edges)

    _postprocess_layer_rotations(
        order,
        psi,
        layers,
        edges,
        fixed_zero_edges=set(),
        rounds=1,
    )

    assert order[1] == [4, 5, 3]
    assert psi == {edge: 0 for edge in edges}
    assert _count_all_crossings(order, psi, layers, edges) == before


def test_rotation_preserves_crossings_for_random_embeddings():
    for seed in range(200):
        rng = random.Random(seed)
        source_size = rng.randint(2, 5)
        target_size = rng.randint(2, 5)
        source = list(range(source_size))
        target = list(range(source_size, source_size + target_size))
        order = {0: source, 1: target}
        edges = [
            (u, v)
            for u in source
            for v in target
            if rng.random() < 0.45
        ]
        psi = {edge: rng.choice((-1, 0, 1)) for edge in edges}
        before = _count_all_crossings(order, psi, [0, 1], edges)
        positions = {
            layer: {node: index for index, node in enumerate(nodes)}
            for layer, nodes in order.items()
        }
        node_to_layer = {
            node: layer for layer, nodes in order.items() for node in nodes
        }

        _rotate_layer_preserving_crossings(
            1,
            rng.randint(-2 * target_size, 2 * target_size),
            order,
            positions,
            psi,
            edges,
            node_to_layer,
        )

        assert _count_all_crossings(order, psi, [0, 1], edges) == before


def test_postprocess_keeps_fixed_torus_offsets_zero():
    order = {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    layers = [0, 1, 2]
    edges = [(0, 2), (1, 3), (2, 4), (3, 5), (4, 0), (5, 1)]
    fixed = {(4, 0), (5, 1)}
    psi = {edge: 0 for edge in edges}

    _postprocess_layer_rotations(order, psi, layers, edges, fixed, rounds=2)

    assert all(psi[edge] == 0 for edge in fixed)
