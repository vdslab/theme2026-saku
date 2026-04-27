import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict


def draw(V, A, x_val, label, node_order=None):
    layers = defaultdict(list)

    for v, x in x_val.items():
        layers[x].append(v)

    pos = {}
    for x, nodes in layers.items():
        if node_order:
            sorted_nodes = sorted(nodes, key=lambda v: node_order.get(v, float("inf")))
        else:
            sorted_nodes = sorted(nodes)
        for i, v in enumerate(sorted_nodes):
            pos[v] = (x, i)

    G = nx.DiGraph()
    G.add_nodes_from(V)
    G.add_edges_from(A)

    fig = plt.figure(figsize=(8, 6))
    nx.draw(
        G, pos, with_labels=True, node_size=100, node_color="lightblue", arrowsize=20
    )

    plt.gca().invert_yaxis()
    plt.show()
    # fig.savefig(f"./fig/{label}")
