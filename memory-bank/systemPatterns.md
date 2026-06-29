# System Patterns: トーラス階層割当・交差削減システム

## システムアーキテクチャ

```
入力(V, A)
    ↓
[階層数推定] layer_length/
    ├─ graph_diameter.py
    ├─ longest_cycle_length.py
    └─ estimate_layer_count_via_fas.py
    ↓
[階層割当] layer_assignment/
    ├─ torus_ilp.py (ILP: 固定階層数、分散最小化)
    ├─ torus_iqp.py (IQP: 階層数変数、2乗最小化)
    ├─ torus_heuristic.py (ヒューリスティック)
    ├─ torus_two_stage.py (2段階法)
    └─ torus_binary_search.py (バイナリサーチ)
    ↓
出力(y_val, t_val, layer_dict)
    ↓
[ダミーノード挿入] lib/insert_dummy_node.py
    ↓
[交差削減] crossing_reduction/
    ├─ minimize_crossings_ilp.py (ILP: 厳密解)
    └─ minimize_crossings_heuristic.py (重心法)
    ↓
出力(order, layer_dict, A, t_val)
    ↓
[可視化] drawing/draw_torus.py
```

## 主要コンポーネント

### 1. 階層割当モジュール (layer_assignment/)

#### torus_ilp.py - ILP階層割当エンジン

**責務**: 固定階層数での厳密な階層割当

**特徴**:

- One-hot変数でエッジ距離を離散化
- エッジスパンの2乗最小化（ILPとして定式化）
- Big-M法によるトーラス辺判定

**入力**:

- V: ノード集合
- A: エッジ集合
- L: 固定階層数
- w, lam: オプションパラメータ

**出力**:

- y_val: 階層割当 dict[node: layer]
- t_val: トーラス辺判定 dict[edge: bool]
- layer_dict: レイヤー集合 dict[layer: nodes[]]
- run_time: 実行時間

#### torus_iqp.py - IQP階層割当エンジン

**責務**: 階層数を変数とした2次計画法による階層割当

**特徴**:

- 階層数L_maxを最適化変数として扱う
- エッジスパンを直接2乗した目的関数
- torus.pyの後継実装

#### torus_heuristic.py - ヒューリスティック階層割当

**責務**: 高速な近似解の計算

**アルゴリズム**:

1. Tarjan法によるSCC分解
2. SCC-DAGの構築と最長パス計算
3. 各SCC内でモジュラーランク最適化

#### torus_two_stage.py - 2段階階層割当

**責務**: トーラス辺最小化後にバランス調整

**ステップ**:

1. トーラス辺数を最小化（ILP）
2. 固定トーラス辺でエッジスパンを最適化（ILP）

### 2. 交差削減モジュール (crossing_reduction/)

#### minimize_crossings_ilp.py - ILP交差削減

**責務**: 平坦トーラス上の厳密な交差最小化

**新しい定式化の特徴**:

- 環状構造のトーラスモデル
- 巻き付き数（alpha）変数の導入
- 対称性を利用した変数削減（x[k,u,v]は常にu<vで生成）
- 推移律制約によるノード順序の一意性保証

**変数**:

- x[k,u,v]: 階層k内でノードuがvより上にあるか（u<v限定）
- alpha[e]: エッジeの巻き付き数（-1, 0, 1）
- alpha_abs[e]: alphaの絶対値
- c[e1,e2]: エッジ対の交差数

**制約**:

- 推移律: x_uv + x_vw - x_uw ∈ {0,1}
- 絶対値: alpha_abs >= ±alpha
- 交差計算: c >= |Δalpha - Δx|

#### minimize_crossings_heuristic.py - ヒューリスティック交差削減

**責務**: 重心法による高速交差削減

**アルゴリズム**:

1. 重心位置計算
2. 重心順にソート
3. サイクリックシフト最適化
4. 収束まで反復

### 3. 階層数推定モジュール (layer_length/)

#### graph_diameter.py

**手法**: ダイクストラ法で全点対最短距離を計算

#### longest_cycle_length.py

**手法**: 最長サイクル長を推定

#### estimate_layer_count_via_fas.py

**手法**: Feedback Arc Set サイズから推定

### 4. 可視化モジュール (drawing/)

#### draw_torus.py - トーラス可視化エンジン

**特徴**:

- ダミーノードの黒点表示（オプション）
- トーラス辺の境界接続描画
- レイヤー順序の反映
- ノードとエッジの重なり回避

### 5. ライブラリモジュール (lib/)

#### create_gurobi_env.py

**責務**: Gurobi環境の作成と設定

#### insert_dummy_node.py

**責務**: 長距離エッジへのダミーノード挿入

**アルゴリズム**:

- 階層差が2以上のエッジを検出
- 中間階層にダミーノードを挿入
- エッジを分割して接続

#### generate_torus_graph.py

**責務**: テスト用グラフの生成

#### scc_decomposition.py

**責務**: 強連結成分分解

## 重要な技術的決定

### Big-M法の実装（layer_assignment共通）

**決定**: トーラス辺を $t_{uv} = 1 \Leftrightarrow y_u > y_v$ として定義

**実装**:

```python
M = n  # ノード数
# (a) y[u] - y[v] <= M * t[u,v]
# (b) y[u] - y[v] >= lam - M * (1 - t[u,v])
# (c) y[v] - y[u] >= lam - M * t[u,v]
```

### ILPにおけるエッジスパン2乗の離散化（torus_ilp.py）

**決定**: One-hot変数による距離の離散化

**実装**:

```python
# K_uv = {lam, lam+1, ..., M-1}
x[u,v,k]: エッジ(u,v)の距離がkかどうか
制約: Σ_k x[u,v,k] = 1
     Σ_k k*x[u,v,k] = y[v] - y[u] + M*t
目的関数: Σ_(u,v) Σ_k (k^2 * x[u,v,k])
```

**利点**: 2乗項を線形化し、ILPで厳密解を計算可能

### 平坦トーラス交差削減の定式化（minimize_crossings_ilp.py）

**決定**: 巻き付き数変数と環状階層構造

**理由**:

- トーラス境界をまたぐエッジの交差を正確に計算
- 視覚的に最適な配置を実現

**実装**:

```python
# 環状構造: 最後の階層の次は最初の階層
next_k = layers[(idx + 1) % num_layers]

# 交差計算
c[e1,e2] >= (alpha[e1] - alpha[e2]) - x_v1v2 + x_u1u2
c[e1,e2] >= -(alpha[e1] - alpha[e2]) + x_v1v2 - x_u1u2
```

### ダミーノード挿入パターン（insert_dummy_node.py）

**決定**: 階層差2以上のエッジに自動挿入

**理由**: 長距離エッジは視覚的に煩雑で交差を増やす

**実装**:

```python
# 階層インデックスの距離を計算（環状考慮）
dist = (v_idx - u_idx) % num_layers
if dist >= 2:
    # ダミーノードを挿入
```

## 設計パターン

### 1. 共通インターフェースパターン

すべての階層割当関数は同じシグネチャ:

```python
def method(V, A, L=None, w=None, lam=None):
    # ...
    return y_val, t_val, layer_dict, run_time
```

### 2. パラメータデフォルト値パターン

```python
if w is None:
    w = {(u, v): 1 for (u, v) in A}
if lam is None:
    lam = {(u, v): 1 for (u, v) in A}
```

### 3. エラーハンドリングパターン

```python
if m.status == GRB.OPTIMAL:
    # 成功時の処理
else:
    print(f"最適化失敗: ステータス = {m.status}")
    m.computeIIS()
    for c in m.getConstrs():
        if c.IISConstr:
            print(f"  {c.constrName}")
```

## コンポーネント関係図

```
main.py
    ↓
┌──────────────┬────────────────┬──────────────┐
│              │                │              │
layer_length   layer_assignment  crossing_reduction  drawing
    ↓               ↓                  ↓             ↓
lib/create_gurobi_env.py ←─────────────┴─────────────┘
lib/insert_dummy_node.py ←─────────────┘
lib/generate_torus_graph.py (テスト用)
```

## 重要な実装パス

### メインワークフロー（main.py）

1. グラフ生成（generate_cyclic_graph）
2. 階層数推定（assign_layer_length_func）
3. 階層割当（選択した手法）
4. ダミーノード挿入（minimize_crossings内で実行）
5. 交差削減（ILPまたはヒューリスティック）
6. 可視化（draw_torus）

### 階層割当最適化フロー（torus_ilp.py例）

1. **変数定義**: y, t, x (one-hot), L_max
2. **制約追加**:
   - 最大階層制約
   - One-hot制約
   - 距離関係制約
   - Big-M制約（a, b, c）
3. **目的関数設定**: α*L_max + β*Σ(k²*x) + γ*Σt
4. **最適化実行**: Gurobi solver
5. **結果抽出**: y_val, t_val, layer_dict
