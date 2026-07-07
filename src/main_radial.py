"""
トーラス階層割当と交差削減のメインスクリプト（Radial版）

1. ランダムなグラフを生成
2. Heuristicで階層割当（Gurobi不要）
3. Radial Siftingで交差削減
4. draw_radial_torus.pyで描画
"""

from layer_assignment.torus_heuristic import torus_heuristic

from crossing_reduction.radial import (
    cartesian_barycenter_heuristic,
    count_radial_crossings,
    radial_sifting_heuristic,
)
from lib.generate_torus_graph import generate_cyclic_graph

from collections import defaultdict

import argparse


def assign_layers_heuristic(V, A):
    """
    Gurobiを使わずに、ヒューリスティック実装で平坦トーラスの階層を割り当てる。

    Returns:
        (y_val, t_val, layer_dict, run_time)
    """
    print("  Heuristicで階層割当を実行中...")
    y_val, t_val, layer_dict, run_time = torus_heuristic(V, A)

    if not y_val:
        print("階層割当に失敗しました。")
        return None

    print(f"  階層割当実行時間: {round(run_time, 5)}秒")

    torus_edges = [(u, v) for (u, v) in A if t_val[(u, v)]]
    normal_edges = [(u, v) for (u, v) in A if not t_val[(u, v)]]

    print(f"\n階層割当結果:")
    print(f"  最大階層: {max(y_val.values())}")
    print(f"  レイヤー数: {len(layer_dict)}")
    print(f"  トーラス辺数: {len(torus_edges)}")
    print(f"  通常辺数: {len(normal_edges)}")
    print(f"  トーラス辺: {torus_edges}")
    print(f"  割当階層: ")
    d = defaultdict(list)
    for k, v in y_val.items():
        d[v].append(k)
    for k, v in sorted(d.items()):
        print(f"    {k}: {v}")

    return y_val, t_val, layer_dict, run_time


def reduce_crossings_radial(
    V, A, layer_dict, t_val, method="sifting", rounds=3, vertical_torus_penalty=0.0
):
    if method == "barycenter":
        print("  Cartesian Barycenterで順序を最適化中...")
        return cartesian_barycenter_heuristic(V, A, layer_dict, t_val)

    print("  Radial Siftingで順序を最適化中...")
    return radial_sifting_heuristic(
        V,
        A,
        layer_dict,
        t_val,
        rounds=rounds,
        vertical_torus_penalty=vertical_torus_penalty,
    )


def main(
    node=None,
    cycle=None,
    prob=None,
    _seed=None,
    method=None,
    rounds=3,
    vertical_torus_penalty=0.0,
):
    n = 10  # ノード数
    num_cycles = 2  # サイクル数
    edge_prob = 0.005  # エッジ確率
    seed = 1  # シード値

    """引数取得"""

    if node is not None:
        n = int(node)
    if cycle is not None:
        num_cycles = int(cycle)
    if prob is not None:
        edge_prob = float(prob)
    if _seed is not None:
        seed = int(_seed)
    if method is None:
        method = "sifting"  # デフォルト: sifting

    """ メイン処理 """

    print("=" * 60)
    print("トーラス階層割当 + Radial交差削減デモ")
    print("=" * 60)

    # 1. ランダムなグラフを生成
    print("\n1. グラフ生成")

    V, A = generate_cyclic_graph(
        n=n, num_cycles=num_cycles, edge_prob=edge_prob, seed=seed
    )

    print(f"  ノード数: {len(V)}")
    print(f"  エッジ数: {len(A)}")
    print(f"  ノード: {V}")
    print(f"  エッジ: {A}")

    # 2. 階層割当（Heuristic）
    print("\n2. 階層割当")

    layer_result = assign_layers_heuristic(V, A)
    if layer_result is None:
        return

    y_val, t_val, layer_dict, run_time = layer_result

    # 3. Radial交差削減
    print("\n3. Radial交差削減")

    order, layer_dict, A, t_val, psi = reduce_crossings_radial(
        V,
        A,
        layer_dict,
        t_val,
        method=method,
        rounds=rounds,
        vertical_torus_penalty=vertical_torus_penalty,
    )

    # 巻き数の統計
    psi_counts = defaultdict(int)
    for e, s in psi.items():
        psi_counts[s] += 1

    print(f"  巻き数の分布:")
    print(f"    ψ = -1 (下側トーラス・緑): {psi_counts[-1]}エッジ")
    print(f"    ψ =  0 (通常エッジ・黒): {psi_counts[0]}エッジ")
    print(f"    ψ = +1 (上側トーラス・青): {psi_counts[1]}エッジ")
    print(f"  交差数: {count_radial_crossings(order, psi, layer_dict, A)}")

    # 交差削減後のグラフ構造を出力
    print(f"\n交差削減後のグラフ構造:")
    print(f"  レイヤー数: {len(layer_dict)}")
    print(f"  各レイヤーのノード順序:")
    for layer_key in sorted(layer_dict.keys()):
        nodes = order.get(layer_key, layer_dict[layer_key])
        print(f"    Layer {layer_key}: {nodes}")

    # エッジの詳細情報
    print(f"\n  エッジの分類:")
    left_right_torus = [(u, v) for (u, v) in A if t_val.get((u, v), False)]
    top_torus = [(u, v) for (u, v) in A if psi.get((u, v), 0) > 0]
    bottom_torus = [(u, v) for (u, v) in A if psi.get((u, v), 0) < 0]
    normal = [
        (u, v)
        for (u, v) in A
        if not t_val.get((u, v), False) and psi.get((u, v), 0) == 0
    ]

    print(f"    左右トーラス（赤）: {len(left_right_torus)}エッジ")
    if left_right_torus:
        print(f"      {left_right_torus}")
    print(f"    上側トーラス（青・ψ=+1）: {len(top_torus)}エッジ")
    if top_torus and len(top_torus) <= 10:
        print(f"      {top_torus}")
    print(f"    下側トーラス（緑・ψ=-1）: {len(bottom_torus)}エッジ")
    if bottom_torus and len(bottom_torus) <= 10:
        print(f"      {bottom_torus}")
    print(f"    通常エッジ（黒・ψ=0）: {len(normal)}エッジ")
    if normal and len(normal) <= 10:
        print(f"      {normal}")

    # 4. 描画
    print("\n4. 描画（draw_radial_torus.py）...")
    print("  グラフを描画します...")
    print(f"  描画色の説明:")
    print(f"    - 赤: 左右のトーラス（最右レイヤー→最左レイヤー）")
    print(f"    - 青: 上側トーラス（ray上端を通過、ψ=+1）")
    print(f"    - 緑: 下側トーラス（ray下端を通過、ψ=-1）")
    print(f"    - 黒: 通常エッジ（ψ=0）")
    print("  ※ 描画ウィンドウを閉じるまでプログラムは待機します。")
    print(f"\n実行時間: {round(run_time, 5)}秒")

    # Radial交差削減で最適化された順序を反映した描画
    from drawing.draw_radial_torus import draw_radial_torus

    draw_radial_torus(
        V=V, A=A, L=layer_dict, order=order, psi=psi, t_val=t_val, draw_dummy_nodes=True
    )

    print("\n" + "=" * 60)
    print("完了！")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=int, help="ノード数")
    parser.add_argument("--cycle", type=int, help="サイクル数")
    parser.add_argument("--prob", type=float, help="エッジ確率")
    parser.add_argument("--seed", type=int, help="シード値")
    parser.add_argument(
        "--method",
        choices=["barycenter", "sifting"],
        default="sifting",
        help="交差削減手法 (barycenter: Cartesian Barycenter, sifting: Radial Sifting, デフォルト: sifting)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Radial Siftingの反復回数 (デフォルト: 3)",
    )
    parser.add_argument(
        "--vertical_torus_penalty",
        type=float,
        default=0.0,
        help="上下トーラス通過数を減らす副目的重み。0なら交差数を増やさない範囲で削減",
    )
    args = parser.parse_args()

    main(
        node=args.node,
        cycle=args.cycle,
        prob=args.prob,
        _seed=args.seed,
        method=args.method,
        rounds=args.rounds,
        vertical_torus_penalty=args.vertical_torus_penalty,
    )
