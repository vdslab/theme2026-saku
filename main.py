import random

import gurobipy as gp
from gurobipy import GRB

from collections import defaultdict

from create_gurobi_env import create_gurobi_env

from formulas import p_g, p_g2, p_q, p_l
from formulas.intersection_reduction import intersection_reduction

from draw import draw


def generate_dag(n, edge_prob=0.4, weight_range=(1, 5)):
    """
    n: ノード数
    edge_prob: 辺が張られる確率
    """
    V = list(range(1, n + 1))
    A = []
    w = {}

    for i in range(n):
        for j in range(i + 1, n):
            if random.random() < edge_prob:
                u, v = V[i], V[j]
                A.append((u, v))
                w[(u, v)] = random.randint(*weight_range)

    return V, A, w


env = create_gurobi_env()

# -------- グラフ生成 --------
# V, A, w = generate_dag(n=10, edge_prob=0.5)

# lam = {e: 0.5 for e in A}  # λ_uv = 0.5

# print("V =", V)
# print("A =", A)
# print("w =", w)

V = [i for i in range(15)]
A = [
    (0, 1),
    (1, 3),
    (2, 3),
    (2, 4),
    (2, 5),
    (3, 6),
    (3, 7),
    (4, 8),
    (5, 9),
    (5, 10),
    (6, 11),
    (7, 12),
    (10, 13),
    (12, 14),
]
V0 = [i for i in V if all(i != v2 for (v1, v2) in A)]
Vl = [i for i in V if all(i != v1 for (v1, v2) in A)]
w = {}
lam = {}

for uv in A:
    w[uv] = 1
    lam[uv] = 1

# -------- 最適化 --------
funcs = [
    {"label": "P_G", "func": p_g.pg},
    {"label": "P_G2", "func": p_g2.pg2},
    {"label": "P_Q", "func": p_q.pq},
    {"label": "P_L", "func": p_l.pl},
]
for f in funcs:
    label = f["label"]
    func = f["func"]

    x_val = func(label, V, A, w, lam, V0, Vl)

    # -------- ダミーノード作成 --------
    a_val = []
    w_val = {}
    lam_val = {}

    for u, v in A:
        if abs(x_val[u] - x_val[v]) == 1:
            a_val.append((u, v))
            w_val[(u, v)] = 1
            lam_val[(u, v)] = 1
        else:
            mn = min(x_val[u], x_val[v])
            mx = max(x_val[u], x_val[v])
            for i in range(mn + 1, mx + 1):
                num = len(V)
                V.append(num)
                x_val[num] = i
                a_val.append((i - 1, i))
                w_val[(i - 1, i)] = 1
                lam_val[(i - 1, i)] = 1

    print(V)
    print(A, w, lam)
    print(a_val, w_val, lam_val)

    draw(V, A, x_val, label)

    """
    # -------- 交差削減 --------
    # 階層割当の結果から V_layers と E_layers を構築
    V_layers = defaultdict(list)
    for v in V:
        layer = x_val[v]
        V_layers[layer].append(v)

    # E_layers: 連続する層間のエッジのみを含む
    E_layers = defaultdict(list)
    for u, v in A:
        layer_u = x_val[u]
        layer_v = x_val[v]
        if layer_u < layer_v and layer_v - layer_u == 1:
            E_layers[layer_u].append((u, v))

    # 交差削減を実行
    if E_layers:  # エッジが存在する場合のみ実行
        x_order_val, c_val = intersection_reduction(V_layers, E_layers, w)

        # x_order_val は既に辞書形式で値を含んでいる
        x_order_bool = {key: val > 0.5 for key, val in x_order_val.items()}

        # 各層内のノードソート順序を計算
        node_order = {}
        for layer, nodes in V_layers.items():
            # 各ノードのスコア: x_order_bool で自分が上にあると判定されたノード数
            sorted_nodes = sorted(
                nodes,
                key=lambda u: sum(
                    1 for v in nodes if u != v and x_order_bool.get((u, v), False)
                ),
                reverse=True,
            )
            for pos, node in enumerate(sorted_nodes):
                node_order[node] = pos

        draw(V, A, x_val, label + "_reduced", node_order)
    else:
        draw(V, A, x_val, label)

    """
