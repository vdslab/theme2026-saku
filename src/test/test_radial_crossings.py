from crossing_reduction.radial import _crossings_between_edges


def test_shared_target_edges_can_cross_away_from_the_target():
    edge1 = (0, 2)
    edge2 = (1, 2)
    pi_fixed = {0: 0, 1: 1}
    pi_free = {2: 0}
    psi = {edge1: 0, edge2: -1}

    assert _crossings_between_edges(edge1, edge2, pi_fixed, pi_free, psi) == 1
