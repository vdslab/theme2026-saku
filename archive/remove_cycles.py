def dfs(G, pos, remove_edges, vis):
    vis[pos] = True
    for i in range(len(G[pos])):
        print(pos, G[pos])
        nex = G[pos][i]
        if vis[nex] == False:
            dfs(G, nex, remove_edges, vis)
        else:
            print("remove", (pos, nex))
            remove_edges.add((pos, nex))
            G[pos].remove(nex)
    vis[pos] = False


def remove_cycles(V, A):
    n = len(V)
    G = [[] for _ in range(n)]
    remove_edges = set()
    vis = [False] * n

    for u, v in A:
        G[u].append(v)

    for i in range(n):
        if vis[i] == False:
            dfs(G, i, remove_edges, vis)

    return [a for a in A if a not in remove_edges]
