from collections import defaultdict
import math

from lib.insert_dummy_node import insert_dummy_node

OFFSET_VALUES = (-1, 0, 1)

DEFAULT_ROUND_COUNT = 5


def get_default_round_count():
    return DEFAULT_ROUND_COUNT


def cartesian_barycenter_heuristic(V, A, layer_dict, t_val, w=None):
    """
    Cartesian Barycenterを用いてノード順序を求める（平坦トーラス用）。

    Returns:
        (order, L, A, t_val, psi)
    """
    V, A, L, t_val, w = insert_dummy_node(V, A, layer_dict, t_val, w)
    layers = sorted(L.keys())

    order = _barycentric_order(_base_order(L, layers), layers, A)
    psi = _compute_winding_numbers(A, order, L, layers)

    return order, L, A, t_val, psi


def radial_sifting_heuristic(
    V,
    A,
    layer_dict,
    t_val,
    w=None,
    rounds=DEFAULT_ROUND_COUNT,
    vertical_torus_penalty=0.0,
):
    """
    Radial Siftingを用いてノード順序を求める（平坦トーラス用）。

    各one-sided 2層siftingでは交差数だけを評価する。

    `vertical_torus_penalty` は過去の呼び出し互換のために受け取る。

    Returns:
        (order, L, A, t_val, psi)
    """
    V, A, L, t_val, w = insert_dummy_node(V, A, layer_dict, t_val, w)
    layers = sorted(L.keys())

    order = _initial_orders(L, layers, A)[0]
    psi = _compute_winding_numbers(A, order, L, layers)
    _run_sifting(order, psi, layers, A, rounds)
    return order, L, A, t_val, psi


def count_radial_crossings(order, psi, layer_dict, edges):
    """
    radial交差削減の評価式で総交差数を数える。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        layer_dict: レイヤー辞書。キーの昇順をレイヤー順として使う。
        edges: ダミー挿入後のエッジ集合。

    Returns:
        int: 全隣接レイヤーペアにおける交差数。
    """
    return _count_all_crossings(order, psi, sorted(layer_dict.keys()), edges)


# ---------------------------------------------------------------------------
# Graph/order preparation
# ---------------------------------------------------------------------------


def _base_order(layer_dict, layers):
    """
    レイヤー辞書から探索用の順序辞書を作る。

    Args:
        layer_dict: レイヤーごとのノードリスト。
        layers: 使用するレイヤーキー列。

    Returns:
        dict: 各レイヤーのノード順序のコピー。
    """
    return {layer: list(layer_dict[layer]) for layer in layers}


def _copy_order(order):
    """
    orderをレイヤー単位で浅くコピーする。

    Args:
        order: 各レイヤー内のノード順序。

    Returns:
        dict: ノードリストを複製したorder。
    """
    return {layer: list(nodes) for layer, nodes in order.items()}


def _node_to_layer(order):
    """
    ノードから所属レイヤーを引ける辞書を作る。

    Args:
        order: 各レイヤー内のノード順序。

    Returns:
        dict: node -> layer。
    """
    node_to_layer = {}
    for layer, nodes in order.items():
        for node in nodes:
            node_to_layer[node] = layer
    return node_to_layer


def _edge_endpoints(edge):
    """通常辺と2層処理用の一時ID付き辺から端点を返す。"""
    return edge[0], edge[1]


# ---------------------------------------------------------------------------
# Barycenter initial ordering
# ---------------------------------------------------------------------------


def _initial_orders(L, layers, edges):
    """
    siftingの開始点に使うbarycenter初期解を作る。

    Args:
        L: ダミー挿入後のレイヤー辞書。
        layers: レイヤーキー列。
        edges: ダミー挿入後のエッジ集合。

    Returns:
        list[dict]: 初期order候補。
    """
    base = _base_order(L, layers)
    return [_barycentric_order(base, layers, edges)]


def _barycentric_order(initial_order, layers, edges, passes=3):
    """
    初期順序にbarycenter sweepを複数回かける。

    Args:
        initial_order: sweep前のorder。
        layers: レイヤーキー列。
        edges: エッジ集合。
        passes: forward/backward sweepの反復回数。

    Returns:
        dict: barycenterで整えたorder。
    """
    order = _copy_order(initial_order)
    for _ in range(passes):
        _barycenter_sweep(order, layers, edges, forward=True)
        _barycenter_sweep(order, layers, edges, forward=False)
    return order


def _barycenter_sweep(order, layers, edges, forward):
    """
    一方向に隣接レイヤーのbarycenter並べ替えを行う。

    Args:
        order: 更新対象のorder。
        layers: レイヤーキー列。
        edges: エッジ集合。
        forward: Trueなら左から右、Falseなら右から左にsweepする。

    Returns:
        None: orderを破壊的に更新する。
    """
    layer_indices = range(len(layers)) if forward else range(len(layers) - 1, -1, -1)
    for i in layer_indices:
        if forward:
            fixed_layer = layers[i]
            free_layer = layers[(i + 1) % len(layers)]
        else:
            free_layer = layers[i]
            fixed_layer = layers[(i + 1) % len(layers)]
        _process_layer_pair(
            fixed_layer, free_layer, order, edges, fixed_is_source=forward
        )


def _process_layer_pair(fixed_key, free_key, order, edges, fixed_is_source=True):
    """
    固定レイヤーに対する自由レイヤーのbarycenter順序を計算する。

    Args:
        fixed_key: 固定するレイヤーキー。
        free_key: 並べ替えるレイヤーキー。
        order: 更新対象のorder。
        edges: エッジ集合。
        fixed_is_source: Trueなら fixed -> free の辺を見る。

    Returns:
        None: order[free_key]を破壊的に更新する。
    """
    fixed_nodes = order[fixed_key]
    free_nodes = order[free_key]
    if not fixed_nodes:
        return

    neighbors = _neighbors_from_fixed_layer(
        fixed_nodes, free_nodes, edges, fixed_is_source
    )
    fixed_positions = _circular_positions(fixed_nodes)
    fixed_angles = {
        node: 2 * math.pi * index / len(fixed_nodes)
        for index, node in enumerate(fixed_nodes)
    }

    order[free_key] = sorted(
        free_nodes,
        key=lambda node: _barycenter_angle(
            node, free_nodes, neighbors, fixed_positions, fixed_angles
        ),
    )


def _neighbors_from_fixed_layer(fixed_nodes, free_nodes, edges, fixed_is_source):
    """
    自由レイヤーの各ノードから固定レイヤー側の隣接ノードを集める。

    Args:
        fixed_nodes: 固定レイヤーのノード列。
        free_nodes: 自由レイヤーのノード列。
        edges: エッジ集合。
        fixed_is_source: Trueなら fixed -> free の辺を見る。

    Returns:
        dict: free_node -> list[fixed_node]。
    """
    fixed_set = set(fixed_nodes)
    free_set = set(free_nodes)
    neighbors = defaultdict(list)

    for u, v in edges:
        if fixed_is_source and u in fixed_set and v in free_set:
            neighbors[v].append(u)
        elif not fixed_is_source and u in free_set and v in fixed_set:
            neighbors[u].append(v)

    return neighbors


def _circular_positions(nodes):
    """
    ノード列を単位円上に等間隔配置した座標を返す。

    Args:
        nodes: 配置対象のノード列。

    Returns:
        dict: node -> (cos(theta), sin(theta))。
    """
    positions = {}
    for index, node in enumerate(nodes):
        theta = 2 * math.pi * index / len(nodes)
        positions[node] = (math.cos(theta), math.sin(theta))
    return positions


def _barycenter_angle(node, free_nodes, neighbors, fixed_positions, fixed_angles):
    """
    固定側隣接ノードの重心角度を計算する。

    Args:
        node: 自由レイヤー側の対象ノード。
        free_nodes: 自由レイヤーの現在順序。
        neighbors: node -> 固定側隣接ノード列。
        fixed_positions: 固定側ノードの単位円座標。
        fixed_angles: 固定側ノードの角度。

    Returns:
        float: ソートキーとして使う角度。
    """
    adjacent = neighbors.get(node, [])
    if not adjacent:
        return 2 * math.pi * free_nodes.index(node) / max(1, len(free_nodes))

    bx = 0.0
    by = 0.0
    for neighbor in adjacent:
        x, y = fixed_positions.get(neighbor, (0.0, 0.0))
        bx += x
        by += y

    if abs(bx) < 1e-9 and abs(by) < 1e-9:
        return fixed_angles.get(adjacent[0], 0.0)

    angle = math.atan2(by, bx)
    return angle + 2 * math.pi if angle < 0 else angle


# ---------------------------------------------------------------------------
# Sifting and offset optimization
# ---------------------------------------------------------------------------


def _forward_layer_pairs(layers):
    """順方向1 sweepの循環隣接レイヤーペアを返す。"""
    if len(layers) < 2:
        return []
    return [
        (layer, layers[(index + 1) % len(layers)]) for index, layer in enumerate(layers)
    ]


def _backward_layer_pairs(layers):
    """逆方向1 sweepの循環隣接レイヤーペアを返す。"""
    return [(free, fixed) for fixed, free in reversed(_forward_layer_pairs(layers))]


def _run_sifting(order, psi, layers, edges, rounds):
    """2層siftingを順方向・逆方向交互にrounds回実行する。"""
    for _ in range(rounds):
        layer_pairs = _forward_layer_pairs(layers)

        for fixed_layer, free_layer in layer_pairs:
            _sift_two_layer_pair(fixed_layer, free_layer, order, psi, edges)


def _sift_two_layer_pair(fixed_layer, free_layer, order, psi, edges):
    """fixed_layerを固定し、free_layerだけを交差数でsiftingする。"""
    pair_edges, oriented_psi, original_edges = _oriented_pair_embedding(
        order, psi, fixed_layer, free_layer, edges
    )
    if not pair_edges:
        return

    for node in list(order[free_layer]):
        incident_edges = [edge for edge in pair_edges if edge[1] == node]
        if incident_edges:
            _sift_vertex_one_sided(
                node,
                fixed_layer,
                free_layer,
                order,
                oriented_psi,
                pair_edges,
                incident_edges,
            )

    for oriented_edge, (original_edge, direction) in original_edges.items():
        psi[original_edge] = direction * oriented_psi[oriented_edge]


def _oriented_pair_embedding(order, psi, fixed_layer, free_layer, edges):
    """2層間の辺をfixed→freeへ揃え、向きに合わせてpsiを変換する。"""
    fixed_nodes = set(order[fixed_layer])
    free_nodes = set(order[free_layer])
    pair_edges = []
    oriented_psi = {}
    original_edges = {}

    for edge_index, edge in enumerate(edges):
        u, v = _edge_endpoints(edge)
        if u in fixed_nodes and v in free_nodes:
            """順方向にswapする時に利用"""
            oriented_edge = (u, v, edge_index)
            direction = 1
        elif u in free_nodes and v in fixed_nodes:
            """逆方向にswapする時に利用"""
            oriented_edge = (v, u, edge_index)
            direction = -1
        else:
            continue

        pair_edges.append(oriented_edge)
        oriented_psi[oriented_edge] = direction * psi.get(edge, 0)
        original_edges[oriented_edge] = (edge, direction)

    return pair_edges, oriented_psi, original_edges


def _sift_vertex_one_sided(
    node,
    fixed_layer,
    free_layer,
    order,
    psi,
    pair_edges,
    incident_edges,
):
    """論文のparting探索を使い、2層間の交差数だけで1頂点をsiftingする。"""
    free_nodes = order[free_layer]
    if len(free_nodes) <= 1:
        return

    fixed_position = {
        fixed_node: index for index, fixed_node in enumerate(order[fixed_layer])
    }
    sorted_incident = sorted(
        incident_edges,
        key=lambda edge: fixed_position[edge[0]],
    )

    best_crossings = _pair_crossings(order, psi, fixed_layer, free_layer, pair_edges)
    best_nodes = list(free_nodes)
    best_offsets = {edge: psi.get(edge, 0) for edge in sorted_incident}

    working_order = _copy_order(order)
    working_psi = dict(psi)
    working_nodes = working_order[free_layer]
    working_nodes.remove(node)
    working_nodes.insert(0, node)
    for edge in sorted_incident:
        working_psi[edge] = 1

    offset = 0
    parting = 0
    for position in range(len(working_nodes) - 1):
        offset, parting = _advance_parting(
            sorted_incident,
            offset,
            parting,
            working_order,
            working_psi,
            pair_edges,
            fixed_layer,
            free_layer,
        )

        candidate_crossings = _pair_crossings(
            working_order,
            working_psi,
            fixed_layer,
            free_layer,
            pair_edges,
        )
        if candidate_crossings < best_crossings:
            best_crossings = candidate_crossings
            best_nodes = list(working_order[free_layer])
            best_offsets = {edge: working_psi[edge] for edge in sorted_incident}

        if position < len(working_nodes) - 2:
            node_index = working_order[free_layer].index(node)
            (
                working_order[free_layer][node_index],
                working_order[free_layer][node_index + 1],
            ) = (
                working_order[free_layer][node_index + 1],
                working_order[free_layer][node_index],
            )

    order[free_layer] = best_nodes
    for edge, value in best_offsets.items():
        psi[edge] = value


def _advance_parting(
    incident_edges,
    offset,
    parting,
    order,
    psi,
    pair_edges,
    fixed_layer,
    free_layer,
):
    """2層間の交差数を増やさない間、論文のpartingを進める。"""
    degree = len(incident_edges)
    while offset >= -1:
        edge = incident_edges[parting]
        before_crossings = _pair_crossings(
            order, psi, fixed_layer, free_layer, pair_edges
        )
        old_value = psi[edge]
        psi[edge] = offset
        after_crossings = _pair_crossings(
            order, psi, fixed_layer, free_layer, pair_edges
        )

        if after_crossings > before_crossings:
            psi[edge] = old_value
            break

        parting += 1
        if parting == degree:
            offset -= 1
            parting = 0

    return offset, parting


def _pair_crossings(order, psi, fixed_layer, free_layer, pair_edges):
    """処理中の2層ペアの交差数だけを返す。"""
    return _count_layer_pair_crossings(order, psi, fixed_layer, free_layer, pair_edges)


def _compute_winding_numbers(A, order, L, layers):
    """
    現在のorderに対する各エッジの初期psiを計算する。

    Args:
        A: エッジ集合。
        order: 各レイヤー内のノード順序。
        L: レイヤー辞書。
        layers: レイヤーキー列。
    Returns:
        dict: edge -> psi。
    """
    psi = {}
    node_to_layer = _node_to_layer(L)
    layer_index = {layer: index for index, layer in enumerate(layers)}

    for edge in A:
        psi[edge] = _best_winding_for_edge(
            edge, order, node_to_layer, layer_index, layers
        )

    return psi


def _best_winding_for_edge(edge, order, node_to_layer, layer_index, layers):
    """
    1本のエッジについて幾何的に最短となるpsiを選ぶ。

    Args:
        edge: 対象エッジ。
        order: 各レイヤー内のノード順序。
        node_to_layer: node -> layer。
        layer_index: layer -> index。
        layers: レイヤーキー列。

    Returns:
        int: -1, 0, 1 のいずれかのpsi。
    """
    u, v = edge
    u_layer = node_to_layer.get(u)
    v_layer = node_to_layer.get(v)
    if u_layer is None or v_layer is None or u_layer == v_layer:
        return 0

    if (layer_index[v_layer] - layer_index[u_layer]) % len(layers) != 1:
        return 0

    u_nodes = order.get(u_layer, [])
    v_nodes = order.get(v_layer, [])
    if u not in u_nodes or v not in v_nodes or not u_nodes or not v_nodes:
        return 0

    theta_u = 2 * math.pi * u_nodes.index(u) / len(u_nodes)
    theta_v = 2 * math.pi * v_nodes.index(v) / len(v_nodes)
    delta_theta = theta_v - theta_u

    return min(
        OFFSET_VALUES, key=lambda offset: abs(delta_theta + 2 * math.pi * offset)
    )


# ---------------------------------------------------------------------------
# Crossing counting
# ---------------------------------------------------------------------------


def _count_all_crossings(order, psi, layers, edges):
    """
    全ての隣接レイヤーペアの交差数を合計する。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        layers: レイヤーキー列。
        edges: エッジ集合。

    Returns:
        int: 総交差数。
    """
    total = 0
    for index, fixed_layer in enumerate(layers):
        free_layer = layers[(index + 1) % len(layers)]
        total += _count_layer_pair_crossings(order, psi, fixed_layer, free_layer, edges)
    return total


def _count_layer_pair_crossings(order, psi, fixed_key, free_key, edges):
    """
    1つの隣接レイヤーペア間の交差数を数える。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        fixed_key: 左側レイヤーキー。
        free_key: 右側レイヤーキー。
        edges: エッジ集合。

    Returns:
        int: このレイヤーペア内の交差数。
    """
    fixed_nodes = order[fixed_key]
    free_nodes = order[free_key]
    pi_fixed = {node: index for index, node in enumerate(fixed_nodes)}
    pi_free = {node: index for index, node in enumerate(free_nodes)}

    edges_between = _edges_between_layers(order, fixed_key, free_key, edges)

    crossings = 0
    for i, edge1 in enumerate(edges_between):
        for edge2 in edges_between[i + 1 :]:
            crossings += _crossings_between_edges(edge1, edge2, pi_fixed, pi_free, psi)
    return crossings


def _edges_between_layers(order, fixed_key, free_key, edges):
    """fixed_keyからfree_keyへ向かう辺だけを抽出する。"""
    fixed_nodes = set(order[fixed_key])
    free_nodes = set(order[free_key])
    return [
        edge
        for edge in edges
        if _edge_endpoints(edge)[0] in fixed_nodes
        and _edge_endpoints(edge)[1] in free_nodes
    ]


def _crossings_between_edges(edge1, edge2, pi_fixed, pi_free, psi):
    """
    2本の隣接レイヤー間エッジが交差する数を計算する。

    Args:
        edge1: 1本目のエッジ。
        edge2: 2本目のエッジ。
        pi_fixed: 左側レイヤーの node -> index。
        pi_free: 右側レイヤーの node -> index。
        psi: 各エッジの上下境界巻き数。

    Returns:
        int: 交差数。
    """
    fixed1, free1 = _edge_endpoints(edge1)
    fixed2, free2 = _edge_endpoints(edge2)

    # 数値の符号を -1, 0, 1 で返す。
    _sign = lambda value: 1 if value > 0 else -1 if value < 0 else 0

    a = _sign(pi_fixed[fixed2] - pi_fixed[fixed1])
    b = _sign(pi_free[free2] - pi_free[free1])
    delta = psi.get(edge2, 0) - psi.get(edge1, 0)

    # Bachmaier Lemma 1 の2層平坦トーラス版。psiは上下境界を
    # またぐ回数を表す。
    value = abs(delta + (b - a) / 2) - 1 + (abs(a) + abs(b)) / 2
    return max(0, int(round(value)))
