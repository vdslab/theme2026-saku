from create_gurobi_env import create_gurobi_env

from formulas import p_l, p_g, p_g2, p_q
from formulas.intersection_reduction import intersection_reduction

from collections import defaultdict

from draw import draw

from generate_dag import generate_dag
from generate_graph import generate_graph

from remove_cycles import remove_cycles


env = create_gurobi_env()
label = "P_g"

# -------- グラフ生成 --------

# DAG自動生成
"""
V, A, w = generate_dag(n=15, edge_prob=0.3, weight_range=(1, 1))

lam = {e: 1 for e in A}
"""
# -----

# グラフ自動生成
"""
V, A, w = generate_graph(n=15, prob=0.3)

lam = {e: 1 for e in A}
"""
# -----


# -- 用意したやつ --
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
w = {}
lam = {}

for uv in A:
    w[uv] = 1
    lam[uv] = 1

# -----


# -------- 閉路除去 --------
# A = remove_cycles(V, A)

V0 = [i for i in V if all(i != v2 for (v1, v2) in A)]
Vl = [i for i in V if all(i != v1 for (v1, v2) in A)]

# -------- 最適化 --------

# x_val = p_g.pg(label, V, A, w, lam, V0, Vl)
# x_val = p_g2.pg2(label, V, A, w, lam, V0, Vl)
# x_val = p_q.pq(label, V, A, w, lam, V0, Vl)
x_val = p_l.pl(label, V, A, w, lam, V0, Vl)

# draw(V, A, x_val, label)

# -------- ダミーノード作成 --------
v_val = [*V]
a_val = []
w_val = {}
lam_val = {}
dummy_node = set()

for u, v in A:
    if abs(x_val[u] - x_val[v]) == 1:
        a_val.append((u, v))
        w_val[(u, v)] = 1
        lam_val[(u, v)] = 1
    else:
        mn = min(x_val[u], x_val[v])
        mx = max(x_val[u], x_val[v])
        num1 = u
        num2 = len(v_val)

        for i in range(mn + 1, mx):
            v_val.append(num2)
            dummy_node.add(num2)
            x_val[num2] = i

            pair = (num1, num2)
            a_val.append(pair)
            w_val[pair] = 1
            lam_val[pair] = 1
            num1 = num2
            num2 = len(v_val)

        pair = (num1, v)
        a_val.append(pair)
        w_val[pair] = 1
        lam_val[pair] = 1


# -------- 交差削減 --------
V_layers = defaultdict(list)
for v in v_val:
    layer = x_val[v]
    V_layers[layer].append(v)

E_layers = defaultdict(list)
for u, v in a_val:
    layer_u = x_val[u]
    layer_v = x_val[v]
    if layer_u < layer_v and layer_v - layer_u == 1:
        E_layers[layer_u].append((u, v))

x_order_val, c_val = intersection_reduction(V_layers, E_layers, w_val)

x_order_bool = {key: val > 0.5 for key, val in x_order_val.items()}

node_order = {}
for layer, nodes in V_layers.items():
    sorted_nodes = sorted(
        nodes,
        key=lambda u: sum(
            1 for v in nodes if u != v and x_order_bool.get((u, v), False)
        ),
        reverse=True,
    )
    for pos, node in enumerate(sorted_nodes):
        node_order[node] = pos

A += (14, 0)
draw(V, A, x_val, label, node_order)
