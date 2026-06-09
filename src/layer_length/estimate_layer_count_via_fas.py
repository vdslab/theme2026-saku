import networkx as nx


def estimate_layer_count_via_fas(V, A):
    """
    FASに基づく階層割り当てと閉路長推定を行い、推奨レイヤー数を返す

    Args:
        V: ノードのリスト
        A: エッジのリスト [(u, v), ...]

    Returns:
        estimated_layers: 推奨される階層数 (int)
    """
    # グラフの構築
    G = nx.DiGraph()
    G.add_nodes_from(V)
    G.add_edges_from(A)

    # 1. FAS (Feedback Arc Set) を用いてDAG化
    # 既存のヒューリスティック(greedy_feedback_arc_set)でバックエッジを取得
    if hasattr(nx, "greedy_feedback_arc_set"):
        back_edges = list(nx.greedy_feedback_arc_set(G))
    else:
        back_edges = _fallback_feedback_arc_set(G)

    # DAGを作成（バックエッジを取り除く）
    DAG = G.copy()
    DAG.remove_edges_from(back_edges)

    # 2. DAG上で階層割り当て (Longest Path Layering)
    # DAGの各ノードの階層 L(x) を計算
    # nx.dag_longest_path_length を使うと各ノードの深さを計算可能
    # より効率的な方法は、トポロジカルソート順にL(v) = max(L(u) + 1)を更新する
    L = {}
    for node in nx.topological_sort(DAG):
        # 親ノードがない場合は階層0からスタート
        preds = list(DAG.predecessors(node))
        if not preds:
            L[node] = 0
        else:
            L[node] = max(L[p] for p in preds) + 1

    # 3. バックエッジを使って疑似最大閉路長を推定
    # 閉路長 = L(u) - L(v) + 1  (逆辺が u -> v の場合)
    # ※DAG上では v から u へパスがつながっている
    max_cycle_len = 0
    for u, v in back_edges:
        # DAG上にパスが存在しない場合はL(u)やL(v)が取得できない可能性があるため注意
        if u in L and v in L:
            cycle_len = L[u] - L[v] + 1
            max_cycle_len = max(max_cycle_len, cycle_len)

    # max_cycle_len が0の場合はグラフが完全なDAGなので、通常の最長パス長を返す
    if max_cycle_len == 0:
        return max(L.values()) + 1 if L else 1

    # 閉路を含む場合、閉路長以上を確保しつつ、必要に応じてアスペクト比を考慮して返す
    return max(max_cycle_len, max(L.values()) + 1)


def _fallback_feedback_arc_set(G):
    """
    greedy_feedback_arc_set がない環境向けの簡易FAS取得
    サイクルを見つけて先頭エッジを除去する貪欲法
    """
    H = G.copy()
    back_edges = []

    while True:
        try:
            cycle = nx.find_cycle(H, orientation="original")
        except nx.exception.NetworkXNoCycle:
            break

        u, v, _ = cycle[0]
        back_edges.append((u, v))
        if H.has_edge(u, v):
            H.remove_edge(u, v)

    return back_edges
