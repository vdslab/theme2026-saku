"""既存の結果表示を、計算の実行から分離する。"""

from collections import defaultdict
from .models import PipelineResult, Edge, Layers, Flags, Winding, SubdividedGraph
from .crossing.lib.crossings import count_all_crossings


def count_radial_crossings(
    order: Layers, psi: Winding, layer_dict: Layers, edges: list[Edge]
) -> int:
    return count_all_crossings(order, psi, sorted(layer_dict), edges)


def print_phase_times(
    step1_time: float, step2_time: float, crossing_time: float, coordinate_time: float,
    *, subdivision_time: float = 0.0,
) -> None:
    """描画前に各処理フェーズの実行時間をまとめて表示する。"""
    total = step1_time + step2_time + subdivision_time + crossing_time + coordinate_time
    print("\n各フェーズの壁時計時間:")
    print(f"  階層割り当て Step 1（最小トーラス構成探索）: {step1_time:.5f}秒")
    print(f"  階層割り当て Step 2（バランス調整）      : {step2_time:.5f}秒")
    print(f"  ダミー挿入                                : {subdivision_time:.5f}秒")
    print(f"  交差削減                                  : {crossing_time:.5f}秒")
    print(f"  座標割り当て                              : {coordinate_time:.5f}秒")
    print(f"  合計                                      : {total:.5f}秒")


def print_drawing_summary(
    node_count: int,
    edge_count: int,
    order: Layers,
    layer_dict: Layers,
    edges: list[Edge],
    t_val: Flags,
    psi: Winding,
) -> None:
    """描画対象グラフと交差削減結果の概要を表示する。"""
    crossing_count = count_radial_crossings(order, psi, layer_dict, edges)
    horizontal_torus_count = sum((1 for edge in edges if t_val.get(edge, False)))
    vertical_torus_count = sum((1 for edge in edges if psi.get(edge, 0) != 0))
    print("\n描画結果の情報:")
    print(f"  ノード数        : {node_count}")
    print(f"  エッジ数        : {edge_count}")
    print(f"  交差数          : {crossing_count}")
    print(f"  左右トーラス数  : {horizontal_torus_count}")
    print(f"  上下トーラス数  : {vertical_torus_count}")


def print_crossing_details(
    order: Layers, layer_dict: Layers, edges: list[Edge], t_val: Flags, psi: Winding
) -> None:
    """交差削減後の交差数、巻き数、辺分類を表示する。"""
    psi_counts: dict[int, int] = defaultdict(int)
    for edge in edges:
        psi_counts[psi.get(edge, 0)] += 1
    print("  巻き数の分布:")
    for winding, count in sorted(psi_counts.items()):
        label = f"{winding:+d}" if winding else "0"
        print(f"    ψ = {label}: {count}線分")
    print(f"  交差数: {count_radial_crossings(order, psi, layer_dict, edges)}")
    left_right_torus = [edge for edge in edges if t_val.get(edge, False)]
    positive_wrap = [edge for edge in edges if psi.get(edge, 0) > 0]
    negative_wrap = [edge for edge in edges if psi.get(edge, 0) < 0]
    normal = [
        edge for edge in edges if not t_val.get(edge, False) and psi.get(edge, 0) == 0
    ]
    print("\n  エッジの分類:")
    print(f"    左右トーラス: {len(left_right_torus)}エッジ")
    if left_right_torus:
        print(f"      {left_right_torus}")
    print(f"    下端→上端 (ψ>0): {len(positive_wrap)}線分")
    if positive_wrap and len(positive_wrap) <= 10:
        print(f"      {positive_wrap}")
    print(f"    上端→下端 (ψ<0): {len(negative_wrap)}線分")
    if negative_wrap and len(negative_wrap) <= 10:
        print(f"      {negative_wrap}")
    print(f"    通常辺 (ψ=0): {len(normal)}エッジ")
    if normal and len(normal) <= 10:
        print(f"      {normal}")


def boundary_metrics(graph: SubdividedGraph, winding: Winding) -> dict[str, int]:
    metrics = {}
    for axis in ("x", "y"):
        offsets = graph.torus_flags if axis == "x" else winding
        events = [abs(offsets.get(edge, 0)) for edge in graph.graph.edges]
        metrics[f"{axis}_seam_segments"] = sum(value > 0 for value in events)
        metrics[f"{axis}_seam_events"] = sum(events)
        if graph.segment_counts or not events:
            start = count = 0
            for size in graph.segment_counts:
                count += any(events[start : start + size])
                start += size
            metrics[f"{axis}_seam_edges"] = count
    return metrics


def report_pipeline(result: PipelineResult) -> None:
    """現在の階層・交差・計測の情報を標準出力へ表示する。"""
    ranks = result.assignment.node_to_layer
    flags = result.assignment.torus_flags
    original_edges = result.original_graph.edges
    wraps = [edge for edge in original_edges if flags[edge]]
    normal = [edge for edge in original_edges if not flags[edge]]
    print("\n階層割当結果:")
    print(f"  最大階層: {max(ranks.values())}")
    print(f"  レイヤー数初期値: {result.search.layer_count}")
    print(f"  トーラス辺数: {len(wraps)}")
    print(f"  通常辺数: {len(normal)}")
    print(f"  トーラス辺: {wraps}")
    print("  割当階層: ")
    for layer, nodes in sorted(result.assignment.layers.items()):
        print(f"    {layer}: {nodes}")
    graph = result.subdivided
    crossing = result.crossing
    edges = list(graph.graph.edges)
    print_crossing_details(
        crossing.order, graph.layers, edges, graph.torus_flags, crossing.winding_numbers
    )
    print_phase_times(
        result.search.runtime,
        result.balance_time,
        result.crossing_time,
        result.coordinate_time,
        subdivision_time=result.subdivision_time,
    )
    print(f"  層数探索の求解時間（内訳）: {result.search.solver_time:.5f}秒")
    if result.assignment.solver_time is not None:
        print(f"  層調整の求解時間（内訳）: {result.assignment.solver_time:.5f}秒")
    if result.assignment.solver_status is not None:
        print(f"  層調整のソルバーステータス: {result.assignment.solver_status}")
    print(f"  分割後: {len(edges)}線分、最大層幅 {max(map(len, graph.layers.values()))}")
    metrics = boundary_metrics(graph, crossing.winding_numbers)
    for axis, label in (("x", "左右"), ("y", "上下")):
        print(f"  {label}境界: {metrics.get(f'{axis}_seam_edges', '不明')}元辺、"
              f"{metrics[f'{axis}_seam_segments']}線分、{metrics[f'{axis}_seam_events']}通過")
    print_drawing_summary(
        len(result.original_graph.nodes),
        len(original_edges),
        crossing.order,
        graph.layers,
        edges,
        graph.torus_flags,
        crossing.winding_numbers,
    )
