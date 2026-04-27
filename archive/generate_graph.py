import networkx as nx


def generate_graph(n=10, prob=0.3):
    G = nx.gnp_random_graph(n, prob, directed=True, seed=0)

    V = G.nodes()
    A = G.edges()
    w = {(u, v): 1 for (u, v) in A}

    return V, A, w
