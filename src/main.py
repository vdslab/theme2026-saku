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
from crossing_reduction.minimize_crossings_ilp import minimize_crossings_ilp
from crossing_reduction.minimize_crossings_heuristic import minimize_crossings_heuristic
from drawing.draw_torus import draw_torus
from lib.generate_torus_graph import generate_cyclic_graph

from collections import defaultdict


def main():
    """メイン処理"""

    print("=" * 60)
    print("トーラス階層割当 + 交差削減デモ")
    print("=" * 60)

    # 1. ランダムなグラフを生成
    print("\n1. グラフ生成")
    n = 50  # ノード数
    num_cycles = 1  # サイクル数
    edge_prob = 0.005  # エッジ確率
    seed = 14  # シード値

    V, A = generate_cyclic_graph(
        n=n, num_cycles=num_cycles, edge_prob=edge_prob, seed=seed
    )

    print(f"  ノード数: {len(V)}")
    print(f"  エッジ数: {len(A)}")
    print(f"  ノード: {V}")
    print(f"  エッジ: {A}")

    # 2. 階層割当
    print("\n2. 階層割当")
    # y_val, t_val, L, run_time = torus(V, A)
    # y_val, t_val, L, run_time = torus_iqp(V, A)
    y_val, t_val, L, run_time = torus_ilp(V, A)
    # y_val, t_val, L, run_time = torus_heuristic(V, A)

    if not y_val:
        print("階層割当に失敗しました。")
        return

    # トーラス辺の情報
    torus_edges = [(u, v) for (u, v) in A if t_val[(u, v)]]
    normal_edges = [(u, v) for (u, v) in A if not t_val[(u, v)]]

    print(f"\n階層割当結果:")
    print(f"  最大階層: {max(y_val.values())}")
    print(f"  トーラス辺数: {len(torus_edges)}")
    print(f"  通常辺数: {len(normal_edges)}")
    print(f"  トーラス辺: {torus_edges}")
    print(f"  割当階層: ")
    d = defaultdict(list)
    for k, v in y_val.items():
        d[v].append(k)
    for k, v in sorted(d.items()):
        print(f"    {k}: {v}")
    print(f"  エッジ: {t_val}")

    # 3. 交差削減
    print("\n3. 交差削減")
    # order, L, A, t_val = minimize_crossings_ilp(V, A, L, t_val)  # ILP版（厳密解）
    order, L, A, t_val = minimize_crossings_heuristic(
        V, A, L, t_val
    )  # ヒューリスティック版（重心法）

    # 4. 描画
    print("\n4. 描画（draw_torus.py）...")
    print("  グラフを描画します...")
    print(f"実行時間: {round(run_time, 5)}")

    # 交差削減で最適化された順序を反映した描画
    draw_torus(V=V, A=A, L=L, t_val=t_val, order=order)

    print("\n" + "=" * 60)
    print("完了！")
    print("=" * 60)


if __name__ == "__main__":
    main()
