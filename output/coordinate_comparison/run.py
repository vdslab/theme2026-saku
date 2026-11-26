import json, random
from pathlib import Path
from statistics import median
from time import perf_counter
from generator import generate_graph
from torus_layout import Graph
from torus_layout.coordinates import assign_coordinates
from torus_layout.crossing import reduce_crossings, count_crossings
from torus_layout.layering import assign_layers
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.subdivision import insert_dummy_nodes
from experiments.torus_study.stages import chains_for, coordinate_metrics
from experiments.torus_study.geometry import torus_routes, route_metrics

variants = [
 ('BK', 'brandes_koepf', 4, 0), ('BK 0', 'brandes_koepf', 0, 0),
 ('Blocks', 'brandes_koepf_blocks', 4, 0), ('Blocks 0', 'brandes_koepf_blocks', 0, 0),
 ('Unsplit', 'brandes_koepf_blocks_unsplit', 4, 0), ('Unsplit 0', 'brandes_koepf_blocks_unsplit', 0, 0),
 ('3x3', 'brandes_koepf_3x3', 0, 0), ('QP', 'torus_qp', 0, 0), ('LP', 'torus_lp', 0, 0),
 ('QP bend 1', 'torus_qp', 0, 1), ('LP bend 1', 'torus_lp', 0, 1),
]
cases = [(f,n,s) for f in ('watts_strogatz','dag','mixed','random') for n in (16,32) for s in range(6)]
cases += [('watts_strogatz',25,s) for s in (2401294602,3272298823,2753771603)]
rows, failures = [], []
with use_local_license():
    for family,n,seed in cases:
        case = f'{family}-{n}-{seed}'
        try:
            parameters = {} if family == 'watts_strogatz' else {'edge_prob': 0.09}
            nodes,edges,_=generate_graph(family,n=n,seed=seed,**parameters)
            graph=Graph(tuple(nodes),tuple(edges))
            _, assignment=assign_layers(graph,'diff_square')
            sub=insert_dummy_nodes(graph,assignment)
            crossing=reduce_crossings(sub,unwind=True,prioritize_internal_seams=True)
            chains=chains_for(graph,sub)
            expected=count_crossings(sub,crossing)
        except Exception as e:
            failures.append(dict(case=case,error=str(e)))
            continue
        schedule=variants.copy()
        random.Random(seed).shuffle(schedule)
        for name,method,iterations,bend in schedule:
            row=dict(case=case,family=family,n=n,edges=len(edges),method=name,embedding_crossings=expected)
            try:
                times=[]
                for _ in range(3):
                    t=perf_counter()
                    coords=assign_coordinates(sub,crossing,method=method,smooth_iterations=iterations,bend_weight=bend)
                    times.append((perf_counter()-t)*1000)
                row.update(ms=median(times), **coordinate_metrics(sub,crossing,coords))
                routes,bounds=torus_routes(chains,sub,crossing,coords)
                row.update(route_metrics(routes,bounds))
            except Exception as e:
                row['error']=str(e)
            rows.append(row)
        print(case,flush=True)
        Path('output/coordinate_comparison/results.json').write_text(json.dumps(dict(failures=failures,rows=rows),indent=2))
