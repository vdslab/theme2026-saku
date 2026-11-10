"""工程間で受け渡すデータ。入力順と辺の重複を保持する。"""

from dataclasses import dataclass
from typing import Literal

type Node = int | str
type Edge = tuple[Node, Node]
type Layers = dict[int, list[Node]]
type Flags = dict[Edge, bool]
type Weights = dict[Edge, float]
type Winding = dict[Edge, int]
type Positions = dict[Node, tuple[float, float]]
type BalanceMethod = Literal["diff", "diff_square", "qp", "barycenter"]


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class LayerSearchResult:
    layer_count: int | None
    torus_count: int | None
    runtime: float


@dataclass(frozen=True)
class LayerAssignmentResult:
    node_to_layer: dict[Node, int]
    torus_flags: Flags
    runtime: float

    @property
    def layers(self) -> Layers:
        result: Layers = {}
        for node, layer in self.node_to_layer.items():
            result.setdefault(layer, []).append(node)
        return result


@dataclass(frozen=True)
class SubdividedGraph:
    graph: Graph
    layers: Layers
    torus_flags: Flags
    weights: Weights
    original_nodes: tuple[Node, ...]

    @property
    def dummy_nodes(self) -> set[Node]:
        return set(self.graph.nodes) - set(self.original_nodes)


@dataclass(frozen=True)
class CrossingResult:
    order: Layers
    winding_numbers: Winding


@dataclass(frozen=True)
class CoordinateResult:
    positions: Positions
    period: float


@dataclass(frozen=True)
class PipelineResult:
    original_graph: Graph
    search: LayerSearchResult
    assignment: LayerAssignmentResult
    subdivided: SubdividedGraph
    crossing: CrossingResult
    coordinates: CoordinateResult
    crossing_time: float
    coordinate_time: float


@dataclass(frozen=True)
class PipelineConfig:
    balance_method: BalanceMethod = "diff_square"
    rounds: int = 5
    coordinate_method: str = "brandes_koepf"
    coordinate_bend_weight: float = 0.0
    optimize_seams: bool = True
