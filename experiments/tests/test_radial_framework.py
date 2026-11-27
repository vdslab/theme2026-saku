from types import SimpleNamespace

from experiments.torus_study.framework import repository_baseline
from radial_layout.random_graph import generate_watts_strogatz_digraph


def test_sampled_spiral_crossings_match_embedding_score():
    nodes, edges = generate_watts_strogatz_digraph(
        size=20, neighbor_count=4, seed=11, rewiring_probability=0.3,
    )
    metrics, _ = repository_baseline(SimpleNamespace(nodes=nodes, edges=edges), radial=True)
    assert metrics["geometric_crossings"] == metrics["combinatorial_crossings"]
    assert metrics["geometric_crossings_on_layout_edges"] == metrics["combinatorial_crossings"]
    assert metrics["contact_events"] == metrics["overlapping_edge_pairs"] == 0


def test_reciprocal_edges_count_as_one_shared_centerline_with_two_directions():
    graph = SimpleNamespace(nodes=(0, 1, 2, 3, 4),
                            edges=((0, 1), (1, 0), (1, 2), (2, 3), (3, 4), (0, 4)))
    metrics, (routes, _) = repository_baseline(graph, radial=True)
    points = {route.edge: route.points for route in routes}
    assert points[0, 1] == points[1, 0][::-1]
    assert metrics["overlapping_edge_pairs"] == 1
    assert metrics["contact_events"] == 0
    assert metrics["geometric_crossings_on_layout_edges"] == metrics["combinatorial_crossings"]
