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
元の examples は既存の呼び出しとの互換性のため、そのまま残しています。
