"""
トーラス階層割当と交差削減のメインスクリプト

1. ランダムなグラフを生成
2. torus.pyで階層割当
3. minimize_crossings.pyで交差削減
4. draw_torus.pyで描画
"""

from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration

from crossing_reduction.radial import radial_sifting_heuristic
from drawing.draw_radial_torus import draw_radial_torus
from lib.generate_torus_graph import generate_cyclic_graph

from collections import defaultdict

import argparse


def parse_augment():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=int)
    parser.add_argument("--cycle", type=int)
    parser.add_argument("--prob", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--l", type=int)
    parser.add_argument(
        "--func_type",
        choices=["diff", "diff_square", "qp", "barycenter"],
        default="diff_square",
        help="階層割当のバランス手法 (binary_balanceで使用、デフォルト: diff_square)",
    )
    args = parser.parse_args()

    # 初期値
    n = 50  # ノード数
    num_cycles = 2  # サイクル数
    edge_prob = 0.005  # エッジ確率
    seed = 10  # シード値
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

    return n, num_cycles, edge_prob, seed, func_type


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
    print(f"  {func_type}手法でバランスを取った階層割当を実行中...")
    y_val, t_val, layer_dict, balance_time = balance_layer_assignment(
        V, A, min_torus_count, optimal_L, func_type
    )

    L = optimal_L
    run_time = search_time + balance_time

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

    return layer_dict, t_val, run_time


def minimize_crossing(V, A, layer_dict, t_val):
    return radial_sifting_heuristic(V, A, layer_dict, t_val, rounds=3)


def coordinate_assignment():
    pass


def main():
    """引数取得"""
    n, num_cycles, edge_prob, seed, func_type = parse_augment()

    """ メイン処理 """
    # 1. ランダムなグラフを生成
    V, A = generate_graph(n, num_cycles, edge_prob, seed)

    # 2. 階層割当
    print("\n2. 階層割当")
    layer_dict, t_val, run_time = layer_assignment(V, A, func_type)

    # 3. 交差削減
    print("\n3. 交差削減")
    order, layer_dict, A, t_val, psi = minimize_crossing(V, A, layer_dict, t_val)

    print("実行時間:", run_time)

    # 4. 描画
    print("\n4. 描画（draw_radial_torus.py）...")
    draw_radial_torus(
        V=V,
        A=A,
        L=layer_dict,
        t_val=t_val,
        order=order,
        psi=psi,
        draw_dummy_nodes=True,
    )

    print("\n" + "=" * 60)
    print("完了！")
    print("=" * 60)


if __name__ == "__main__":
    main()
