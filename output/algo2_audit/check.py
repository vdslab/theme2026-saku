"""Reproduce the reviewed 23/8/5 case without depending on overwritten CLI output."""
import json
from pathlib import Path

from generator import generate_graph
from torus_layout.models import Graph, LayerAssignmentResult, CrossingResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import count_crossings, reduce_crossings, optimize_seam
from torus_layout.crossing.initialization import initial_orders
from torus_layout.crossing.sifting import run_sifting_with_global_guard
from torus_layout.crossing.lib import embedding as emb

out = Path(__file__).resolve().parent
nodes, original_edges, seed = generate_graph('cyclic', 25, seed=3409470963, num_cycles=2, edge_prob=0.005)
expected_edges = [(i, i+1) for i in range(11)] + [(11, 0)]
expected_edges += [(i, i+1) for i in range(12, 23)] + [(23, 12)]
expected_edges += [(5,24),(24,5),(11,15),(9,13),(15,0)]
assert original_edges == expected_edges, (original_edges, expected_edges)
# This is the exact order recorded from the screenshot's result.json before a later CLI run replaced it.
order = {0:[26,8,29], 1:[12,9,30], 2:[13,10,31], 3:[14,11,32], 4:[15,25,24],
         5:[16,0,33], 6:[17,1,34], 7:[18,2,35], 8:[19,3,36], 9:[20,4,37],
         10:[21,5], 11:[22,6,27], 12:[23,7,28]}
ranks = {node: layer for layer,group in order.items() for node in group if node < 25}
flags = {(u,v):ranks[u]>ranks[v] for u,v in original_edges}
graph = insert_dummy_nodes(Graph(tuple(nodes),tuple(original_edges)), LayerAssignmentResult(ranks, flags, 0))
assert {k:set(v) for k,v in graph.layers.items()} == {k:set(v) for k,v in order.items()}
edges = list(graph.graph.edges)
layers = sorted(order)
target_edges = [(26,12),(8,9),(29,30)]
winding = {edge:int(edge in target_edges) for edge in edges}

# Recover complete paths for every original edge, including the two long edges.
paths = {}
original_set = set(nodes)
for first in edges:
    if first[0] not in original_set: continue
    chain = [first]
    while chain[-1][1] not in original_set:
        following = [e for e in edges if e[0] == chain[-1][1]]
        assert len(following) == 1
        chain.append(following[0])
    paths[first[0],chain[-1][1]] = chain
cycles = [list(range(12))+[0], list(range(12,24))+[12], [5,24,5]]

def cycle_totals(psi):
    return [sum(psi.get(edge,0) for u,v in zip(cycle,cycle[1:]) for edge in paths[u,v]) for cycle in cycles]

def state(name, current_order, psi):
    crossing = CrossingResult(current_order,psi)
    return {'stage':name, 'crossings':count_crossings(graph,crossing),
            'nonzero_windings':[[u,v,value] for (u,v),value in psi.items() if value],
            'cycle_winding_sums':cycle_totals(psi)}

report = {'seed':seed,'input_edges':original_edges,'original_order':order,'original_winding':[[u,v,value] for (u,v),value in winding.items()], 'stages':[]}
report['stages'].append(state('saved_result',order,winding))
assert report['stages'][-1]['crossings'] == 0

# Algorithm 2 on the two layers only: no outgoing edges can carry the twist onwards.
local_order = {0:list(order[0]),1:list(order[1])}
local_psi = {edge:winding[edge] for edge in target_edges}
emb.postprocess_two_layer_rotation(0,1,local_order,local_psi,target_edges)
report['isolated_two_layer'] = {'before':[1,1,1], 'after':[local_psi[e] for e in target_edges], 'same_order':local_order=={0:order[0],1:order[1]}}
assert all(value == 0 for value in local_psi.values())

# The same single call with all incident edges present.
current_order = emb.copy_order(order)
current_psi = dict(winding)
for fixed,free in emb.forward_layer_pairs(layers):
    emb.postprocess_two_layer_rotation(fixed,free,current_order,current_psi,layers and edges)
    report['stages'].append(state(f'rotation_{fixed}_to_{free}',current_order,current_psi))
    assert cycle_totals(current_psi) == [1,1,1]
report['full_sweep_returns_to_start'] = current_order==order and current_psi==winding
for _ in range(5):
    emb.postprocess_sifting_rotations(current_order,current_psi,layers,edges)
report['six_sweeps_return_to_start'] = current_order==order and current_psi==winding

# Check current production processing, including whether the guard rolls back.
actual_order = initial_orders(graph.layers,layers,edges)[0]
actual_psi = emb.compute_winding_numbers(edges,actual_order,graph.layers,layers)
report['production'] = [state('initialization',actual_order,actual_psi)]
run_sifting_with_global_guard(actual_order,actual_psi,layers,edges,5,dummy_nodes=graph.dummy_nodes)
report['production'].append(state('after_sifting',actual_order,actual_psi))
before_order,before_psi = emb.copy_order(actual_order),dict(actual_psi)
before_count = count_crossings(graph,CrossingResult(actual_order,actual_psi))
emb.postprocess_sifting_rotations(actual_order,actual_psi,layers,edges)
report['production'].append(state('after_algo2',actual_order,actual_psi))
rollback = count_crossings(graph,CrossingResult(actual_order,actual_psi)) > before_count
if rollback: actual_order,actual_psi = before_order,before_psi
final = optimize_seam(graph,CrossingResult(actual_order,actual_psi))
report['production'].append(state('after_guard_and_seam_dp',final.order,final.winding_numbers))
report['guard_rollback'] = rollback
report['production_matches_screenshot'] = final.order==order and final.winding_numbers==winding
api = reduce_crossings(graph,rounds=5,unwind=False)
assert api == final

# Remove the common turn from this edge bundle directly (a different allowed operation).
removed = dict(winding)
for edge in target_edges: removed[edge] -= 1
report['common_bundle_turn_removed'] = state('bundle_shift_minus_one',order,removed)
assert report['common_bundle_turn_removed']['crossings'] == 0
assert cycle_totals(removed) == [0,0,0]
(out/'trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Isolated Algorithm 2:',report['isolated_two_layer'])
print('First full-graph rotation:', report['stages'][1])
print('Full sweep returns to start:',report['full_sweep_returns_to_start'])
print('Six sweeps return to start:',report['six_sweeps_return_to_start'])
print('Production guard rollback:',rollback)
print('Production matches screenshot:',report['production_matches_screenshot'])
for row in report['production']: print(row)
print('Direct bundle shift:',report['common_bundle_turn_removed'])
print('Trace:',out/'trace.json')
