"""CLI for generation, layout, reporting, and reproducible validation artifacts.

From the repository root:
    PYTHONPATH=src ./theme2026-saku/bin/python -m torus_layout
Or run ./theme2026-saku/bin/python src/torus_layout/main.py directly.
"""

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
from time import perf_counter

import gurobipy as gp

if __package__ in (None, ""):
    # Direct script execution starts sys.path inside torus_layout, not src.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generator import generate_graph
from torus_layout import constants
from torus_layout.coordinates import assign_coordinates
from torus_layout.crossing import count_crossings, count_seam_segments, reduce_crossings
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.models import Graph, PipelineConfig
from torus_layout.pipeline import run_pipeline
from torus_layout.reporting import report_pipeline


def _nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("0以上の整数を指定してください")
    return number


def _nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("0以上の有限の数値を指定してください")
    return number


def _probability(value: str) -> float:
    number = _nonnegative_float(value)
    if number > 1:
        raise argparse.ArgumentTypeError("確率は0以上1以下で指定してください")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="提案トーラス階層描画の全工程を実行し、画像と検証データを保存します。"
    )
    parser.add_argument(
        "--graph",
        choices=["cyclic", "watts_strogatz", "random", "dag", "mixed"],
        default=constants.DEFAULT_GRAPH_TYPE,
    )
    parser.add_argument(
        "--nodes", "--node", type=int, default=constants.DEFAULT_NODE_COUNT, help=f"元ノード数（既定: {constants.DEFAULT_NODE_COUNT}）"
    )
    parser.add_argument("--seed", type=int, default=constants.DEFAULT_RANDOM_SEED, help=f"再現用seed（既定: {constants.DEFAULT_RANDOM_SEED}）")
    parser.add_argument("--cycles", type=int, default=constants.DEFAULT_CYCLE_COUNT, help="cyclic生成器の閉路数")
    parser.add_argument("--edge-prob", type=_probability, default=constants.DEFAULT_EDGE_PROBABILITY)
    parser.add_argument(
        "--cycle-prob",
        type=_probability,
        default=constants.DEFAULT_CYCLE_PROBABILITY,
        help="mixed生成器の閉路ノード確率",
    )
    parser.add_argument(
        "--neighbors", type=int, default=constants.DEFAULT_NEIGHBOR_COUNT, help="Watts–Strogatzの近傍数k"
    )
    parser.add_argument(
        "--rewire-prob",
        type=_probability,
        default=constants.DEFAULT_REWIRING_PROBABILITY,
        help="Watts–Strogatzの張替確率p",
    )
    parser.add_argument(
        "--balance-method",
        choices=["diff", "diff_square", "qp", "barycenter"],
        default=constants.DEFAULT_BALANCE_METHOD,
    )
    parser.add_argument("--rounds", type=_nonnegative_int, default=constants.DEFAULT_ROUNDS)
    parser.add_argument(
        "--coordinate-method",
        choices=["torus_qp", "torus_lp", "brandes_koepf"],
        default=constants.DEFAULT_COORDINATE_METHOD,
    )
    parser.add_argument("--bend-weight", type=_nonnegative_float, default=constants.DEFAULT_BEND_WEIGHT)
    parser.add_argument(
        "--no-optimize-seams", action="store_true", help="境界最適化DPを無効化"
    )
    parser.add_argument(
        "--compare-seams",
        action="store_true",
        help="同一階層割当で境界最適化前の結果も計算・描画",
    )
    parser.add_argument("--output-dir", type=Path, default=Path(constants.DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--show", action="store_true", help="保存に加えて描画画面を表示"
    )
    parser.add_argument("--draw-dummy-nodes", action="store_true")
    parser.add_argument(
        "--tile-surroundings",
        action=argparse.BooleanOptionalAction,
        default=constants.DEFAULT_CLI_TILE_SURROUNDINGS,
        help="周辺タイルを表示（既定: 有効、--no-tile-surroundingsで無効化）",
    )
    parser.add_argument(
        "--local-license",
        action="store_true",
        help=".envのWLS設定の代わりにローカルGurobiライセンスを明示的に使用",
    )
    return parser


def _run(args: argparse.Namespace) -> None:
    from torus_layout.drawing import DrawingOptions, draw_layout

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
    )
    print(
        f"グラフ: {args.graph}, ノード数: {len(nodes)}, 辺数: {len(edges)}, seed: {used_seed}"
    )
    print(
        f"階層割当: {config.balance_method}, 座標割当: {config.coordinate_method}, 境界最適化: {config.optimize_seams}"
    )
    print(
        "Gurobi: " + ("local（明示指定）" if args.local_license else ".env WLS設定"),
        flush=True,
    )
    started = perf_counter()
    with use_local_license(args.local_license):
        result = run_pipeline(graph, config)
        if result is None:
            raise RuntimeError("階層割当に失敗しました")
        report_pipeline(result)
        after_seams = count_seam_segments(result.subdivided, result.crossing)
        after_crossings = count_crossings(result.subdivided, result.crossing)
        before_seams: int | None = None
        before_crossings: int | None = None
        baseline = None
        baseline_coordinates = None
        if args.compare_seams:
            baseline = reduce_crossings(
                result.subdivided, rounds=config.rounds, optimize_seams=False
            )
            before_seams = count_seam_segments(result.subdivided, baseline)
            before_crossings = count_crossings(result.subdivided, baseline)
            if after_seams > before_seams or after_crossings != before_crossings:
                raise RuntimeError(
                    "境界最適化の検証失敗: 通過線分数が増加、または交差数が変化しました"
                )
            baseline_coordinates = assign_coordinates(
                result.subdivided,
                baseline,
                method=config.coordinate_method,
                bend_weight=config.coordinate_bend_weight,
            )
            print(f"境界通過線分数: {before_seams} → {after_seams}")
            print(f"辺同士の交差数: {before_crossings} → {after_crossings}")
    computation_seconds = perf_counter() - started
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    options = DrawingOptions(
        draw_dummy_nodes=args.draw_dummy_nodes,
        tile_surroundings=args.tile_surroundings,
    )
    draw_layout(
        result.subdivided,
        result.crossing,
        result.coordinates,
        options=options,
        save_path=output / "layout.png",
        show=args.show,
    )
    if baseline is not None and baseline_coordinates is not None:
        draw_layout(
            result.subdivided,
            baseline,
            baseline_coordinates,
            options=options,
            save_path=output / "before_seam.png",
            show=False,
        )
    settings = {
        "graph": args.graph,
        "nodes": args.nodes,
        "seed": used_seed,
        "generator_parameters": parameters,
        "pipeline": asdict(config),
        "license_mode": "local" if args.local_license else "application_env",
        "compare_seams": args.compare_seams,
        "drawing": asdict(options),
    }
    metrics = {
        "original_nodes": len(graph.nodes),
        "original_edges": len(graph.edges),
        "subdivided_nodes": len(result.subdivided.graph.nodes),
        "segments": len(result.subdivided.graph.edges),
        "layers": len(result.crossing.order),
        "seam_segments": after_seams,
        "crossings": after_crossings,
        "seam_segments_before": before_seams,
        "crossings_before": before_crossings,
        "layer_search_seconds": result.search.runtime,
        "balance_seconds": result.assignment.runtime,
        "crossing_seconds": result.crossing_time,
        "coordinate_seconds": result.coordinate_time,
        "computation_wall_seconds": computation_seconds,
    }
    # Arrays preserve node IDs and edge occurrences without JSON tuple-key coercion.
    payload = {
        "status": "completed",
        "settings": settings,
        "metrics": metrics,
        "input_graph": {"nodes": graph.nodes, "edges": graph.edges},
        "layer_assignment": [
            [node, layer] for node, layer in result.assignment.node_to_layer.items()
        ],
        "order": [[layer, group] for layer, group in result.crossing.order.items()],
        "segments": [
            {
                "source": u,
                "target": v,
                "winding": result.crossing.winding_numbers.get((u, v), 0),
                "horizontal_wrap": result.subdivided.torus_flags.get((u, v), False),
            }
            for u, v in result.subdivided.graph.edges
        ],
        "coordinates": [
            [node, x, y] for node, (x, y) in result.coordinates.positions.items()
        ],
        "period": result.coordinates.period,
    }
    (output / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"画像: {output / 'layout.png'}")
    if baseline is not None:
        print(f"比較画像: {output / 'before_seam.png'}")
    print(f"設定・グラフ・座標・評価値: {output / 'result.json'}")


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
