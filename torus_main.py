"""
トーラス階層割当と交差削減のメインスクリプト

1. ランダムなグラフを生成
2. torus.pyで階層割当
3. minimize_crossings.pyで交差削減
4. draw_torus.pyで描画
"""

from torus_iqp import torus_iqp
from torus import torus
from torus_ilp import torus_ilp
from minimize_crossings import minimize_crossings
from draw_torus import draw_torus
from generate_torus_graph import generate_cyclic_graph


def main():
    """メイン処理"""

    print("=" * 60)
    print("トーラス階層割当 + 交差削減デモ")
    print("=" * 60)

    # 1. ランダムなグラフを生成
    print("\n1. グラフ生成...")
    n = 20  # ノード数
    num_cycles = 1  # サイクル数
    edge_prob = 0.1  # エッジ確率
    seed = 1  # シード値

    V, A = generate_cyclic_graph(
        n=n, num_cycles=num_cycles, edge_prob=edge_prob, seed=seed
    )

    print(f"  ノード数: {len(V)}")
    print(f"  エッジ数: {len(A)}")
    print(f"  ノード: {V}")
    print(f"  エッジ: {A}")

    # 2. 階層割当
    print("\n2. 階層割当（torus.py）...")
    y_val, t_val, L, run_time = torus_ilp(V, A)

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

    # 3. 交差削減
    print("\n3. 交差削減（minimize_crossings.py）...")
    order = minimize_crossings(V, A, L, t_val)

    print(f"\n最適化されたノード順序:")
    for k in sorted(order.keys()):
        print(f"  階層 {k}: {order[k]}")

    # 4. 描画
    print("\n4. 描画（draw_torus.py）...")
    print("  グラフを描画します...")
    print(f"実行時間: {run_time}")

    # 順序を反映した描画（draw_torus.pyが順序を受け取れるように拡張が必要）
    # 現状はデフォルトの順序で描画
    draw_torus(V=V, A=A, L=L, t_val=t_val, order=order)

    print("\n" + "=" * 60)
    print("完了！")
    print("=" * 60)


if __name__ == "__main__":
    main()
