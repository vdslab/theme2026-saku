"""Held-out, matched, public, and representative inputs for the validation study."""

from dataclasses import dataclass, field
from itertools import product
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from zipfile import ZipFile

import networkx as nx

from torus_layout.models import Graph
from .inputs import Case, FAMILIES, generate


@dataclass(frozen=True)
class Trial:
    group: str
    case: Case
    extra: dict = field(default_factory=dict)

    def record(self):
        return {"group": self.group, **self.case.manifest(), **self.extra}


def read_jsonl(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def previous_case(row):
    return Case(row["id"], row["family"], row["seed"],
                Graph(tuple(row["graph"]["nodes"]), tuple(map(tuple, row["graph"]["edges"]))))


def topology_trials():
    for n, rewiring, seed in product((12, 16), (0.1, 0.35), range(5)):
        trial_seed = seed + 110
        uses = nx.connected_watts_strogatz_graph(n, 4, rewiring, seed=trial_seed)
        pairs = sorted(tuple(sorted(edge)) for edge in uses.edges())
        rng = Random(trial_seed + n)
        label = list(range(n))
        rng.shuffle(label)
        rank = list(range(n))
        rng.shuffle(rank)
        kept = [rng.random() for _ in pairs]
        original = [(u, v) if (v-u) % n <= (u-v) % n else (v, u) for u, v in pairs]
        conditions = {
            "coherent": original,
            "flip_quarter": [(v, u) if x < 0.25 else (u, v) for (u, v), x in zip(original, kept)],
            "random_direction": [(v, u) if x < 0.5 else (u, v) for (u, v), x in zip(original, kept)],
            "acyclic": [(u, v) if rank[u] < rank[v] else (v, u) for u, v in pairs],
        }
        block = f"ws-{n}-{rewiring}-{trial_seed}"
        for orientation, arcs in conditions.items():
            retained = sum(a == b for a, b in zip(arcs, original))/len(arcs)
            edges = tuple(sorted((label[u], label[v]) for u, v in arcs))
            case = Case(f"{block}-{orientation}", "watts_strogatz", trial_seed, Graph(tuple(range(n)), edges))
            yield Trial("topology", case, {"block": block, "orientation": orientation,
                                           "rewiring": rewiring, "coherent_edge_fraction": retained})


def local_public_graph(path):
    with path.open(newline="", encoding="utf-8") as source:
        return nx.DiGraph((int(u), int(v)) for u, v in csv.reader(source) if u != v)


def scc_control_trials():
    for n, seed in product((12,16), range(5)):
        rng=Random(510+seed)
        ring=[(u,(u+1)%n) for u in range(n)]
        chords=rng.sample([(u,(u+d)%n) for u,d in product(range(n),(2,3,4))],n)
        labels=list(range(n))
        rng.shuffle(labels)
        flips=[rng.randrange(2) for _ in chords]
        block=f"single-scc-{n}-{seed}"
        for orientation,extra in (
            ("coherent",chords),
            ("random_chords",[(v,u) if flip else (u,v) for (u,v),flip in zip(chords,flips)]),
            ("counter_chords",[(v,u) for u,v in chords]),
        ):
            edges=tuple(sorted((labels[u],labels[v]) for u,v in ring+extra))
            case=Case(f"{block}-{orientation}","ring_chords",510+seed,Graph(tuple(range(n)),edges))
            yield Trial("scc_control",case,{"block":block,"orientation":orientation})


def degree_control_trials():
    for n, step in product((12, 16, 20), (2, 3, 4)):
        seed = 1500 + n + step
        labels = list(range(n))
        Random(seed).shuffle(labels)
        ring = [(u, (u + 1) % n) for u in range(n)]
        chords = [(u, (u + step) % n) for u in range(n)]
        block = f"regular-ring-{n}-{step}"
        for orientation, extra in (
            ("coherent", chords),
            ("counter_chords", [(v, u) for u, v in chords]),
        ):
            edges = tuple(sorted((labels[u], labels[v]) for u, v in ring + extra))
            graph = Graph(tuple(range(n)), edges)
            case = Case(f"{block}-{orientation}", "regular_ring", seed, graph)
            yield Trial("degree_control", case, {"block": block, "orientation": orientation,
                                                  "chord_step": step})


def degree_control_random_trials():
    for n, seed in product((12, 16, 20), range(1600, 1605)):
        rng = Random(seed)
        labels = rng.sample(range(n), n)
        successors = [(u + 3) % n for u in range(n)]
        changed = set()
        for u in rng.sample(range(n), n):
            v = (u + 1) % n
            if u not in changed and v not in changed and rng.random() < .65:
                successors[u], successors[v] = successors[v], successors[u]
                changed.update((u, v))
        ring = [(u, (u + 1) % n) for u in range(n)]
        chords = list(enumerate(successors))
        block = f"random-regular-ring-{n}-{seed}"
        for orientation, extra in (
            ("coherent", chords),
            ("counter_chords", [(v, u) for u, v in chords]),
        ):
            edges = tuple(sorted((labels[u], labels[v]) for u, v in ring + extra))
            graph = Graph(tuple(range(n)), edges)
            case = Case(f"{block}-{orientation}", "random_regular_ring", seed, graph)
            yield Trial("degree_control_random", case, {"block": block, "orientation": orientation})


def holdout_trials(directory):
    sources = (
        ("krackhardt", "advice", "krackhardt_advice.csv",
         "https://github.com/JeffreyAlanSmith/Integrated_Network_Science/blob/master/data/krackhardt_advice.csv"),
        ("krackhardt", "friendship", "krackhardt_friendship.csv",
         "https://github.com/JeffreyAlanSmith/Integrated_Network_Science/blob/master/data/krackhardt_friendship.csv"),
        ("sociopatterns", "friendship", "highschool2013.gz",
         "https://github.com/SocioPatterns/sociopatterns.github.io/blob/main/assets/data/HighSchool2013_friendship_network.csv.gz"),
        ("email_eu", "email", "email-Eu-core-official-count.txt",
         "https://github.com/jinhangjiang/Datasets/blob/main/Network%20Data/emailEUcore/email-Eu-core.txt"),
    )
    for family, relation, filename, source in sources:
        raw = (directory / filename).read_bytes()
        if filename.endswith(".csv"):
            arcs = [(int(u), int(v)) for u, v, tie in list(csv.reader(raw.decode().splitlines()))[1:]
                    if int(tie)]
        else:
            content = gzip.decompress(raw) if filename.endswith(".gz") else raw
            arcs = [tuple(map(int, line.split())) for line in content.decode().splitlines() if line.strip()]
        graph = nx.DiGraph((u, v) for u, v in arcs if u != v)
        weak = graph.to_undirected()
        component = min(nx.connected_components(weak), key=lambda nodes: (-len(nodes), min(nodes)))
        centers = Random(1967).sample(sorted(component), 3)
        for i, center in enumerate(centers):
            bfs = list(nx.bfs_tree(weak, center, sort_neighbors=sorted))
            for size in (12, 16):
                if len(bfs) < size:
                    raise ValueError(f"{filename} has insufficient connected vertices")
                sample = graph.subgraph(bfs[:size])
                label = {u: index for index, u in enumerate(sorted(sample))}
                edges = tuple(sorted((label[u], label[v]) for u, v in sample.edges()))
                case = Case(f"{family}-{relation}-{i}-{size}", family, 1967,
                            Graph(tuple(range(size)), edges), sha256(raw).hexdigest(), source)
                yield Trial("public_holdout", case, {
                    "relation": relation, "center": center, "sample_nodes": sorted(sample),
                    "source_nodes": graph.number_of_nodes(), "source_edges": graph.number_of_edges(),
                })


def public_trials(directory):
    with ZipFile(directory / "sampson.zip") as archive:
        for period in range(1, 4):
            member = f"samplike{period}.txt"
            lines = archive.read(member).decode().splitlines()
            graph = nx.parse_edgelist(lines, delimiter="\t", data=False, create_using=nx.DiGraph)
            graph.remove_edges_from(nx.selfloop_edges(graph))
            yield public_trial("sampson", f"time-{period}", graph, 0,
                "https://github.com/networkx/networkx/blob/main/examples/drawing/sampson_data.zip", member)
    for family, filename in (("UKfaculty", "UKfaculty.csv"), ("macaque", "macaque.csv")):
        original = local_public_graph(directory / filename)
        largest = sorted(max(nx.strongly_connected_components(original), key=len))
        candidates = original.subgraph(largest)
        url = f"https://github.com/igraph/igraphdata/blob/main/data/{Path(filename).stem}.rda"
        # Four independently seeded centers per corpus. The neighborhoods can overlap.
        for i, center in enumerate(Random(91).sample(largest, 4)):
            neighbors = nx.bfs_tree(candidates.to_undirected(), center, sort_neighbors=sorted)
            current = list(neighbors)[:14]
            sample = original.subgraph(current)
            yield public_trial(family, f"induced-{i}", sample, i, url, ",".join(map(str, current)))


def public_trial(family, name, graph, seed, source, selection):
    relabel = {node: i for i, node in enumerate(sorted(graph))}
    edges = tuple(sorted((relabel[u], relabel[v]) for u, v in graph.edges))
    return Trial("public", Case(f"{family}-{name}", family, seed, Graph(tuple(range(len(graph))), edges),
                                source=source), {"selection": selection})


def budget_trials(previous):
    all_rows = read_jsonl(previous / "framework_timed" / "rows.jsonl")
    records = {row["id"]: row for row in read_jsonl(previous / "framework_timed" / "inputs.jsonl")}
    for family in FAMILIES:
        pool = {r["case"] for r in all_rows if r["family"] == family}
        slow = sorted({r["case"] for r in all_rows if r["case"] in pool and
                       r["variant"] in ("sugiyama", "radial") and r["status"] != "ok"})
        ok = sorted(pool - set(slow))
        for case_id in slow[:2] + ok[:1]:
            yield Trial("budget", previous_case(records[case_id]), {"previous_censored": case_id in slow})


def proper_cases(group, count):
    for i in range(count):
        rng = Random(212 + i)
        width = 2 + i % 2
        layers = [[layer*width + pos for pos in range(width)] for layer in range(3)]
        choices = [(u, v) for j, layer in enumerate(layers)
                   for u in layer for v in layers[(j+1) % 3]]
        mandatory = {edge for j, layer in enumerate(layers)
                     for edge in zip(layer, layers[(j+1) % 3])}
        available = sorted(set(choices) - mandatory)
        edges = tuple(sorted(mandatory | set(rng.sample(available, width+1))))
        case = Case(f"{group}-{i:02}", "proper", 212+i, Graph(tuple(range(3*width)), edges))
        yield Trial(group, case, {"width": width})


def stress_subdivision():
    for n, height in ((50, 15), (200, 35), (800, 80)):
        rng = Random(611 + n)
        ranks = {u: u % height for u in range(n)}
        candidates = [(u,v) for u in range(n) for v in range(n)
                      if (ranks[v] - ranks[u]) % height >= height//2]
        edges = tuple(rng.sample(candidates, 3*n))
        case = Case(f"long-span-{n}", "long_span", 611+n, Graph(tuple(range(n)), edges))
        yield Trial("subdivision", case, {"height":height})


def trials(group, previous, public):
    if group == "winding_ablation":
        for row in read_jsonl(previous / "inputs.jsonl"):
            yield Trial(group, previous_case(row))
    elif group == "topology":
        yield from topology_trials()
    elif group == "scc_control":
        yield from scc_control_trials()
    elif group == "degree_control":
        yield from degree_control_trials()
    elif group == "degree_control_random":
        yield from degree_control_random_trials()
    elif group == "public_restart_holdout":
        for item in holdout_trials(public):
            if len(item.case.graph.nodes) == 12:
                yield Trial(group, item.case, item.extra)
    elif group == "public_holdout":
        yield from holdout_trials(public)
    elif group == "public":
        yield from public_trials(public)
    elif group == "public_retry":
        failures={r["case"]:r["status"] for r in read_jsonl(public.parent/"public"/"rows.jsonl")
                  if r["variant"]=="torus" and r["status"]!="ok"}
        for item in public_trials(public):
            if item.case.id in failures:
                yield Trial(group,item.case,{**item.extra,"original_status":failures[item.case.id]})
    elif group == "budget":
        yield from budget_trials(previous)
    elif group in ("winding", "geometry"):
        yield from proper_cases(group, 20 if group=="winding" else 36)
    elif group == "subdivision":
        yield from stress_subdivision()
    elif group == "seam_stress":
        ranks=(0,0,1,1,2,3)
        possible=[(u,v) for u,v in product(range(len(ranks)),repeat=2)
                  if (ranks[v]-ranks[u])%4 in (2,3)]
        for i in range(36):
            rng=Random(1190+i)
            edges=tuple(sorted(rng.sample(possible,8)))
            case=Case(f"stress-{i:02}","artificial_long_edges",1190+i,Graph(tuple(range(len(ranks))),edges))
            yield Trial(group,case,{"specified_ranks":ranks})
    elif group == "fixed_rank_width":
        lanes, period = 4, 24
        nodes = tuple(range(lanes * period))
        for seed in (941, 942, 943):
            rng = Random(seed)
            edges = []
            for step in range(period):
                destinations = list(range(lanes))
                rng.shuffle(destinations)
                for lane in range(lanes):
                    successor = ((step + 1) % period) * lanes
                    edges.extend(
                        (step * lanes + lane, successor + destinations[(lane + offset) % lanes])
                        for offset in (0, 1)
                    )
            graph = Graph(nodes, tuple(edges))
            for layers in (4, 8, 12, 24):
                case = Case(f"fixed-width-{seed}-{layers}", "same_graph_width", seed, graph)
                yield Trial(group, case, {
                    "layer_width": len(nodes) // layers,
                    "specified_ranks": [u // lanes % layers for u in nodes],
                })
    elif group == "fixed_rank_width_variation":
        layers = 8
        for seed in (951, 952, 953, 954, 955):
            rng = Random(seed)
            partitions = []
            edges = []
            next_node = 0
            for _ in range(2):
                buckets = []
                for width in (4, 12) * (layers // 2):
                    buckets.append(list(range(next_node, next_node + width)))
                    next_node += width
                partitions.append(buckets)
                for index, current in enumerate(buckets):
                    following = buckets[(index + 1) % layers]
                    sources, targets = current.copy(), following.copy()
                    rng.shuffle(sources)
                    rng.shuffle(targets)
                    for i in range(12):
                        u, v = sources[i % len(sources)], targets[i % len(targets)]
                        edges.append((u, v))
                        if len(sources) == 4:
                            edges.append((sources[(i + 1) % 4], v))
                        else:
                            edges.append((u, targets[(i + 1) % 4]))
            nodes = tuple(range(next_node))
            graph = Graph(nodes, tuple(edges))
            for condition, shift in (("alternating", 0), ("uniform", 1)):
                ranks = [0] * len(nodes)
                for offset, buckets in zip((0, shift), partitions, strict=True):
                    for layer, bucket in enumerate(buckets):
                        for node in bucket:
                            ranks[node] = (layer + offset) % layers
                case = Case(f"width-variation-{seed}-{condition}", "same_graph_width", seed, graph)
                yield Trial(group, case, {
                    "layer_width": len(nodes) // layers,
                    "width_condition": condition,
                    "specified_ranks": ranks,
                })
    elif group in ("fixed_rank_scaling", "fixed_rank_rounds", "fixed_rank_sparse"):
        spans = (1, 2) if group == "fixed_rank_scaling" else (2,)
        for size, width, skip in product((100, 500, 1000), (5, 10), spans):
            nodes = tuple(range(size))
            arcs = tuple(edge for u in nodes for edge in (
                (u, (u + width) % size),
                (u, ((u // width + skip) * width + (u + 1) % width) % size),
            ))
            graph = Graph(nodes, arcs)
            case = Case(f"fixed-ring-{size}-{width}-{skip}", "fixed_ring", 0, graph)
            yield Trial(group, case, {"layer_width": width, "second_edge_span": skip})
    elif group in ("dag_large", "scc_large", "scc_compact", "dag_square_cut", "scc_square_cut", "scc_square_scaled"):
        family = "dag" if group in ("dag_large", "dag_square_cut") else "scc_chain"
        for size, density in product((12, 36, 500, 1000), (2, 4)):
            yield Trial(group, generate(family, size, density, 0))
    elif group in ("budget_scoring_holdout", "budget_holdout_dot"):
        for family, size, seed in product(("cycle", "watts_strogatz"), (90, 120), (811, 812, 813)):
            yield Trial(group, generate(family, size, 2, seed))
    elif group in ("large_geometry", "large_local_winding", "large_integer_scoring", "large_vector_scoring", "large_cached_scoring", "large_incremental_scoring", "large_delta_scoring", "large_budgeted_scoring", "large_graphviz"):
        for family, size in product(("cycle", "watts_strogatz"), (500, 1000)):
            yield Trial(group, generate(family, size, 2, 0))
    elif group in ("wrap_bounds", "wrap_bounds_refine", "wrap_bounds_short_cycles"):
        for family, size, density in product(("cycle", "watts_strogatz"), (12, 36, 500, 1000), (2, 4)):
            yield Trial(group, generate(family, size, density, 0))
    elif group == "square_diagnosis":
        for family, size, density in (("dag", 90, 2), ("dag", 90, 4),
                                      ("watts_strogatz", 90, 4), ("watts_strogatz", 120, 2)):
            yield Trial(group, generate(family, size, density, 323))
    elif group in ("square_holdout", "square_pipeline"):
        for family, size, density, seed in product(("dag", "watts_strogatz"), (90, 120), (2, 4), (322, 323)):
            yield Trial(group, generate(family, size, density, seed))
    elif group == "square_scaling":
        for family, size in product(("dag", "watts_strogatz"), (12, 18, 36, 60, 90, 120)):
            yield Trial(group, generate(family, size, 2, 321))
    elif group == "scaling":
        for family, size in product(("dag", "watts_strogatz"), (36, 60, 90, 120)):
            yield Trial(group, generate(family, size, 2, 321))
    elif group == "ranks":
        for family, size, density in product(FAMILIES, (12, 18), (2, 4)):
            yield Trial(group, generate(family, size, density, 319))
    else:
        for family, size, seed in product(FAMILIES, (12, 16), range(2)):
            yield Trial(group, generate(family, size, 2, seed + 401))
        if group == "seams":
            for seed in range(12):
                yield Trial(group, generate("cycle", 6, 2, seed + 515), {"tiny": True})
