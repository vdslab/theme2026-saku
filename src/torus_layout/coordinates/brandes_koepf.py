"""4方向の整列・ブロック圧縮・中央値による統合。"""

from collections import defaultdict, deque
from collections.abc import Mapping, Callable
from statistics import median
from ..models import Node, Edge, Layers


def single_bk_assignment(
    node_order: Layers,
    edges: list[Edge],
    t_val: Mapping[Edge, bool],
    psi: Mapping[Edge, float],
    layers: list[int],
    node_to_layer: dict[Node, int],
    layer_index: dict[int, int],
    scan_forward: bool,
    min_gap: float,
    dummy_nodes: set[Node],
) -> dict[Node, float]:
    conflicts = mark_conflicts(
        node_order=node_order,
        edges=edges,
        t_val=t_val,
        psi=psi,
        layers=layers,
        node_to_layer=node_to_layer,
        dummy_nodes=dummy_nodes,
    )
    block_of = vertical_alignment(
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
    return horizontal_compaction(node_order, block_of, min_gap)


def orient_order(node_order: Layers, horizontal_forward: bool) -> Layers:
    if horizontal_forward:
        return {layer: list(nodes) for layer, nodes in node_order.items()}
    return {layer: list(reversed(nodes)) for layer, nodes in node_order.items()}


def map_node_layers(order: Layers) -> dict[Node, int]:
    result: dict[Node, int] = {}
    for _layer, nodes in order.items():
        for node in nodes:
            result[node] = _layer
    return result


def node_positions(order: Layers) -> dict[Node, int]:
    result: dict[Node, int] = {}
    for _layer, nodes in order.items():
        for index, node in enumerate(nodes):
            result[node] = index
    return result


def mark_conflicts(
    node_order: Layers,
    edges: list[Edge],
    t_val: Mapping[Edge, bool],
    psi: Mapping[Edge, float],
    layers: list[int],
    node_to_layer: dict[Node, int],
    dummy_nodes: set[Node],
) -> set[Edge]:
    """Mark conflicts that must not displace an inner dummy segment.

    Type-0 conflicts between two non-inner segments are resolved greedily by
    the alignment pass.  For a type-1 conflict only the non-inner segment is
    marked.  Crossing inner segments (type 2) violate the usual BK precondition;
    both are marked so the fixed layer order remains authoritative.
    """
    conflicts: set[Edge] = set()
    positions = node_positions(node_order)
    for index, fixed_layer in enumerate(layers[:-1]):
        free_layer = layers[index + 1]
        layer_edges = edges_between_layers(
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
                if first_inner and (not second_inner):
                    conflicts.add(second)
                elif second_inner and (not first_inner):
                    conflicts.add(first)
                elif first_inner and second_inner:
                    conflicts.add(first)
                    conflicts.add(second)
    return conflicts


def edges_between_layers(
    edges: list[Edge], fixed_layer: int, free_layer: int, node_to_layer: dict[Node, int]
) -> list[Edge]:
    return [
        (u, v)
        for u, v in edges
        if node_to_layer.get(u) == fixed_layer and node_to_layer.get(v) == free_layer
    ]


def vertical_alignment(
    node_order: Layers,
    edges: list[Edge],
    psi: Mapping[Edge, float],
    layers: list[int],
    node_to_layer: dict[Node, int],
    layer_index: dict[int, int],
    t_val: Mapping[Edge, bool],
    conflicts: set[Edge],
    scan_forward: bool,
) -> dict[Node, Node]:
    dsu = DisjointBlocks(node_order)
    positions = node_positions(node_order)
    incoming: dict[Node, list[Edge]] = defaultdict(list)
    outgoing: dict[Node, list[Edge]] = defaultdict(list)
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
            candidates = median_edges(
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


def median_edges(
    node: Node,
    incoming: dict[Node, list[Edge]],
    outgoing: dict[Node, list[Edge]],
    positions: dict[Node, int],
    node_to_layer: dict[Node, int],
    layer_index: dict[int, int],
    current_layer: int,
    layers: list[int],
    scan_forward: bool,
) -> list[Edge]:
    current_index = layer_index[current_layer]
    if scan_forward:
        fixed_layer = layers[current_index - 1]
        source_edges = [
            edge
            for edge in incoming.get(node, [])
            if node_to_layer.get(edge[0]) == fixed_layer
        ]
        key: Callable[[Edge], Node] = lambda edge: edge[0]
    else:
        fixed_layer = layers[current_index + 1]
        source_edges = [
            edge
            for edge in outgoing.get(node, [])
            if node_to_layer.get(edge[1]) == fixed_layer
        ]
        key: Callable[[Edge], Node] = lambda edge: edge[1]
    if not source_edges:
        return []
    source_edges.sort(key=lambda edge: positions[key(edge)])
    mid = len(source_edges) // 2
    if len(source_edges) % 2 == 1:
        return [source_edges[mid]]
    return [source_edges[mid - 1], source_edges[mid]]


def horizontal_compaction(
    node_order: Layers, block_of: dict[Node, Node], min_gap: float
) -> dict[Node, float]:
    block_graph: dict[Node, list[Node]] = defaultdict(list)
    blocks: list[Node] = []
    seen_blocks: set[Node] = set()
    for nodes in node_order.values():
        for node in nodes:
            block = block_of[node]
            if block not in seen_blocks:
                blocks.append(block)
                seen_blocks.add(block)
    constraints: set[tuple[Node, Node]] = set()
    for nodes in node_order.values():
        previous_block: Node | None = None
        for node in nodes:
            block = block_of[node]
            if previous_block is not None and previous_block != block:
                constraints.add((previous_block, block))
            previous_block: Node | None = block
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
            block_y[next_block] = max(block_y[next_block], block_y[block] + min_gap)
            indegree[next_block] -= 1
            if indegree[next_block] == 0:
                queue.append(next_block)
    if visited != len(blocks):
        raise RuntimeError("alignment block constraints contain a cycle")
    return {
        node: block_y[block_of[node]] for nodes in node_order.values() for node in nodes
    }


def align_to_narrowest(
    variants: list[dict[Node, float]], horizontal_directions: list[bool]
) -> list[dict[Node, float]]:
    """Align biased layouts as prescribed by Brandes--Koepf balancing."""
    if not variants:
        return []
    bounds: list[tuple[float, float, float]] = []
    for variant in variants:
        values = list(variant.values())
        lower = min(values, default=0.0)
        upper = max(values, default=0.0)
        bounds.append((lower, upper, upper - lower))
    reference_index = min(range(len(variants)), key=lambda index: bounds[index][2])
    reference_lower, reference_upper, _ = bounds[reference_index]
    aligned: list[dict[Node, float]] = []
    for variant, horizontal_forward, (lower, upper, _) in zip(
        variants, horizontal_directions, bounds
    ):
        if horizontal_forward:
            shift = reference_lower - lower
        else:
            shift = reference_upper - upper
        aligned.append({node: value + shift for node, value in variant.items()})
    return aligned


def balanced_coordinates(variants: list[dict[Node, float]]) -> dict[Node, float]:
    if not variants:
        return {}
    nodes = variants[0].keys()
    return {node: median([variant[node] for variant in variants]) for node in nodes}


class DisjointBlocks:

    def __init__(self, node_order: Layers) -> None:
        self.parent: dict[Node, Node] = {}
        self.layers: dict[Node, set[int]] = {}
        for layer, nodes in node_order.items():
            for node in nodes:
                self.parent[node] = node
                self.layers[node] = {layer}

    def find(self, node: Node) -> Node:
        parent = self.parent[node]
        if parent != node:
            self.parent[node] = self.find(parent)
        return self.parent[node]

    def union(self, first: Node, second: Node) -> bool:
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root == second_root:
            return False
        if self.layers[first_root] & self.layers[second_root]:
            return False
        if len(self.layers[first_root]) < len(self.layers[second_root]):
            first_root, second_root = (second_root, first_root)
        self.parent[second_root] = first_root
        self.layers[first_root].update(self.layers[second_root])
        return True

    def block_of(self) -> dict[Node, Node]:
        return {node: self.find(node) for node in self.parent}
