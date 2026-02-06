"""
トーラステスト用のグラフ自動生成関数

連結グラフを生成し、以下の特性を持つ可能性がある：
- DAG（有向非巡回グラフ）
- ソース頂点（入次数0）やシンク頂点（出次数0）を持つ
- サイクルを含む
"""

import random
from collections import deque


def is_connected(V, A):
    """グラフが弱連結かどうかを判定"""
    if not V:
        return True

    # 無向グラフとして扱って連結性を確認
    adj = {v: [] for v in V}
    for u, v in A:
        adj[u].append(v)
        adj[v].append(u)

    visited = set()
    queue = deque([V[0]])
    visited.add(V[0])

    while queue:
        node = queue.popleft()
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return len(visited) == len(V)


def generate_random_connected_graph(n, edge_prob=0.3, seed=None):
    """
    ランダムな連結有向グラフを生成

    Args:
        n: ノード数
        edge_prob: エッジの生成確率
        seed: 乱数シード

    Returns:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
    """
    if seed is not None:
        random.seed(seed)

    V = list(range(n))

    # まず連結性を保証するためのスパニングツリーを作成
    A = []
    unvisited = set(V[1:])
    visited = {V[0]}

    while unvisited:
        u = random.choice(list(visited))
        v = random.choice(list(unvisited))
        A.append((u, v))
        visited.add(v)
        unvisited.remove(v)

    # 追加のエッジをランダムに生成
    for u in V:
        for v in V:
            if u != v and (u, v) not in A:
                if random.random() < edge_prob:
                    A.append((u, v))

    return V, A


def generate_dag(n, edge_prob=0.3, seed=None):
    """
    ランダムなDAG（有向非巡回グラフ）を生成

    Args:
        n: ノード数
        edge_prob: エッジの生成確率
        seed: 乱数シード

    Returns:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
    """
    if seed is not None:
        random.seed(seed)

    V = list(range(n))
    A = []

    # トポロジカル順序を保証するため、小さい番号から大きい番号へのエッジのみ生成
    for u in V:
        for v in V:
            if u < v and random.random() < edge_prob:
                A.append((u, v))

    # 連結性を確保
    if not is_connected(V, A):
        # 連結になるまでエッジを追加
        for i in range(len(V) - 1):
            if (i, i + 1) not in A:
                A.append((i, i + 1))

    return V, A


def generate_cyclic_graph(n, num_cycles=2, edge_prob=0.2, seed=None):
    """
    サイクルを含む連結グラフを生成

    Args:
        n: ノード数
        num_cycles: 生成するサイクルの数
        edge_prob: 追加エッジの生成確率
        seed: 乱数シード

    Returns:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
    """
    if seed is not None:
        random.seed(seed)

    V = list(range(n))
    A = []

    # サイクルを作成
    nodes_per_cycle = max(3, n // num_cycles)
    node_idx = 0

    for _ in range(num_cycles):
        cycle_size = min(nodes_per_cycle, n - node_idx)
        if cycle_size < 3:
            break

        cycle_nodes = V[node_idx : node_idx + cycle_size]

        # サイクルを形成
        for i in range(len(cycle_nodes)):
            u = cycle_nodes[i]
            v = cycle_nodes[(i + 1) % len(cycle_nodes)]
            A.append((u, v))

        node_idx += cycle_size

    # 残りのノードを接続
    if node_idx < n:
        for i in range(node_idx, n):
            target = random.randint(0, node_idx - 1)
            A.append((target, i))
            A.append((i, target))

    # サイクル間を接続
    if num_cycles > 1:
        for i in range(num_cycles - 1):
            u = random.randint(0, nodes_per_cycle - 1) + i * nodes_per_cycle
            v = random.randint(0, nodes_per_cycle - 1) + (i + 1) * nodes_per_cycle
            A.append((u, v))

    # 追加のランダムエッジ
    for u in V:
        for v in V:
            if u != v and (u, v) not in A:
                if random.random() < edge_prob:
                    A.append((u, v))

    return V, A


def generate_mixed_graph(n, edge_prob=0.3, cycle_prob=0.3, seed=None):
    """
    DAG部分とサイクル部分を混在させたグラフを生成

    Args:
        n: ノード数
        edge_prob: エッジの生成確率
        cycle_prob: ノードがサイクル部分に属する確率
        seed: 乱数シード

    Returns:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
    """
    if seed is not None:
        random.seed(seed)

    V = list(range(n))
    A = []

    # ノードをDAG部分とサイクル部分に分割
    cycle_nodes = [v for v in V if random.random() < cycle_prob]
    dag_nodes = [v for v in V if v not in cycle_nodes]

    # サイクル部分を生成
    if len(cycle_nodes) >= 3:
        for i in range(len(cycle_nodes)):
            u = cycle_nodes[i]
            v = cycle_nodes[(i + 1) % len(cycle_nodes)]
            A.append((u, v))

    # DAG部分を生成
    dag_nodes_sorted = sorted(dag_nodes)
    for i, u in enumerate(dag_nodes_sorted):
        for v in dag_nodes_sorted[i + 1 :]:
            if random.random() < edge_prob:
                A.append((u, v))

    # DAG部分とサイクル部分を接続
    if dag_nodes and cycle_nodes:
        # DAGからサイクルへ
        u = random.choice(dag_nodes)
        v = random.choice(cycle_nodes)
        A.append((u, v))

        # サイクルからDAGへ
        u = random.choice(cycle_nodes)
        v = random.choice(dag_nodes)
        A.append((u, v))

    # 連結性を確保
    if not is_connected(V, A):
        for i in range(len(V) - 1):
            if not is_connected(V, A):
                A.append((i, i + 1))

    return V, A


if __name__ == "__main__":
    # テスト
    print("=== ランダム連結グラフ ===")
    V, A = generate_random_connected_graph(5, edge_prob=0.4, seed=42)
    print(f"ノード数: {len(V)}, エッジ数: {len(A)}")
    print(f"エッジ: {A}")
    print(f"連結: {is_connected(V, A)}\n")

    print("=== DAG ===")
    V, A = generate_dag(5, edge_prob=0.5, seed=42)
    print(f"ノード数: {len(V)}, エッジ数: {len(A)}")
    print(f"エッジ: {A}")
    print(f"連結: {is_connected(V, A)}\n")

    print("=== サイクリックグラフ ===")
    V, A = generate_cyclic_graph(8, num_cycles=2, seed=42)
    print(f"ノード数: {len(V)}, エッジ数: {len(A)}")
    print(f"エッジ: {A}")
    print(f"連結: {is_connected(V, A)}\n")

    print("=== 混合グラフ ===")
    V, A = generate_mixed_graph(8, edge_prob=0.3, cycle_prob=0.5, seed=42)
    print(f"ノード数: {len(V)}, エッジ数: {len(A)}")
    print(f"エッジ: {A}")
    print(f"連結: {is_connected(V, A)}")
