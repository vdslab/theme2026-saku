"""Command-line options and value validation."""

import argparse
import math
from pathlib import Path

from . import constants


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
        "--no-optimize-seams", action="store_true", default=not constants.DEFAULT_OPTIMIZE_SEAMS, help="境界最適化DPを無効化"
    )
    parser.add_argument(
        "--compare-seams",
        action="store_true",
        help="同一階層割当で境界最適化前の結果も計算・描画",
    )
    parser.add_argument("--output-dir", type=Path, default=Path(constants.DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--show",
        action="store_true",
        default=constants.DEFAULT_CLI_SHOW,
        help="保存に加えて描画画面を表示",
    )
    parser.add_argument("--draw-dummy-nodes", action="store_true", default=constants.DEFAULT_DRAW_DUMMY_NODES)
    parser.add_argument(
        "--tile-surroundings",
        action=argparse.BooleanOptionalAction,
        default=constants.DEFAULT_CLI_TILE_SURROUNDINGS,
        help=f"周辺タイルを表示（既定: {constants.DEFAULT_CLI_TILE_SURROUNDINGS}、--no-tile-surroundingsで無効化）",
    )
    parser.add_argument(
        "--local-license",
        action="store_true",
        help=".envのWLS設定の代わりにローカルGurobiライセンスを明示的に使用",
    )
    return parser
