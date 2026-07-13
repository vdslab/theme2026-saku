from collections import defaultdict
from itertools import product
import math

from lib.insert_dummy_node import insert_dummy_node

OFFSET_VALUES = (-1, 0, 1)
MAX_EXHAUSTIVE_OFFSET_EDGES = 4
MAX_BOUNDARY_GROUP_CANDIDATES = 2500
BOUNDARY_SWEEP_ROUNDS = 3


def cartesian_barycenter_heuristic(V, A, layer_dict, t_val, w=None):
    """
    Cartesian Barycenterを用いてノード順序を求める（平坦トーラス用）。

    Returns:
        (order, L, A, t_val, psi)
    """
    V, A, L, t_val, w = insert_dummy_node(V, A, layer_dict, t_val, w)
    layers = sorted(L.keys())
    fixed_zero_edges = _fixed_zero_edges(A, t_val)

    order = _barycentric_order(_base_order(L, layers), layers, A)
    psi = _compute_winding_numbers(
        A, order, L, layers, fixed_zero_edges=fixed_zero_edges
    )

    return order, L, A, t_val, psi


def radial_sifting_heuristic(
    V, A, layer_dict, t_val, w=None, rounds=3, vertical_torus_penalty=0.0
):
    """
    Radial Siftingを用いてノード順序を求める（平坦トーラス用）。

    評価は辞書順で行う:
        1. 交差数
        2. 上下トーラス通過数
        3. 水平性

    `vertical_torus_penalty` は過去の呼び出し互換のために受け取る。

    Returns:
        (order, L, A, t_val, psi)
    """
    V, A, L, t_val, w = insert_dummy_node(V, A, layer_dict, t_val, w)
    layers = sorted(L.keys())
    fixed_zero_edges = _fixed_zero_edges(A, t_val)

    best_order = None
    best_psi = None
    best_score = None

    for order in _initial_orders(L, layers, A):
        psi = _compute_winding_numbers(
            A, order, L, layers, fixed_zero_edges=fixed_zero_edges
        )
        _optimize_offsets(order, psi, layers, A, fixed_zero_edges=fixed_zero_edges)
        _run_sifting(order, psi, layers, A, rounds, fixed_zero_edges)

        score = _score(order, psi, layers, A)
        if best_score is None or score < best_score:
            best_score = score
            best_order = _copy_order(order)
            best_psi = dict(psi)
            if _is_perfect_primary_score(best_score):
                break

    _optimize_boundary_positions(best_order, best_psi, L, layers, A, fixed_zero_edges)
    return best_order, L, A, t_val, best_psi


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


def _fixed_zero_edges(edges, t_val):
    """
    上下巻き数を0に固定する辺集合を返す。

    Args:
        edges: ダミー挿入後のエッジ集合。
        t_val: 左右トーラス辺フラグ。

    Returns:
        set: t_val=True のエッジ集合。
    """
    return {edge for edge in edges if t_val.get(edge, False)}


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


def _incident_edges(edges, node):
    """
    指定ノードに接続するエッジを抽出する。

    Args:
        edges: エッジ集合。
        node: 対象ノード。

    Returns:
        list: nodeを端点に持つエッジ。
    """
    return [edge for edge in edges if node in edge]


def _rotate_list(values, shift):
    """
    リストを循環回転する。

    Args:
        values: 回転対象のリスト。
        shift: 左回転量。

    Returns:
        list: 回転後のリスト。
    """
    shift %= len(values)
    return list(values[shift:]) + list(values[:shift])


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


def _dedupe_orders(orders, layers):
    """
    同じレイヤー順序を持つorder候補を取り除く。

    Args:
        orders: order候補列。
        layers: 比較に使うレイヤーキー列。

    Returns:
        list[dict]: 重複除去済みのorder候補。
    """
    seen = set()
    unique = []
    for order in orders:
        key = tuple(tuple(order[layer]) for layer in layers)
        if key not in seen:
            seen.add(key)
            unique.append(_copy_order(order))
    return unique


# ---------------------------------------------------------------------------
# Sifting and offset optimization
# ---------------------------------------------------------------------------


def _run_sifting(order, psi, layers, edges, rounds, fixed_zero_edges):
    """
    全レイヤー・全ノードに対してlexicographic siftingを反復する。

    Args:
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        rounds: sifting反復回数。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        None: orderとpsiを破壊的に更新する。
    """
    for _ in range(rounds):
        improved = False

        for layer in layers:
            for node in list(order[layer]):
                improved |= _sift_vertex_incremental(
                    node, layer, order, psi, layers, edges, fixed_zero_edges
                )

        _optimize_offsets(order, psi, layers, edges, fixed_zero_edges=fixed_zero_edges)
        if not improved:
            break


def _sift_vertex(node, layer, order, psi, layers, edges, fixed_zero_edges):
    """
    1ノードを同一レイヤー内の全位置へ試し、最良位置へ移動する。

    Args:
        node: 移動対象ノード。
        layer: nodeが属するレイヤー。
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        bool: orderまたはpsiが改善された場合True。
    """
    nodes = order[layer]
    if len(nodes) <= 1 or node not in nodes:
        return False

    current_score = _score(order, psi, layers, edges)
    best_score = current_score
    best_position = nodes.index(node)
    best_psi = dict(psi)

    for position in range(len(nodes)):
        candidate_order = _copy_order(order)
        candidate_nodes = candidate_order[layer]
        candidate_nodes.remove(node)
        candidate_nodes.insert(position, node)

        candidate_psi = dict(psi)
        _optimize_offsets(
            candidate_order,
            candidate_psi,
            layers,
            edges,
            candidate_edges=_incident_edges(edges, node),
            fixed_zero_edges=fixed_zero_edges,
        )

        candidate_score = _score(candidate_order, candidate_psi, layers, edges)
        if candidate_score < best_score:
            best_score = candidate_score
            best_position = position
            best_psi = candidate_psi

    if best_score >= current_score:
        return False

    nodes.remove(node)
    nodes.insert(best_position, node)
    psi.clear()
    psi.update(best_psi)
    return True


def _sift_vertex_incremental(node, layer, order, psi, layers, edges, fixed_zero_edges):
    """
    1ノードを隣接交換で円周上に流し、影響するレイヤーペアだけを差分評価する。

    既存のradial siftingに近い形で、nodeを境界直後から1位置ずつ動かす。
    交差数はnodeが属するレイヤーの前後ペアだけを再計算し、psiはnodeの
    incident edgeだけを改善する。

    Args:
        node: 移動対象ノード。
        layer: nodeが属するレイヤー。
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        bool: orderまたはpsiが改善された場合True。
    """
    nodes = order[layer]
    if len(nodes) <= 1 or node not in nodes:
        return False

    current_score = _score(order, psi, layers, edges)
    best_score = current_score
    best_nodes = list(nodes)
    best_psi = dict(psi)

    working_order = _copy_order(order)
    working_psi = dict(psi)
    working_nodes = working_order[layer]
    working_nodes.remove(node)
    working_nodes.insert(0, node)
    working_score = _score_after_local_change(
        order, working_order, psi, working_psi, layers, edges, layer, current_score
    )

    working_score = _optimize_incident_offsets_incremental(
        node,
        layer,
        working_order,
        working_psi,
        layers,
        edges,
        fixed_zero_edges,
        working_score,
    )
    if working_score < best_score:
        best_score = working_score
        best_nodes = list(working_order[layer])
        best_psi = dict(working_psi)

    for position in range(1, len(nodes)):
        before_order = _copy_order(working_order)
        before_psi = dict(working_psi)
        working_nodes = working_order[layer]
        node_index = working_nodes.index(node)
        working_nodes[node_index], working_nodes[node_index + 1] = (
            working_nodes[node_index + 1],
            working_nodes[node_index],
        )

        working_score = _score_after_local_change(
            before_order,
            working_order,
            before_psi,
            working_psi,
            layers,
            edges,
            layer,
            working_score,
        )
        working_score = _optimize_incident_offsets_incremental(
            node,
            layer,
            working_order,
            working_psi,
            layers,
            edges,
            fixed_zero_edges,
            working_score,
        )

        if working_score < best_score:
            best_score = working_score
            best_nodes = list(working_order[layer])
            best_psi = dict(working_psi)

    if best_score >= current_score:
        return False

    order[layer] = best_nodes
    psi.clear()
    psi.update(best_psi)
    return True


def _optimize_incident_offsets_incremental(
    node, layer, order, psi, layers, edges, fixed_zero_edges, current_score
):
    """
    nodeに接続するpsiだけを、影響レイヤーペアの差分評価で改善する。

    Args:
        node: 移動対象ノード。
        layer: nodeが属するレイヤー。
        order: 現在のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。
        current_score: 現在の全体スコア。

    Returns:
        tuple: 改善後の全体スコア。
    """
    candidates = _offset_candidate_edges(
        edges, psi, _incident_edges(edges, node), fixed_zero_edges
    )
    if not candidates:
        return current_score

    improved = True
    while improved:
        improved = False
        for edge in candidates:
            old_value = psi.get(edge, 0)
            best_value = old_value
            best_score = current_score

            for value in OFFSET_VALUES:
                if value == old_value:
                    continue

                psi[edge] = old_value
                before_psi = dict(psi)
                psi[edge] = value
                score = _score_after_edge_offset_change(
                    order, before_psi, psi, layers, edges, edge, current_score
                )
                if score < best_score:
                    best_score = score
                    best_value = value

            psi[edge] = best_value
            if best_score < current_score:
                current_score = best_score
                improved = True

    _force_zero_offsets(psi, fixed_zero_edges)
    return current_score


def _optimize_offsets(
    order, psi, layers, edges, candidate_edges=None, fixed_zero_edges=None
):
    """
    指定エッジ群のpsiを辞書順スコアが良くなるように調整する。

    Args:
        order: 現在のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        candidate_edges: 調整対象のエッジ集合。Noneなら全エッジ。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        None: psiを破壊的に更新する。
    """
    fixed_zero_edges = fixed_zero_edges or set()
    _force_zero_offsets(psi, fixed_zero_edges)

    candidates = _offset_candidate_edges(edges, psi, candidate_edges, fixed_zero_edges)
    if not candidates:
        return

    current_score = _score(order, psi, layers, edges)
    if len(candidates) <= MAX_EXHAUSTIVE_OFFSET_EDGES:
        current_score = _optimize_offsets_exhaustive(
            order, psi, layers, edges, candidates, current_score
        )

    _optimize_offsets_coordinate_descent(
        order, psi, layers, edges, candidates, current_score
    )
    _force_zero_offsets(psi, fixed_zero_edges)


def _force_zero_offsets(psi, fixed_zero_edges):
    """
    固定対象エッジのpsiを0に戻す。

    Args:
        psi: 更新対象の巻き数辞書。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        None: psiを破壊的に更新する。
    """
    for edge in fixed_zero_edges:
        if edge in psi:
            psi[edge] = 0


def _score_after_local_change(
    before_order,
    after_order,
    before_psi,
    after_psi,
    layers,
    edges,
    changed_layer,
    current_score,
):
    """
    changed_layerの順序変更後スコアを、前後レイヤーペアの交差差分で更新する。

    Args:
        before_order: 変更前のorder。
        after_order: 変更後のorder。
        before_psi: 変更前のpsi。
        after_psi: 変更後のpsi。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        changed_layer: 順序を変えたレイヤー。
        current_score: 変更前の全体スコア。

    Returns:
        tuple: 変更後の全体スコア。
    """
    pair_keys = _incident_layer_pairs(changed_layer, layers)
    return _score_after_pair_changes(
        before_order,
        after_order,
        before_psi,
        after_psi,
        layers,
        edges,
        pair_keys,
        current_score,
    )


def _score_after_edge_offset_change(
    order, before_psi, after_psi, layers, edges, changed_edge, current_score
):
    """
    1本のpsi変更後スコアを、そのエッジが属するレイヤーペアの交差差分で更新する。

    Args:
        order: 現在のorder。
        before_psi: 変更前のpsi。
        after_psi: 変更後のpsi。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        changed_edge: psiを変えたエッジ。
        current_score: 変更前の全体スコア。

    Returns:
        tuple: 変更後の全体スコア。
    """
    pair_key = _edge_layer_pair(changed_edge, order, layers)
    if pair_key is None:
        return (
            current_score[0],
            _vertical_torus_cost(edges, after_psi),
            _horizontal_cost(order, after_psi, edges),
        )

    return _score_after_pair_changes(
        order,
        order,
        before_psi,
        after_psi,
        layers,
        edges,
        [pair_key],
        current_score,
    )


def _score_after_pair_changes(
    before_order,
    after_order,
    before_psi,
    after_psi,
    layers,
    edges,
    pair_keys,
    current_score,
):
    """
    指定レイヤーペアだけ交差数を数え直し、全体スコアを差分更新する。

    Args:
        before_order: 変更前のorder。
        after_order: 変更後のorder。
        before_psi: 変更前のpsi。
        after_psi: 変更後のpsi。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        pair_keys: 再計算する (fixed_layer, free_layer) の列。
        current_score: 変更前の全体スコア。

    Returns:
        tuple: 変更後の全体スコア。
    """
    before_crossings = 0
    after_crossings = 0
    for fixed_layer, free_layer in set(pair_keys):
        before_crossings += _count_layer_pair_crossings(
            before_order, before_psi, fixed_layer, free_layer, edges
        )
        after_crossings += _count_layer_pair_crossings(
            after_order, after_psi, fixed_layer, free_layer, edges
        )

    return (
        current_score[0] - before_crossings + after_crossings,
        _vertical_torus_cost(edges, after_psi),
        _horizontal_cost(after_order, after_psi, edges),
    )


def _incident_layer_pairs(layer, layers):
    """
    layerの順序変更で交差数が変わり得る前後レイヤーペアを返す。

    Args:
        layer: 対象レイヤー。
        layers: レイヤーキー列。

    Returns:
        list[tuple]: (fixed_layer, free_layer) の列。
    """
    layer_index = layers.index(layer)
    previous_layer = layers[(layer_index - 1) % len(layers)]
    next_layer = layers[(layer_index + 1) % len(layers)]
    return [(previous_layer, layer), (layer, next_layer)]


def _edge_layer_pair(edge, order, layers):
    """
    edgeが属する循環隣接レイヤーペアを返す。

    Args:
        edge: 対象エッジ。
        order: 現在のorder。
        layers: レイヤーキー列。

    Returns:
        tuple | None: (fixed_layer, free_layer)。隣接前進エッジでなければNone。
    """
    node_to_layer = _node_to_layer(order)
    u, v = edge
    u_layer = node_to_layer.get(u)
    v_layer = node_to_layer.get(v)
    if u_layer is None or v_layer is None:
        return None

    u_index = layers.index(u_layer)
    v_index = layers.index(v_layer)
    if (v_index - u_index) % len(layers) != 1:
        return None
    return (u_layer, v_layer)


def _offset_candidate_edges(edges, psi, candidate_edges, fixed_zero_edges):
    """
    psi最適化の対象エッジを固定対象を除いて作る。

    Args:
        edges: 全エッジ集合。
        psi: 巻き数辞書。
        candidate_edges: 呼び出し側が指定した候補。Noneなら全エッジ。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        list: 実際にpsiを変更してよいエッジ集合。
    """
    source = edges if candidate_edges is None else candidate_edges
    return [edge for edge in source if edge in psi and edge not in fixed_zero_edges]


def _optimize_offsets_exhaustive(order, psi, layers, edges, candidates, current_score):
    """
    少数エッジのpsi組み合わせを全探索する。

    Args:
        order: 現在のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        candidates: 全探索対象エッジ。
        current_score: 探索開始時のスコア。

    Returns:
        tuple: 全探索後の最良スコア。
    """
    best_values = {edge: psi.get(edge, 0) for edge in candidates}
    best_score = current_score

    for values in product(OFFSET_VALUES, repeat=len(candidates)):
        for edge, value in zip(candidates, values):
            psi[edge] = value

        score = _score(order, psi, layers, edges)
        if score < best_score:
            best_score = score
            best_values = {edge: value for edge, value in zip(candidates, values)}

    for edge in candidates:
        psi[edge] = best_values[edge]
    return best_score


def _optimize_offsets_coordinate_descent(
    order, psi, layers, edges, candidates, current_score
):
    """
    各エッジのpsiを1本ずつ改善する座標降下を行う。

    Args:
        order: 現在のorder。
        psi: 更新対象の巻き数辞書。
        layers: レイヤーキー列。
        edges: 全エッジ集合。
        candidates: 調整対象エッジ。
        current_score: 探索開始時のスコア。

    Returns:
        None: psiを破壊的に更新する。
    """
    improved = True
    while improved:
        improved = False
        for edge in candidates:
            old_value = psi.get(edge, 0)
            best_value = old_value
            best_score = current_score

            for value in OFFSET_VALUES:
                if value == old_value:
                    continue
                psi[edge] = value
                score = _score(order, psi, layers, edges)
                if score < best_score:
                    best_score = score
                    best_value = value

            psi[edge] = best_value
            if best_score < current_score:
                current_score = best_score
                improved = True


def _compute_winding_numbers(A, order, L, layers, fixed_zero_edges=None):
    """
    現在のorderに対する各エッジの初期psiを計算する。

    Args:
        A: エッジ集合。
        order: 各レイヤー内のノード順序。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        dict: edge -> psi。
    """
    psi = {}
    fixed_zero_edges = fixed_zero_edges or set()
    node_to_layer = _node_to_layer(L)
    layer_index = {layer: index for index, layer in enumerate(layers)}

    for edge in A:
        if edge in fixed_zero_edges:
            psi[edge] = 0
            continue
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
# Boundary optimization
# ---------------------------------------------------------------------------


def _optimize_boundary_positions(order, psi, L, layers, edges, fixed_zero_edges):
    """
    円周順序を保ったまま上下境界の切れ目を最適化する。

    Args:
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        None: orderとpsiを破壊的に更新する。
    """
    _optimize_single_layer_boundaries(order, psi, L, layers, edges, fixed_zero_edges)
    _optimize_consecutive_boundary_groups(
        order, psi, L, layers, edges, fixed_zero_edges
    )


def _optimize_single_layer_boundaries(order, psi, L, layers, edges, fixed_zero_edges):
    """
    1レイヤーずつ境界位置を動かして改善を試す。

    Args:
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        None: orderとpsiを破壊的に更新する。
    """
    for _ in range(BOUNDARY_SWEEP_ROUNDS):
        improved = False
        for layer in layers:
            improved |= _try_rotate_layer_boundary(
                layer, order, psi, L, layers, edges, fixed_zero_edges
            )
        if not improved:
            break


def _try_rotate_layer_boundary(layer, order, psi, L, layers, edges, fixed_zero_edges):
    """
    指定レイヤーの境界位置だけを回転して改善候補を探す。

    Args:
        layer: 境界を動かすレイヤー。
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        bool: 改善を採用した場合True。
    """
    nodes = order[layer]
    if len(nodes) <= 1:
        return False

    current_score = _score(order, psi, layers, edges)
    best_nodes = list(nodes)
    best_psi = dict(psi)
    best_score = current_score

    for shift in _candidate_boundary_shifts(len(nodes)):
        if shift == 0:
            continue

        candidate_order = _copy_order(order)
        candidate_order[layer] = _rotate_list(nodes, shift)
        candidate_psi = _boundary_candidate_psi(
            candidate_order, L, layers, edges, fixed_zero_edges
        )

        score = _score(candidate_order, candidate_psi, layers, edges)
        if score < best_score:
            best_score = score
            best_nodes = candidate_order[layer]
            best_psi = candidate_psi

    if best_score >= current_score:
        return False

    order[layer] = best_nodes
    psi.clear()
    psi.update(best_psi)
    return True


def _optimize_consecutive_boundary_groups(
    order, psi, L, layers, edges, fixed_zero_edges
):
    """
    連続する2層・3層の境界位置を同時に動かして改善を試す。

    Args:
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        None: orderとpsiを破壊的に更新する。
    """
    shift_options = {
        layer: list(_candidate_boundary_shifts(len(order[layer]))) for layer in layers
    }
    if (
        _boundary_group_candidate_count(layers, shift_options)
        > MAX_BOUNDARY_GROUP_CANDIDATES
    ):
        return

    current_score = _score(order, psi, layers, edges)
    for group_size in (2, 3):
        for group in _consecutive_layer_groups(layers, group_size):
            current_score = _try_rotate_boundary_group(
                group,
                shift_options,
                order,
                psi,
                L,
                layers,
                edges,
                fixed_zero_edges,
                current_score,
            )


def _try_rotate_boundary_group(
    group,
    shift_options,
    order,
    psi,
    L,
    layers,
    edges,
    fixed_zero_edges,
    current_score,
):
    """
    レイヤー群の境界位置を同時回転して最良候補を採用する。

    Args:
        group: 同時に境界を動かすレイヤー群。
        shift_options: layer -> 試すshift列。
        order: 更新対象のorder。
        psi: 更新対象の巻き数辞書。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。
        current_score: 現在のスコア。

    Returns:
        tuple: 採用後の現在スコア。
    """
    best_order = None
    best_psi = None
    best_score = current_score

    for shifts in product(*(shift_options[layer] for layer in group)):
        if all(shift == 0 for shift in shifts):
            continue

        candidate_order = _copy_order(order)
        for layer, shift in zip(group, shifts):
            candidate_order[layer] = _rotate_list(candidate_order[layer], shift)

        candidate_psi = _boundary_candidate_psi(
            candidate_order, L, layers, edges, fixed_zero_edges
        )
        score = _score(candidate_order, candidate_psi, layers, edges)
        if score < best_score:
            best_score = score
            best_order = candidate_order
            best_psi = candidate_psi

    if best_score < current_score:
        order.clear()
        order.update(best_order)
        psi.clear()
        psi.update(best_psi)
        return best_score

    return current_score


def _boundary_candidate_psi(order, L, layers, edges, fixed_zero_edges):
    """
    境界回転候補に対するpsiを再計算して最適化する。

    Args:
        order: 候補order。
        L: レイヤー辞書。
        layers: レイヤーキー列。
        edges: エッジ集合。
        fixed_zero_edges: psi=0に固定するエッジ集合。

    Returns:
        dict: 候補orderに対応するpsi。
    """
    psi = _compute_winding_numbers(edges, order, L, layers, fixed_zero_edges)
    _optimize_offsets(order, psi, layers, edges, fixed_zero_edges=fixed_zero_edges)
    return psi


def _boundary_group_candidate_count(layers, shift_options):
    """
    連続境界グループ探索で試す候補数を見積もる。

    Args:
        layers: レイヤーキー列。
        shift_options: layer -> 試すshift列。

    Returns:
        int: 2層・3層グループ探索の候補総数。
    """
    total = 0
    for group_size in (2, 3):
        for group in _consecutive_layer_groups(layers, group_size):
            count = 1
            for layer in group:
                count *= len(shift_options[layer])
            total += count
    return total


def _candidate_boundary_shifts(layer_size):
    """
    境界位置として試すshift量を返す。

    Args:
        layer_size: 対象レイヤーのノード数。

    Returns:
        iterable: 試す左回転量。
    """
    if layer_size <= 16:
        return range(layer_size)

    step = max(1, layer_size // 16)
    shifts = {0, layer_size // 2}
    shifts.update(range(0, layer_size, step))
    return sorted(shifts)


def _consecutive_layer_groups(layers, group_size):
    """
    トーラス上で連続するレイヤー群を列挙する。

    Args:
        layers: レイヤーキー列。
        group_size: グループに含めるレイヤー数。

    Returns:
        list[tuple]: 連続レイヤーグループ。
    """
    if len(layers) < group_size:
        return []

    groups = []
    for start in range(len(layers)):
        group = tuple(
            layers[(start + offset) % len(layers)] for offset in range(group_size)
        )
        if len(set(group)) == group_size:
            groups.append(group)
    return groups


# ---------------------------------------------------------------------------
# Scoring and crossing counting
# ---------------------------------------------------------------------------


def _score(order, psi, layers, edges):
    """
    探索で使う辞書順スコアを作る。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        layers: レイヤーキー列。
        edges: エッジ集合。

    Returns:
        tuple: (交差数, 上下トーラス通過数, 水平性コスト)。
    """
    return (
        _count_all_crossings(order, psi, layers, edges),
        _vertical_torus_cost(edges, psi),
        _horizontal_cost(order, psi, edges),
    )


def _is_perfect_primary_score(score):
    """
    これ以上副目的を見る必要がないスコアか判定する。

    Args:
        score: _score が返すスコア。

    Returns:
        bool: 交差数0かつ上下トーラス通過数0ならTrue。
    """
    crossings, vertical_torus_edges, _ = score
    return crossings == 0 and vertical_torus_edges == 0


def _vertical_torus_cost(edges, psi):
    """
    上下境界を通るエッジ数を数える。

    Args:
        edges: エッジ集合。
        psi: 各エッジの上下境界巻き数。

    Returns:
        int: sum(abs(psi))。
    """
    return sum(abs(psi.get(edge, 0)) for edge in edges)


def _horizontal_cost(order, psi, edges):
    """
    辺がどれだけ水平からズレているかを測る。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        edges: エッジ集合。

    Returns:
        float: 中央揃え座標上のdy二乗和。
    """
    node_to_layer = _node_to_layer(order)
    cost = 0.0

    for edge in edges:
        u, v = edge
        u_layer = node_to_layer.get(u)
        v_layer = node_to_layer.get(v)
        if u_layer is None or v_layer is None or u_layer == v_layer:
            continue

        u_nodes = order[u_layer]
        v_nodes = order[v_layer]
        if u not in u_nodes or v not in v_nodes:
            continue

        dy = (
            _centered_position(v, v_nodes)
            - _centered_position(u, u_nodes)
            + psi.get(edge, 0) * max(len(u_nodes), len(v_nodes), 1)
        )
        cost += dy * dy

    return cost


def _centered_position(node, layer):
    """
    レイヤー内indexを中心0のy座標へ変換する。

    Args:
        node: 対象ノード。
        layer: ノード列。

    Returns:
        float: 中心揃えした位置。
    """
    return layer.index(node) - (len(layer) - 1) / 2


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

    edges_between = _edges_between_forward_layers(
        edges, set(fixed_nodes), set(free_nodes)
    )

    crossings = 0
    for i, edge1 in enumerate(edges_between):
        for edge2 in edges_between[i + 1 :]:
            crossings += _crossings_between_edges(edge1, edge2, pi_fixed, pi_free, psi)
    return crossings


def _edges_between_forward_layers(edges, fixed_set, free_set):
    """
    fixed -> free 方向の隣接レイヤー間エッジだけを抽出する。

    Args:
        edges: エッジ集合。
        fixed_set: 左側レイヤーのノード集合。
        free_set: 右側レイヤーのノード集合。

    Returns:
        list: fixed_setからfree_setへ向かうエッジ。
    """
    return [(u, v) for u, v in edges if u in fixed_set and v in free_set]


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
    fixed1, free1 = edge1
    fixed2, free2 = edge2

    if fixed1 == fixed2 or free1 == free2:
        return 0

    a = _sign(pi_fixed[fixed2] - pi_fixed[fixed1])
    b = _sign(pi_free[free2] - pi_free[free1])
    delta = psi.get(edge2, 0) - psi.get(edge1, 0)

    # Bachmaier Lemma 1 の2層平坦トーラス版。psiは上下境界を
    # またぐ回数を表す。
    value = abs(delta + (b - a) / 2) - 1 + (abs(a) + abs(b)) / 2
    return max(0, int(round(value)))


def _sign(value):
    """
    数値の符号を -1, 0, 1 で返す。

    Args:
        value: 判定する数値。

    Returns:
        int: 正なら1、負なら-1、0なら0。
    """
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
