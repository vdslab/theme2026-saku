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

from crossing_reduction.radial import radial_sifting_heuristic
from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates
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
    parser.add_argument(
        "--func_type",
        choices=["diff", "diff_square", "qp", "barycenter"],
        default="diff_square",
        help="階層割当のバランス手法 (binary_balanceで使用、デフォルト: diff_square)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Radial Siftingの反復回数 (デフォルト: 3)",
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
    seed = None  # シード値
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


def reduce_crossings_radial(V, A, layer_dict, t_val, rounds=3):
    """Radial Siftingでレイヤー内順序とトーラスの巻き数を最適化する。"""
    print("  Radial Siftingで順序を最適化中...")
    return radial_sifting_heuristic(V, A, layer_dict, t_val, rounds=rounds)


def coordinate_assignment(order, layer_dict, A, t_val, psi, original_nodes=None):
    return assign_torus_brandes_koepf_coordinates(
        order=order,
        layer_dict=layer_dict,
        edges=A,
        t_val=t_val,
        psi=psi,
        original_nodes=original_nodes,
    )


def main():
    """引数取得"""
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

    """ メイン処理 """
    # 1. ランダムなグラフを生成
    V, A = generate_graph(n, num_cycles, edge_prob, seed)

    # 2. 階層割当
    print("\n2. 階層割当")
    layer_dict, t_val, run_time = layer_assignment(V, A, func_type)

    # 3. 交差削減
    print("\n3. Radial交差削減")
    order, layer_dict, A, t_val, psi = reduce_crossings_radial(
        V, A, layer_dict, t_val, rounds=rounds
    )

    # 4. 座標割当
    print("\n4. 座標割当（4方向Brandes-Köpf系 + torus smoothing）")
    pos = coordinate_assignment(order, layer_dict, A, t_val, psi, original_nodes=V)

    print("実行時間:", run_time)

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

    print("\n" + "=" * 60)
    print("完了！")
    print("=" * 60)


if __name__ == "__main__":
    main()
