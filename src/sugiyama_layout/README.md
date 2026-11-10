# 平面上の杉山フレームワークの実装例

このパッケージは `examples/sugiyama` から移植した独立実装です。
既存の `src/main.py`、`torus_layout`、examples には依存しません。
乱数シードに基づいて生成・方向付けした Watts--Strogatz グラフを、通常の
ユークリッド平面上に描画します。最初のレイヤーを左端に置き、後続の
レイヤーを右方向へ並べます。

コードは次の処理段階に分かれています。

1. `random_graph.py` は NetworkX の `watts_strogatz_graph` を呼び出し、
   再現可能な方法で各辺に向きを与えます。
2. `cycle_removal.py` はフィードバック辺を一時的に反転し、循環を除去します。
3. `layer_assignment.py` は最長経路に基づいて各頂点のランクを割り当てます。
4. `dummy_insertion.py` は複数レイヤーにまたがる長い辺を、隣接レイヤー間の
   区間に分割します。
5. `crossing_reduction.py` は中央値スイープと隣接頂点の交換を適用し、
   辺の交差を削減します。
6. `coordinate_assignment.py` は平面向けの Brandes--Köpf 法で座標を
   割り当てます。
7. `drawing.py` は辺を元の向きに戻し、`plt.show()` を呼び出して描画します。

リポジトリのルートから次のように実行します。

```sh
PYTHONPATH=src MPLCONFIGDIR=/tmp/theme2026-saku-matplotlib \
  ./theme2026-saku/bin/python -m sugiyama_layout \
  --size 20 --seed 7 --neighbors 4 --prob 0.25
```

`--neighbors` はリング上の近傍数 `k` で、偶数を指定します。`--prob` は
Watts--Strogatz グラフの辺を張り替える確率 `p` です。画像ファイルへの保存は
行いません。

## 使用しているアルゴリズム

各処理段階では、杉山フレームワークの実装で一般的に使われている、確立された
アルゴリズムを採用しています。

- 循環除去：Eades--Lin--Smyth の貪欲フィードバック辺集合ヒューリスティック
- レイヤー割当：最長経路レイヤリング
- 正規化：途中の各レイヤーへのダミー頂点の挿入
- 交差削減：交互方向の中央値スイープと隣接頂点の交換
- 座標割当：4方向の Brandes--Köpf 法

各段階で採用している手法は、1981年の論文に記載された個々のヒューリスティックを
そのまま再実装したものではなく、現代の実装で一般的に使われている手法です。

## Import / 実行方法

`PYTHONPATH=src` を指定し、`sugiyama_layout` から各処理を import できます。
CLI は `-m sugiyama_layout` または `-m sugiyama_layout.main` で実行します。
`main.py` の直接実行には対応しません。
移植元の `examples/sugiyama` は削除済みです。import は `sugiyama_layout` を使用してください。

## 共通処理と手法固有の処理

閉路除去・DAG走査・長辺分割は `layout_common`、乱数グラフ生成は
`generator.random_oriented_watts_strogatz` を使用します。
交差数計算は辺対の計算を含め、このパッケージ専用の実装を使用します。
階層割当の方針、交差削減の探索、座標割当、描画はこのパッケージに残しています。
依存関係と分離理由は [layout_common/README.md](../layout_common/README.md) を参照してください。
