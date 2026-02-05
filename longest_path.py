from collections import deque


def longest_path(V, A):
    n = len(V)

    g = [[] for _ in range(n)]
    d = [0] * n

    for x, y in A:
        g[x - 1].append(y - 1)
        d[y - 1] += 1

    src = deque()
    l = 0
    for i in range(n):
        if d[i] == 0:
            src.append(i)

    while len(src) > 0:
        for _ in range(len(src)):
            i = src.popleft()
            for j in g[i]:
                d[j] -= 1
                if d[j] == 0:
                    src.append(j)
        l += 1

    return l - 1
