"""通常の平面向け杉山フレームワークでランダムグラフを描画する。"""

import argparse

from .coordinate_assignment import assign_coordinates
from .crossing_reduction import count_crossings, reduce_crossings
from .cycle_removal import remove_cycles
from .drawing import draw_hierarchical_graph
from .dummy_insertion import insert_dummy_nodes
from .layer_assignment import assign_layers
from .random_graph import generate_watts_strogatz_digraph


DEFAULT_SIZE = 10
DEFAULT_SEED = None
DEFAULT_REWIRING_PROBABILITY = 0.15


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size",
        "--node",
        dest="size",
        type=int,
        default=DEFAULT_SIZE,
        help=f"頂点数（デフォルト：{DEFAULT_SIZE}）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"乱数シード（デフォルト：{DEFAULT_SEED}）",
    )
    parser.add_argument(
        "--prob",
        type=float,
        default=DEFAULT_REWIRING_PROBABILITY,
        help=(
            "Watts--Strogatz グラフの辺を張り替える確率 "
            f"（デフォルト：{DEFAULT_REWIRING_PROBABILITY}）"
        ),
    )
    parser.add_argument(
        "--neighbors",
        type=int,
        default=None,
        help="リング上の偶数近傍数 k（デフォルト：min(4, 使用可能な最大の偶数 k)）",
    )
    return parser.parse_args()


def main() -> None:
    # 引数取得
    args = parse_arguments()

    # Watts--Strogatz 法を用いた複雑ネットワークグラフの生成
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
    reduced_order = reduce_crossings(hierarchy.layers, hierarchy.edges)
    crossings_after = count_crossings(reduced_order, hierarchy.edges)
    positions = assign_coordinates(
        reduced_order,
        hierarchy.edges,
        dummy_nodes=hierarchy.dummy_nodes,
    )

    print(f"乱数シード: {args.seed}")
    print(f"頂点数: {len(original_nodes)}")
    print(f"辺数: {len(original_edges)}")
    print(f"辺を張り替える確率: {args.prob}")
    print(f"レイヤー数: {max(ranks.values(), default=-1) + 1}")
    print(f"交差数: {crossings_before} -> {crossings_after}")

    draw_hierarchical_graph(
        acyclic.nodes,
        original_edges,
        positions,
        hierarchy.chains,
        acyclic.reversed_edges,
    )


if __name__ == "__main__":
    main()
