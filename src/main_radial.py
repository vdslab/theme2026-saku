"""
トーラス階層割当と交差削減のメインスクリプト（Radial版）

1. ランダムなグラフを生成
2. Binary Search + Balanceで階層割当
3. Radial Siftingで交差削減
4. Brandes-Köpf系の座標割当
5. draw_radial_torus.pyで描画
"""

import time

from crossing_reduction.radial import (
    cartesian_barycenter_heuristic,
    count_radial_crossings,
    radial_sifting_heuristic,
)
from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates
from drawing.draw_radial_torus import draw_radial_torus
from lib.generate_torus_graph import generate_cyclic_graph

from collections import defaultdict

import argparse


def assign_layers_binary_balance(V, A, func_type="diff_square"):
    """
    Binary Search + Balance の2段階アプローチで平坦トーラスの階層を割り当てる。

    Returns:
        (y_val, t_val, layer_dict, run_time)
    """
    from layer_assignment.torus_balance import balance_layer_assignment
    from layer_assignment.torus_binary_search import find_minimum_torus_configuration

    print("  Binary Searchで最小トーラス構成を探索中...")
    optimal_L, min_torus_count, search_time = find_minimum_torus_configuration(V, A)

    if optimal_L is None:
        print("Binary Search失敗: 最適なレイヤー数が見つかりませんでした。")
        return None

    print(f"  {func_type}手法でバランスを取った階層割当を実行中...")
    y_val, t_val, layer_dict, balance_time = balance_layer_assignment(
        V, A, min_torus_count, optimal_L, func_type
    )
    run_time = search_time + balance_time

    if not y_val:
        print("階層割当に失敗しました。")
        return None

    print(f"  階層割当実行時間: {round(run_time, 5)}秒")

    torus_edges = [(u, v) for (u, v) in A if t_val[(u, v)]]
    normal_edges = [(u, v) for (u, v) in A if not t_val[(u, v)]]

    print(f"\n階層割当結果:")
    print(f"  最大階層: {max(y_val.values())}")
    print(f"  レイヤー数初期値: {optimal_L}")
    print(f"  レイヤー数: {len(layer_dict)}")
    print(f"  最小トーラス辺数: {min_torus_count}")
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


def reduce_crossings_radial(V, A, layer_dict, t_val, method="sifting", rounds=3):
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
    )


def assign_coordinates_radial(
    order, layer_dict, edges, t_val, psi, original_nodes=None
):
    """
    Radial交差削減後の順序を保ったまま、平坦トーラス用の座標を割り当てる。

    Returns:
        dict[node, (x, y)]
    """
    print("  4方向Brandes-Köpf系 + torus smoothingで座標を割当中...")
    return assign_torus_brandes_koepf_coordinates(
        order=order,
        layer_dict=layer_dict,
        edges=edges,
        t_val=t_val,
        psi=psi,
        original_nodes=original_nodes,
    )


def main(
    node=None,
    cycle=None,
    prob=None,
    _seed=None,
    method=None,
    rounds=3,
    func_type="diff_square",
    save_path=None,
    show=True,
    draw_dummy_nodes=True,
):
    n = 20  # ノード数
    num_cycles = 2  # サイクル数
    edge_prob = 0.005  # エッジ確率
    seed = None  # シード値

    """引数取得"""

    if node is not None:
        n = int(node)
    if cycle is not None:
        num_cycles = int(cycle)
    if prob is not None:
        edge_prob = float(prob)
    if _seed is not None:
        seed = int(_seed)
    if func_type is None:
        func_type = "diff_square"  # デフォルト: diff_square
    if method is None:
        method = "sifting"  # デフォルト: sifting
    if save_path is not None and seed is None:
        raise ValueError("再現可能な図を保存するには --seed を指定してください。")

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

    # 2. 階層割当（Binary Search + Balance）
    print("\n2. 階層割当")

    layer_result = assign_layers_binary_balance(V, A, func_type=func_type)
    if layer_result is None:
        return

    y_val, t_val, layer_dict, run_time = layer_result

    # 3. Radial交差削減
    print("\n3. Radial交差削減")

    t = time.time()

    order, layer_dict, A, t_val, psi = reduce_crossings_radial(
        V,
        A,
        layer_dict,
        t_val,
        method=method,
        rounds=rounds,
    )

    # 巻き数の統計
    psi_counts = defaultdict(int)
    for e, s in psi.items():
        psi_counts[s] += 1

    print(f"  巻き数の分布:")
    print(f"    ψ = -1 (上端→下端): {psi_counts[-1]}エッジ")
    print(f"    ψ =  0 (通常エッジ): {psi_counts[0]}エッジ")
    print(f"    ψ = +1 (下端→上端): {psi_counts[1]}エッジ")
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
    positive_wrap = [(u, v) for (u, v) in A if psi.get((u, v), 0) > 0]
    negative_wrap = [(u, v) for (u, v) in A if psi.get((u, v), 0) < 0]
    normal = [
        (u, v)
        for (u, v) in A
        if not t_val.get((u, v), False) and psi.get((u, v), 0) == 0
    ]

    print(f"    左右トーラス（橙破線）: {len(left_right_torus)}エッジ")
    if left_right_torus:
        print(f"      {left_right_torus}")
    print(f"    下端→上端（青・ψ=+1）: {len(positive_wrap)}エッジ")
    if positive_wrap and len(positive_wrap) <= 10:
        print(f"      {positive_wrap}")
    print(f"    上端→下端（紫・ψ=-1）: {len(negative_wrap)}エッジ")
    if negative_wrap and len(negative_wrap) <= 10:
        print(f"      {negative_wrap}")
    print(f"    通常エッジ（濃灰実線・ψ=0）: {len(normal)}エッジ")
    if normal and len(normal) <= 10:
        print(f"      {normal}")

    print(f"    交差削減実行時間 : {time.time() - t}")

    # 4. 座標割当
    print("\n4. 座標割当")
    pos = assign_coordinates_radial(
        order, layer_dict, A, t_val, psi, original_nodes=V
    )

    # 5. 描画
    print("\n5. 描画（draw_radial_torus.py）...")
    print("  グラフを描画します...")
    print(f"  描画色の説明:")
    print(f"    - 橙破線: 左右のトーラス（最右レイヤー→最左レイヤー）")
    print(f"    - 青一点鎖線: 下端→上端（ψ=+1）")
    print(f"    - 紫点線: 上端→下端（ψ=-1）")
    print(f"    - 濃灰実線: 通常エッジ（ψ=0）")
    if show:
        print("  ※ 描画ウィンドウを閉じるまでプログラムは待機します。")
    if save_path:
        print(f"  保存先: {save_path}")
    if not show:
        print("  show=False のため描画ウィンドウは表示しません。")
    print(f"\n実行時間: {round(run_time, 5)}秒")

    draw_radial_torus(
        V=V,
        A=A,
        L=layer_dict,
        order=order,
        psi=psi,
        t_val=t_val,
        pos=pos,
        save_path=save_path,
        show=show,
        draw_dummy_nodes=draw_dummy_nodes,
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
        help="交差削減手法 (barycenter: Cartesian Barycenter, sifting: Radial Sifting, デフォルト: sifting)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Radial Siftingの反復回数 (デフォルト: 3)",
    )
    parser.add_argument(
        "--func_type",
        choices=["diff", "diff_square", "qp", "barycenter"],
        help="階層割当のバランス手法 (デフォルト: diff_square)",
    )
    parser.add_argument(
        "--save_path", type=str, help="描画画像の保存先（論文用はPDF/SVG推奨）"
    )
    parser.add_argument(
        "--no_show",
        action="store_true",
        help="描画ウィンドウを表示しない",
    )
    parser.add_argument(
        "--hide_dummy_nodes",
        action="store_true",
        help="ダミーノードを表示しない",
    )
    args = parser.parse_args()

    main(
        node=args.node,
        cycle=args.cycle,
        prob=args.prob,
        _seed=args.seed,
        method=args.method,
        rounds=args.rounds,
        func_type=args.func_type,
        save_path=args.save_path,
        show=not args.no_show,
        draw_dummy_nodes=not args.hide_dummy_nodes,
    )
