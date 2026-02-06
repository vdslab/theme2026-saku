"""
トーラス階層割当のテストスイート

手動で定義されたテストケースと自動生成されたテストケースの両方を含む
"""

from torus import torus
from draw_torus import draw_torus
from generate_torus_graph import (
    generate_random_connected_graph,
    generate_dag,
    generate_cyclic_graph,
    generate_mixed_graph,
)


def analyze_graph(V, A):
    """グラフの特性を分析"""
    in_degree = {v: 0 for v in V}
    out_degree = {v: 0 for v in V}

    for u, v in A:
        out_degree[u] += 1
        in_degree[v] += 1

    sources = [v for v in V if in_degree[v] == 0]
    sinks = [v for v in V if out_degree[v] == 0]

    print(f"  ノード数: {len(V)}, エッジ数: {len(A)}")
    print(f"  ソース頂点（入次数0）: {sources if sources else 'なし'}")
    print(f"  シンク頂点（出次数0）: {sinks if sinks else 'なし'}")

    return sources, sinks


def run_test(test_name, V, A, draw=False, verbose=True, store_results=None):
    """
    テストを実行

    Args:
        test_name: テスト名
        V: ノード集合
        A: エッジ集合
        draw: 描画するかどうか
        verbose: 詳細情報を表示するかどうか
        store_results: 結果を保存する辞書（Noneの場合は保存しない）

    Returns:
        success: テストが成功したかどうか
    """
    print(f"\n{'='*60}")
    print(f"{test_name}")
    print(f"{'='*60}")

    if verbose:
        analyze_graph(V, A)

    try:
        y_val, t_val, L = torus(V, A)

        if y_val:
            if verbose:
                print(f"\nレイヤー: {L}")

            # トーラス辺がない場合の警告（DAGの場合は問題ない）
            torus_edges = [(u, v) for (u, v) in A if t_val[(u, v)]]
            if not torus_edges:
                print("  ⚠️  トーラス辺が存在しません（DAGの可能性）")

            # 結果を保存
            if store_results is not None:
                store_results[test_name] = {
                    "V": V,
                    "A": A,
                    "y_val": y_val,
                    "t_val": t_val,
                    "L": L,
                    "success": True,
                }

            if draw:
                draw_torus(V, A, L)

            print(f"  ✅ テスト成功")
            return True
        else:
            if store_results is not None:
                store_results[test_name] = {"success": False}
            print(f"  ❌ 最適化失敗")
            return False

    except Exception as e:
        if store_results is not None:
            store_results[test_name] = {"success": False, "error": str(e)}
        print(f"  ❌ エラー発生: {e}")
        return False


def test_manual_cases(store_results=None):
    """手動定義のテストケース"""
    print("\n" + "=" * 60)
    print("手動定義テストケース")
    print("=" * 60)

    results = []

    # テストケース1: シンプルなサイクル
    V1 = [0, 1, 2]
    A1 = [(0, 1), (1, 2), (2, 0)]
    results.append(
        run_test(
            "テスト1: シンプルなサイクル（3ノード）",
            V1,
            A1,
            store_results=store_results,
        )
    )

    # テストケース2: 大きなサイクル
    V2 = [0, 1, 2, 3, 4]
    A2 = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
    results.append(
        run_test(
            "テスト2: 大きなサイクル（5ノード）", V2, A2, store_results=store_results
        )
    )

    # テストケース3: 複数のサイクル
    V3 = [0, 1, 2, 3, 4, 5, 6]
    A3 = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 0),  # サイクル1
        (0, 5),
        (5, 6),
        (6, 5),  # サイクル2
        (6, 3),
        (4, 5),
    ]
    results.append(
        run_test(
            "テスト3: 複数のサイクルを含むグラフ", V3, A3, store_results=store_results
        )
    )

    # テストケース4: DAG（サイクルなし）
    V4 = [0, 1, 2, 3, 4]
    A4 = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]
    results.append(
        run_test(
            "テスト4: DAG（有向非巡回グラフ）", V4, A4, store_results=store_results
        )
    )

    # テストケース5: ソースとシンクを持つグラフ
    V5 = [0, 1, 2, 3, 4, 5]
    A5 = [
        (0, 1),  # 0はソース
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 2),  # サイクル: 2→3→4→2
        (3, 5),  # 5はシンク
    ]
    results.append(
        run_test(
            "テスト5: ソース・シンクを持つグラフ", V5, A5, store_results=store_results
        )
    )

    # テストケース6: 密なグラフ
    V6 = [0, 1, 2, 3]
    A6 = [
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (1, 3),
        (2, 3),
        (3, 0),  # トーラス辺候補
        (2, 0),  # トーラス辺候補
    ]
    results.append(run_test("テスト6: 密なグラフ", V6, A6, store_results=store_results))

    return results


def test_auto_generated_cases(store_results=None):
    """自動生成テストケース"""
    print("\n" + "=" * 60)
    print("自動生成テストケース")
    print("=" * 60)

    results = []

    seeds = [1, 2, 3, 4, 5]

    # ランダム連結グラフ
    for i, seed in enumerate(seeds, 1):
        V, A = generate_random_connected_graph(n=8, edge_prob=0.3, seed=seed)
        results.append(
            run_test(
                f"自動生成{i}: ランダム連結グラフ（seed={seed}）",
                V,
                A,
                verbose=False,
                store_results=store_results,
            )
        )

    # DAG
    for i, seed in enumerate(seeds, 1):
        V, A = generate_dag(n=8, edge_prob=0.4, seed=seed)
        results.append(
            run_test(
                f"自動生成{i+3}: DAG（seed={seed}）",
                V,
                A,
                verbose=False,
                store_results=store_results,
            )
        )

    # サイクリックグラフ
    for i, seed in enumerate(seeds, 1):
        V, A = generate_cyclic_graph(n=10, num_cycles=2, edge_prob=0.2, seed=seed)
        results.append(
            run_test(
                f"自動生成{i+6}: サイクリックグラフ（seed={seed}）",
                V,
                A,
                verbose=False,
                store_results=store_results,
            )
        )

    # 混合グラフ
    for i, seed in enumerate(seeds, 1):
        V, A = generate_mixed_graph(n=10, edge_prob=0.3, cycle_prob=0.5, seed=seed)
        results.append(
            run_test(
                f"自動生成{i+9}: 混合グラフ（seed={seed}）",
                V,
                A,
                verbose=False,
                store_results=store_results,
            )
        )

    return results


def test_edge_cases(store_results=None):
    """エッジケースのテスト"""
    print("\n" + "=" * 60)
    print("エッジケーステスト")
    print("=" * 60)

    results = []

    # 最小サイクル
    V1 = [0, 1, 2]
    A1 = [(0, 1), (1, 2), (2, 0)]
    results.append(
        run_test(
            "エッジケース1: 最小サイクル（3ノード）",
            V1,
            A1,
            store_results=store_results,
        )
    )

    # 自己ループを含むグラフ（除外される可能性）
    V2 = [0, 1, 2]
    A2 = [(0, 1), (1, 2), (2, 0)]
    results.append(
        run_test("エッジケース2: 単純なサイクル", V2, A2, store_results=store_results)
    )

    # 線形チェーン（DAG）
    V3 = [0, 1, 2, 3, 4]
    A3 = [(0, 1), (1, 2), (2, 3), (3, 4)]
    results.append(
        run_test(
            "エッジケース3: 線形チェーン（DAG）", V3, A3, store_results=store_results
        )
    )

    # ダブルサイクル
    V4 = [0, 1, 2, 3]
    A4 = [(0, 1), (1, 0), (2, 3), (3, 2), (1, 2)]
    results.append(
        run_test("エッジケース4: ダブルサイクル", V4, A4, store_results=store_results)
    )

    return results


def run_all_tests():
    """すべてのテストを実行"""
    print("\n" + "#" * 60)
    print("# トーラス階層割当テストスイート")
    print("#" * 60)

    # テスト結果を保存
    test_results = {}

    all_results = []

    # 手動定義テスト
    manual_results = test_manual_cases(store_results=test_results)
    all_results.extend(manual_results)

    # 自動生成テスト
    auto_results = test_auto_generated_cases(store_results=test_results)
    all_results.extend(auto_results)

    # エッジケーステスト
    edge_results = test_edge_cases(store_results=test_results)
    all_results.extend(edge_results)

    # サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    total = len(all_results)
    passed = sum(all_results)
    failed = total - passed

    print(f"総テスト数: {total}")
    print(f"成功: {passed} ({'✅' if failed == 0 else '⚠️'})")
    print(f"失敗: {failed} ({'✅' if failed == 0 else '❌'})")
    print(f"成功率: {passed/total*100:.1f}%")

    if failed == 0:
        print("\n🎉 すべてのテストが成功しました！")
    else:
        print(f"\n⚠️  {failed}個のテストが失敗しました。")

    # 描画オプション
    print("\n" + "=" * 60)
    print("描画オプション")
    print("=" * 60)
    print("成功したテストケースの描画結果を見ますか？")
    print("選択肢:")
    print("  1. すべての成功したテストを描画")
    print("  2. 特定のテストを選択して描画")
    print("  3. 描画しない")

    try:
        choice = input("\n選択してください (1/2/3): ").strip()

        if choice == "1":
            # すべての成功したテストを描画
            print("\n成功したテストをすべて描画します...")
            for test_name, result in test_results.items():
                if result.get("success", False):
                    print(f"\n描画: {test_name}")
                    draw_torus(result["V"], result["A"], result["L"])

        elif choice == "2":
            # 特定のテストを選択
            print("\n成功したテストケース:")
            successful_tests = [
                (i + 1, name)
                for i, (name, result) in enumerate(test_results.items())
                if result.get("success", False)
            ]

            for idx, name in successful_tests:
                print(f"  {idx}. {name}")

            test_nums = input(
                "\n描画するテスト番号をカンマ区切りで入力 (例: 1,3,5): "
            ).strip()
            if test_nums:
                for num_str in test_nums.split(","):
                    try:
                        num = int(num_str.strip())
                        if 1 <= num <= len(successful_tests):
                            test_name = successful_tests[num - 1][1]
                            result = test_results[test_name]
                            print(f"\n描画: {test_name}")
                            draw_torus(result["V"], result["A"], result["L"])
                    except ValueError:
                        print(f"無効な入力: {num_str}")

        elif choice == "3":
            print("\n描画をスキップします。")

        else:
            print("\n無効な選択です。描画をスキップします。")

    except (EOFError, KeyboardInterrupt):
        print("\n\n描画をスキップします。")

    return all_results, test_results


if __name__ == "__main__":
    # すべてのテストを実行
    run_all_tests()
