"""現在の工程順を組み立てる。生成器、表示、画像出力には依存しない。"""

from time import perf_counter
from .models import Graph, PipelineConfig, PipelineResult
from .layering import assign_layers
from .subdivision import insert_dummy_nodes
from .crossing import reduce_crossings
from .coordinates import assign_coordinates


def run_pipeline(
    graph: Graph, config: PipelineConfig | None = None
) -> PipelineResult | None:
    """既存の工程を実行し、階層割当の失敗時は元と同じくNoneを返す。"""
    config = PipelineConfig() if config is None else config
    started = perf_counter()
    assigned = assign_layers(graph, config.balance_method)
    if assigned is None:
        return None
    search, assignment = assigned
    balance_time = perf_counter() - started - search.runtime

    started = perf_counter()
    subdivided = insert_dummy_nodes(graph, assignment)
    subdivision_time = perf_counter() - started

    started = perf_counter()
    crossing = reduce_crossings(
        subdivided, rounds=config.rounds, optimize_seams=config.optimize_seams,
        unwind=config.unwind_levels, sifting_method=config.sifting_method, algo2=config.algo2,
    )
    crossing_time = perf_counter() - started

    started = perf_counter()
    coordinates = assign_coordinates(
        subdivided, crossing, method=config.coordinate_method,
        bend_weight=config.coordinate_bend_weight,
    )
    coordinate_time = perf_counter() - started
    return PipelineResult(
        graph,
        search,
        assignment,
        subdivided,
        crossing,
        coordinates,
        crossing_time,
        coordinate_time,
        balance_time=balance_time,
        subdivision_time=subdivision_time,
    )
