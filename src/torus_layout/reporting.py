"""既存の結果表示を、計算の実行から分離する。"""

from collections import defaultdict
from .models import PipelineResult, Edge, Layers, Flags, Winding
from .crossing.lib.crossings import count_all_crossings


def count_radial_crossings(
    order: Layers, psi: Winding, layer_dict: Layers, edges: list[Edge]
) -> int:
    return count_all_crossings(order, psi, sorted(layer_dict), edges)


def print_phase_times(
    step1_time: float, step2_time: float, crossing_time: float, coordinate_time: float
) -> None:
    """描画前に各処理フェーズの実行時間をまとめて表示する。"""
    total = step1_time + step2_time + crossing_time + coordinate_time
    print("\n各フェーズの実行時間:")
    print(f"  階層割り当て Step 1（最小トーラス構成探索）: {step1_time:.5f}秒")
    print(f"  階層割り当て Step 2（バランス調整）      : {step2_time:.5f}秒")
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
    for winding in psi.values():
        psi_counts[winding] += 1
    print("  巻き数の分布:")
    print(f"    ψ = -1 (上端→下端): {psi_counts[-1]}エッジ")
    print(f"    ψ =  0 (通常エッジ): {psi_counts[0]}エッジ")
    print(f"    ψ = +1 (下端→上端): {psi_counts[1]}エッジ")
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
    print(f"    下端→上端 (ψ=+1): {len(positive_wrap)}エッジ")
    if positive_wrap and len(positive_wrap) <= 10:
        print(f"      {positive_wrap}")
    print(f"    上端→下端 (ψ=-1): {len(negative_wrap)}エッジ")
    if negative_wrap and len(negative_wrap) <= 10:
        print(f"      {negative_wrap}")
    print(f"    通常辺 (ψ=0): {len(normal)}エッジ")
    if normal and len(normal) <= 10:
        print(f"      {normal}")


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
        result.assignment.runtime,
        result.crossing_time,
        result.coordinate_time,
    )
    print_drawing_summary(
        len(result.original_graph.nodes),
        len(original_edges),
        crossing.order,
        graph.layers,
        edges,
        graph.torus_flags,
        crossing.winding_numbers,
    )
