# グラフ生成

`src/lib/generate_torus_graph.py` にある5種類の生成処理を、手法ごとに
分けた追加パッケージです。既存ファイルと呼び出し箇所はそのままです。

## 共通の入口

`generator.generate_graph` が `graph_type` を見て生成関数へ振り分けます。
手法固有の引数は、対応する関数にそのまま渡します。

```python
from generator import generate_graph

vertices, edges = generate_graph("dag", n=20, edge_prob=0.1, seed=42)

vertices, edges = generate_graph(
    "cyclic", n=20, num_cycles=3, edge_prob=0.2, seed=42
)

vertices, edges = generate_graph(
    "watts_strogatz", n=20, k=4, p=0.25, seed=42
)
```

設定を辞書で受け取る場合も、同じ入口を使えます。

```python
config = {
    "graph_type": "mixed",
    "n": 20,
    "edge_prob": 0.1,
    "cycle_prob": 0.3,
    "seed": 42,
}
vertices, edges = generate_graph(**config)
```

戻り値は既存と同じ `(vertices, edges)` です。頂点は `0` から `n - 1`
までの整数リスト、有向辺は `(始点, 終点)` のリストです。
`return_seed=True` では、すべての手法で `(vertices, edges, seed)` を返します。

```python
vertices, edges, used_seed = generate_graph("random", n=20, return_seed=True)
# 未指定だったシードを使って、同じグラフを再生成できる。
assert (vertices, edges) == generate_graph("random", n=20, seed=used_seed)
```

同じ手法・引数・シードで再現できます。乱数は生成処理ごとに独立しており、
Python のグローバルな `random` の状態を変更しません。
未知の手法名は `ValueError`、その手法にない引数は `TypeError` になります。

## 各手法が行うこと

ここでの「連結」は、辺の向きを無視した**弱連結**です。
有向辺をたどってすべての頂点へ到達できる強連結は保証しません。

| `graph_type` | ファイル / 関数 | 生成の手順 | 手法固有の引数（既定値） |
| --- | --- | --- | --- |
| `random` | `random_connected.py` / `generate_random_connected_graph` | 既訪問頂点と未訪問頂点を結んでスパニングツリーを作り、未使用の有向辺を確率的に追加する。弱連結を保証し、閉路や双方向の辺を許容する。 | `edge_prob=0.3` |
| `dag` | `dag.py` / `generate_dag` | 小さい頂点番号から大きい番号への辺だけを確率的に追加する。非連結なら `0→1→2→…` の不足辺を補い、弱連結なDAGにする。 | `edge_prob=0.3` |
| `cyclic` | `cyclic.py` / `generate_cyclic_graph` | 頂点を連続したグループに分けて長さ3以上の有向閉路を作る。余った頂点を閉路へ双方向に接続し、閉路同士をつなぎ、追加辺を確率的に生成する。弱連結で、少なくとも1つの閉路を持つ。 | `num_cycles=2`, `edge_prob=0.2` |
| `mixed` | `mixed.py` / `generate_mixed_graph` | 各頂点を確率的に閉路部分へ割り当て、3頂点以上なら環状に結ぶ。残りのDAG部分に昇順の辺を追加し、両部分を相互に接続する。最後に番号の隣り合う頂点を結んで弱連結にする。 | `edge_prob=0.3`, `cycle_prob=0.3` |
| `watts_strogatz` | `watts_strogatz.py` / `generate_watts_strogatz_graph` | NetworkXで円環上の近傍を結んだ無向グラフを作り、辺を確率的に張り替える。各辺を円環上の短い時計回り方向へ向ける。同距離の場合はNetworkXの辺の順序を採用する。 | `k=4`, `p=0.1`, `ensure_connected=True`, `tries=100` |

- `edge_prob` は**追加候補の辺**の生成確率です。木・閉路・連結補完の辺は
  確率によらず追加するため、最終的なグラフ密度と一致するとは限りません。
- `num_cycles` は最初に配置を試みる閉路数です。頂点が足りなければ配置数が
  減り、双方向接続や追加辺で生じる閉路を含めた総数はさらに増えることがあります。
- `mixed` は閉路用に選ばれる頂点が3個未満になることがあります。
  閉路の存在は保証せず、連結補完によっても全体の構造は変わります。
- Watts–Strogatz の `p` は辺の**張り替え確率**です。`k` は正の偶数で
  `n` 未満を指定します。既定の `k=4` を使うなら `n>=5` が必要です。
  `p=0` は規則的な円環で、有向化後も円環に沿った閉路を持ちます。
  `ensure_connected=False` では弱連結を保証しません。
  連結な生成に `tries` 回失敗した場合は NetworkX の例外が伝わります。

各関数は `generator` から直接インポートすることもできます。
直接呼び出す場合の引数名と既定値は元の関数に合わせています。
直接の `return_seed` は元と同じく `generate_cyclic_graph` のみで対応しています。

## ファイルの責務

```text
generator/
├── __init__.py            公開する関数の一覧
├── router.py              手法名による振り分け、共通のシード付き戻り値
├── random_connected.py    ランダム連結グラフ
├── dag.py                 有向非巡回グラフ
├── cyclic.py              閉路を明示的に配置するグラフ
├── mixed.py               DAG部分と閉路部分を混在させるグラフ
├── watts_strogatz.py      小世界グラフの生成と有向化
├── lib/
│   ├── types.py           頂点・辺リストの戻り値の型
│   ├── randomness.py      シードの確定、独立した乱数器の作成
│   ├── connectivity.py    幅優先探索による弱連結判定
│   ├── edges.py           未使用の有向辺の確率的な追加
│   └── validation.py      頂点数と確率の共通検証
└── tests/
    └── test_generator.py  既存実装との比較、構造・入口・境界条件の検証
```

新しい手法を追加するときは、`(n, seed=None, ...) -> (vertices, edges)` の
生成関数を新しいファイルに置き、`router.py` の `_GENERATORS` に登録します。

## 既存実装との関係と境界条件

通常の入力では、シードを指定したときの頂点・辺の順序を含め、既存実装の
結果を維持します。`mixed` の連結補完で同じ辺が重複する挙動も維持します。
乱数処理の独立化と入力検証に加え、新しいパッケージでは次を扱います。

- `random` / `dag` / `mixed` は `n>=0` の整数を受け付け、`n=0` では空の
  頂点・辺リストを返します。元の `random` は `n=0` でエラーになっていました。
- `cyclic` は `n>=3`、`num_cycles` は正の整数です。実際に生成できた閉路だけを
  接続することで、要求した閉路数に対して頂点が不足する場合に、元の実装が
  頂点リストに存在しない番号への辺を作る問題を防ぎます。
- `watts_strogatz` は `n>=3`、`tries` は正の整数です。
- 確率はすべて `0<=値<=1` を検証します。

## 実行・検証

リポジトリのルートから、プロジェクトのPython環境と `PYTHONPATH=src` を使います。

```sh
PYTHONPATH=src ./theme2026-saku/bin/python -c 'from generator import generate_graph; print(generate_graph("dag", n=5, seed=42))'
PYTHONPATH=src ./theme2026-saku/bin/python -m pytest src/generator/tests -q -p no:cacheprovider
```
