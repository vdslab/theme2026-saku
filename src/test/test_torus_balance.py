"""Step 2 の4つの階層バランス手法に対する回帰テスト。"""

import pytest

from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration


METHODS = ("diff", "diff_square", "qp", "barycenter")


# グラフ形状、頂点、辺、固定トーラス辺数、固定レイヤー数
CASES = (
    (
        "path",
        list(range(5)),
        [(0, 1), (1, 2), (2, 3), (3, 4)],
        0,
        5,
    ),
    (
        "diamond",
        list(range(4)),
        [(0, 1), (0, 2), (1, 3), (2, 3)],
        0,
        3,
    ),
    (
        "fan_out_and_in",
        list(range(6)),
        [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4), (4, 5)],
        0,
        4,
    ),
    (
        "cycle_5",
        list(range(5)),
        [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)],
        1,
        5,
    ),
    (
        "joined_cycles",
        list(range(5)),
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
        2,
        5,
    ),
    (
        "bidirectional_star",
        list(range(4)),
        [(0, 1), (1, 0), (0, 2), (2, 0), (0, 3), (3, 0)],
        3,
        2,
    ),
)


def _edge_constraint_holds(y_u, y_v, is_torus, layer_count, minimum_span=1):
    """本実装で使う3本のBig-M制約を、整数化後の解に対して再評価する。"""
    t = int(bool(is_torus))
    return (
        y_u - y_v <= layer_count * t
        and y_u - y_v >= minimum_span - layer_count * (1 - t)
        and y_v - y_u >= minimum_span - layer_count * t
    )


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("_name,vertices,edges,torus_count,layer_count", CASES)
def test_balance_methods_return_feasible_assignments(
    method, _name, vertices, edges, torus_count, layer_count
):
    y_val, t_val, layer_dict, _runtime = balance_layer_assignment(
        vertices, edges, torus_count, layer_count, method
    )

    assert set(y_val) == set(vertices)
    assert sum(bool(t_val[edge]) for edge in edges) == torus_count
    assert sorted(node for nodes in layer_dict.values() for node in nodes) == vertices
    assert all(0 <= y_val[node] < layer_count for node in vertices)
    assert all(
        _edge_constraint_holds(
            y_val[u], y_val[v], t_val[(u, v)], layer_count
        )
        for u, v in edges
    )


@pytest.mark.parametrize("_name,vertices,edges,torus_count,layer_count", CASES)
def test_continuous_relaxation_does_not_create_same_layer_edges(
    _name, vertices, edges, torus_count, layer_count
):
    """連続QPの解を丸めた後も、端点が同じ整数レイヤーにならないことを固定する。"""
    y_val, _t_val, _layer_dict, _runtime = balance_layer_assignment(
        vertices, edges, torus_count, layer_count, "qp"
    )

    same_layer_edges = [(u, v) for u, v in edges if y_val[u] == y_val[v]]
    assert same_layer_edges == []


@pytest.mark.xfail(
    strict=True,
    reason=(
        "連続解で1だけ離れた隣接する半整数がPythonの偶数丸めで同じ整数になる"
    ),
)
def test_continuous_relaxation_known_half_integer_rounding_counterexample():
    """拡張実験で見つかったqpの同一レイヤー辺を再現する。"""
    vertices = list(range(12))
    edges = [
        (0, 1), (0, 5), (0, 6), (1, 11), (2, 5),
        (4, 2), (5, 2), (6, 0), (6, 3), (6, 4),
        (6, 9), (7, 8), (8, 7), (10, 8), (11, 10),
    ]
    y_val, _t_val, _layer_dict, _runtime = balance_layer_assignment(
        vertices, edges, torus_count=3, layer_count=4, func_type="qp"
    )

    assert all(y_val[u] != y_val[v] for u, v in edges)


@pytest.mark.parametrize("_name,vertices,edges,torus_count,layer_count", CASES)
def test_each_exact_objective_dominates_the_other_methods_on_its_metric(
    _name, vertices, edges, torus_count, layer_count
):
    """diff と diff_square が、それぞれ宣言した目的で劣らないことを確認する。"""
    assignments = {}
    for method in METHODS:
        y_val, t_val, _layer_dict, _runtime = balance_layer_assignment(
            vertices, edges, torus_count, layer_count, method
        )
        spans = [
            y_val[v] - y_val[u] + layer_count * int(bool(t_val[(u, v)]))
            for u, v in edges
        ]
        assignments[method] = (sum(spans), sum(span * span for span in spans))

    tolerance = 1e-8
    assert assignments["diff"][0] <= min(
        value[0] for value in assignments.values()
    ) + tolerance
    assert assignments["diff_square"][1] <= min(
        value[1] for value in assignments.values()
    ) + tolerance


@pytest.mark.parametrize(
    "vertices,edges,expected_layers,expected_torus",
    (
        (list(range(3)), [(0, 1), (1, 2)], 3, 0),
        (list(range(3)), [(0, 1), (1, 2), (2, 0)], 3, 1),
    ),
)
def test_layer_search_returns_a_count_not_a_maximum_index(
    vertices, edges, expected_layers, expected_torus
):
    layer_count, torus_count, _runtime = find_minimum_torus_configuration(
        vertices, edges
    )

    assert layer_count == expected_layers
    assert torus_count == expected_torus
