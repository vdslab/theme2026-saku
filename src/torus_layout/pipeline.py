"""現在の工程順を組み立てる。生成器、表示、画像出力には依存しない。"""

from time import perf_counter
from warnings import warn
from .models import Graph, PipelineConfig, PipelineResult
from .layering import assign_layers
from .subdivision import insert_dummy_nodes
from .crossing import reduce_crossings
from .crossing.seam import seam_score
from .coordinates import assign_coordinates
from .coordinates.blocks import UnsplitBlockOrderError


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
    prioritize_internal_seams = config.coordinate_method == "brandes_koepf_blocks_unsplit"
    crossing = reduce_crossings(
        subdivided, rounds=config.rounds, optimize_seams=config.optimize_seams,
        unwind=config.unwind_levels, sifting_method=config.sifting_method, algo2=config.algo2,
        prioritize_internal_seams=prioritize_internal_seams, seam_method=config.seam_method,
    )
    crossing_time = perf_counter() - started

    started = perf_counter()
    method_used = config.seam_method if config.unwind_levels and config.optimize_seams else None
    try:
        coordinates = assign_coordinates(
            subdivided, crossing, method=config.coordinate_method,
            bend_weight=config.coordinate_bend_weight,
        )
        coordinate_time = perf_counter() - started
    except UnsplitBlockOrderError as error:
        if method_used != "joint":
            raise
        coordinate_time = perf_counter() - started
        started = perf_counter()
        crossing = reduce_crossings(
            subdivided, rounds=config.rounds, sifting_method=config.sifting_method, algo2=config.algo2,
            prioritize_internal_seams=True, unwind=True, optimize_seams=True, seam_method="legacy",
        )
        if seam_score(subdivided, crossing, True)[0] != 0:
            raise error
        crossing_time += perf_counter() - started
        started = perf_counter()
        coordinates = assign_coordinates(
            subdivided, crossing, method=config.coordinate_method,
            bend_weight=config.coordinate_bend_weight,
        )
        coordinate_time += perf_counter() - started
        method_used = "legacy"
        warn(
            "同時境界最適化の切れ目では分割なしBKの層内順序制約が循環したため、"
            "ダミー同士の境界通過が0本になる従来方式を適用しました。",
            stacklevel=2,
        )
    return PipelineResult(
        graph,
        search,
        assignment,
        subdivided,
        crossing,
        coordinates,
        crossing_time,
        coordinate_time,
        balance_time=balance_time, seam_method_used=method_used,
        subdivision_time=subdivision_time,
    )
