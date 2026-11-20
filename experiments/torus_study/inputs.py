"""Deterministic generated cases and optional local GraphML benchmarks."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import permutations, product
from pathlib import Path
from random import Random
from xml.etree import ElementTree

import networkx as nx

from torus_layout.models import Graph

FAMILIES = ("dag", "random", "scc_chain", "watts_strogatz")
BINS = ((10, 25), (26, 50), (51, 75), (76, 100))


@dataclass(frozen=True)
class Case:
    id: str
    family: str
    seed: int
    graph: Graph
    source_sha256: str = ""
    source: str = ""

    def manifest(self):
        graph = nx.DiGraph()
        graph.add_nodes_from(self.graph.nodes)
        graph.add_edges_from(self.graph.edges)
        components = list(nx.strongly_connected_components(graph))
        n = len(self.graph.nodes)
        return {
            **asdict(self),
            "nodes": n,
            "edges": len(self.graph.edges),
            "scc_count": len(components),
            "largest_scc_fraction": max(map(len, components)) / n,
            "cyclic_node_fraction": sum(len(c) for c in components if len(c) > 1) / n,
            "reciprocal_pairs": sum(graph.has_edge(v, u) for u, v in graph.edges) // 2,
            "in_degrees": [graph.in_degree(u) for u in self.graph.nodes],
            "out_degrees": [graph.out_degree(u) for u in self.graph.nodes],
        }


def generate(family, n, density, seed):
    rng = Random(seed)
    nodes = list(range(n))
    m = n * density
    if family == "watts_strogatz":
        base = nx.connected_watts_strogatz_graph(n, 2 * density, 0.1, seed=rng)
        edges = [
            (u, v) if (v - u) % n <= (u - v) % n else (v, u)
            for u, v in sorted(base.edges)
        ]
    else:
        if family in ("scc_chain", "cycle"):
            size = max(2, n // 10) if family == "scc_chain" else n
            blocks = [nodes[i:i + size] for i in range(0, n, size)]
            if len(blocks[-1]) == 1:
                blocks[-2].extend(blocks.pop())
            block_index = {u: i for i, block in enumerate(blocks) for u in block}
            edges = [(u, block[(i + 1) % len(block)]) for block in blocks
                     for i, u in enumerate(block)]
            edges += [(left[-1], right[0]) for left, right in zip(blocks, blocks[1:])]
            allowed = lambda u, v: block_index[u] <= block_index[v]
        else:
            edges = [(rng.randrange(v), v) for v in nodes[1:]]
            if family == "random":
                edges = [(u, v) if rng.randrange(2) else (v, u) for u, v in edges]
            allowed = lambda u, v: family == "random" or u < v
        present = set(edges)
        candidates = [(u, v) for u, v in permutations(nodes, 2)
                      if (u, v) not in present and allowed(u, v)]
        edges += rng.sample(candidates, m - len(edges))
    labels = nodes.copy()
    rng.shuffle(labels)
    relabeled = [(labels[u], labels[v]) for u, v in edges]
    rng.shuffle(relabeled)
    return Case(f"{family}-{n}-{density}-{seed}", family, seed,
                Graph(tuple(nodes), tuple(relabeled)))


def proper_cases(profile):
    widths = (2,) if profile == "quick" else (2, 3)
    seeds = range(1 if profile == "quick" else 10)
    for width, probability, seed in product(widths, (0.25, 0.65), seeds):
        rng = Random(seed)
        n = width * 3
        layers = [list(range(i, i + width)) for i in range(0, n, width)]
        edges = []
        for left, right in zip(layers, layers[1:] + layers[:1]):
            edges.extend(zip(left, right))
            edges.extend((u, v) for u, v in product(left, right)
                         if (u, v) not in edges and rng.random() < probability)
        yield Case(f"proper-3-{width}-{probability}-{seed}", "proper", seed,
                   Graph(tuple(range(n)), tuple(edges)))


def generated_cases(group, profile, *, sizes=None, densities=None, seed_count=None):
    if group == "drawing":
        yield Case("boundary-fixtures", "fixture", 0, Graph((0, 1), ((0, 1),)))
        yield from (generate(f, 10, 2, 0) for f in FAMILIES)
        return
    if group == "oracles":
        yield from proper_cases(profile)
        sizes, seeds = ((6,), range(1)) if profile == "quick" else ((8, 12, 20), range(10))
        for family, n, seed in product(("dag", "random", "cycle"), sizes, seeds):
            yield generate(family, n, 2, seed)
        return
    if profile == "quick":
        default_sizes, default_densities, default_seeds = (10,), (2,), 1
    elif group == "scaling":
        default_sizes, default_densities, default_seeds = (50, 100, 200, 500, 1000), (2, 4), 10
    else:
        default_sizes, default_densities, default_seeds = (50, 100, 200), (2, 4), 20
    sizes = sizes or default_sizes
    densities = densities or default_densities
    seeds = range(seed_count or default_seeds)
    for family, n, density, seed in product(FAMILIES, sizes, densities, seeds):
        yield generate(family, n, density, seed)


def public_cases(directory: Path, family: str):
    rng = Random(20261119)
    bins = {bounds: [] for bounds in BINS}
    audit = []
    for path in sorted(p for p in directory.rglob("*")
                       if p.suffix.lower() in {".graphml", ".xml"} and p.is_file()):
        relative = path.relative_to(directory).as_posix()
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        row = {"source": relative, "family": family, "sha256": digest}
        audit.append(row)
        try:
            root = ElementTree.fromstring(raw)
            legacy = root.find("graph") if root.tag == "graphml" else None
            if legacy is not None and "edgedefault" not in legacy.attrib:
                legacy.set("edgedefault", "undirected" if family == "rome" else "directed")
                row["legacy_direction_from_catalog"] = True
                graph = nx.parse_graphml(ElementTree.tostring(root, encoding="unicode"))
            else:
                graph = nx.read_graphml(path)
        except (nx.NetworkXError, ValueError, OSError, SyntaxError) as exc:
            row["status"] = type(exc).__name__
            continue
        n = len(graph)
        row["nodes"] = n
        bounds = next((b for b in BINS if b[0] <= n <= b[1]), None)
        if bounds is None:
            row["status"] = "size"
            continue
        if graph.is_directed() != (family != "rome"):
            row["status"] = "direction"
            continue
        if graph.is_multigraph() or nx.number_of_selfloops(graph):
            row["status"] = "loop_or_parallel"
            continue
        if not nx.is_connected(graph.to_undirected()):
            row["status"] = "disconnected"
            continue
        if family == "dagmar" and not nx.is_directed_acyclic_graph(graph):
            row["status"] = "directed_cycle"
            continue
        index = {node: i for i, node in enumerate(sorted(graph.nodes))}
        edges = [(index[u], index[v]) for u, v in graph.edges]
        seed = int(sha256(relative.encode()).hexdigest()[:8], 16)
        if family == "rome":
            orient = Random(seed)
            edges = [(u, v) if orient.randrange(2) else (v, u)
                     for u, v in sorted(tuple(sorted(edge)) for edge in edges)]
        row["status"] = "eligible"
        case = Case(f"{family}-{relative}", family, seed,
                    Graph(tuple(range(n)), tuple(sorted(edges))), digest, relative)
        bins[bounds].append((case, row))
    selected = []
    for candidates in bins.values():
        for case, row in rng.sample(candidates, min(50, len(candidates))):
            row["status"] = "selected"
            selected.append(case)
    if not selected:
        raise ValueError(f"No eligible GraphML files for {family}: {directory}")
    return selected, audit
