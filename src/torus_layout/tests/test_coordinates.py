import copy
import random
import pytest
from torus_layout import Graph
from torus_layout.models import LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import reduce_crossings
from torus_layout.coordinates import assign_coordinates
from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates as legacy

@pytest.mark.parametrize("seed",range(5))
@pytest.mark.parametrize("gap",[0.5,1.0,2.0])
@pytest.mark.parametrize("iterations",[0,4])
def test_coordinates_match_legacy(seed,gap,iterations):
    rng=random.Random(seed)
    nodes=tuple(range(12))
    ranks={node:node//4 for node in nodes}
    edges=tuple((u,v) for u in nodes for v in nodes if ranks[u]!=ranks[v] and rng.random()<0.18)
    flags={edge:ranks[edge[0]]>ranks[edge[1]] for edge in edges}
    divided=insert_dummy_nodes(Graph(nodes,edges),LayerAssignmentResult(ranks,flags,0))
    crossing=reduce_crossings(divided,1)
    before=copy.deepcopy((divided,crossing))
    expected=legacy(crossing.order,divided.layers,list(divided.graph.edges),divided.torus_flags,crossing.winding_numbers,gap,iterations,nodes)
    actual=assign_coordinates(divided,crossing,min_gap=gap,smooth_iterations=iterations)
    assert actual.positions.keys()==expected.keys()
    for node,position in expected.items():
        assert actual.positions[node]==pytest.approx(position,abs=1e-10)
    assert actual.period==max(len(ns) for ns in crossing.order.values())*gap
    assert (divided,crossing)==before


def test_existing_coordinate_regressions_with_new_implementation(monkeypatch):
    import importlib.util
    from pathlib import Path
    from torus_layout.coordinates.api import compute_positions
    path=Path(__file__).resolve().parents[2]/"test/test_coordinate_assignment.py"
    spec=importlib.util.spec_from_file_location("coordinate_regressions",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module,"assign_torus_brandes_koepf_coordinates",compute_positions)
    for name in dir(module):
        if name.startswith("test_"):
            getattr(module,name)()
