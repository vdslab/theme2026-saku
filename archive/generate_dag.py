import random


def generate_dag(n, edge_prob=0.4, weight_range=(1, 5)):
    V = [i for i in range(n)]
    A = []
    w = {}

    for i in range(n):
        for j in range(i + 1, n):
            if random.random() < edge_prob:
                u, v = V[i], V[j]
                A.append((u, v))
                w[(u, v)] = random.randint(*weight_range)

    return V, A, w
