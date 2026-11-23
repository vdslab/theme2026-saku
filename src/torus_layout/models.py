"""工程間で受け渡すデータ。入力順と辺の重複を保持する。"""

from . import constants

from dataclasses import dataclass, field
from typing import Literal

type Node = int | str
type Edge = tuple[Node, Node]
type Layers = dict[int, list[Node]]
type Flags = dict[Edge, bool]
type Weights = dict[Edge, float]
type Winding = dict[Edge, int]
type Positions = dict[Node, tuple[float, float]]
type BalanceMethod = Literal["diff", "diff_square", "qp", "barycenter"]
type SiftingMethod = Literal["radial", "shortest", "parting"]


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class LayerSearchResult:
    layer_count: int | None
    torus_count: int | None
    runtime: float
    solver_time: float = 0.0
    solver_status: int | None = None


@dataclass(frozen=True)
class LayerAssignmentResult:
    node_to_layer: dict[Node, int]
    torus_flags: Flags
    runtime: float
    solver_status: int | None = field(default=None, compare=False)
    solver_time: float | None = field(default=None, compare=False)

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
    segment_counts: tuple[int, ...] = field(default=(), compare=False, repr=False)

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
    balance_time: float = 0.0
    subdivision_time: float = 0.0


@dataclass(frozen=True)
class PipelineConfig:
    balance_method: BalanceMethod = constants.DEFAULT_BALANCE_METHOD
    rounds: int = constants.DEFAULT_ROUNDS
    coordinate_method: str = constants.DEFAULT_COORDINATE_METHOD
    coordinate_bend_weight: float = constants.DEFAULT_BEND_WEIGHT
    optimize_seams: bool = constants.DEFAULT_OPTIMIZE_SEAMS
    unwind_levels: bool = constants.DEFAULT_UNWIND_LEVELS
    sifting_method: SiftingMethod = constants.DEFAULT_SIFTING_METHOD
