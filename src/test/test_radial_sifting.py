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
