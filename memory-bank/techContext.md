# Tech Context: トーラス階層割当システム

## 技術スタック

### 言語

- **Python 3.x**: メイン実装言語

### 主要ライブラリ

#### 最適化

- **Gurobi Optimizer 13.0.0**: 混合整数計画法ソルバー
  - ライセンス: Academic License
  - 用途: トーラス階層割当の数理最適化
  - インターフェース: gurobipy

#### 可視化

- **Matplotlib**: グラフ描画
  - 用途: 階層グラフとトーラス辺の視覚化

#### ユーティリティ

- **collections.defaultdict**: レイヤー集合の構築
- **random**: テストグラフの生成

## 開発環境

### ツール

- **Visual Studio Code**: IDE
- **Git**: バージョン管理

### Python環境

- パッケージマネージャ: pip
- 仮想環境: 推奨（明示的な設定なし）

## ファイル構成

```
theme2026-saku/
├── torus.py                    # メイン最適化関数
├── create_gurobi_env.py        # Gurobi環境作成
├── draw_torus.py               # 可視化関数
├── generate_torus_graph.py     # グラフ生成ユーティリティ
├── test_torus.py               # テストスイート
├── torus_formulation.md        # 数理モデルドキュメント
├── memory-bank/                # プロジェクトメモリ
│   ├── projectbrief.md
│   ├── productContext.md
│   ├── systemPatterns.md
│   ├── techContext.md
│   ├── activeContext.md
│   └── progress.md
└── formulas/                   # その他の定式化
    ├── p_l.py
    ├── p_g.py
    └── ...
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

### create_gurobi_env.py

```python
def create_gurobi_env():
    # Gurobiの環境を作成
    # ライセンス情報の設定
    return env
```

**使用箇所**: torus.py

### torus.py → draw_torus.py

```python
# torus.pyの出力がdraw_torus.pyの入力
y_val, t_val, L = torus(V, A)
draw_torus(V, A, L)
```

## 開発ツール使用パターン

### Gurobiモデルの構築

```python
env = create_gurobi_env()
with gp.Model(name="Torus_Layout", env=env) as m:
    # 変数定義
    y = m.addVars(V, vtype=GRB.INTEGER, ...)

    # 制約追加
    m.addConstrs(...)

    # 最適化実行
    m.optimize()
```

### エラー診断

```python
if m.status != GRB.OPTIMAL:
    m.computeIIS()  # 実行不可能制約集合を計算
    for c in m.getConstrs():
        if c.IISConstr:
            print(f"  {c.constrName}")
```

## パフォーマンス考慮事項

### 計算複雑度

- **変数数**: O(n) (y) + O(|A|) (t) + 1 (L_max) ≈ O(n + |A|)
- **制約数**: O(n) + 3×O(|A|) ≈ O(n + |A|)
- **2次項**: O(|A|) (目的関数の2乗項)

### 最適化時間

- **小規模** (n<10): < 0.1秒
- **中規模** (n=10-50): 0.1-1秒
- **大規模** (n>100): 数秒〜数分（未検証）

## テスト戦略

### テストカバレッジ

1. **手動定義テスト**: 6件
   - シンプルなサイクル
   - 大きなサイクル
   - 複数サイクル
   - DAG
   - ソース・シンク付き
   - 密グラフ

2. **自動生成テスト**: 12件
   - ランダム連結グラフ ×3
   - DAG ×3
   - サイクリックグラフ ×3
   - 混合グラフ ×3

3. **エッジケーステスト**: 4件
   - 最小サイクル
   - 線形チェーン
   - ダブルサイクル

### テスト実行

```bash
python test_torus.py
```

インタラクティブに描画を選択可能。

## 今後の技術的課題

1. **大規模グラフ対応**: ヒューリスティック手法の検討
2. **数値安定性**: Big-M値の動的調整
3. **パフォーマンス**: 前処理による変数削減
4. **可視化**: より洗練されたレイアウトアルゴリズム
