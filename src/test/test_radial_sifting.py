import crossing_reduction.radial as radial


def test_sifting_alternates_forward_and_backward_pairs(monkeypatch):
    calls = []
    order = {0: [0], 1: [1], 2: [2]}
    monkeypatch.setattr(
        radial,
        "_sift_two_layer_pair",
        lambda fixed, free, order, psi, edges: calls.append((fixed, free)),
    )

    radial._run_sifting(order, {}, [0, 1, 2], [], rounds=3)

    assert calls == [
        (0, 1),
        (1, 2),
        (2, 0),
        (0, 2),
        (2, 1),
        (1, 0),
        (0, 1),
        (1, 2),
        (2, 0),
    ]


def test_two_layer_sifting_reduces_crossings_and_keeps_fixed_layer():
    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3), (1, 2)]
    psi = {edge: 0 for edge in edges}
    fixed_before = list(order[0])
    crossings_before = radial._pair_crossings(order, psi, 0, 1, edges)

    radial._sift_two_layer_pair(0, 1, order, psi, edges)

    assert order[0] == fixed_before
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
