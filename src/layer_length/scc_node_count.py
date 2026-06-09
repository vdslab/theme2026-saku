from lib.scc_decomposition import scc_decomposition


def scc_node_count(V, A):
    sccs, _ = scc_decomposition(V, A)
    return len(sccs)
