"""
トーラス階層割当と交差削減のメインスクリプト

1. ランダムなグラフを生成
2. torus.pyで階層割当
3. Radial Siftingで交差削減
4. Brandes-Köpf系の座標割当
5. 平坦トーラスの切開図を描画
"""

from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration

from crossing_reduction.radial import (
    count_radial_crossings,
    radial_sifting_global_guard_heuristic,
)
from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates
from drawing.draw_radial_torus import draw_radial_torus
from lib.generate_torus_graph import (
    generate_cyclic_graph,
    generate_watts_strogatz_graph,
)

from collections import defaultdict

import argparse
import time

# CLIから指定されなかった場合に使用する設定値。
# 実行時の初期値はここだけを変更すればよいように、一か所へ集約する。
DEFAULT_NODE_COUNT = 25
DEFAULT_CYCLE_COUNT = 2
DEFAULT_EDGE_PROBABILITY = 0.005
DEFAULT_RANDOM_SEED = 1
DEFAULT_BALANCE_METHOD = "diff_square"
DEFAULT_ROUND_COUNT = 5
DEFAULT_SAVE_PATH = None
DEFAULT_SHOW_DRAWING = True
DEFAULT_DRAW_DUMMY_NODES = False
DEFAULT_TILE_SURROUNDINGS = True
DEFAULT_SURROUNDING_OPACITY = 0.5
DEFAULT_TILE_GAP = 0

BALANCE_METHOD_CHOICES = ("diff", "diff_square", "qp", "barycenter")


def parse_augment():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--node",
        type=int,
        default=DEFAULT_NODE_COUNT,
        help=f"ノード数 (デフォルト: {DEFAULT_NODE_COUNT})",
    )
    parser.add_argument(
        "--cycle",
        type=int,
        default=DEFAULT_CYCLE_COUNT,
        help=f"生成するサイクル数 (デフォルト: {DEFAULT_CYCLE_COUNT})",
    )
    parser.add_argument(
        "--prob",
        type=float,
        default=DEFAULT_EDGE_PROBABILITY,
        help=f"追加辺の生成確率 (デフォルト: {DEFAULT_EDGE_PROBABILITY})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"乱数シード (デフォルト: {DEFAULT_RANDOM_SEED})",
    )
    parser.add_argument(
        "--func_type",
        choices=BALANCE_METHOD_CHOICES,
        default=DEFAULT_BALANCE_METHOD,
        help=("階層割当のバランス手法 " f"(デフォルト: {DEFAULT_BALANCE_METHOD})"),
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_ROUND_COUNT,
        help=f"Radial Siftingの反復回数 (デフォルト: {DEFAULT_ROUND_COUNT})",
    )
    parser.add_argument(
        "--save_path",
        type=str,
        default=DEFAULT_SAVE_PATH,
        help="描画画像の保存先（通常はPDF/SVG、周囲配置時はPNG等のラスター画像）",
    )
    parser.add_argument(
        "--no_show",
        action="store_false",
        dest="show",
        default=DEFAULT_SHOW_DRAWING,
        help="描画画面を表示しない",
    )
    parser.add_argument(
        "--hide_dummy_nodes",
        action="store_false",
        dest="draw_dummy_nodes",
        default=DEFAULT_DRAW_DUMMY_NODES,
        help="ダミーノードを表示しない",
    )
    tile_group = parser.add_mutually_exclusive_group()
    tile_group.add_argument(
        "--tile_surroundings",
        action="store_true",
        help="描画結果の周囲8方向に、半透明の同一画像の一部を配置する（デフォルト）",
    )
    tile_group.add_argument(
        "--no_tile_surroundings",
        action="store_false",
        dest="tile_surroundings",
        help="周囲8方向への画像配置を無効にする",
    )
    parser.set_defaults(tile_surroundings=DEFAULT_TILE_SURROUNDINGS)
    parser.add_argument(
        "--surrounding_opacity",
        type=float,
        default=DEFAULT_SURROUNDING_OPACITY,
        help=f"周囲8枚の不透明度 (デフォルト: {DEFAULT_SURROUNDING_OPACITY})",
    )
    parser.add_argument(
        "--tile_gap",
        type=int,
        default=DEFAULT_TILE_GAP,
        help=f"周囲画像との間隔[pixel] (デフォルト: {DEFAULT_TILE_GAP})",
    )
    args = parser.parse_args()

    return (
        args.node,
        args.cycle,
        args.prob,
        args.seed,
        args.func_type,
        args.rounds,
        args.save_path,
        args.show,
        args.draw_dummy_nodes,
        args.tile_surroundings,
        args.surrounding_opacity,
        args.tile_gap,
    )


def generate_graph(n, num_cycles, edge_prob, seed):
    print("\n1. グラフ生成")

    V, A = generate_cyclic_graph(
        n=n, num_cycles=num_cycles, edge_prob=edge_prob, seed=seed
    )
    # V, A = generate_watts_strogatz_graph(n, 4, 0.8)

    print(f"  ノード数: {len(V)}")
    print(f"  エッジ数: {len(A)}")
    print(f"  ノード: {V}")
    print(f"  エッジ: {A}")

    return V, A


def layer_assignment(V, A, func_type):
    # Binary Search + Balance の2段階アプローチ
    optimal_L, min_torus_count, search_time = find_minimum_torus_configuration(V, A)

    if optimal_L is None:
        print("Binary Search失敗: 最適なレイヤー数が見つかりませんでした。")
        return

    # balanceで階層割当を完成
    y_val, t_val, layer_dict, balance_time = balance_layer_assignment(
        V, A, min_torus_count, optimal_L, func_type
    )

    L = optimal_L
    if not y_val:
        print("階層割当に失敗しました。")
        return

    # トーラス辺の情報
    torus_edges = [(u, v) for (u, v) in A if t_val[(u, v)]]
    normal_edges = [(u, v) for (u, v) in A if not t_val[(u, v)]]

    print(f"\n階層割当結果:")
    print(f"  最大階層: {max(y_val.values())}")
    print(f"  レイヤー数初期値: {L}")
    print(f"  トーラス辺数: {len(torus_edges)}")
    print(f"  通常辺数: {len(normal_edges)}")
    print(f"  トーラス辺: {torus_edges}")
    print(f"  割当階層: ")
    d = defaultdict(list)
    for k, v in y_val.items():
        d[v].append(k)
    for k, v in sorted(d.items()):
        print(f"    {k}: {v}")

    return layer_dict, t_val, search_time, balance_time


def reduce_crossings_radial(V, A, layer_dict, t_val, rounds):
    """交差削減結果と実行時間を返す。"""
    started_at = time.perf_counter()
    result = radial_sifting_global_guard_heuristic(
        V, A, layer_dict, t_val, rounds=rounds
    )
    run_time = time.perf_counter() - started_at
    return (*result, run_time)


def coordinate_assignment(order, layer_dict, A, t_val, psi, original_nodes):
    """座標割り当て結果と実行時間を返す。"""
    started_at = time.perf_counter()
    pos = assign_torus_brandes_koepf_coordinates(
        order=order,
        layer_dict=layer_dict,
        edges=A,
        t_val=t_val,
        psi=psi,
        original_nodes=original_nodes,
    )
    run_time = time.perf_counter() - started_at
    return pos, run_time


def _print_phase_times(step1_time, step2_time, crossing_time, coordinate_time):
    """描画前に各処理フェーズの実行時間をまとめて表示する。"""
    total = step1_time + step2_time + crossing_time + coordinate_time
    print("\n各フェーズの実行時間:")
    print(f"  階層割り当て Step 1（最小トーラス構成探索）: {step1_time:.5f}秒")
    print(f"  階層割り当て Step 2（バランス調整）      : {step2_time:.5f}秒")
    print(f"  交差削減                                  : {crossing_time:.5f}秒")
    print(f"  座標割り当て                              : {coordinate_time:.5f}秒")
    print(f"  合計                                      : {total:.5f}秒")


def _print_drawing_summary(
    node_count, edge_count, order, layer_dict, edges, t_val, psi
):
    """描画対象グラフと交差削減結果の概要を表示する。"""
    crossing_count = count_radial_crossings(order, psi, layer_dict, edges)
    horizontal_torus_count = sum(1 for edge in edges if t_val.get(edge, False))
    vertical_torus_count = sum(1 for edge in edges if psi.get(edge, 0) != 0)

    print("\n描画結果の情報:")
    print(f"  ノード数        : {node_count}")
    print(f"  エッジ数        : {edge_count}")
    print(f"  交差数          : {crossing_count}")
    print(f"  左右トーラス数  : {horizontal_torus_count}")
    print(f"  上下トーラス数  : {vertical_torus_count}")


def _print_crossing_details(order, layer_dict, edges, t_val, psi):
    """交差削減後の交差数、巻き数、辺分類を表示する。"""
    psi_counts = defaultdict(int)
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


def main(
    node,
    cycle,
    prob,
    seed,
    rounds,
    func_type,
    save_path,
    show,
    draw_dummy_nodes,
    tile_surroundings=DEFAULT_TILE_SURROUNDINGS,
    surrounding_opacity=DEFAULT_SURROUNDING_OPACITY,
    tile_gap=DEFAULT_TILE_GAP,
):
    if save_path is not None and seed is None:
        raise ValueError("再現可能な図を保存するにはseedを指定してください。")

    """ メイン処理 """
    # 1. ランダムなグラフを生成
    V, A = generate_graph(node, cycle, prob, seed)
    original_node_count = len(V)
    original_edge_count = len(A)

    # 2. 階層割当
    print("\n2. 階層割当")
    layer_result = layer_assignment(V, A, func_type)
    if layer_result is None:
        return None
    layer_dict, t_val, step1_time, step2_time = layer_result

    # 3. 交差削減
    print("\n3. Radial交差削減")
    order, layer_dict, A, t_val, psi, crossing_time = reduce_crossings_radial(
        V, A, layer_dict, t_val, rounds=rounds
    )
    _print_crossing_details(order, layer_dict, A, t_val, psi)

    # 4. 座標割当
    print("\n4. 座標割当（4方向Brandes-Köpf系 + torus smoothing）")
    pos, coordinate_time = coordinate_assignment(
        order, layer_dict, A, t_val, psi, original_nodes=V
    )

    _print_phase_times(step1_time, step2_time, crossing_time, coordinate_time)
    _print_drawing_summary(
        original_node_count,
        original_edge_count,
        order,
        layer_dict,
        A,
        t_val,
        psi,
    )

    # 5. 描画
    print("\n5. 描画（draw_radial_torus.py）...")
    draw_radial_torus(
        V=V,
        A=A,
        L=layer_dict,
        t_val=t_val,
        order=order,
        psi=psi,
        pos=pos,
        save_path=save_path,
        show=show,
        draw_dummy_nodes=draw_dummy_nodes,
        tile_surroundings=tile_surroundings,
        surrounding_opacity=surrounding_opacity,
        tile_gap=tile_gap,
    )


if __name__ == "__main__":
    (
        n,
        num_cycles,
        edge_prob,
        seed,
        func_type,
        rounds,
        save_path,
        show,
        draw_dummy_nodes,
        tile_surroundings,
        surrounding_opacity,
        tile_gap,
    ) = parse_augment()
    main(
        node=n,
        cycle=num_cycles,
        prob=edge_prob,
        seed=seed,
        rounds=rounds,
        func_type=func_type,
        save_path=save_path,
        show=show,
        draw_dummy_nodes=draw_dummy_nodes,
        tile_surroundings=tile_surroundings,
        surrounding_opacity=surrounding_opacity,
        tile_gap=tile_gap,
    )
