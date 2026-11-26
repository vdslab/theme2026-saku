"""Time disjoint crossing-reduction stages without timing graph preparation."""
import contextlib
import io
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch
import runpy

from generator import generate_graph
from torus_layout.models import Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import api, sifting

with contextlib.redirect_stdout(io.StringIO()):
    audited = runpy.run_path('output/algo2_audit/check.py')
cases = [('screenshot_cyclic25', audited['graph'])]
for n,layer_count in ((50,5),(100,10)):
    nodes,edges,_ = generate_graph('watts_strogatz', n, k=4, p=0.8, seed=0)
    ranks = {node:node//(n//layer_count) for node in nodes}
    # Controlled proper-hierarchy input; this is not an optimized layering benchmark.
    edges = [edge for edge in edges if ranks[edge[0]] != ranks[edge[1]]]
    graph = Graph(tuple(nodes),tuple(edges))
    assignment = LayerAssignmentResult(ranks,{e:ranks[e[0]]>ranks[e[1]] for e in edges},0)
    cases.append((f'ws_derived_{n}_fixed_{layer_count}_layers',insert_dummy_nodes(graph,assignment)))

results=[]
for name,graph in cases:
    started=perf_counter()
    api.reduce_crossings(graph,rounds=5)
    warm_seconds=perf_counter()-started
    print(name,'prepared',len(graph.graph.nodes),'nodes',len(graph.graph.edges),'segments','warmup',round(warm_seconds,3),flush=True)
    trials=[]
    for repeat in range(3):
        elapsed={}
        calls={}
        def timer(label,function):
            def run(*args,**kwargs):
                started=perf_counter()
                try: return function(*args,**kwargs)
                finally:
                    elapsed[label]=elapsed.get(label,0)+perf_counter()-started
                    calls[label]=calls.get(label,0)+1
            return run
        with contextlib.ExitStack() as stack:
            for module,attribute,label in (
                (api,'initial_orders','initial_order'),
                (api,'compute_winding_numbers','initial_winding'),
                (api,'run_sifting_with_global_guard','sifting_including_guard'),
                (sifting,'sift_two_layer_pair','local_sifting'),
                (sifting,'count_all_crossings','guard_global_recount'),
                (api,'postprocess_sifting_rotations','algo2'),
                (api,'count_all_crossings','rotation_checks'),
                (api,'optimize_seam','seam_dp'),
            ):
                stack.enter_context(patch.object(module,attribute,timer(label,getattr(module,attribute))))
            started=perf_counter()
            result=api.reduce_crossings(graph,rounds=5)
            total=perf_counter()-started
        elapsed['guard_total_overhead']=elapsed['sifting_including_guard']-elapsed['local_sifting']
        trials.append({'seconds':elapsed,'calls':calls,'total_seconds':total})
        print(name,'trial',repeat+1,'total',round(total,3),'local %',round(100*elapsed['local_sifting']/total,1),'guard %',round(100*elapsed['guard_total_overhead']/total,1),'DP %',round(100*elapsed['seam_dp']/total,1),flush=True)
    summary={'case':name,'original_nodes':len(graph.original_nodes),'subdivided_nodes':len(graph.graph.nodes),'segments':len(graph.graph.edges),'layers':len(graph.layers),
             'median_total_seconds':median(t['total_seconds'] for t in trials),
             'median_stage_seconds':{key:median(t['seconds'][key] for t in trials) for key in trials[0]['seconds']},
             'median_stage_percent':{key:median(100*t['seconds'][key]/t['total_seconds'] for t in trials) for key in trials[0]['seconds']},
             'calls_per_trial':trials[0]['calls'],'trials':trials}
    results.append(summary)
    Path('output/crossing_profile/results.json').write_text(json.dumps(results,indent=2)+'\n')
print('Saved output/crossing_profile/results.json',flush=True)
