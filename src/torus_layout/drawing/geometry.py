from ..validation import is_integer, is_number, is_sequence, is_tuple

"""描画の検証、周期境界での辺分割、座標補完。"""
from collections import defaultdict
from collections.abc import Mapping
from typing import TypedDict
import math
from ..models import Node, Edge, Layers, Positions


class IsotonicBlock(TypedDict):
    sum: float
    weight: int
    start: int
    end: int


def validate_drawing_parameters(
    dpi: float,
    node_size: float,
    dummy_node_size: float,
    font_size: float,
    edge_width: float,
    alignment_iterations: int,
) -> None:
    values = {
        "dpi": dpi,
        "node_size": node_size,
        "dummy_node_size": dummy_node_size,
        "font_size": font_size,
        "edge_width": edge_width,
    }
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not is_number(value)
            or (not math.isfinite(value))
            or (value <= 0)
        ):
            raise ValueError(f"{name} must be a finite positive number")
    if (
        isinstance(alignment_iterations, bool)
        or not is_integer(alignment_iterations)
        or alignment_iterations < 0
    ):
        raise ValueError("alignment_iterations must be a non-negative integer")


def complete_node_order(order: Layers | None, layer_dict: Layers) -> Layers:
    node_to_layer: dict[Node, int] = {}
    for layer, nodes in layer_dict.items():
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"L[{layer!r}] contains duplicate nodes")
        for node in nodes:
            if node in node_to_layer:
                raise ValueError(
                    f"node {node!r} occurs in both layer {node_to_layer[node]!r} and layer {layer!r}"
                )
            node_to_layer[node] = layer
    if order is None:
        return {layer: list(nodes) for layer, nodes in layer_dict.items()}
    unknown_layers = [
        layer for layer, nodes in order.items() if layer not in layer_dict and nodes
    ]
    if unknown_layers:
        raise ValueError(f"order contains unknown layers: {unknown_layers!r}")
    completed: Layers = {}
    for layer, layer_nodes in layer_dict.items():
        nodes = list(order.get(layer, []))
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"order[{layer!r}] contains duplicate nodes")
        unknown_nodes = [node for node in nodes if node not in layer_nodes]
        if unknown_nodes:
            raise ValueError(
                f"order[{layer!r}] contains nodes outside the layer: {unknown_nodes!r}"
            )
        seen = set(nodes)
        completed[layer] = nodes + [node for node in layer_nodes if node not in seen]
    return completed


def validate_positions(
    pos: Positions,
    layer_dict: Layers,
    edges: list[Edge],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> None:
    required_nodes = {node for nodes in layer_dict.values() for node in nodes}
    for edge in edges:
        if not is_tuple(edge) or len(edge) != 2:
            raise ValueError(f"invalid edge: {edge!r}")
        if edge[0] not in required_nodes or edge[1] not in required_nodes:
            raise ValueError(f"edge endpoint is missing from L: {edge!r}")
    missing = required_nodes - set(pos)
    if missing:
        raise ValueError(f"pos is missing layered nodes: {sorted(missing, key=repr)!r}")
    tolerance = 1e-09
    for node in required_nodes:
        value = pos[node]
        if not is_sequence(value) or len(value) != 2:
            raise ValueError(f"pos[{node!r}] must be an (x, y) pair")
        x, y = value
        if not all((is_number(item) and math.isfinite(item) for item in value)):
            raise ValueError(f"pos[{node!r}] must contain finite coordinates")
        if not x_min + tolerance < x < x_max - tolerance:
            raise ValueError(f"pos[{node!r}] lies outside the horizontal domain")
        if not y_min + tolerance < y < y_max - tolerance:
            raise ValueError(f"pos[{node!r}] lies outside the vertical domain")


def paper_figure_size(
    num_layers: int, max_layer_size: int, show_legend: bool
) -> tuple[float, float]:
    width = min(7.2, max(3.4, 0.72 * num_layers + 1.2))
    data_ratio = num_layers / max(max_layer_size, 1)
    height = width / max(data_ratio, 0.65)
    height = min(5.4, max(2.4, height))
    if show_legend:
        height = min(5.8, height + 0.3)
    return (width, height)


def periodic_edge_segments(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    horizontal_winding: int,
    vertical_winding: int,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """普遍被覆上の直線を、基本領域内の線分列へ分割する。"""
    width = x_max - x_min
    height = y_max - y_min
    lifted_end = (
        end[0] + horizontal_winding * width,
        end[1] + vertical_winding * height,
    )
    crossing_times = [0.0, 1.0]
    crossing_times.extend(axis_crossing_times(start[0], lifted_end[0], x_min, width))
    crossing_times.extend(axis_crossing_times(start[1], lifted_end[1], y_min, height))
    crossing_times.sort()
    unique_times: list[float] = []
    for value in crossing_times:
        if not unique_times or not math.isclose(
            value, unique_times[-1], rel_tol=0.0, abs_tol=1e-12
        ):
            unique_times.append(value)
    dx = lifted_end[0] - start[0]
    dy = lifted_end[1] - start[1]
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for left_t, right_t in zip(unique_times, unique_times[1:]):
        middle_t = (left_t + right_t) / 2.0
        middle_x = start[0] + middle_t * dx
        middle_y = start[1] + middle_t * dy
        x_tile = math.floor((middle_x - x_min) / width)
        y_tile = math.floor((middle_y - y_min) / height)

        def wrapped_point(t: float) -> tuple[float, float]:
            return (
                start[0] + t * dx - x_tile * width,
                start[1] + t * dy - y_tile * height,
            )

        segments.append((wrapped_point(left_t), wrapped_point(right_t)))
    return segments


def axis_crossing_times(
    start: float, end: float, minimum: float, period: float
) -> list[float]:
    """開区間(start, end)にある周期境界との交差時刻を返す。"""
    delta = end - start
    if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=1e-15):
        return []
    lower = min(start, end)
    upper = max(start, end)
    first_index = math.floor((lower - minimum) / period) + 1
    last_index = math.ceil((upper - minimum) / period) - 1
    times: list[float] = []
    for index in range(first_index, last_index + 1):
        boundary = minimum + index * period
        t = (boundary - start) / delta
        if 0.0 < t < 1.0:
            times.append(t)
    return times


def assign_positions(
    A: list[Edge],
    psi: Mapping[Edge, float],
    node_order: Layers,
    sorted_layers: list[int],
    layer_index: dict[int, int],
    vertical_period: float,
    coordinate_gap: float,
    align_edges: bool,
    alignment_iterations: int,
) -> Positions:
    center_y = (vertical_period - coordinate_gap) / 2.0
    y_by_node: dict[Node, float] = {}
    for layer_num in sorted_layers:
        nodes = node_order[layer_num]
        centered_y = centered_positions(len(nodes), center_y, coordinate_gap)
        for node, y in zip(nodes, centered_y):
            y_by_node[node] = y
    if align_edges:
        adjacency: dict[Node, list[tuple[Node, float]]] = defaultdict(list)
        for u, v in A:
            if u in y_by_node and v in y_by_node:
                winding = psi.get((u, v), 0)
                adjacency[u].append((v, winding * vertical_period))
                adjacency[v].append((u, -winding * vertical_period))
        for _ in range(alignment_iterations):
            next_y = dict(y_by_node)
            for layer_num in sorted_layers:
                nodes = node_order[layer_num]
                if not nodes:
                    continue
                targets: list[float] = []
                for node in nodes:
                    neighbors = adjacency.get(node, [])
                    if neighbors:
                        neighbor_y = sum(
                            (
                                y_by_node[neighbor] + offset
                                for neighbor, offset in neighbors
                            )
                        ) / len(neighbors)
                        targets.append(0.7 * neighbor_y + 0.3 * y_by_node[node])
                    else:
                        targets.append(y_by_node[node])
                projected = project_ordered_centered(
                    targets,
                    center_y,
                    min_gap=coordinate_gap,
                    max_span=max(0.0, vertical_period - coordinate_gap),
                )
                for node, y in zip(nodes, projected):
                    next_y[node] = y
            y_by_node: dict[Node, float] = next_y
    pos: Positions = {}
    for layer_num in sorted_layers:
        x = float(layer_index[layer_num])
        nodes = node_order[layer_num]
        for node in nodes:
            pos[node] = (x, y_by_node[node])
    return pos


def centered_positions(
    count: int, center_y: float, spacing: float = 1.0
) -> list[float]:
    if count == 0:
        return []
    start = center_y - (count - 1) * spacing / 2.0
    return [start + idx * spacing for idx in range(count)]


def project_ordered_centered(
    targets: list[float],
    center_y: float,
    min_gap: float = 1.0,
    max_span: float | None = None,
) -> list[float]:
    if not targets:
        return []
    shifted_targets = [target - idx * min_gap for idx, target in enumerate(targets)]
    fitted = isotonic_non_decreasing(shifted_targets)
    positions = [value + idx * min_gap for idx, value in enumerate(fitted)]
    if max_span is not None and positions[-1] - positions[0] > max_span:
        return centered_positions(len(targets), center_y, min_gap)
    mean_y = sum(positions) / len(positions)
    shift = center_y - mean_y
    return [position + shift for position in positions]


def isotonic_non_decreasing(values: list[float]) -> list[float]:
    blocks: list[IsotonicBlock] = []
    for idx, value in enumerate(values):
        blocks.append({"sum": value, "weight": 1, "start": idx, "end": idx})
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
        for idx in range(block["start"], block["end"] + 1):
            fitted[idx] = value
    return fitted
