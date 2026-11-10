"""
トーラス階層割当のヒューリスティック実装
SCC-based Modular Layering方式

アルゴリズム:
1. SCC分解（Tarjanアルゴリズム）
2. SCC DAGを構築
3. SCC DAGにlongest-path layeringを適用
4. 各SCC内でmodular rank optimizationを適用

周期的rank空間 (rank ∈ Z_k) を使用し、
各辺 (u,v) について rank(v) - rank(u) ≡ 1 (mod k) を目指す。
"""

import time
import random
import math
from collections import defaultdict, deque


def tarjan_scc(V, A):
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

    def strongconnect(node):
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        # 後続ノードを探索
        for successor in adj[node]:
            if successor not in index:
                strongconnect(successor)
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
            strongconnect(node)

    # ノードからSCC IDへのマッピングを作成
    node_to_scc = {}
    for scc_id, scc in enumerate(sccs):
        for node in scc:
            node_to_scc[node] = scc_id

    return sccs, node_to_scc


def build_scc_dag(node_to_scc, A):
    """
    SCC DAGを構築

    Args:
        sccs: SCCのリスト
        node_to_scc: ノードからSCC IDへのマッピング
        A: 元のエッジ集合

    Returns:
        scc_edges: SCC間のエッジ list[tuple(int, int)]
    """
    scc_edges = set()
    for u, v in A:
        scc_u = node_to_scc[u]
        scc_v = node_to_scc[v]
        if scc_u != scc_v:
            scc_edges.add((scc_u, scc_v))

    return list(scc_edges)


def longest_path_layering_scc(sccs, scc_edges):
    """
    SCC DAGに対してlongest-path layeringを適用

    Args:
        sccs: SCCのリスト
        scc_edges: SCC間のエッジ

    Returns:
        scc_layers: 各SCCの階層 dict[int: int]
    """
    num_sccs = len(sccs)

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

    # BFSでlongest pathを計算
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            # longest pathを更新
            scc_layers[v] = max(scc_layers.get(v, 0), scc_layers[u] + 1)
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    return scc_layers


def cyclic_dist(a, b, k):
    """
    周期的距離を計算

    Args:
        a: 開始rank
        b: 終了rank
        k: 周期

    Returns:
        (b - a) mod k
    """
    return (b - a) % k


def compute_energy(rank, edges, k, w):
    """
    エネルギー関数を計算
    E = Σ w(u,v) * penalty(d(u,v))
    d(u,v) = (rank(v) - rank(u)) mod k

    penalty(d) = {
        1000000 if d == 0  (同階層ペナルティ)
        (d - 1)^2 otherwise (理想距離1からのずれ)
    }

    Args:
        rank: ノードのrank dict[int: int]
        edges: エッジリスト list[tuple(int, int)]
        k: 周期
        w: エッジ重み dict[(int,int): float]

    Returns:
        エネルギー値 float
    """
    energy = 0.0
    for u, v in edges:
        d = cyclic_dist(rank[u], rank[v], k)
        weight = w.get((u, v), 1.0)

        # d = 0（同階層）には非常に大きなペナルティ
        if d == 0:
            energy += weight * 1000000
        else:
            energy += weight * (d - 1) ** 2
    return energy


def estimate_period(scc_nodes, internal_edges):
    """
    SCC内の周期を推定

    Args:
        scc_nodes: SCC内のノードリスト
        internal_edges: SCC内のエッジリスト

    Returns:
        推定周期 int
    """
    n = len(scc_nodes)

    if n <= 1:
        return 1

    # エッジ数からの推定
    m = len(internal_edges)

    # 閉路の平均長を推定
    # 簡易的に sqrt(n) から 2*sqrt(n) の範囲で推定
    estimated_k = max(3, min(n, int(math.sqrt(n) * 1.5)))

    return estimated_k


def bfs_rank_initialization(scc_nodes, internal_edges, k):
    """
    BFSによるrank初期化

    Args:
        scc_nodes: SCC内のノードリスト
        internal_edges: SCC内のエッジリスト
        k: 周期

    Returns:
        初期rank dict[int: int]
    """
    if not scc_nodes:
        return {}

    # 隣接リストを構築
    adj = defaultdict(list)
    for u, v in internal_edges:
        adj[u].append(v)

    # 出次数が多いノードを開始点とする
    out_degree = defaultdict(int)
    for u, v in internal_edges:
        out_degree[u] += 1

    start_node = max(scc_nodes, key=lambda n: out_degree.get(n, 0))

    # BFSで距離を計算
    rank = {}
    rank[start_node] = 0
    queue = deque([start_node])
    visited = {start_node}

    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in visited:
                visited.add(v)
                rank[v] = (rank[u] + 1) % k
                queue.append(v)

    # 未訪問ノードはランダムに配置
    for node in scc_nodes:
        if node not in rank:
            rank[node] = random.randint(0, k - 1)

    return rank


def modular_rank_optimization(
    scc_nodes,
    internal_edges,
    k,
    w,
    max_iterations=2000,
    temperature=10.0,
    cooling_rate=0.995,
):
    """
    周期的rank最適化（Simulated Annealing）

    Args:
        scc_nodes: SCC内のノードリスト
        internal_edges: SCC内のエッジリスト
        k: 周期
        w: エッジ重み dict[(int,int): float]
        max_iterations: 最大反復回数
        temperature: 初期温度
        cooling_rate: 冷却率

    Returns:
        最適化されたrank dict[int: int]
    """
    if not scc_nodes:
        return {}

    if len(scc_nodes) == 1:
        return {scc_nodes[0]: 0}

    if not internal_edges:
        return {node: 0 for node in scc_nodes}

    # 初期化
    rank = bfs_rank_initialization(scc_nodes, internal_edges, k)
    current_energy = compute_energy(rank, internal_edges, k, w)
    best_rank = rank.copy()
    best_energy = current_energy

    temp = temperature

    # Simulated Annealing
    for iteration in range(max_iterations):
        # ランダムにノードを選択
        node = random.choice(scc_nodes)
        old_rank = rank[node]

        # ±1 の変更を試す
        delta = random.choice([-1, 1])
        new_rank = (old_rank + delta) % k

        # 変更を適用
        rank[node] = new_rank
        new_energy = compute_energy(rank, internal_edges, k, w)

        # エネルギー差を計算
        energy_diff = new_energy - current_energy

        # 受理判定
        if energy_diff < 0 or (
            temp > 0 and random.random() < math.exp(-energy_diff / temp)
        ):
            # 受理
            current_energy = new_energy
            if new_energy < best_energy:
                best_energy = new_energy
                best_rank = rank.copy()
        else:
            # 棄却
            rank[node] = old_rank

        # 温度を下げる
        temp *= cooling_rate

    # ポストプロセス: 同階層エッジの最終チェック
    # エネルギー関数で解消されるべきだが、念のため確認して調整
    max_post_iterations = len(scc_nodes) * 2
    for _ in range(max_post_iterations):
        same_layer_edges = [
            (u, v)
            for u, v in internal_edges
            if cyclic_dist(best_rank[u], best_rank[v], k) == 0
        ]

        if not same_layer_edges:
            break

        # 同階層エッジがある場合、片方のノードを調整
        u, v = same_layer_edges[0]

        # vを+1または-1して、エネルギーが小さくなる方を選択
        old_rank_v = best_rank[v]

        best_rank[v] = (old_rank_v + 1) % k
        energy_plus = compute_energy(best_rank, internal_edges, k, w)

        best_rank[v] = (old_rank_v - 1) % k
        energy_minus = compute_energy(best_rank, internal_edges, k, w)

        # より良い方を選択
        if energy_plus < energy_minus:
            best_rank[v] = (old_rank_v + 1) % k
        # energy_minusの方が良いのでそのまま（すでに設定済み）

    return best_rank


def modular_layering(scc_nodes, A, base_layer, w):
    """
    SCC内でmodular rank optimizationを適用

    Args:
        scc_nodes: SCC内のノードリスト
        A: エッジ集合
        base_layer: このSCCのベース階層（使用しない）
        w: エッジ重み

    Returns:
        node_rank: 各ノードのrank (0 to k-1) dict[int: int]
        k: 周期 int
    """
    if len(scc_nodes) == 1:
        return {scc_nodes[0]: 0}, 1

    # SCC内のエッジのみを抽出
    scc_node_set = set(scc_nodes)
    internal_edges = [(u, v) for u, v in A if u in scc_node_set and v in scc_node_set]

    if not internal_edges:
        return {node: 0 for node in scc_nodes}, 1

    # 周期を推定
    k = estimate_period(scc_nodes, internal_edges)

    # Modular rank最適化
    rank = modular_rank_optimization(scc_nodes, internal_edges, k, w)

    return rank, k


def torus_heuristic(V, A, w=None, lam=None):
    """
    トーラス階層割当のヒューリスティック実装
    SCC-based Periodic Layering方式

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        w: エッジ重み dict[(int,int): float] (未使用、互換性のため)
        lam: エッジの最小階層差 dict[(int,int): int] (未使用、互換性のため)
        alpha: 階層数の重み (未使用、互換性のため)
        beta: エッジスパンの重み (未使用、互換性のため)
        gamma: トーラス辺数の重み (未使用、互換性のため)

    Returns:
        y_val: 各ノードの階層 dict[int: int]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]
        layer_dict: レイヤー集合 dict[int: list[int]]
        run_time: 実行時間 float
    """
    start_time = time.time()

    # エッジの重複を除去
    A = list(set(A))

    # デフォルト値の設定（互換性のため）
    if w is None:
        w = {(u, v): 1 for (u, v) in A}
    if lam is None:
        lam = {(u, v): 1 for (u, v) in A}

    # Step 1: SCC分解
    sccs, node_to_scc = tarjan_scc(V, A)

    # Step 2: SCC DAGを構築
    scc_edges = build_scc_dag(node_to_scc, A)

    # Step 3: SCC DAGにlongest-path layeringを適用
    scc_layers = longest_path_layering_scc(sccs, scc_edges)

    # Step 4: 各SCC内でmodular rank optimizationを適用
    y_val = {}
    scc_periods = {}  # 各SCCの周期を記録
    scc_rank_offset = {}  # 各SCCのrank offset（base層との対応）

    # まず全SCCのmodular rankingを計算し、周期を取得
    scc_node_ranks = {}
    for scc_id, scc_nodes in enumerate(sccs):
        base_layer = scc_layers[scc_id]
        node_rank, k = modular_layering(scc_nodes, A, base_layer, w)
        scc_node_ranks[scc_id] = node_rank
        scc_periods[scc_id] = k

    # 累積オフセットを計算（各SCCの周期分だけオフセット）
    # トポロジカル順にオフセットを割り当て
    # scc_layersの順序でオフセットを計算
    scc_by_layer = sorted(enumerate(sccs), key=lambda x: scc_layers[x[0]])

    current_offset = 0
    for scc_id, scc_nodes in scc_by_layer:
        scc_rank_offset[scc_id] = current_offset
        # 次のSCCは現在のSCCの周期分だけオフセット
        current_offset += scc_periods[scc_id]

    # 絶対的な階層値に変換
    for scc_id, scc_nodes in enumerate(sccs):
        node_rank = scc_node_ranks[scc_id]
        for node in scc_nodes:
            y_val[node] = scc_rank_offset[scc_id] + node_rank[node]

    # t_valを構築（wrap edgeの判定）
    t_val = {}
    for u, v in A:
        if node_to_scc[u] == node_to_scc[v]:
            # 同じSCC内のエッジ
            scc_id = node_to_scc[u]
            k = scc_periods[scc_id]
            offset = scc_rank_offset[scc_id]

            # modular rankを取得
            rank_u = y_val[u] - offset
            rank_v = y_val[v] - offset

            # wrap edge判定: rank_v < rank_u の場合
            # （周期境界を跨ぐ前進辺）
            if rank_v < rank_u:
                t_val[(u, v)] = True
            else:
                t_val[(u, v)] = False
        else:
            # 異なるSCC間のエッジ
            # DAGなので基本的にはwrapしない
            if y_val[v] < y_val[u]:
                t_val[(u, v)] = True
            else:
                t_val[(u, v)] = False

    # layer_dictを構築
    layer_dict = defaultdict(list)
    for v in V:
        layer_dict[y_val[v]].append(v)

    run_time = time.time() - start_time

    return y_val, t_val, dict(layer_dict), run_time
