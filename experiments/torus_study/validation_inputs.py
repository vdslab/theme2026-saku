"""Held-out, matched, public, and representative inputs for the validation study."""

from dataclasses import dataclass, field
from itertools import product
import csv
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
    if group == "topology":
        yield from topology_trials()
    elif group == "scc_control":
        yield from scc_control_trials()
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
