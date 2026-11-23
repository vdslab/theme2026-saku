"""CLI for generation, layout, reporting, and reproducible validation artifacts.

From the repository root:
    PYTHONPATH=src ./theme2026-saku/bin/python -m torus_layout
Or run ./theme2026-saku/bin/python src/torus_layout/main.py directly.
"""

import argparse
from pathlib import Path
import sys
from time import perf_counter

import gurobipy as gp

if __package__ in (None, ""):
    # Direct script execution starts sys.path inside torus_layout, not src.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generator import generate_graph
from torus_layout.cli_arguments import build_parser
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.models import Graph, PipelineConfig
from torus_layout.pipeline import run_pipeline
from torus_layout.reporting import report_pipeline
from torus_layout.seam_comparison import compare_seams


def _run(args: argparse.Namespace) -> None:
    from torus_layout.cli_output import save_outputs

    parameters: dict[str, int | float]
    if args.graph == "watts_strogatz":
        parameters = {"k": args.neighbors, "p": args.rewire_prob}
    else:
        parameters = {"edge_prob": args.edge_prob}
        if args.graph == "cyclic":
            parameters["num_cycles"] = args.cycles
        elif args.graph == "mixed":
            parameters["cycle_prob"] = args.cycle_prob
    nodes, edges, used_seed = generate_graph(
        args.graph, n=args.nodes, seed=args.seed, **parameters
    )
    graph = Graph(tuple(nodes), tuple(edges))
    config = PipelineConfig(
        balance_method=args.balance_method,
        rounds=args.rounds,
        coordinate_method=args.coordinate_method,
        coordinate_bend_weight=args.bend_weight,
        optimize_seams=not args.no_optimize_seams,
        unwind_levels=args.unwind,
        sifting_method=args.sifting_method,
    )
    print(
        f"グラフ: {args.graph}, ノード数: {len(nodes)}, 辺数: {len(edges)}, seed: {used_seed}"
    )
    print(
        f"階層割当: {config.balance_method}, 座標割当: {config.coordinate_method}, "
        f"UNWIND: {config.unwind_levels}, 境界最適化: {config.optimize_seams}"
    )
    print(
        "Gurobi: " + ("local（明示指定）" if args.local_license else ".env WLS設定"),
        flush=True,
    )
    with use_local_license(args.local_license):
        started = perf_counter()
        result = run_pipeline(graph, config)
        computation_seconds = perf_counter() - started
        if result is None:
            raise RuntimeError("階層割当に失敗しました")
        report_pipeline(result)
        comparison = compare_seams(result, config, enabled=args.compare_seams)
    save_outputs(
        args, graph, config, result, comparison, parameters, used_seed,
        computation_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.nodes < 3:
        parser.error("--nodes は3以上を指定してください")
    if args.cycles <= 0:
        parser.error("--cycles は正の整数を指定してください")
    try:
        _run(args)
    except (gp.GurobiError, ValueError, RuntimeError, OSError) as error:
        print(f"実行失敗: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
