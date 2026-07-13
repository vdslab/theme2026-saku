"""Coordinate assignment for a layered drawing on a flat torus.

The graph is assumed to be properly layered and crossing-reduced.  Layers are
drawn along the x-axis and this module computes the in-layer y coordinates.
It uses the four directional passes and average-median balancing of
Brandes--Koepf, followed by a constrained torus-aware smoothing pass.

This is deliberately a torus adaptation rather than a verbatim implementation
of the planar algorithm: cut segments (``t_val`` or non-zero ``psi``) are not
used for vertical alignment, and the compaction is solved on the explicit
block-constraint DAG.  The latter avoids the class-shift accumulation issue
documented in the 2020 Brandes--Koepf erratum.
"""

from collections import defaultdict, deque
import math
from statistics import median


MIN_NODE_GAP = 1.0
ALIGNMENT_ITERATIONS = 4


def assign_torus_brandes_koepf_coordinates(
    order,
    layer_dict,
    edges,
    t_val=None,
    psi=None,
    min_gap=MIN_NODE_GAP,
    smooth_iterations=ALIGNMENT_ITERATIONS,
    original_nodes=None,
):
    """
    Compute node coordinates for the drawing stage.

    Args:
        order: dict[layer, list[node]], final in-layer order.
        layer_dict: dict[layer, list[node]], layered graph after dummy insertion.
        edges: list[(u, v)], edges after dummy insertion.
        t_val: dict[(u, v), bool], left-right torus flags.
        psi: dict[(u, v), int], top-bottom winding numbers.
        min_gap: minimum cyclic distance between consecutive nodes in one
            layer, including the last-to-first gap across the torus seam.
        smooth_iterations: ordered smoothing rounds after BK compaction.
        original_nodes: original (non-dummy) nodes.  If supplied, inner
            dummy-to-dummy segments are preferred when type-1 conflicts are
            marked, as in Brandes--Koepf.

    Returns:
        dict[node, (x, y)]: coordinates in the same drawing coordinate system as
        draw_radial_torus.  When ``min_gap`` is not 1, pass
        ``vertical_period=max_layer_size * min_gap`` to that drawing function.
    """
    _validate_parameters(min_gap, smooth_iterations)
    t_val = {} if t_val is None else t_val
    psi = {} if psi is None else psi
    layers = sorted(layer_dict.keys())
    if not layers:
        return {}

    node_order = _complete_order(order, layer_dict, layers)
    _validate_graph(node_order, edges, psi)
    node_to_layer = _node_to_layer(node_order)
    layer_index = {layer: index for index, layer in enumerate(layers)}
    period = _drawing_period(node_order, min_gap)
    dummy_nodes = _dummy_nodes(node_order, original_nodes)

    variants = []
    horizontal_directions = []
    for scan_forward in (True, False):
        for horizontal_forward in (True, False):
            oriented_order = _orient_order(node_order, horizontal_forward)
            y_values = _single_bk_assignment(
                node_order=oriented_order,
                edges=edges,
                t_val=t_val,
                psi=psi,
                layers=layers,
                node_to_layer=node_to_layer,
                layer_index=layer_index,
                scan_forward=scan_forward,
                min_gap=min_gap,
                dummy_nodes=dummy_nodes,
            )
            if not horizontal_forward:
                y_values = {node: -value for node, value in y_values.items()}
            variants.append(y_values)
            horizontal_directions.append(horizontal_forward)

    variants = _align_to_narrowest(variants, horizontal_directions)
    y_by_node = _balanced_coordinates(variants)
    y_by_node = _center_in_period(y_by_node, period, min_gap)
    y_by_node = _project_all_layers(y_by_node, node_order, period, min_gap)
    y_by_node = _smooth_torus_edges(
        y_by_node=y_by_node,
        node_order=node_order,
        edges=edges,
        psi=psi,
        period=period,
        min_gap=min_gap,
        iterations=smooth_iterations,
    )

    x_min = -0.5
    pos = {}
    for layer in layers:
        x = x_min + layer_index[layer] + 0.5
        for node in node_order[layer]:
            pos[node] = (x, y_by_node[node])
    return pos


def _single_bk_assignment(
    node_order,
    edges,
    t_val,
    psi,
    layers,
    node_to_layer,
    layer_index,
    scan_forward,
    min_gap,
    dummy_nodes,
):
    conflicts = _mark_conflicts(
        node_order=node_order,
        edges=edges,
        t_val=t_val,
        psi=psi,
        layers=layers,
        node_to_layer=node_to_layer,
        dummy_nodes=dummy_nodes,
    )
    block_of = _vertical_alignment(
        node_order=node_order,
        edges=edges,
        psi=psi,
        layers=layers,
        node_to_layer=node_to_layer,
        layer_index=layer_index,
        t_val=t_val,
        conflicts=conflicts,
        scan_forward=scan_forward,
    )
    return _horizontal_compaction(node_order, block_of, min_gap)


def _complete_order(order, layer_dict, layers):
    order = {} if order is None else order
    unknown_layers = [
        layer for layer, nodes in order.items() if layer not in layer_dict and nodes
    ]
    if unknown_layers:
        raise ValueError(f"order contains unknown layers: {unknown_layers!r}")

    completed = {}
    for layer in layers:
        layer_nodes = layer_dict[layer]
        seen = set()
        nodes = []
        for node in order.get(layer, []):
            if node not in layer_nodes:
                raise ValueError(
                    f"node {node!r} in order[{layer!r}] is absent from that layer"
                )
            if node in seen:
                raise ValueError(f"order[{layer!r}] contains duplicate node {node!r}")
            nodes.append(node)
            seen.add(node)
        for node in layer_nodes:
            if node not in seen:
                nodes.append(node)
        completed[layer] = nodes
    return completed


def _validate_parameters(min_gap, smooth_iterations):
    if not isinstance(min_gap, (int, float)) or not math.isfinite(min_gap):
        raise ValueError("min_gap must be a finite number")
    if min_gap <= 0:
        raise ValueError("min_gap must be greater than zero")
    if isinstance(smooth_iterations, bool) or not isinstance(smooth_iterations, int):
        raise ValueError("smooth_iterations must be a non-negative integer")
    if smooth_iterations < 0:
        raise ValueError("smooth_iterations must be a non-negative integer")


def _validate_graph(node_order, edges, psi):
    node_to_layer = {}
    for layer, nodes in node_order.items():
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"layer {layer!r} contains duplicate nodes")
        for node in nodes:
            if node in node_to_layer:
                raise ValueError(
                    f"node {node!r} occurs in both layer "
                    f"{node_to_layer[node]!r} and layer {layer!r}"
                )
            node_to_layer[node] = layer

    for edge in edges:
        if not isinstance(edge, tuple) or len(edge) != 2:
            raise ValueError(f"invalid edge: {edge!r}")
        if edge[0] not in node_to_layer or edge[1] not in node_to_layer:
            raise ValueError(f"edge endpoint is missing from layer_dict: {edge!r}")
        winding = psi.get(edge, 0)
        if not isinstance(winding, (int, float)) or not math.isfinite(winding):
            raise ValueError(f"psi must contain finite numeric values: {edge!r}")


def _dummy_nodes(node_order, original_nodes):
    if original_nodes is None:
        return set()
    all_nodes = {node for nodes in node_order.values() for node in nodes}
    original_set = set(original_nodes)
    unknown = original_set - all_nodes
    if unknown:
        raise ValueError(
            "original_nodes contains nodes that are absent from layer_dict: "
            f"{sorted(unknown, key=repr)!r}"
        )
    return all_nodes - original_set


def _orient_order(node_order, horizontal_forward):
    if horizontal_forward:
        return {layer: list(nodes) for layer, nodes in node_order.items()}
    return {layer: list(reversed(nodes)) for layer, nodes in node_order.items()}


def _node_to_layer(order):
    result = {}
    for layer, nodes in order.items():
        for node in nodes:
            result[node] = layer
    return result


def _drawing_period(order, min_gap):
    max_layer_size = max((len(nodes) for nodes in order.values()), default=1)
    return max(float(max_layer_size) * min_gap, min_gap)


def _positions(order):
    result = {}
    for layer, nodes in order.items():
        for index, node in enumerate(nodes):
            result[node] = index
    return result


def _mark_conflicts(
    node_order,
    edges,
    t_val,
    psi,
    layers,
    node_to_layer,
    dummy_nodes,
):
    """Mark conflicts that must not displace an inner dummy segment.

    Type-0 conflicts between two non-inner segments are resolved greedily by
    the alignment pass.  For a type-1 conflict only the non-inner segment is
    marked.  Crossing inner segments (type 2) violate the usual BK precondition;
    both are marked so the fixed layer order remains authoritative.
    """
    conflicts = set()
    positions = _positions(node_order)

    for index, fixed_layer in enumerate(layers[:-1]):
        free_layer = layers[index + 1]
        layer_edges = _edges_between_layers(
            edges, fixed_layer, free_layer, node_to_layer
        )
        layer_edges = [
            edge
            for edge in layer_edges
            if not t_val.get(edge, False) and psi.get(edge, 0) == 0
        ]

        for i, first in enumerate(layer_edges):
            for second in layer_edges[i + 1 :]:
                if first[0] == second[0] or first[1] == second[1]:
                    continue
                source_delta = positions[first[0]] - positions[second[0]]
                target_delta = positions[first[1]] - positions[second[1]]
                if source_delta * target_delta >= 0:
                    continue

                first_inner = first[0] in dummy_nodes and first[1] in dummy_nodes
                second_inner = second[0] in dummy_nodes and second[1] in dummy_nodes
                if first_inner and not second_inner:
                    conflicts.add(second)
                elif second_inner and not first_inner:
                    conflicts.add(first)
                elif first_inner and second_inner:
                    # Type-2 conflicts cannot preserve both inner segments.
                    conflicts.add(first)
                    conflicts.add(second)

    return conflicts


def _edges_between_layers(edges, fixed_layer, free_layer, node_to_layer):
    return [
        (u, v)
        for u, v in edges
        if node_to_layer.get(u) == fixed_layer and node_to_layer.get(v) == free_layer
    ]


def _vertical_alignment(
    node_order,
    edges,
    psi,
    layers,
    node_to_layer,
    layer_index,
    t_val,
    conflicts,
    scan_forward,
):
    dsu = _DisjointBlocks(node_order)
    positions = _positions(node_order)
    incoming = defaultdict(list)
    outgoing = defaultdict(list)

    for edge in edges:
        if t_val.get(edge, False) or psi.get(edge, 0) != 0:
            continue
        u, v = edge
        incoming[v].append(edge)
        outgoing[u].append(edge)

    layer_scan = layers[1:] if scan_forward else list(reversed(layers[:-1]))

    for layer in layer_scan:
        nodes = node_order[layer]
        last_fixed_position = -1

        for node in nodes:
            candidates = _median_edges(
                node=node,
                incoming=incoming,
                outgoing=outgoing,
                positions=positions,
                node_to_layer=node_to_layer,
                layer_index=layer_index,
                current_layer=layer,
                layers=layers,
                scan_forward=scan_forward,
            )
            for edge in candidates:
                if edge in conflicts:
                    continue

                fixed_node = edge[0] if scan_forward else edge[1]
                fixed_position = positions[fixed_node]
                if fixed_position <= last_fixed_position:
                    continue

                if dsu.union(node, fixed_node):
                    last_fixed_position = fixed_position
                    break

    return dsu.block_of()


def _median_edges(
    node,
    incoming,
    outgoing,
    positions,
    node_to_layer,
    layer_index,
    current_layer,
    layers,
    scan_forward,
):
    current_index = layer_index[current_layer]
    if scan_forward:
        fixed_layer = layers[current_index - 1]
        source_edges = [
            edge
            for edge in incoming.get(node, [])
            if node_to_layer.get(edge[0]) == fixed_layer
        ]
        key = lambda edge: edge[0]
    else:
        fixed_layer = layers[current_index + 1]
        source_edges = [
            edge
            for edge in outgoing.get(node, [])
            if node_to_layer.get(edge[1]) == fixed_layer
        ]
        key = lambda edge: edge[1]

    if not source_edges:
        return []

    source_edges.sort(key=lambda edge: positions[key(edge)])
    mid = len(source_edges) // 2
    if len(source_edges) % 2 == 1:
        return [source_edges[mid]]
    return [source_edges[mid - 1], source_edges[mid]]


def _horizontal_compaction(node_order, block_of, min_gap):
    block_graph = defaultdict(list)
    blocks = []
    seen_blocks = set()
    for nodes in node_order.values():
        for node in nodes:
            block = block_of[node]
            if block not in seen_blocks:
                blocks.append(block)
                seen_blocks.add(block)

    constraints = set()

    for nodes in node_order.values():
        previous_block = None
        for node in nodes:
            block = block_of[node]
            if previous_block is not None and previous_block != block:
                constraints.add((previous_block, block))
            previous_block = block

    indegree = {block: 0 for block in blocks}
    for previous_block, block in constraints:
        block_graph[previous_block].append(block)
        indegree[block] += 1

    block_y = {block: 0.0 for block in blocks}
    queue = deque([block for block in blocks if indegree[block] == 0])
    visited = 0

    while queue:
        block = queue.popleft()
        visited += 1
        for next_block in block_graph[block]:
            block_y[next_block] = max(
                block_y[next_block], block_y[block] + min_gap
            )
            indegree[next_block] -= 1
            if indegree[next_block] == 0:
                queue.append(next_block)

    if visited != len(blocks):
        raise RuntimeError("alignment block constraints contain a cycle")

    return {
        node: block_y[block_of[node]]
        for nodes in node_order.values()
        for node in nodes
    }
def _align_to_narrowest(variants, horizontal_directions):
    """Align biased layouts as prescribed by Brandes--Koepf balancing."""
    if not variants:
        return []

    bounds = []
    for variant in variants:
        values = list(variant.values())
        lower = min(values, default=0.0)
        upper = max(values, default=0.0)
        bounds.append((lower, upper, upper - lower))

    reference_index = min(range(len(variants)), key=lambda index: bounds[index][2])
    reference_lower, reference_upper, _ = bounds[reference_index]
    aligned = []

    for variant, horizontal_forward, (lower, upper, _) in zip(
        variants, horizontal_directions, bounds
    ):
        if horizontal_forward:
            shift = reference_lower - lower
        else:
            shift = reference_upper - upper
        aligned.append({node: value + shift for node, value in variant.items()})

    return aligned


def _balanced_coordinates(variants):
    if not variants:
        return {}
    nodes = variants[0].keys()
    return {node: median([variant[node] for variant in variants]) for node in nodes}


def _center_in_period(y_by_node, period, min_gap):
    if not y_by_node:
        return {}
    lower = min(y_by_node.values())
    upper = max(y_by_node.values())
    current_center = (lower + upper) / 2.0
    domain_center = (period - min_gap) / 2.0
    shift = domain_center - current_center
    return {node: value + shift for node, value in y_by_node.items()}


def _project_all_layers(y_by_node, node_order, period, min_gap):
    projected = dict(y_by_node)
    for nodes in node_order.values():
        targets = [projected[node] for node in nodes]
        values = _project_ordered_periodic(targets, period, min_gap)
        for node, value in zip(nodes, values):
            projected[node] = value
    return projected


def _smooth_torus_edges(
    y_by_node,
    node_order,
    edges,
    psi,
    period,
    min_gap,
    iterations,
):
    y_values = dict(y_by_node)
    adjacency = defaultdict(list)

    for edge in edges:
        u, v = edge
        winding = psi.get(edge, 0)
        adjacency[v].append((u, -winding * period))
        adjacency[u].append((v, winding * period))

    for _ in range(iterations):
        next_values = dict(y_values)
        for nodes in node_order.values():
            targets = []
            for node in nodes:
                neighbors = adjacency.get(node, [])
                if neighbors:
                    target = sum(y_values[n] + offset for n, offset in neighbors)
                    target /= len(neighbors)
                    targets.append(0.65 * target + 0.35 * y_values[node])
                else:
                    targets.append(y_values[node])

            projected = _project_ordered_periodic(targets, period, min_gap)
            for node, value in zip(nodes, projected):
                next_values[node] = value
        y_values = next_values

    return y_values


def _project_ordered_periodic(targets, period, min_gap):
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

    shifted_targets = [
        target - index * min_gap for index, target in enumerate(targets)
    ]
    fitted = _isotonic_non_decreasing(shifted_targets)
    slack = max(0.0, period - required)
    bounded = [min(slack, max(0.0, value)) for value in fitted]
    return [value + index * min_gap for index, value in enumerate(bounded)]


def _isotonic_non_decreasing(values):
    blocks = []
    for index, value in enumerate(values):
        blocks.append({"sum": value, "weight": 1, "start": index, "end": index})
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            if left["sum"] / left["weight"] <= right["sum"] / right["weight"]:
                break
            merged = {
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


class _DisjointBlocks:
    def __init__(self, node_order):
        self.parent = {}
        self.layers = {}
        for layer, nodes in node_order.items():
            for node in nodes:
                self.parent[node] = node
                self.layers[node] = {layer}

    def find(self, node):
        parent = self.parent[node]
        if parent != node:
            self.parent[node] = self.find(parent)
        return self.parent[node]

    def union(self, first, second):
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root == second_root:
            return False
        if self.layers[first_root] & self.layers[second_root]:
            return False

        if len(self.layers[first_root]) < len(self.layers[second_root]):
            first_root, second_root = second_root, first_root

        self.parent[second_root] = first_root
        self.layers[first_root].update(self.layers[second_root])
        return True

    def block_of(self):
        return {node: self.find(node) for node in self.parent}
