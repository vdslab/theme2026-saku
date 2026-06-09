from collections import defaultdict, deque

from lib.scc_decomposition import scc_decomposition


def build_scc_dag(sccs, node_to_scc, A):
    """
    SCC DAGを構築

    Args:
        sccs: SCCのリスト
        node_to_scc: ノードからSCC IDへのマッピング
        A: 元のエッジ集合

    Returns:
        sccs: SCCのリスト
        scc_edges: SCC間のエッジ list[tuple(int, int)]
    """
    scc_edges = set()
    for u, v in A:
        scc_u = node_to_scc[u]
        scc_v = node_to_scc[v]
        if scc_u != scc_v:
            scc_edges.add((scc_u, scc_v))

    return sccs, list(scc_edges)


def get_longest_path_length_scc(sccs, scc_edges):
    """
    SCC DAGに対して最長パスの長さ（最大レイヤー数）を計算する

    Args:
        sccs: SCCのリスト
        scc_edges: SCC間のエッジ

    Returns:
        max_path_length: 最長パスの数値 (int)
    """
    num_sccs = len(sccs)
    if num_sccs == 0:
        return 0

    # 入次数を計算
    in_degree = defaultdict(int)
    adj = defaultdict(list)
    for u, v in scc_edges:
        adj[u].append(v)
        in_degree[v] += 1

    # トポロジカルソートとlongest-path計算
    scc_layers = {}
    queue = deque()

    # 入次数0のSCCを開始点とする
    for scc_id in range(num_sccs):
        if in_degree[scc_id] == 0:
            queue.append(scc_id)
            scc_layers[scc_id] = 0

    # 未処理のSCCがある場合（孤立ノードなど）
    for scc_id in range(num_sccs):
        if scc_id not in scc_layers:
            scc_layers[scc_id] = 0

    # 最長パスの最大値を保持する変数
    max_length = 0

    # BFSでlongest pathを計算
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            # longest pathを更新
            scc_layers[v] = max(scc_layers.get(v, 0), scc_layers[u] + 1)

            # 最大値を常に更新しておく
            if scc_layers[v] > max_length:
                max_length = scc_layers[v]

            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # 必要な数値（最長パスの長さ）だけを返す
    return max_length


def longest_path_scc_dag(V, A):
    sccs, node_to_scc = scc_decomposition(V, A)
    sccs, scc_edges = build_scc_dag(sccs, node_to_scc, A)

    return get_longest_path_length_scc(sccs, scc_edges)
