"""Controlled comparisons on the complete pipeline and on fixed intermediate states."""

from itertools import combinations, permutations, product
from math import prod
from random import Random
from statistics import median
from time import perf_counter
from unittest.mock import patch

import gurobipy as gp

from old_torus_layout.lib.insert_dummy_node import insert_dummy_node as old_subdivision
from torus_layout import constants
from torus_layout.coordinates import api
from torus_layout.coordinates.periodic import drawing_period
from torus_layout.crossing import count_crossings, count_seam_segments, optimize_seam, reduce_crossings, unwind_levels
from torus_layout.crossing.lib.embedding import compute_winding_numbers, rotate_layer_preserving_embedding
from torus_layout.layering import balance_layers, find_minimum_configuration
from torus_layout.layering.lib.model import add_layer_variables_and_constraints
from torus_layout.layering.lib.solver import create_gurobi_env
from torus_layout.models import CoordinateResult, CrossingResult, Graph, LayerAssignmentResult, PipelineConfig
from torus_layout.subdivision import insert_dummy_nodes

from .framework import graphviz, repository_baseline, torus
from .geometry import route_metrics, torus_routes
from .stages import (assignment_metrics, attempt_time, coordinate_metrics, copied, fixed_count, initialize,
                     prepared, rotate, sift, subdivision_metrics, uniform_coordinates)

ROUNDS = constants.DEFAULT_ROUNDS


def setup(graph, run):
    return run("setup", lambda: ({}, prepared(graph)))


def display_metrics(sub, paths, embedding, coords=None, *, geometry=True):
    coords = api.assign_coordinates(sub, embedding) if coords is None else coords
    routes, bounds = torus_routes(paths, sub, embedding, coords)
    return route_metrics(routes, bounds, geometry=geometry)


def topology(trial, run):
    graph = trial.case.graph
    run("torus", lambda: torus(graph))
    run("dot", lambda: graphviz(graph, run.args.dot, 8))


def public(trial, run):
    graph = trial.case.graph
    run("torus", lambda: torus(graph))
    run("dot", lambda: graphviz(graph, run.args.dot, 8))
    run("sugiyama", lambda: repository_baseline(graph), budget=8)


def budget(trial, run):
    graph = trial.case.graph
    for variant, method in (
        ("torus", lambda: torus(graph)), ("dot", lambda: graphviz(graph, run.args.dot, 8)),
        ("sugiyama", lambda: repository_baseline(graph)), ("radial", lambda: repository_baseline(graph, radial=True)),
    ):
        # Completion under the lower budget follows from the independent rerun's wall measurement.
        run(variant, method, budget=run.args.wall_seconds)


def proper(trial):
    graph = trial.case.graph
    width = trial.extra["width"]
    ranks = {node: node//width for node in graph.nodes}
    flags = {(u,v):ranks[u]>ranks[v] for u,v in graph.edges}
    return insert_dummy_nodes(graph, LayerAssignmentResult(ranks, flags, 0))


def pair_count(edges, indices, windings, width):
    count = 0
    for i, j in combinations(range(len(edges)), 2):
        a, b = edges[i]
        u, v = edges[j]
        first = indices[a]-indices[u]
        last = indices[b]-indices[v] + width*(windings[i]-windings[j])
        low, high = sorted((first,last))
        count += max(0,(high-1)//width - low//width)
    return count


def bounded_minimum(sub, limit):
    width = len(sub.layers[0])
    layers = sorted(sub.layers)
    edge_sets = [[(u,v) for u,v in sub.graph.edges if u in sub.layers[layer]] for layer in layers]
    orders = [list(permutations(sub.layers[layer])) for layer in layers]
    costs = []
    for i, edges in enumerate(edge_sets):
        right = orders[(i+1) % len(layers)]
        candidates = list(product(range(-limit,limit+1), repeat=len(edges)))
        table = {}
        for left_order, right_order in product(orders[i], right):
            indices = {node: rank for order in (left_order,right_order) for rank,node in enumerate(order)}
            table[left_order,right_order] = min(pair_count(edges,indices,w,width) for w in candidates)
        costs.append(table)
    return min(sum(costs[i][orders_[i],orders_[(i+1)%len(layers)]] for i in layers)
               for orders_ in product(*orders))


def winding(trial, run):
    sub = proper(trial)
    for level in (0,1):
        run(f"oracle_{level}", lambda: ({"crossings":bounded_minimum(sub, level)},None))
    start = initialize(sub, True)
    for free in (False,True):
        def compare():
            result = sift(sub,start,ROUNDS,winding=free)
            values = [result.winding_numbers[e] for e in sub.graph.edges]
            within = all(max(local)-min(local)<=2 for layer in sub.layers.values()
                         if (local := [result.winding_numbers[e] for e in sub.graph.edges if e[0] in layer]))
            return {"crossings":count_crossings(sub,result), "max_abs_winding":max(map(abs,values)),
                    "within_bound_by_common_shift":within}, None
        run("current_free" if free else "fixed_at_initial",compare)


def sifting(trial, run):
    base = setup(trial.case.graph,run)
    if base is None:
        return
    _, _, sub, paths = base
    start = initialize(sub, True)
    candidates = {}
    for variant, seed, free, rounds in (("current",None,True,ROUNDS), ("fixed",None,False,ROUNDS),
            ("one_round",None,True,1), ("shuffle_0",812,True,ROUNDS), ("shuffle_1",813,True,ROUNDS),
            ("shuffle_2",814,True,ROUNDS)):
        def compare():
            order = copied(start)
            if seed is not None:
                rng = Random(seed)
                for group in order.order.values():
                    rng.shuffle(group)
                order = CrossingResult(order.order, compute_winding_numbers(
                    list(sub.graph.edges), order.order, sub.layers, sorted(sub.layers)))
            outcome, seconds = attempt_time(sift,sub,order,rounds,winding=free)
            metrics = {"crossings":count_crossings(sub,outcome), "search_seconds":seconds}
            return metrics, (outcome, metrics)
        record = run(variant, compare)
        if record:
            candidates[variant]=record
    for variant, keys in (("fixed_or_free",("current","fixed")),("best_of_four",("current","shuffle_0","shuffle_1","shuffle_2"))):
        if not all(key in candidates for key in keys):
            continue
        best, score = min((candidates[key] for key in keys), key=lambda r:r[1]["crossings"])
        run(variant, lambda: ({"crossings":score["crossings"], "search_seconds":sum(
            candidates[key][1]["search_seconds"] for key in keys),
            **display_metrics(sub,paths,rotate(sub,best,True))},None))


def geometry(trial, run):
    sub = proper(trial)
    graph = trial.case.graph
    rng = Random(trial.case.seed)
    order = {k:list(v) for k,v in sub.layers.items()}
    for group in order.values():
        rng.shuffle(group)
    embedding = CrossingResult(order,{e:rng.randrange(-2,3) for e in sub.graph.edges})
    paths, _ = subdivision_metrics(graph,sub)
    coords = uniform_coordinates(sub,embedding,0)

    def evaluate(result, coordinates):
        return {"crossings":count_crossings(sub,result),
                **display_metrics(sub,paths,result,coordinates)},None

    run("original", lambda:evaluate(embedding,coords))
    shifted = copied(embedding)
    for layer in shifted.order:
        rotate_layer_preserving_embedding(layer,rng.randrange(-4,5),
                                          shifted.order,shifted.winding_numbers,list(sub.graph.edges))
    run("layer_cut_rotation", lambda:evaluate(shifted,uniform_coordinates(sub,shifted,0)))
    # Translate all y values by 43% of the period and transfer tile indices to windings.
    low = -coords.period/max(map(len,order.values()))/2
    tiles = {u:int((y+0.43*coords.period-low)//coords.period) for u,(x,y) in coords.positions.items()}
    moved = CoordinateResult({u:(x,y+0.43*coords.period-tiles[u]*coords.period)
                               for u,(x,y) in coords.positions.items()},coords.period)
    moved_order = {layer:sorted(nodes,key=lambda u:moved.positions[u][1]) for layer,nodes in order.items()}
    moved_embedding = CrossingResult(moved_order,{(u,v):w+tiles[v]-tiles[u]
                         for (u,v),w in embedding.winding_numbers.items()})
    run("global_seam_translation",lambda:evaluate(moved_embedding,moved))


def subdivision(trial, run):
    graph, height = trial.case.graph, trial.extra["height"]
    ranks = {u:u%height for u in graph.nodes}
    flags = {(u,v):ranks[u]>ranks[v] for u,v in graph.edges}
    assignment = LayerAssignmentResult(ranks,flags,0)
    old, new = [], []
    reference = None
    same = True
    for i in range(9):
        def legacy():
            return old_subdivision(list(graph.nodes),list(graph.edges),assignment.layers,flags)
        def current():
            result=insert_dummy_nodes(graph,assignment)
            return (list(result.graph.nodes),list(result.graph.edges),result.layers,result.torus_flags,result.weights)
        if i%2:
            reference,b=attempt_time(current)
            original,a=attempt_time(legacy)
        else:
            original,a=attempt_time(legacy)
            reference,b=attempt_time(current)
        old.append(a); new.append(b)
        same = same and original==reference
    for variant, elapsed in (("legacy",old),("indexed",new)):
        run(variant,lambda:({"seconds":median(elapsed), "repetitions":9, "same_output":same,
                             "dummy_nodes":len(reference[0])-len(graph.nodes),
                             "segments":len(reference[1]), "per_trial_seconds":elapsed},None))


def trial_rank(graph, layers, wraps, method, work_limit, seed=None):
    nodes = list(graph.nodes)
    edges = list(set(graph.edges))
    with create_gurobi_env() as env, gp.Model(name=f"Validation_{method}", env=env) as model:
        y,t = add_layer_variables_and_constraints(model,nodes,edges,layers,dict.fromkeys(edges,1),wraps)
        spans = [y[v]-y[u]+layers*t[u,v] for u,v in edges]
        expression = gp.quicksum(x*x for x in spans) if method=="square" else gp.quicksum(spans)
        model.setObjective(expression,gp.GRB.MINIMIZE)
        model.Params.WorkLimit = work_limit
        if seed is not None:
            model.setAttr("Start",list(y.values()),[seed.node_to_layer[u] for u in nodes])
            model.setAttr("Start",list(t.values()),[int(seed.torus_flags[e]) for e in edges])
        model.optimize()
        common = {"solutions":model.SolCount, "model_status":model.Status, "work_units":model.Work,
                  "solver_seconds":model.Runtime, "work_limit":work_limit, "variables":model.NumVars}
        if model.SolCount < 1:
            return {**common, "status":"no_incumbent"},None
        ranks = {u:round(y[u].X) for u in nodes}
        flags = {edge:t[edge].X>.5 for edge in edges}
        result = LayerAssignmentResult(ranks,flags,model.Runtime)
        details = assignment_metrics(graph,result,layers,wraps)
        return {**common, **details, "optimal":int(model.Status==gp.GRB.OPTIMAL),
                "reported_gap":float(model.MIPGap)},result


def ranks(trial, run):
    graph = trial.case.graph

    def search():
        result = find_minimum_configuration(graph)
        if result.layer_count is None:
            return {"status":"no_solution"},None
        return {"layers":result.layer_count, "rank_wrap_edges":result.torus_count},result

    configuration = run("setup_configuration",search)
    if configuration is None:
        return
    layers,wraps = configuration.layer_count,configuration.torus_count

    def feasible():
        result = fixed_count(graph,layers)
        if result is None or result[1]!=wraps:
            return {"status":"fixed_wrap_target_not_recovered"},None
        return assignment_metrics(graph,result[0],layers,wraps),result[0]

    start = run("setup_incumbent",feasible)
    for work in (.03, .25):
        for variant, use in (("cold",None),("warm",start)):
            if variant=="warm" and use is None:
                continue
            run(f"{variant}_{work}",lambda:trial_rank(graph,layers,wraps,"square",work,use))
    for variant,method,count in (("linear_diff","linear",layers),
                                  ("square_diff","square",layers),
                                  ("square_two_extra_layers","square",min(len(graph.nodes),layers+2))):
        assignment=run(variant,lambda:trial_rank(graph,count,wraps,method,.25))
        if assignment is not None:
            def complete():
                sub=insert_dummy_nodes(graph,assignment)
                paths,details=subdivision_metrics(graph,sub)
                if details["unit_span_violations"]:
                    return {**details,"status":"invalid_subdivision"},None
                crossing=reduce_crossings(sub)
                return {**details,**display_metrics(sub,paths,crossing)},None
            run(f"{variant}_drawing",complete)


def raw_seam_stats(paths, embedding):
    numbers = embedding.winding_numbers
    chains = [[numbers.get(edge,0) for edge in zip(path,path[1:])] for path in paths.values()]
    return {"seam_segments":sum(w!=0 for chain in chains for w in chain),
            "seam_edges":sum(any(chain) for chain in chains),
            "seam_events":sum(abs(w) for chain in chains for w in chain)}


def compare_cuts(paths, rotated):
    ranks = {node:(layer,i) for layer, order in rotated.order.items() for i,node in enumerate(order)}
    path_segments = [list(zip(path,path[1:])) for path in paths.values()]
    ranges = {layer:range(max(1,len(nodes))) for layer,nodes in rotated.order.items()}
    combinations_count=prod(map(len,ranges.values()))
    if combinations_count>30_000:
        return {"status":"above_enumeration_cap","cut_combinations":combinations_count},None
    segment_best=(float("inf"),float("inf"))
    edge_best=(float("inf"),float("inf"))
    for cuts in product(*ranges.values()):
        offsets=dict(zip(ranges,cuts))
        shift={node:i<offsets[layer] for node,(layer,i) in ranks.items()}
        edge_count=0
        segments=0
        for chain in path_segments:
            count=sum(rotated.winding_numbers.get((u,v),0)+shift[u]-shift[v]!=0 for u,v in chain)
            edge_count+=count>0
            segments+=count
        segment_best=min(segment_best,(segments,edge_count))
        edge_best=min(edge_best,(edge_count,segments))
    return {"cut_combinations":combinations_count, "segment_minimum":segment_best[0],
            "edges_at_segment_minimum":segment_best[1], "original_edge_minimum":edge_best[0],
            "segments_at_original_edge_minimum":edge_best[1]},None


def seams(trial, run):
    base=setup(trial.case.graph,run)
    if base is None:
        return
    _,_,sub,paths=base

    def candidates():
        rotated=reduce_crossings(sub,unwind=False,optimize_seams=False)
        dp_only=optimize_seam(sub,rotated)
        early=unwind_levels(sub,rotated)
        first=optimize_seam(sub,early)
        inner=unwind_levels(sub,rotated,include_non_inner=False)
        cut_first=first if inner==early else optimize_seam(sub,inner)
        late=unwind_levels(sub,cut_first)
        second=optimize_seam(sub,late) if late!=cut_first else cut_first
        current=min((first,second),key=lambda candidate:count_seam_segments(sub,candidate))
        return {},(rotated,dp_only,current,first,second)

    options=run("setup_candidates",candidates)
    if options is None:
        return
    rotated,dp_only,current,first,second=options
    # Tie-breaking compares the same candidates in a declared stable order.
    pool=(current,dp_only,first,second)

    def score(candidate,key):
        raw=raw_seam_stats(paths,candidate)
        return tuple(raw[field] for field in key)

    guarded=min((current,dp_only),key=lambda x:score(x,("seam_segments",)))
    lexicographic=min(pool,key=lambda x:score(x,("seam_segments","seam_edges","seam_events")))
    original_first=min(pool,key=lambda x:score(x,("seam_edges","seam_segments","seam_events")))
    for name,candidate in (("off",rotated),("dp_only",dp_only),("current",current),
                           ("guarded",guarded),("segments_then_edges",lexicographic),
                           ("edges_then_segments",original_first)):
        run(name,lambda:({**raw_seam_stats(paths,candidate),
                         **display_metrics(sub,paths,candidate)},None))
    if trial.extra.get("tiny"):
        run("cut_oracle",lambda:compare_cuts(paths,rotated))


def coordinates(trial, run):
    base=setup(trial.case.graph,run)
    if base is None:
        return
    _,_,sub,paths=base

    def embedding():
        return {},reduce_crossings(sub)

    crossing=run("setup_embedding",embedding)
    if crossing is None:
        return
    period=drawing_period(crossing.order,1.)
    for factor in (1.,1.25,1.6):
        methods=(("bk_k0","brandes_koepf",0,0.),("bk_k4","brandes_koepf",4,0.),
                 ("bk_k10","brandes_koepf",10,0.),("lp_w0","torus_lp",0,0.),
                 ("lp_w025","torus_lp",0,.25),("lp_w1","torus_lp",0,1.),
                 ("lp_w4","torus_lp",0,4.))
        for name,method,smoothing,bend in methods:
            def compute():
                with patch.object(api,"drawing_period",return_value=period*factor):
                    coords, seconds=attempt_time(api.assign_coordinates,sub,crossing,method=method,
                                                 smooth_iterations=smoothing,bend_weight=bend)
                return {"seconds":seconds,"period_factor":factor,
                        **coordinate_metrics(sub,crossing,coords),
                        **display_metrics(sub,paths,crossing,coords)},None
            run(f"{name}_p{factor:g}",compute)

    def replicate():
        coords, seconds=attempt_time(api.assign_coordinates,sub,crossing,method="brandes_koepf_3x3")
        return {"seconds":seconds,"period_factor":coords.period/period,
                **coordinate_metrics(sub,crossing,coords),
                **display_metrics(sub,paths,crossing,coords)},coords

    replica = run("replica_3x3",replicate)
    if replica:
        def matched():
            with patch.object(api,"drawing_period",return_value=replica.period):
                coords,seconds=attempt_time(api.assign_coordinates,sub,crossing)
            return {"seconds":seconds,"period_factor":coords.period/period,
                    **coordinate_metrics(sub,crossing,coords),
                    **display_metrics(sub,paths,crossing,coords)},None
        run("matched_period_bk",matched)


def scaling(trial, run):
    graph=trial.case.graph

    def search():
        result=find_minimum_configuration(graph)
        if result.layer_count is None:
            return {"status":"no_solution"},None
        return {"layers":result.layer_count,"rank_wrap_edges":result.torus_count},result

    configuration=run("setup_configuration",search)
    if configuration is None:
        return
    layers,wraps=configuration.layer_count,configuration.torus_count
    for name in ("diff_square","diff"):
        def rank():
            assignment,seconds=attempt_time(balance_layers,graph,wraps,layers,name)
            if not assignment.node_to_layer:
                return {"status":"no_incumbent"},None
            return {"seconds":seconds,"rank_variables":len(graph.nodes)+len(graph.edges),
                    **assignment_metrics(graph,assignment,layers,wraps)},assignment
        assignment=run(f"{name}_rank",rank)
        if assignment is None:
            continue

        def finish():
            sub=insert_dummy_nodes(graph,assignment)
            paths,details=subdivision_metrics(graph,sub)
            if details["unit_span_violations"]:
                return {**details,"status":"invalid_subdivision"},None
            embedding,elapsed=attempt_time(reduce_crossings,sub,rounds=1)
            return {**details, "crossing_seconds":elapsed, "rounds":1,
                    "crossings":count_crossings(sub,embedding),
                    **display_metrics(sub,paths,embedding,geometry=False)},None
        run(f"{name}_drawing_one_round",finish)


def public_retry(trial, run):
    graph=trial.case.graph
    run("native",lambda:torus(graph))
    run("one_round_linear",lambda:torus(graph,PipelineConfig(rounds=1,balance_method="diff")))


def seam_stress(trial, run):
    graph=trial.case.graph
    ranks=dict(enumerate(trial.extra["specified_ranks"]))
    flags={(u,v):ranks[u]>ranks[v] for u,v in graph.edges}
    sub=insert_dummy_nodes(graph,LayerAssignmentResult(ranks,flags,0))
    paths,_=subdivision_metrics(graph,sub)
    rng=Random(trial.case.seed)
    order={layer:list(nodes) for layer,nodes in sub.layers.items()}
    for layer in order.values():
        rng.shuffle(layer)
    winding={edge:rng.randrange(-2,3) for edge in sub.graph.edges}
    start=CrossingResult(order,winding)
    run("cut_oracle",lambda:compare_cuts(paths,start))
    def check_dp():
        result=optimize_seam(sub,start)
        return raw_seam_stats(paths,result),None
    run("dp",check_dp)


def strip_crossings(sub, embedding, coordinates):
    """Independent intersections on lifted strips, without rectangle clipping."""
    from math import ceil, floor

    group={u:layer for layer,nodes in sub.layers.items() for u in nodes}
    strips={layer:[] for layer in sub.layers}
    for u,v in sub.graph.edges:
        strips[group[u]].append((u,v,embedding.winding_numbers.get((u,v),0)))
    heights={u:point[1]/coordinates.period for u,point in coordinates.positions.items()}
    count=0
    for edges in strips.values():
        for (u,v,w),(a,b,z) in combinations(edges,2):
            interval=(heights[u]-heights[a],heights[v]-heights[b]+w-z)
            low,high=sorted(interval)
            count+=max(0,ceil(high)-floor(low)-1)
    return count


def coordinate_audit(trial,run):
    base=setup(trial.case.graph,run)
    if base is None:
        return
    _,_,sub,paths=base
    embedding=run("setup_embedding",lambda:({},reduce_crossings(sub)))
    if embedding is None:
        return
    expected=count_crossings(sub,embedding)
    minimum=drawing_period(embedding.order,1.)
    for factor in (1.,1.25,1.6):
        for variant,method,smooth,bend in (("bk","brandes_koepf",4,0),("lp","torus_lp",0,0),
                                            ("lp_bend","torus_lp",0,1)):
            def check():
                with patch.object(api,"drawing_period",return_value=minimum*factor):
                    coords=api.assign_coordinates(sub,embedding,method=method,
                                                  smooth_iterations=smooth,bend_weight=bend)
                return {"embedding_crossings":expected, "strip_crossings":strip_crossings(sub,embedding,coords),
                        **coordinate_metrics(sub,embedding,coords),
                        **display_metrics(sub,paths,embedding,coords)},None
            run(f"{variant}_p{factor:g}",check)
