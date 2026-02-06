# System Patterns: トーラス階層割当システム

## システムアーキテクチャ

```
入力(V, A)
    ↓
[torus.py] 数理最適化
    ├─ 変数定義: y[v], t[u,v], L_max
    ├─ 制約追加: Big-M法
    ├─ 目的関数: α*L_max + β*Σ(span²) + γ*Σt
    └─ Gurobi最適化
    ↓
出力(y_val, t_val, L)
    ↓
[draw_torus.py] 可視化
```

## 主要コンポーネント

### 1. torus.py - 最適化エンジン

**責務**: 階層割当の数理最適化

**入力**:

- V: ノード集合
- A: エッジ集合
- w, lam: オプションパラメータ
- α, β, γ: 重みパラメータ

**出力**:

- y_val: 階層割当 dict[node: layer]
- t_val: トーラス辺判定 dict[edge: bool]
- L: レイヤー集合 dict[layer: nodes[]]

### 2. draw_torus.py - 可視化エンジン

**責務**: 階層グラフの視覚化

### 3. generate_torus_graph.py - テストデータ生成

**責務**: 多様なグラフパターンの自動生成

- ランダム連結グラフ
- DAG
- サイクリックグラフ
- 混合グラフ

### 4. test_torus.py - テストスイート

**責務**: 包括的なテストと検証

- 22件のテストケース
- インタラクティブな描画選択

## 重要な技術的決定

### Big-M法の実装

**決定**: トーラス辺を $t_{uv} = 1 \Leftrightarrow y_u > y_v$ として定義

**理由**:

- 論理条件を線形制約で表現できる
- Gurobiの混合整数計画法で厳密解を保証

**実装**:

```python
# (a) y[u] - y[v] <= M * t[u,v]
# (b) y[u] - y[v] >= 1 - M * (1 - t[u,v])
```

### 目的関数の設計

**決定**: 3項の重み付き和

```
min: α*L_max + β*Σ(y[v]-y[u]+M*t)² + γ*Σt
```

**理由**:

1. **α\*L_max**: 階層数を最小化（優先度高: 100）
2. **β\*Σ(span²)**: エッジスパンの分散を最小化（副次的: 1）
3. **γ\*Σt**: トーラス辺数を直接最小化（強く優先: 1000）

**2乗形式の利点**:

- 長いエッジに対して強いペナルティ
- エッジスパンの均等化
- トーラス辺では $(M)^2$ の巨大なペナルティ

### 階層の範囲設定

**決定**: y[v] ∈ {0, 1, ..., n-1}

**理由**:

- n個のノード → 最大n階層（0-indexed）
- Big-M = n との整合性
- 実用上十分な範囲

### トーラス辺存在性制約の削除

**決定**: `Σt >= 1` 制約を削除

**理由**:

- DAGではトーラス辺が不要
- γ項で自然にトーラス辺を最小化
- より柔軟な最適化が可能

## 設計パターン

### 1. パラメータのデフォルト値パターン

```python
def torus(V, A, w=None, lam=None, alpha=100, beta=1, gamma=1000):
    if w is None:
        w = {(u, v): 1 for (u, v) in A}
    if lam is None:
        lam = {(u, v): 1 for (u, v) in A}
```

### 2. エッジ重複除去パターン

```python
A = list(set(A))  # 重複エッジを自動除去
```

### 3. エラーハンドリングパターン

```python
if m.status == GRB.OPTIMAL:
    # 成功時の処理
else:
    # IIS（実行不可能制約集合）を表示
    m.computeIIS()
```

## コンポーネント関係図

```
create_gurobi_env.py
        ↓ (環境作成)
    torus.py ←─── test_torus.py (テスト)
        ↓         ↑
    (y, t, L)    generate_torus_graph.py
        ↓
draw_torus.py (可視化)
```

## 重要な実装パス

### 最適化フロー

1. **変数定義**: y, t, L_max の作成
2. **制約追加**: 4種の制約（最大階層、Big-M(a)(b)、通常辺）
3. **目的関数設定**: 3項の重み付き和
4. **最適化実行**: Gurobi solver
5. **結果抽出**: y_val, t_val, L の構築

### レイヤー集合の構築

```python
layer_dict = defaultdict(list)
for v in V:
    layer_dict[y_val[v]].append(v)
L = dict(layer_dict)
```
