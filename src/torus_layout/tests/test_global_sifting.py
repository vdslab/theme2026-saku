from itertools import combinations, product

import pytest

from generator import generate_graph
from torus_layout.crossing import count_crossings, reduce_crossings
from torus_layout.crossing.global_sifting import _strip_score, sift_blocks
from torus_layout.crossing.lib.crossings import crossings_between_edges, pair_crossings, pair_positions
from torus_layout.crossing.lib.embedding import edges_by_directed_strip
from torus_layout.models import Graph, LayerAssignmentResult
from torus_layout.reporting import boundary_metrics
from torus_layout.subdivision import insert_dummy_nodes


def test_global_sifting_preserves_block_order_across_the_horizontal_cut():
    ranks = {"p": 3, "q": 3, "r": 2, "s": 2, "a": 0, "b": 1, "c": 4}
    edges = (("p", "s"), ("q", "r"), ("a", "b"), ("q", "c"))
    flags = {edge: ranks[edge[0]] > ranks[edge[1]] for edge in edges}
    graph = insert_dummy_nodes(Graph(tuple(ranks), edges), LayerAssignmentResult(ranks, flags, 0))

    before = reduce_crossings(graph, 0, sifting_method="global",
                              unwind=False, optimize_seams=False)
    after = reduce_crossings(graph, 5, sifting_method="global",
                             unwind=False, optimize_seams=False)
    assert count_crossings(graph, after) <= count_crossings(graph, before)

    dummy = graph.dummy_nodes
    internal = [edge for edge in graph.graph.edges if set(edge) <= dummy]
    strips = edges_by_directed_strip(after.order, sorted(graph.layers), internal)
    assert len(strips[4, 0]) == 2
    for pair, strip in strips.items():
        source, target = pair_positions(after.order, *pair)
        for first, second in combinations(strip, 2):
            assert crossings_between_edges(first, second, source, target, after.winding_numbers) == 0


def test_global_rotation_is_opt_in():
    nodes, edges, _ = generate_graph("watts_strogatz", 25, seed=2388070675, k=4, p=0.1)
    ranks = dict(enumerate((18, 19, 20, 21, 0, 1, 2, 3, 4, 5, 5, 6, 6, 7, 8, 9, 10, 11, 12, 12,
                           13, 14, 15, 16, 17)))
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    graph = insert_dummy_nodes(Graph(tuple(nodes), tuple(edges)), LayerAssignmentResult(ranks, flags, 0))

    result = reduce_crossings(graph, sifting_method="global", unwind=False)
    metrics = boundary_metrics(graph, result.winding_numbers)

    assert count_crossings(graph, result) == 2
    assert metrics["x_seam_events"] == 2
    assert metrics["y_seam_edges"] == metrics["y_seam_events"] == 5
    rotated = reduce_crossings(graph, sifting_method="global", unwind=False, algo2=True)
    assert count_crossings(graph, rotated) == 2
    assert boundary_metrics(graph, rotated.winding_numbers)["y_seam_events"] == 12


def test_experimental_block_schedule_keeps_round_budget_at_a_fixed_point():
    ranks = {0: 0, 1: 0, 2: 1, 3: 1}
    edges = ((0, 2), (1, 3))
    graph = insert_dummy_nodes(Graph(tuple(ranks), edges),
                               LayerAssignmentResult(ranks, dict.fromkeys(edges, False), 0))
    forward, alternating, early = [], [], []
    options = dict(early_exit=False)
    result = sift_blocks(graph, graph.layers, [0, 1], 5, **options,
                         on_round_start=lambda visits, *_: forward.append(visits))
    assert sift_blocks(graph, graph.layers, [0, 1], 5, **options, alternate_visits=True,
                       on_round_start=lambda visits, *_: alternating.append(visits)) == result
    assert sift_blocks(graph, graph.layers, [0, 1], 5,
                       on_round_start=lambda visits, *_: early.append(visits)) == result
    assert len(early) == 1
    assert len(early[0]) == 4
    assert forward == early * 5
    assert alternating == [early[0], early[0][::-1], early[0], early[0][::-1], early[0]]


@pytest.mark.parametrize("outgoing", [False, True])
def test_parting_matches_winding_enumeration_for_either_endpoint(outgoing):
    order = {0: [0, 1, 2], 1: [3, 4, 5]}
    edges = [(0, 3), (1, 3), (2, 3), (0, 4), (1, 4), (2, 5)]
    variable = edges[:3]
    if outgoing:
        order = {0: order[1], 1: order[0]}
        edges = [(v, u) for u, v in edges]
        variable = edges[:3]
    winding = dict(zip(edges, (0, 0, 0, 0, 1, -1)))
    score, offsets = _strip_score(order, winding, (0, 1), edges, set(variable), outgoing=outgoing)
    expected = min(pair_crossings(order, winding | dict(zip(variable, offsets)), 0, 1, edges)
                   for offsets in product((-1, 0, 1), repeat=len(variable)))
    assert score == expected
    assert score == pair_crossings(order, winding | offsets, 0, 1, edges)


@pytest.mark.parametrize("seed", range(12))
def test_sparse_candidates_preserve_first_minimizer_and_windings(seed):
    from random import Random

    from torus_layout.crossing.initialization import initial_orders

    rng = Random(seed)
    layer_count = 2 + seed % 4
    nodes = tuple(range(layer_count * 3))
    ranks = {node: node // 3 for node in nodes}
    edges = tuple(
        (source, target) for source in nodes for target in nodes
        if ranks[source] != ranks[target] and rng.random() < .21
    )
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    subgraph = insert_dummy_nodes(Graph(nodes, edges), LayerAssignmentResult(ranks, flags, 0))
    layers = sorted(subgraph.layers)
    start = initial_orders(subgraph.layers, layers, list(subgraph.graph.edges))[0]
    baseline = sift_blocks(subgraph, start, layers, rounds=3)
    sparse = sift_blocks(subgraph, start, layers, rounds=3, sparse_candidates=True)
    assert sparse == baseline
    assert sift_blocks(subgraph, start, layers, rounds=3, sparse_candidates=True,
                       local_winding=True) == baseline
    assert sift_blocks(subgraph, start, layers, rounds=3, sparse_candidates=True,
                       integer_scoring=True, cache_strip_scores=True, incremental_orders=True,
                       incremental_scores=True) == baseline
    stopped = sift_blocks(subgraph, start, layers, rounds=3, should_stop=lambda: True)
    assert stopped == sift_blocks(subgraph, start, layers, rounds=0)
