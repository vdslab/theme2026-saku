# Radial Sugiyama framework example

This package was ported from `examples/radial`. It is self-contained and
does not depend on `main`, `torus_layout`, or either examples package.

The pipeline is split into independent phases:

1. `random_graph.py` generates and reproducibly orients a Watts--Strogatz graph.
2. `cycle_removal.py` reverses feedback edges to obtain a DAG.
3. `layer_assignment.py` places sinks on the outer ring and predecessors inward.
4. `dummy_insertion.py` splits long edges at every intermediate ring.
5. `crossing_reduction.py` optimizes cyclic orders with circular barycenters,
   rotations, and vertex sifting; it also assigns edge winding numbers.
6. `coordinate_assignment.py` places each level on a concentric circle.
7. `drawing.py` joins proper segments into outward-monotone spiral routes.

Run from the repository root:

```sh
PYTHONPATH=src MPLCONFIGDIR=/tmp/theme2026-saku-matplotlib \
  ./theme2026-saku/bin/python -m radial_layout \
  --size 20 --seed 7 --neighbors 4 --prob 0.25
```

Save without opening a window:

```sh
PYTHONPATH=src MPLCONFIGDIR=/tmp/theme2026-saku-matplotlib \
  ./theme2026-saku/bin/python -m radial_layout \
  --size 20 --seed 7 --save radial-example.png --no-show
```

Reversed feedback edges are shown as red dashed arrows.  Gray dashed circles
are level guides; dummy vertices are used only as hidden bend points.


## Import / 実行方法

`PYTHONPATH=src` を指定し、`radial_layout` から各処理を import できます。
CLI は `-m radial_layout` または `-m radial_layout.main` で実行します。
`main.py` の直接実行には対応しません。
移植元の `examples/radial` は削除済みです。import は `radial_layout` を使用してください。

## 共通処理と手法固有の処理

閉路除去・DAG走査・長辺分割は `layout_common`、乱数グラフ生成は
`generator.random_oriented_watts_strogatz` を使用します。
交差数計算は辺対の計算を含め、このパッケージ専用の実装を使用します。
階層割当の方針、交差削減の探索、座標割当、描画はこのパッケージに残しています。
依存関係と分離理由は [layout_common/README.md](../layout_common/README.md) を参照してください。

## 既定値の変更

この方式のCLI入力、交差削減の反復数、同心円の間隔、描画設定は
[`constants.py`](constants.py) にまとめています。
`DEFAULT_ROUNDS` が交差削減回数、`DEFAULT_INNER_RADIUS` が最内周の半径、
`DEFAULT_LAYER_GAP` が層間隔です。変更は次回のプロセス起動から反映されます。
CLI引数やAPI引数の明示指定が優先されます。共有生成器そのものの関数既定値は変更しません。
