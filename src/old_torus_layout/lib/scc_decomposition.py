from collections import defaultdict


def scc_decomposition(V, A):
    """
    Tarjanのアルゴリズムで強連結成分分解を行う

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]

    Returns:
        sccs: SCC のリスト list[list[int]]
        node_to_scc: ノードからSCC IDへのマッピング dict[int: int]
    """
    # 隣接リストを構築
    adj = defaultdict(list)
    for u, v in A:
        adj[u].append(v)

    # Tarjanのアルゴリズムの変数
    index_counter = [0]
    stack = []
    lowlinks = {}
    index = {}
    on_stack = defaultdict(bool)
    sccs = []

    def strong_connect(node):
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        # 後続ノードを探索
        for successor in adj[node]:
            if successor not in index:
                strong_connect(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif on_stack[successor]:
                lowlinks[node] = min(lowlinks[node], index[successor])

        # ルートノードの場合、SCCを生成
        if lowlinks[node] == index[node]:
            connected_component = []
            while True:
                successor = stack.pop()
                on_stack[successor] = False
                connected_component.append(successor)
                if successor == node:
                    break
            sccs.append(connected_component)

    # すべてのノードを探索
    for node in V:
        if node not in index:
            strong_connect(node)

    # ノードからSCC IDへのマッピングを作成
    node_to_scc = {}
    for scc_id, scc in enumerate(sccs):
        for node in scc:
            node_to_scc[node] = scc_id

    return sccs, node_to_scc
