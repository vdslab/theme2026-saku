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
    radial_sifting_heuristic,
    get_default_round_count,
)
from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates
from drawing.draw_radial_torus import draw_radial_torus
from lib.generate_torus_graph import generate_cyclic_graph

from collections import defaultdict

import argparse
import time


def parse_augment():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=int)
    parser.add_argument("--cycle", type=int)
    parser.add_argument("--prob", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--func_type",
        choices=["diff", "diff_square", "qp", "barycenter"],
        default="barycenter",
        help="階層割当のバランス手法 (binary_balanceで使用、デフォルト: diff_square)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=get_default_round_count(),
        help=f"Radial Siftingの反復回数 (デフォルト: {get_default_round_count()})",
    )
    parser.add_argument("--save_path", type=str, help="描画画像の保存先（PDF/SVG推奨）")
    parser.add_argument("--no_show", action="store_true", help="描画画面を表示しない")
    parser.add_argument(
        "--hide_dummy_nodes", action="store_true", help="ダミーノードを表示しない"
    )
    args = parser.parse_args()

    # 初期値
    n = 25  # ノード数
    num_cycles = 2  # サイクル数
    edge_prob = 0.005  # エッジ確率
    seed = 1  # シード値
    func_type = "diff_square"

    if args.node is not None:
        n = int(args.node)
    if args.cycle is not None:
        num_cycles = int(args.cycle)
    if args.prob is not None:
        edge_prob = float(args.prob)
    if args.seed is not None:
        seed = int(args.seed)
    if args.func_type is not None:
        func_type = args.func_type

    return (
        n,
        num_cycles,
        edge_prob,
        seed,
        func_type,
        args.rounds,
        args.save_path,
        not args.no_show,
        not args.hide_dummy_nodes,
    )


def generate_graph(n, num_cycles, edge_prob, seed):
    print("\n1. グラフ生成")

    V, A = generate_cyclic_graph(
        n=n, num_cycles=num_cycles, edge_prob=edge_prob, seed=seed
    )

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


def reduce_crossings_radial(V, A, layer_dict, t_val, rounds=3):
    """交差削減結果と実行時間を返す。"""
    started_at = time.perf_counter()
    result = radial_sifting_heuristic(V, A, layer_dict, t_val, rounds=rounds)
    run_time = time.perf_counter() - started_at
    return (*result, run_time)


def coordinate_assignment(order, layer_dict, A, t_val, psi, original_nodes=None):
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
    node=None,
    cycle=None,
    prob=None,
    seed=None,
    rounds=get_default_round_count(),
    func_type="diff_square",
    save_path=None,
    show=True,
    draw_dummy_nodes=True,
):
    """グラフ生成から平坦トーラス描画までの処理を実行する。"""
    n = 25 if node is None else int(node)
    num_cycles = 2 if cycle is None else int(cycle)
    edge_prob = 0.005 if prob is None else float(prob)
    seed = None if seed is None else int(seed)
    rounds = int(rounds)
    if func_type is None:
        func_type = "diff_square"

    if save_path is not None and seed is None:
        raise ValueError("再現可能な図を保存するにはseedを指定してください。")

    """ メイン処理 """
    # 1. ランダムなグラフを生成
    V, A = generate_graph(n, num_cycles, edge_prob, seed)
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
    )
