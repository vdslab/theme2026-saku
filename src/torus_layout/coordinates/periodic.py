"""周期境界で順序と最小間隔を保つ射影。"""

from typing import TypedDict
from ..models import Node, Layers


class IsotonicBlock(TypedDict):
    sum: float
    weight: int
    start: int
    end: int


def drawing_period(order: Layers, min_gap: float) -> float:
    max_layer_size = max((len(nodes) for nodes in order.values()), default=1)
    return max(float(max_layer_size) * min_gap, min_gap)


def center_in_period(
    y_by_node: dict[Node, float], period: float, min_gap: float
) -> dict[Node, float]:
    if not y_by_node:
        return {}
    lower = min(y_by_node.values())
    upper = max(y_by_node.values())
    current_center = (lower + upper) / 2.0
    domain_center = (period - min_gap) / 2.0
    shift = domain_center - current_center
    return {node: value + shift for node, value in y_by_node.items()}


def project_all_layers(
    y_by_node: dict[Node, float], node_order: Layers, period: float, min_gap: float
) -> dict[Node, float]:
    projected = dict(y_by_node)
    for nodes in node_order.values():
        targets = [projected[node] for node in nodes]
        values = project_ordered_periodic(targets, period, min_gap)
        for node, value in zip(nodes, values):
            projected[node] = value
    return projected


def project_ordered_periodic(
    targets: list[float], period: float, min_gap: float
) -> list[float]:
    """Project targets onto ordered points in one torus fundamental domain.

    Transforming ``y[i]`` to ``z[i] = y[i] - i * min_gap`` turns the linear
    separation constraints into monotonicity.  Bounding every fitted ``z`` by
    the remaining slack also guarantees the cyclic last-to-first separation.
    """
    if not targets:
        return []
    required = len(targets) * min_gap
    if required > period + 1e-12:
        raise ValueError("the torus period is too small for the requested min_gap")
    shifted_targets = [target - index * min_gap for index, target in enumerate(targets)]
    fitted = isotonic_non_decreasing(shifted_targets)
    slack = max(0.0, period - required)
    bounded = [min(slack, max(0.0, value)) for value in fitted]
    return [value + index * min_gap for index, value in enumerate(bounded)]


def isotonic_non_decreasing(values: list[float]) -> list[float]:
    blocks: list[IsotonicBlock] = []
    for index, value in enumerate(values):
        blocks.append({"sum": value, "weight": 1, "start": index, "end": index})
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            if left["sum"] / left["weight"] <= right["sum"] / right["weight"]:
                break
            merged: IsotonicBlock = {
                "sum": left["sum"] + right["sum"],
                "weight": left["weight"] + right["weight"],
                "start": left["start"],
                "end": right["end"],
            }
            blocks[-2:] = [merged]
    fitted = [0.0] * len(values)
    for block in blocks:
        value = block["sum"] / block["weight"]
        for index in range(block["start"], block["end"] + 1):
            fitted[index] = value
    return fitted
