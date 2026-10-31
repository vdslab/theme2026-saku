"""Draw a random graph with a standalone radial Sugiyama framework."""

import argparse
from pathlib import Path

if __package__:
    from .coordinate_assignment import assign_coordinates
    from .crossing_reduction import count_crossings, reduce_crossings
    from .cycle_removal import remove_cycles
    from .drawing import draw_radial_graph
    from .dummy_insertion import insert_dummy_nodes
    from .layer_assignment import assign_layers
    from .random_graph import generate_watts_strogatz_digraph
else:
    from coordinate_assignment import assign_coordinates
    from crossing_reduction import count_crossings, reduce_crossings
    from cycle_removal import remove_cycles
    from drawing import draw_radial_graph
    from dummy_insertion import insert_dummy_nodes
    from layer_assignment import assign_layers
    from random_graph import generate_watts_strogatz_digraph

DEFAULT_SIZE = 10
DEFAULT_SEED = None
DEFAULT_REWIRING_PROBABILITY = 0.15
DEFAULT_ROUNDS = 4


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", "--node", dest="size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--prob", type=float, default=DEFAULT_REWIRING_PROBABILITY)
    parser.add_argument(
        "--neighbors",
        type=int,
        default=None,
        help="even Watts--Strogatz ring-neighbor count",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_ROUNDS,
        help=f"crossing-reduction rounds (default: {DEFAULT_ROUNDS})",
    )
    parser.add_argument("--save", type=Path, default=None, help="optional image path")
    parser.add_argument("--no-show", action="store_true", help="do not open a plot window")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    original_nodes, original_edges = generate_watts_strogatz_digraph(
        size=args.size,
        seed=args.seed,
        neighbor_count=args.neighbors,
        rewiring_probability=args.prob,
    )
    acyclic = remove_cycles(original_nodes, original_edges)
    ranks = assign_layers(acyclic.nodes, acyclic.edges)
    hierarchy = insert_dummy_nodes(acyclic.nodes, acyclic.edges, ranks)
    crossings_before = count_crossings(hierarchy.layers, hierarchy.edges)
    embedding = reduce_crossings(
        hierarchy.layers,
        hierarchy.edges,
        rounds=args.rounds,
    )
    coordinates = assign_coordinates(embedding.order)

    print(f"seed: {args.seed}")
    print(f"nodes: {len(original_nodes)}")
    print(f"edges: {len(original_edges)}")
    print(f"layers: {len(hierarchy.layers)}")
    print(f"crossings: {crossings_before} -> {embedding.crossings}")
    if args.save is not None:
        print(f"saved: {args.save}")

    draw_radial_graph(
        acyclic.nodes,
        original_edges,
        coordinates.cartesian,
        coordinates.polar,
        coordinates.radii,
        hierarchy.chains,
        embedding.winding,
        acyclic.reversed_edges,
        save_path=args.save,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()

