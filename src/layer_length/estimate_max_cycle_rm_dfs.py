import random
from collections import defaultdict


def estimate_max_cycle_rm_dfs(V, A, K=100):
    """
    RM-DFSを用いてグラフの最大閉路長を近似的に取得する

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        K: 試行回数

    Returns:
        max_cycle_len: サンプリングされた最大閉路長
    """
    # 1. 隣接リストの構築
    adj = defaultdict(list)
    for u, v in A:
        adj[u].append(v)

    global_max_cycle = 0

    # 2. K回の繰り返し探索
    for _ in range(K):
        # 探索順をランダム化
        nodes = list(V)
        random.shuffle(nodes)
        for u in adj:
            random.shuffle(adj[u])

        # 探索状態の管理 (0: 未訪問, 1: 探索中, 2: 完了)
        state = {v: 0 for v in V}
        depth = {v: 0 for v in V}

        def dfs(u, d):
            nonlocal global_max_cycle
            state[u] = 1  # 探索中にマーク
            depth[u] = d

            for v in adj[u]:
                if state[v] == 1:
                    # 後退辺(バックエッジ)を発見！閉路の長さ＝現在の深さ - ぶつかったノードの深さ + 1
                    cycle_len = d - depth[v] + 1
                    if cycle_len > global_max_cycle:
                        global_max_cycle = cycle_len
                elif state[v] == 0:
                    dfs(v, d + 1)

            state[u] = 2  # 探索完了マーク

        # 3. ランダムな始点からDFS実行
        for start_node in nodes:
            if state[start_node] == 0:
                dfs(start_node, 0)

    return global_max_cycle
