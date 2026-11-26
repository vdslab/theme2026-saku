"""Experimental vectorization of the three parting costs in a strip."""

import numpy as np


def vector_parting_costs(groups, fixed, start, end, winding, sign):
    costs = {-1: [], 0: [], 1: []}
    if not fixed:
        return {value: [0] * len(groups) for value in costs}

    right_x = np.array([start[u] for u, _ in fixed], dtype=np.int64)
    right_y = np.array([end[v] for _, v in fixed], dtype=np.int64)
    right_w = np.array([winding.get(edge, 0) for edge in fixed], dtype=np.int64)
    variable = [edge for group in groups for edge in group]
    left_x = np.array([start[u] for u, _ in variable], dtype=np.int64)[:, None]
    left_y = np.array([end[v] for _, v in variable], dtype=np.int64)[:, None]
    x = np.sign(right_x - left_x)
    y = np.sign(right_y - left_y)
    center = 2 * right_w + y - x
    correction = np.abs(x) + np.abs(y) - 2
    for candidate in costs:
        sums = np.maximum(0, (np.abs(center - 2 * sign * candidate) + correction) // 2).sum(axis=1)
        index = 0
        for group in groups:
            end_index = index + len(group)
            costs[candidate].append(sum(map(int, sums[index:end_index])))
            index = end_index
    return costs
