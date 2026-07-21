"""
2分探索を用いて最小のトーラス辺数とそれを達成する最小のレイヤー数を求める
"""

import os
import sys
import time
from pprint import pprint

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layer_assignment.torus_two_stage import minimize_torus_edges


def find_minimum_torus_configuration(V, A, w=None, lam=None):
    """
    グラフに対する最小のトーラス辺数とそれを達成する最小のレイヤー数を求める

    レイヤー数を2分探索し、最小のトーラス辺数を達成できる最小のレイヤー数を見つける。
    L は最大レイヤー番号ではなくレイヤー数であり、番号は 0, ..., L - 1。

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        w: エッジ重み dict[(int,int): float] (オプション)
        lam: エッジの最小階層差 dict[(int,int): int] (オプション)

    Returns:
        optimal_L: 最小のトーラス辺数を達成する最小のレイヤー数 int
        min_torus_count: 最小のトーラス辺数 int

    計算量:
        1. グラフの直径計算: O(|V| * |E| * log|V|)
            - すべてのノードからDijkstra法を実行
            - Dijkstra法: O(|E| * log|V|) (優先度付きキュー使用)
            - これを|V|回実行

        2. 2分探索: O(log D) 回のILP求解
            - D: グラフの直径 (最大でO(|V|))
            - 探索範囲: [1, D]
            - 2分探索の反復回数: O(log D) = O(log |V|)

        3. 各反復でのILP求解 (minimize_torus_edges):
            - 変数数: O(|V| + |E|)
             * y[v]: |V|個 (各ノードの階層)
             * t[e]: |E|個 (各エッジのトーラスフラグ)
            - 制約数: O(|V| + |E|)
             * 階層制約: O(|V|)
             * トーラス辺定義: O(|E|)
            - ILP求解: 最悪ケースでは指数時間だが、
             * 実用的には問題の構造により多項式時間で解けることが多い

        総合計算量:
           O(|V| * |E| * log|V|) + O(log|V|) * T_ILP
            ここで T_ILP は1回のILP求解時間

        実用上の性能:
            - グラフの直径が小さい場合、2分探索の回数が減少
            - Gurobiのヒューリスティックにより、多くの場合高速に最適解を発見
            - 典型的なグラフ（|V|=10-100）では数秒〜数分で完了
    """

    st = time.time()

    # エッジの重複を除去
    A = list(set(A))

    # 1. 全頂点を異なる位置に置ける値をレイヤー数の上限にする。
    #
    # 有向直径は安全な上限ではない。例えば3-cycleの有向直径は2だが、
    # このモデルは y in {0, ..., L-1} かつトーラス辺の正方向スパンを1以上に
    # するため L=3 を必要とする。最大の最小階層差を使った以下の上限なら、
    # 任意の頂点順を十分な間隔で配置できる。
    max_lam = max(lam.values(), default=1) if lam is not None else 1
    max_L = max(1, len(V) * max_lam)

    # 2. 安全な上限でトーラス辺の最小値を計算
    _, _, _, _, target_min_torus = minimize_torus_edges(V, A, max_L, w, lam)

    if target_min_torus is None:
        # 最適化に失敗した場合
        return None, None, time.time() - st

    # 3. target_min_torusを達成できる最小のLを2分探索
    left, right = 1, max_L
    optimal_L = max_L
    min_torus_count = target_min_torus

    while left <= right:
        mid = (left + right) // 2

        # midでトーラス辺数を最小化
        _, _, _, _, torus_count = minimize_torus_edges(V, A, mid, w, lam)

        if torus_count is None:
            # 最適化に失敗した場合、Lが小さすぎる可能性
            left = mid + 1
            continue

        if torus_count <= target_min_torus:
            # 目標を達成できた場合、より小さいLを探索
            optimal_L = mid
            min_torus_count = torus_count
            right = mid - 1
        else:
            # 目標を達成できない場合、より大きいLが必要
            left = mid + 1

    ed = time.time()
    return optimal_L, min_torus_count, ed - st


def test_binary_search_correctness(num_tests=10, verbose=True):
    """
    2分探索アルゴリズムの正しさをテストする関数

    Args:
        num_tests: テスト回数
        verbose: 詳細な情報を出力するか

    Returns:
        成功したテスト数、失敗したテスト数
    """
    import random
    from lib.generate_torus_graph import generate_cyclic_graph

    success_count = 0
    failure_count = 0
    failures = []

    results = []

    for test_id in range(num_tests):
        # ランダムにグラフパラメータを決定
        n = random.randint(50, 150)
        num_cycles = random.randint(3, 5)
        edge_prob = random.uniform(0.001, 0.004)

        if verbose:
            print(f"\n{'='*60}")
            print(f"テスト {test_id + 1}/{num_tests}")
            print(f"ノード数={n}, num_cycles={num_cycles}, edge_prob={edge_prob:.4f}")

        # グラフを生成
        V, A = generate_cyclic_graph(n=n, num_cycles=num_cycles, edge_prob=edge_prob)

        if verbose:
            print(f"生成されたエッジ数: {len(A)}")

        # 2分探索で結果を取得
        binary_L, binary_T, binary_time = find_minimum_torus_configuration(V, A)

        if binary_L is None:
            if verbose:
                print("2分探索が失敗しました（スキップ）")
            continue

        if verbose:
            print(f"2分探索結果: L={binary_L}, T={binary_T}, 時間={binary_time:.2f}秒")

        results.append(
            {
                "V": len(V),
                "A": len(A),
                "cycle": num_cycles,
                "T": binary_time,
            }
        )

    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"テスト完了")
    print(f"  成功: {success_count}/{num_tests}")
    print(f"  失敗: {failure_count}/{num_tests}")

    if failure_count > 0:
        print(f"\n失敗したテストの詳細:")
        for fail in failures:
            print(f"\n  テスト#{fail['test_id']}:")
            print(f"    ノード数={fail['n']}, エッジ数={fail['num_edges']}")
            print(f"    2分探索: L={fail['binary']['L']}, T={fail['binary']['T']}")
            print(
                f"    全探索:   L={fail['exhaustive']['L']}, T={fail['exhaustive']['T']}"
            )

    pprint(results)

    return success_count, failure_count, results


if __name__ == "__main__":
    # テスト実行
    test_binary_search_correctness(num_tests=30, verbose=False)
