# Tech Context: トーラス階層割当・交差削減システム

## 技術スタック

### 言語

- **Python 3.x**: メイン実装言語

### 主要ライブラリ

#### 最適化

- **Gurobi Optimizer 13.0.0**: 混合整数計画法ソルバー
  - ライセンス: Academic License
  - 用途: トーラス階層割当と交差削減の数理最適化
  - インターフェース: gurobipy

#### 可視化

- **Matplotlib**: グラフ描画
  - 用途: 階層グラフとトーラス辺の視覚化
  - FancyArrowPatchを活用した高品質な描画

#### グラフ処理

- **NetworkX**: グラフ構造の扱い（描画時のみ使用）

#### ユーティリティ

- **collections.defaultdict**: レイヤー集合の構築
- **collections.deque**: BFS/DFS探索
- **random**: テストグラフの生成
- **itertools**: 組み合わせ生成

## 開発環境

### ツール

- **Visual Studio Code**: IDE
- **Git**: バージョン管理
  - リポジトリ: git@github.com:vdslab/theme2026-saku.git

### Python環境

- パッケージマネージャ: pip
- 仮想環境: 推奨（明示的な設定なし）

## ファイル構成

```
theme2026-saku/
├── src/                           # ソースコード
│   ├── main.py                    # メインエントリポイント
│   ├── layer_assignment/          # 階層割当モジュール
│   │   ├── torus.py              # 元の実装（IQPベース）
│   │   ├── torus_ilp.py          # ILP版（固定階層数）
│   │   ├── torus_iqp.py          # IQP版（階層数変数）
│   │   ├── torus_heuristic.py    # ヒューリスティック版
│   │   ├── torus_two_stage.py    # 2段階最適化版
│   │   ├── torus_binary_search.py # バイナリサーチ版
│   │   ├── torus_balance.py      # バランス調整関数群
│   │   └── torus_minimize_torus_edge.py
│   ├── crossing_reduction/        # 交差削減モジュール
│   │   ├── minimize_crossings_ilp.py         # ILP版
│   │   └── minimize_crossings_heuristic.py   # ヒューリスティック版
│   ├── layer_length/              # 階層数推定モジュール
│   │   ├── graph_diameter.py
│   │   ├── longest_cycle_length.py
│   │   ├── estimate_layer_count_via_fas.py
│   │   ├── estimate_max_cycle_rm_dfs.py
│   │   ├── longest_path_scc_dag.py
│   │   └── scc_node_count.py
│   ├── drawing/                   # 可視化モジュール
│   │   └── draw_torus.py
│   ├── lib/                       # ライブラリ
│   │   ├── create_gurobi_env.py
│   │   ├── generate_torus_graph.py
│   │   ├── insert_dummy_node.py
│   │   └── scc_decomposition.py
│   └── test/                      # テストコード
│       ├── test_torus.py
│       └── test_draw_torus.py
├── memory-bank/                   # プロジェクトメモリ
│   ├── projectbrief.md
│   ├── productContext.md
│   ├── systemPatterns.md
│   ├── techContext.md
│   ├── activeContext.md
│   └── progress.md
├── archive/                       # 旧コード（読まない）
├── documents/                     # ドキュメント
├── fig/                          # 図
├── .clinerules                   # Cline開発ルール
└── .gitignore
```

## 技術的制約

### Gurobi制約

1. **ライセンス**: Academic License必須
2. **スケーラビリティ**: 大規模問題（数千変数以上）では計算時間増加
3. **プラットフォーム**: Mac (ARM64), Darwin 25.2.0

### Big-M法の制約

1. **M値の選択**: M = n（ノード数）
   - 小さすぎ: 制約が正しく機能しない
   - 大きすぎ: 数値的不安定性
2. **変数範囲**: y[v] ∈ [0, n-1] と整合性が必要

### 数値的安定性

- 2乗項使用により、大規模グラフでは目的関数値が大きくなる可能性
- 現状: 小〜中規模グラフ（〜100ノード程度）を想定

## 依存関係

### モジュール間の依存

```
main.py
  ↓
  ├─ layer_length.* (階層数推定)
  ├─ layer_assignment.* (階層割当)
  ├─ crossing_reduction.* (交差削減)
  └─ drawing.draw_torus (可視化)

layer_assignment.*
  ├─ lib.create_gurobi_env
  └─ lib.scc_decomposition (heuristicのみ)

crossing_reduction.*
  ├─ lib.create_gurobi_env
  └─ lib.insert_dummy_node

drawing.draw_torus
  └─ (外部依存なし、標準ライブラリのみ)
```

## 開発ツール使用パターン

### Gurobiモデルの構築

```python
env = create_gurobi_env()
with gp.Model(name="Torus_ILP", env=env) as m:
    # 変数定義
    y = m.addVars(V, vtype=GRB.INTEGER, ...)
    t = m.addVars(A, vtype=GRB.BINARY, ...)

    # 制約追加
    m.addConstrs(...)

    # 最適化実行
    m.optimize()

    # 結果取得
    if m.status == GRB.OPTIMAL:
        y_val = {v: int(round(y[v].X)) for v in V}
```

### エラー診断

```python
if m.status != GRB.OPTIMAL:
    print(f"最適化失敗: ステータス = {m.status}")
    m.computeIIS()  # 実行不可能制約集合を計算
    for c in m.getConstrs():
        if c.IISConstr:
            print(f"  {c.constrName}")
```

### コマンドライン引数

```bash
# 基本実行
python src/main.py

# カスタムパラメータ
python src/main.py --node 50 --cycle 2 --prob 0.005 --seed 10

# 階層数推定法の選択
python src/main.py --layer cycle_length  # または diameter

# 階層割当手法の選択
python src/main.py --assigner ilp        # ILP（デフォルト）
python src/main.py --assigner iqp        # IQP
python src/main.py --assigner heuristic  # ヒューリスティック
python src/main.py --assigner two_stage  # 2段階法

# 階層数の手動指定
python src/main.py --l 5
```

## パフォーマンス考慮事項

### 計算複雑度

#### 階層割当（ILP）

- **変数数**:
  - y: O(n)
  - t: O(|A|)
  - x (one-hot): O(|A| × n)
  - 合計: O(n + |A| × n)
- **制約数**: O(n + |A| × n)
- **2次項**: なし（ILPとして定式化）

#### 交差削減（ILP）

- **変数数**:
  - x: O(Σ_k |L_k|²) ≈ O(n²/k) (k=階層数)
  - alpha: O(|A|)
  - c: O(|A|²)
- **制約数**: O(n³/k + |A|²)

### 最適化時間

- **小規模** (n<10): < 1秒
- **中規模** (n=10-50): 1-10秒
- **大規模** (n>100): 数十秒〜数分（未検証）

### ヒューリスティック手法の性能

- **階層割当**: < 0.1秒（n=50）
- **交差削減**: < 1秒（n=50）

## テスト戦略

### テストファイル

1. **test_torus.py**: 階層割当のテスト
   - 手動定義テスト
   - 自動生成テスト
   - エッジケーステスト

2. **test_draw_torus.py**: 描画のテスト

### テスト実行

```bash
python src/test/test_torus.py
python src/test/test_draw_torus.py
```

## 今後の技術的課題

1. **大規模グラフ対応**: ヒューリスティック手法の精度向上
2. **数値安定性**: Big-M値の動的調整
3. **パフォーマンス**: 前処理による変数削減、制約の効率化
4. **可視化**: より洗練されたレイアウトアルゴリズム
5. **パラメータ**: α, β, γの自動チューニング

## Gurobiパラメータに関する注意

**.clinerules**に記載の通り、Gurobiのパラメータ調整による性能向上は行わない方針。
デフォルト設定のままで使用する。
