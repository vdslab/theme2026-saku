import math

from coordinate_assignment.brandes_koepf import (
    assign_torus_brandes_koepf_coordinates,
)


def _assert_periodic_order(pos, order, period, min_gap=1.0):
    for nodes in order.values():
        if not nodes:
            continue
        y_values = [pos[node][1] for node in nodes]
        assert all(math.isfinite(value) for value in y_values)
        assert all(-1e-9 <= value <= period - min_gap + 1e-9 for value in y_values)
        assert all(
            right - left >= min_gap - 1e-9
            for left, right in zip(y_values, y_values[1:])
        )
        seam_gap = period + y_values[0] - y_values[-1]
        assert seam_gap >= min_gap - 1e-9


def test_brandes_koepf_coordinates_cover_all_nodes_and_preserve_order():
    order = {
        0: [0, 1],
        1: [2, 3],
        2: [4, 5],
    }
    edges = [(0, 2), (1, 3), (2, 4), (3, 5)]

    pos = assign_torus_brandes_koepf_coordinates(order, order, edges)

    assert set(pos) == {0, 1, 2, 3, 4, 5}
    _assert_periodic_order(pos, order, period=2.0)


def test_brandes_koepf_coordinates_accept_torus_winding_numbers():
    order = {
        0: [0, 1],
        1: [2, 3],
    }
    edges = [(0, 2), (1, 3), (0, 3)]
    psi = {(0, 2): 0, (1, 3): 0, (0, 3): 1}

    pos = assign_torus_brandes_koepf_coordinates(
        order=order,
        layer_dict=order,
        edges=edges,
        psi=psi,
    )

    assert set(pos) == {0, 1, 2, 3}
    assert pos[0][1] < pos[1][1]
    assert pos[2][1] < pos[3][1]
    _assert_periodic_order(pos, order, period=2.0)


def test_coordinates_stay_inside_periodic_domain_for_regression_case():
    order = {
        0: [0, 1],
        1: [2, 3, 4, 5],
        2: [6, 7, 8, 9],
        3: [10, 11, 12],
        4: [13, 14, 15],
        5: [16, 17, 18, 19],
    }
    edges = [
        (0, 5),
        (1, 2),
        (2, 6),
        (3, 9),
        (6, 10),
        (9, 10),
        (11, 14),
        (14, 18),
        (14, 19),
        (18, 0),
    ]
    t_val = {edge: edge == (18, 0) for edge in edges}

    pos = assign_torus_brandes_koepf_coordinates(
        order=order,
        layer_dict=order,
        edges=edges,
        t_val=t_val,
    )

    _assert_periodic_order(pos, order, period=4.0)


def test_four_direction_balancing_is_mirror_invariant():
    order = {0: [0, 1, 2], 1: [3, 4, 5], 2: [6, 7, 8]}
    reversed_order = {layer: list(reversed(nodes)) for layer, nodes in order.items()}
    edges = [(7, 0), (0, 3), (3, 7)]
    t_val = {edge: edge == (7, 0) for edge in edges}

    pos = assign_torus_brandes_koepf_coordinates(
        order, order, edges, t_val=t_val, smooth_iterations=0
    )
    mirrored_pos = assign_torus_brandes_koepf_coordinates(
        reversed_order, order, edges, t_val=t_val, smooth_iterations=0
    )

    for node in pos:
        assert abs(mirrored_pos[node][1] - (2.0 - pos[node][1])) < 1e-9


def test_incomplete_order_is_completed_without_losing_nodes():
    layer_dict = {0: [0, 1], 1: [2, 3]}
    pos = assign_torus_brandes_koepf_coordinates(
        order={0: [1], 1: [3]},
        layer_dict=layer_dict,
        edges=[(0, 2), (1, 3)],
    )

    assert set(pos) == {0, 1, 2, 3}


def test_inner_dummy_segment_is_preferred_in_type_one_conflict():
    order = {
        0: ["a", "dummy-1"],
        1: ["dummy-2", "b"],
        2: ["c", "d", "e"],
    }
    edges = [("dummy-1", "dummy-2"), ("a", "b")]

    pos = assign_torus_brandes_koepf_coordinates(
        order=order,
        layer_dict=order,
        edges=edges,
        original_nodes={"a", "b", "c", "d", "e"},
        smooth_iterations=0,
    )

    assert pos["dummy-1"][1] == pos["dummy-2"][1]


def test_smoothing_includes_horizontal_wrap_edges():
    order = {0: [0, 1], 1: [2], 2: [3, 4, 5]}
    edges = [(5, 0)]
    t_val = {(5, 0): True}

    unsmoothed = assign_torus_brandes_koepf_coordinates(
        order, order, edges, t_val=t_val, smooth_iterations=0
    )
    smoothed = assign_torus_brandes_koepf_coordinates(
        order, order, edges, t_val=t_val, smooth_iterations=4
    )

    before = abs(unsmoothed[5][1] - unsmoothed[0][1])
    after = abs(smoothed[5][1] - smoothed[0][1])
    assert after < before
