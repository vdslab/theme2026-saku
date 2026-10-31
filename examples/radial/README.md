# Radial Sugiyama framework example

This directory contains a self-contained radial layered-graph drawing.  It
does not import implementation code from `src` or `examples/sugiyama`.

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
MPLCONFIGDIR=/tmp/theme2026-saku-matplotlib \
  ./theme2026-saku/bin/python -m examples.radial.main \
  --size 20 --seed 7 --neighbors 4 --prob 0.25
```

Save without opening a window:

```sh
MPLCONFIGDIR=/tmp/theme2026-saku-matplotlib \
  ./theme2026-saku/bin/python -m examples.radial.main \
  --size 20 --seed 7 --save radial-example.png --no-show
```

Reversed feedback edges are shown as red dashed arrows.  Gray dashed circles
are level guides; dummy vertices are used only as hidden bend points.

