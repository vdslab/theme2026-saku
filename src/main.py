"""
トーラス階層割当と交差削減のメインスクリプト

1. ランダムなグラフを生成
2. torus.pyで階層割当
3. minimize_crossings.pyで交差削減
4. draw_torus.pyで描画
"""

from layer_assignment.torus_iqp import torus_iqp
from layer_assignment.torus import torus
from layer_assignment.torus_ilp import torus_ilp
from layer_assignment.torus_heuristic import torus_heuristic
from layer_assignment.torus_two_stage import torus_two_stage_with_diameter
from layer_assignment.torus_minimize_torus_edge import torus_minimize_torus_edge
from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration

from crossing_reduction.minimize_crossings_ilp import minimize_crossings_ilp
from crossing_reduction.minimize_crossings_heuristic import minimize_crossings_heuristic
from drawing.draw_torus import draw_torus
from lib.generate_torus_graph import generate_cyclic_graph

from layer_length.estimate_layer_count_via_fas import estimate_layer_count_via_fas
from layer_length.estimate_max_cycle_rm_dfs import estimate_max_cycle_rm_dfs
from layer_length.graph_diameter import graph_diameter
from layer_length.longest_cycle_length import longest_cycle_length
from layer_length.longest_path_scc_dag import longest_path_scc_dag
from layer_length.scc_node_count import scc_node_count

from collections import defaultdict

import argparse


def assign_layer_length_func(layer, l, V, A):
    """
    階層数取得の関数の割り当て

    Args:
        layer: 使用する階層数取得法
        l: ユーザー指定の階層数
        V: ノードのリスト list[int]
        A: エッジのリスト [(u, v), ...]

    Returns:
        estimated_layers: 推奨される階層数 (int)
    """

    if l != None:
        return l

    if layer == None:
        layer = "cycle_length"

    d = {
        # "fas": estimate_layer_count_via_fas,
        # "rand": estimate_max_cycle_rm_dfs,
        "diameter": graph_diameter,
        "cycle_length": longest_cycle_length,
        # "scc_dag": longest_path_scc_dag, # 非推奨
        # "scc_node": scc_node_count, # 非推奨
    }

    return d[layer](V, A)


def main(
    node=None,
    cycle=None,
    prob=None,
    _seed=None,
    layer=None,
    assigner="ilp",
    l=None,
    func_type=None,
):
    n = 50  # ノード数
    num_cycles = 2  # サイクル数
    edge_prob = 0.005  # エッジ確率
    seed = 10  # シード値

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
        func_type = "diff_square"  # デフォルト値

    """ メイン処理 """

    print("=" * 60)
    print("トーラス階層割当 + 交差削減デモ")
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

    # 2. 階層割当
    print("\n2. 階層割当")

    if assigner == "binary_balance":
        # Binary Search + Balance の2段階アプローチ
        print(f"  Binary Searchでトーラス辺数とレイヤー数を探索中...")
        optimal_L, min_torus_count, search_time = find_minimum_torus_configuration(V, A)

        if optimal_L is None:
            print("Binary Search失敗: 最適なレイヤー数が見つかりませんでした。")
            return

        print(f"  最適レイヤー数: {optimal_L}, 最小トーラス辺数: {min_torus_count}")
        print(f"  Binary Search実行時間: {round(search_time, 5)}秒")

        # balanceで階層割当を完成
        print(f"  {func_type}手法でバランスを取った階層割当を実行中...")
        y_val, t_val, layer_dict, balance_time = balance_layer_assignment(
            V, A, min_torus_count, optimal_L, func_type
        )

        L = optimal_L
        run_time = search_time + balance_time
    else:
        L = assign_layer_length_func(layer, l, V, A)

        if assigner == "two_stage":
            result = torus_two_stage_with_diameter(V, A, L)
            if not result["success"]:
                print("階層割当に失敗しました。")
                return
            y_val = result["y_val"]
            t_val = result["t_val"]
            layer_dict = result["layer_dict"]
            run_time = result["step1_runtime"] + result["step2_runtime"]
        elif assigner == "torus":
            y_val, t_val, layer_dict, run_time = torus(V, A)
        elif assigner == "iqp":
            y_val, t_val, layer_dict, run_time = torus_iqp(V, A)
        elif assigner == "torus_edge":
            y_val, t_val, layer_dict, run_time = torus_minimize_torus_edge(V, A, L)
        elif assigner == "heuristic":
            y_val, t_val, layer_dict, run_time = torus_heuristic(V, A)
        else:
            y_val, t_val, layer_dict, run_time = torus_ilp(V, A, L)

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

    # 3. 交差削減
    print("\n3. 交差削減")
    order, layer_dict, A, t_val = minimize_crossings_ilp(
        V, A, layer_dict, t_val
    )  # ILP版（厳密解）
    # order, layer_dict, A, t_val = minimize_crossings_heuristic(
    #     V, A, layer_dict, t_val
    # )  # ヒューリスティック版（重心法）

    # 4. 描画
    print("\n4. 描画（draw_torus.py）...")
    print("  グラフを描画します...")
    print(f"実行時間: {round(run_time, 5)}")

    # 交差削減で最適化された順序を反映した描画
    draw_torus(V=V, A=A, L=layer_dict, t_val=t_val, order=order, draw_dummy_nodes=True)

    print("\n" + "=" * 60)
    print("完了！")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=int)
    parser.add_argument("--cycle", type=int)
    parser.add_argument("--prob", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--layer",
        choices=["diameter", "cycle_length"],
    )
    parser.add_argument(
        "--assigner",
        choices=[
            "ilp",
            "two_stage",
            "torus",
            "iqp",
            "torus_edge",
            "heuristic",
            "binary_balance",
        ],
        default="ilp",
    )
    parser.add_argument("--l", type=int)
    parser.add_argument(
        "--func_type",
        choices=["diff", "diff_square", "qp", "barycenter"],
        default="diff_square",
        help="階層割当のバランス手法 (binary_balanceで使用、デフォルト: diff_square)",
    )
    args = parser.parse_args()

    main(
        node=args.node,
        cycle=args.cycle,
        prob=args.prob,
        _seed=args.seed,
        layer=args.layer,
        assigner=args.assigner,
        l=args.l,
        func_type=args.func_type,
    )
