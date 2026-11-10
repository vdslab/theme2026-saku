"""同一グラフを提案手法と通常の杉山フレームワークで比較表示する。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import warnings

import matplotlib.pyplot as plt
from PIL import Image

from sugiyama_layout.coordinate_assignment import assign_coordinates
from sugiyama_layout.crossing_reduction import count_crossings, reduce_crossings
from sugiyama_layout.cycle_removal import remove_cycles
from sugiyama_layout.drawing import create_hierarchical_figure
from sugiyama_layout.dummy_insertion import insert_dummy_nodes
from sugiyama_layout.layer_assignment import assign_layers
from lib.generate_torus_graph import generate_watts_strogatz_graph
from main import (
    coordinate_assignment,
    layer_assignment,
    reduce_crossings_radial,
)
from crossing_reduction.radial import count_radial_crossings
from drawing.draw_radial_torus import draw_radial_torus


@dataclass(frozen=True)
class ProposedResult:
    image: Image.Image
    crossings: int
    horizontal_wraps: int
    vertical_wraps: int


@dataclass(frozen=True)
class SugiyamaResult:
    image: Image.Image
    crossings_before: int
    crossings_after: int
    layer_count: int
    reversed_edge_count: int


DEFAULT_NODE_COUNT = 10
DEFAULT_CYCLE_COUNT = 4
DEFAULT_EDGE_PROBABILITY = 0.5
DEFAULT_RANDOM_SEED = None
DEFAULT_BALANCE_METHOD = "diff_square"
DEFAULT_ROUND_COUNT = 5
DEFAULT_SAVE_PATH = None
DEFAULT_SHOW_DRAWING = True
DEFAULT_DRAW_DUMMY_NODES = False
DEFAULT_TILE_SURROUNDINGS = True
DEFAULT_SURROUNDING_OPACITY = 0.5
DEFAULT_TILE_GAP = 0

BALANCE_METHOD_CHOICES = ("diff", "diff_square", "qp", "barycenter")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=int, default=DEFAULT_NODE_COUNT)
    parser.add_argument("--cycle", type=int, default=DEFAULT_CYCLE_COUNT)
    parser.add_argument("--prob", type=float, default=DEFAULT_EDGE_PROBABILITY)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument(
        "--func_type",
        "--func-type",
        choices=BALANCE_METHOD_CHOICES,
        default=DEFAULT_BALANCE_METHOD,
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUND_COUNT)
    parser.add_argument(
        "--draw-dummy-nodes",
        action="store_true",
        default=DEFAULT_DRAW_DUMMY_NODES,
        help="提案手法のダミーノードも表示する",
    )
    parser.add_argument(
        "--surrounding-opacity",
        type=float,
        default=DEFAULT_SURROUNDING_OPACITY,
        help="提案手法の周囲8領域の不透明度",
    )
    parser.add_argument(
        "--tile-gap",
        type=int,
        default=DEFAULT_TILE_GAP,
        help="提案手法の周囲領域との間隔[pixel]",
    )
    parser.add_argument(
        "--proposed-save-path",
        type=Path,
        default=None,
        help="提案手法の保存先（デフォルト: comparison_proposed_seed_<seed>.png）",
    )
    parser.add_argument(
        "--sugiyama-save-path",
        type=Path,
        default=None,
        help="杉山法の保存先（デフォルト: comparison_sugiyama_seed_<seed>.png）",
    )
    parser.add_argument(
        "--save-both",
        action="store_true",
        help="比較画面を開く前に両方を個別保存する",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="比較画面を開かない（通常は --save-both と一緒に使用）",
    )
    parser.add_argument(
        "--no-save-prompt",
        action="store_true",
        help="比較画面を閉じた後の保存確認を表示しない",
    )
    return parser.parse_args()


def run_proposed_method(
    nodes,
    edges,
    *,
    func_type: str,
    rounds: int,
    draw_dummy_nodes: bool,
    surrounding_opacity: float,
    tile_gap: int,
) -> ProposedResult:
    print("\n=== 提案手法 ===")
    assigned = layer_assignment(nodes, edges, func_type)
    if assigned is None:
        raise RuntimeError("提案手法の階層割り当てに失敗しました。")
    layers, torus_flags, _, _ = assigned
    order, layers, routed_edges, torus_flags, psi, _ = reduce_crossings_radial(
        nodes, edges, layers, torus_flags, rounds=rounds
    )
    positions, _ = coordinate_assignment(
        order,
        layers,
        routed_edges,
        torus_flags,
        psi,
        original_nodes=nodes,
    )

    with TemporaryDirectory(prefix="theme2026-comparison-") as directory:
        output = Path(directory) / "proposed.png"
        draw_radial_torus(
            V=nodes,
            A=routed_edges,
            L=layers,
            t_val=torus_flags,
            order=order,
            psi=psi,
            pos=positions,
            save_path=output,
            show=False,
            draw_dummy_nodes=draw_dummy_nodes,
            tile_surroundings=True,
            surrounding_opacity=surrounding_opacity,
            tile_gap=tile_gap,
        )
        with Image.open(output) as rendered:
            image = rendered.convert("RGBA").copy()

    return ProposedResult(
        image=image,
        crossings=count_radial_crossings(order, psi, layers, routed_edges),
        horizontal_wraps=sum(
            bool(torus_flags.get(edge, False)) for edge in routed_edges
        ),
        vertical_wraps=sum(psi.get(edge, 0) != 0 for edge in routed_edges),
    )


def run_sugiyama_method(nodes, edges) -> SugiyamaResult:
    print("\n=== 通常の杉山フレームワーク ===")
    acyclic = remove_cycles(nodes, edges)
    ranks = assign_layers(acyclic.nodes, acyclic.edges)
    hierarchy = insert_dummy_nodes(acyclic.nodes, acyclic.edges, ranks)
    crossings_before = count_crossings(hierarchy.layers, hierarchy.edges)
    order = reduce_crossings(hierarchy.layers, hierarchy.edges)
    crossings_after = count_crossings(order, hierarchy.edges)
    positions = assign_coordinates(
        order,
        hierarchy.edges,
        dummy_nodes=hierarchy.dummy_nodes,
    )
    figure = create_hierarchical_figure(
        acyclic.nodes,
        edges,
        positions,
        hierarchy.chains,
        acyclic.reversed_edges,
        figsize=(12, 7),
    )
    buffer = BytesIO()
    figure.savefig(
        buffer,
        format="png",
        dpi=180,
        bbox_inches="tight",
        pad_inches=0.04,
        facecolor="white",
    )
    plt.close(figure)
    buffer.seek(0)
    with Image.open(buffer) as rendered:
        image = rendered.convert("RGBA").copy()
    buffer.close()

    return SugiyamaResult(
        image=image,
        crossings_before=crossings_before,
        crossings_after=crossings_after,
        layer_count=max(ranks.values(), default=-1) + 1,
        reversed_edge_count=len(acyclic.reversed_edges),
    )


def save_image(image: Image.Image, path: Path) -> Path:
    """Save one comparison panel and return its normalized path."""
    path = Path(path).expanduser()
    if not path.suffix:
        path = path.with_suffix(".png")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        flattened = Image.new("RGB", image.size, "white")
        flattened.paste(image, mask=image.getchannel("A"))
        flattened.save(path)
    else:
        image.save(path)
    return path.resolve()


def show_comparison(
    proposed: ProposedResult,
    sugiyama: SugiyamaResult,
    *,
    seed: int,
) -> None:
    """Show both drawings and return after the user closes the window."""
    figure, axes = plt.subplots(1, 2, figsize=(18, 9))
    figure.subplots_adjust(bottom=0.08, top=0.88, left=0.02, right=0.98, wspace=0.04)
    figure.suptitle(f"同一グラフの描画比較（seed={seed}）", fontsize=16)

    axes[0].imshow(proposed.image)
    axes[0].set_title(
        "提案手法（周囲配置あり）\n"
        f"交差数={proposed.crossings}, 左右巻き={proposed.horizontal_wraps}, "
        f"上下巻き={proposed.vertical_wraps}"
    )
    axes[1].imshow(sugiyama.image)
    axes[1].set_title(
        "通常の杉山フレームワーク\n"
        f"交差数={sugiyama.crossings_before}→{sugiyama.crossings_after}, "
        f"階層数={sugiyama.layer_count}, 反転辺={sugiyama.reversed_edge_count}"
    )
    for axis in axes:
        axis.set_axis_off()

    figure.text(
        0.5,
        0.025,
        "確認後にウィンドウを閉じると、ターミナルで保存する図を選べます。",
        ha="center",
        fontsize=10,
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Glyph .* missing from font\(s\).*",
            category=UserWarning,
        )
        plt.show()
    plt.close(figure)


def prompt_to_save(
    proposed: ProposedResult,
    sugiyama: SugiyamaResult,
    *,
    proposed_save_path: Path,
    sugiyama_save_path: Path,
) -> None:
    """Ask what to save after the user has inspected and closed the window."""
    print("\n描画結果の確認が終わりました。")
    print("  p: 提案手法のみ保存")
    print("  s: 杉山法のみ保存")
    print("  b: 両方保存")
    print("  n: 保存しない")
    while True:
        try:
            choice = input("保存する図を選んでください [p/s/b/n] (デフォルト: n): ")
        except EOFError:
            choice = "n"
        choice = choice.strip().lower() or "n"
        if choice in {"p", "s", "b", "n"}:
            break
        print("p、s、b、n のいずれかを入力してください。")

    if choice in {"p", "b"}:
        print(
            f"提案手法を保存しました: "
            f"{save_image(proposed.image, proposed_save_path)}"
        )
    if choice in {"s", "b"}:
        print(
            f"杉山法を保存しました: "
            f"{save_image(sugiyama.image, sugiyama_save_path)}"
        )
    if choice == "n":
        print("保存せずに終了します。")


def main() -> None:
    args = parse_arguments()
    actual_seed = (
        args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    )
    nodes, edges = generate_watts_strogatz_graph(
        n=args.node,
        k=args.cycle,
        p=args.prob,
        seed=actual_seed,
    )
    # 両手法へ同じ、変更前のグラフを渡す。
    nodes = tuple(nodes)
    edges = tuple(edges)
    print("=== 比較対象グラフ ===")
    print(f"ノード数: {len(nodes)}")
    print(f"エッジ数: {len(edges)}")
    print(f"シード値: {actual_seed}")

    proposed = run_proposed_method(
        nodes,
        edges,
        func_type=args.func_type,
        rounds=args.rounds,
        draw_dummy_nodes=args.draw_dummy_nodes,
        surrounding_opacity=args.surrounding_opacity,
        tile_gap=args.tile_gap,
    )
    sugiyama = run_sugiyama_method(nodes, edges)
    proposed_path = args.proposed_save_path or Path(
        f"comparison_proposed_seed_{actual_seed}.png"
    )
    sugiyama_path = args.sugiyama_save_path or Path(
        f"comparison_sugiyama_seed_{actual_seed}.png"
    )

    print("\n=== 比較結果 ===")
    print(
        "提案手法: "
        f"交差数={proposed.crossings}, "
        f"左右巻き={proposed.horizontal_wraps}, "
        f"上下巻き={proposed.vertical_wraps}"
    )
    print(
        "杉山法: "
        f"交差数={sugiyama.crossings_before}→{sugiyama.crossings_after}, "
        f"階層数={sugiyama.layer_count}, "
        f"反転辺={sugiyama.reversed_edge_count}"
    )

    if args.save_both:
        print(f"提案手法を保存しました: {save_image(proposed.image, proposed_path)}")
        print(f"杉山法を保存しました: {save_image(sugiyama.image, sugiyama_path)}")
    if not args.no_show:
        show_comparison(
            proposed,
            sugiyama,
            seed=actual_seed,
        )
        if not args.no_save_prompt:
            prompt_to_save(
                proposed,
                sugiyama,
                proposed_save_path=proposed_path,
                sugiyama_save_path=sugiyama_path,
            )


if __name__ == "__main__":
    main()
