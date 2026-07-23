import crossing_reduction.radial as radial


def test_rounds_repeat_each_pair_during_two_forward_passes(monkeypatch):
    calls = []
    order = {0: [0], 1: [1], 2: [2]}
    monkeypatch.setattr(
        radial,
        "_sift_two_layer_pair",
        lambda fixed, free, order, psi, edges, **kwargs: calls.append((fixed, free)),
    )

    radial._run_sifting(order, {}, [0, 1, 2], [], rounds=3)

    assert calls == [
        (0, 1),
        (0, 1),
        (0, 1),
        (1, 2),
        (1, 2),
        (1, 2),
        (2, 0),
        (2, 0),
        (2, 0),
        (0, 1),
        (0, 1),
        (0, 1),
        (1, 2),
        (1, 2),
        (1, 2),
    ]


def test_global_guard_never_returns_more_crossings_than_initial_order():
    order = {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    edges = [
        (0, 3),
        (1, 2),
        (2, 5),
        (3, 4),
        (4, 1),
        (5, 0),
    ]
    psi = {edge: 0 for edge in edges}
    initial = radial._count_all_crossings(order, psi, [0, 1, 2], edges)

    radial._run_sifting_with_global_guard(
        order, psi, [0, 1, 2], edges, rounds=2
    )

    assert radial._count_all_crossings(order, psi, [0, 1, 2], edges) <= initial


def test_two_layer_sifting_reduces_crossings_and_keeps_fixed_layer():
    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3), (1, 2)]
    psi = {edge: 0 for edge in edges}
    fixed_before = list(order[0])
    crossings_before = radial._pair_crossings(order, psi, 0, 1, edges)

    radial._sift_two_layer_pair(0, 1, order, psi, edges)

    assert order[0] == fixed_before
    assert radial._pair_crossings(order, psi, 0, 1, edges) < crossings_before


def test_fixed_winding_sifting_changes_order_but_not_winding():
    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3), (1, 2)]
    psi = {(0, 3): 0, (1, 2): 0}
    crossings_before = radial._pair_crossings(order, psi, 0, 1, edges)

    radial._sift_two_layer_pair(
        0, 1, order, psi, edges, optimize_winding=False
    )

    assert psi == {(0, 3): 0, (1, 2): 0}
    assert radial._pair_crossings(order, psi, 0, 1, edges) < crossings_before


def test_backward_sifting_reorients_edges():
    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3), (1, 2)]
    psi = {edge: 0 for edge in edges}
    fixed_before = list(order[1])

    radial._sift_two_layer_pair(1, 0, order, psi, edges)

    assert order[1] == fixed_before
    pair_edges, oriented_psi, _ = radial._oriented_pair_embedding(
        order, psi, 1, 0, edges
    )
    assert radial._pair_crossings(order, oriented_psi, 1, 0, pair_edges) == 0


def test_equal_crossing_candidates_do_not_use_horizontal_tiebreak():
    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3)]
    psi = {(0, 3): 0}

    radial._sift_two_layer_pair(0, 1, order, psi, edges)

    assert order[1] == [2, 3]


def test_two_layer_sifting_counts_the_whole_pair_only_once(monkeypatch):
    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 2), (1, 2), (0, 3), (1, 3)]
    psi = {edge: 0 for edge in edges}
    original_pair_crossings = radial._pair_crossings
    calls = 0

    def count_calls(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_pair_crossings(*args, **kwargs)

    monkeypatch.setattr(radial, "_pair_crossings", count_calls)

    radial._sift_two_layer_pair(0, 1, order, psi, edges)

    assert calls == 1


def test_edge_offset_delta_matches_whole_pair_recalculation():
    order = {0: [0, 1, 2], 1: [3, 4]}
    edges = [(0, 3), (1, 3), (1, 4), (2, 4)]
    psi = {edge: 0 for edge in edges}
    changed_edge = (1, 3)

    whole_before = radial._pair_crossings(order, psi, 0, 1, edges)
    edge_before = radial._crossings_for_edge(
        changed_edge, edges, order, psi, 0, 1
    )
    psi[changed_edge] = -1
    whole_after = radial._pair_crossings(order, psi, 0, 1, edges)
    edge_after = radial._crossings_for_edge(
        changed_edge, edges, order, psi, 0, 1
    )

    assert whole_after - whole_before == edge_after - edge_before


def test_adjacent_swap_delta_matches_whole_pair_recalculation():
    order = {0: [0, 1, 2], 1: [3, 4, 5]}
    edges = [(0, 3), (2, 3), (1, 4), (0, 5), (2, 5)]
    psi = {edge: 0 for edge in edges}
    first_incident = [(0, 3), (2, 3)]
    second_incident = [(1, 4)]

    whole_before = radial._pair_crossings(order, psi, 0, 1, edges)
    sets_before = radial._crossings_between_edge_sets(
        first_incident, second_incident, order, psi, 0, 1
    )
    order[1][0], order[1][1] = order[1][1], order[1][0]
    whole_after = radial._pair_crossings(order, psi, 0, 1, edges)
    sets_after = radial._crossings_between_edge_sets(
        first_incident, second_incident, order, psi, 0, 1
    )

    assert whole_after - whole_before == sets_after - sets_before


def test_algorithm_2_rotates_free_layer_and_reduces_winding():
    order = {0: [0, 1, 2], 1: [3, 4, 5]}
    edges = [(0, 4), (1, 5), (2, 3)]
    psi = {(0, 4): 0, (1, 5): 0, (2, 3): 1}
    crossings_before = radial._pair_crossings(order, psi, 0, 1, edges)

    radial._postprocess_two_layer_rotation(0, 1, order, psi, edges)

    assert order[1] == [4, 5, 3]
    assert psi == {edge: 0 for edge in edges}
    assert radial._pair_crossings(order, psi, 0, 1, edges) == crossings_before


def test_algorithm_2_updates_edges_on_both_sides_of_rotated_layer():
    order = {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    edges = [(0, 3), (1, 2), (2, 5), (3, 4)]
    psi = {edge: 0 for edge in edges}
    crossings_before = radial._count_all_crossings(order, psi, [0, 1, 2], edges)

    radial._rotate_layer_preserving_embedding(1, 1, order, psi, edges)

    assert order[1] == [3, 2]
    assert psi[(1, 2)] == -1
    assert psi[(2, 5)] == 1
    assert radial._count_all_crossings(order, psi, [0, 1, 2], edges) == crossings_before


def test_inner_segment_crossing_uses_edge_count_as_weight():
    order = {0: [0, 10], 1: [11, 1]}
    edges = [(10, 11), (0, 1)]
    psi = {edge: 0 for edge in edges}
    weights = radial._sifting_edge_weights(edges, {10, 11}, edge_count=7)

    assert radial._pair_crossings(order, psi, 0, 1, edges) == 1
    assert radial._pair_crossings(
        order, psi, 0, 1, edges, edge_weights=weights
    ) == 7
