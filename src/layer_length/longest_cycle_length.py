import networkx as nx
from collections import defaultdict

from lib.scc_decomposition import scc_decomposition


def longest_cycle_length(V, A):
    """
    すべてのSCCに対してJohnsonのアルゴリズム(1975)を適用し、
    グラフ全体の真の最大閉路長（厳密解）を計算する。

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]

    Returns:
        max_cycle_length: グラフ内の真の最大閉路長 (int)
    """
    # 1. グラフ全体の隣接リストを作成
    adj = defaultdict(list)
    for u, v in A:
        adj[u].append(v)

    # 2. SCC分解を実行（マッピング辞書は不要なので破棄）
    sccs, _ = scc_decomposition(V, A)
    max_cycle_length = 0

    # 3. 各SCCごとに閉路長を計算
    for scc in sccs:
        # ノード数1のSCCの場合、自己ループの有無だけ確認
        if len(scc) == 1:
            if scc[0] in adj[scc[0]]:
                max_cycle_length = max(max_cycle_length, 1)
            continue

        # SCC内部の部分グラフ（サブグラフ）の隣接リストを抽出
        scc_set = set(scc)
        adj_scc = {u: [v for v in adj[u] if v in scc_set] for u in scc_set}

        # 4. 例外なくすべてのSCCに対してJohnson法（厳密解）を適用
        G = nx.DiGraph(adj_scc)

        # nx.simple_cycles は内部的にJohnson法を使用し、全閉路を生成するジェネレータを返す
        for cycle in nx.simple_cycles(G):
            cycle_len = len(cycle)
            max_cycle_length = max(max_cycle_length, cycle_len)

    return max_cycle_length
