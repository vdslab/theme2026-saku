import heapq


def dijkstra(g, n, s):
    distance = [float("inf")] * n
    distance[s] = 0
    heap = []

    heapq.heappush(heap, (distance[s], s))
    while heap:
        dist, pos = heapq.heappop(heap)

        if distance[pos] < dist:
            continue

        for nex, cost in g[pos]:
            if distance[nex] > distance[pos] + cost:
                distance[nex] = distance[pos] + cost
                heapq.heappush(heap, (distance[nex], nex))

    return distance


def graph_diameter(V, A, w=None):
    n = len(V)
    g = [[] for _ in range(n)]

    for u, v in A:
        _w = w[(u, v)] if w != None else 1
        g[u].append((v, _w))

    diameter = 0
    for i in range(n):
        d = dijkstra(g, n, i)
        diameter = max(diameter, *[di for di in d if di != float("inf")])

    return diameter
