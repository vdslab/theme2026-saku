"""Sift vertex positions with the shortest angular winding for each candidate."""

from ..models import Edge, Layers, Winding
from .lib.crossings import pair_crossings, pair_positions
from .lib.embedding import edges_by_directed_strip


def sift_with_shortest_windings(
    order: Layers, layers: list[int], edges: list[Edge], rounds: int
) -> Winding:
    """Score the two directed strips affected by each trial position."""
    strips = edges_by_directed_strip(order, layers, edges)
    by_layer: dict[int, list[tuple[int, int, list[Edge]]]] = {layer: [] for layer in layers}
    winding: Winding = dict.fromkeys(edges, 0)
    scores: dict[tuple[int, int], int] = {}
    for (source, target), segments in strips.items():
        if segments:
            by_layer[source].append((source, target, segments))
            by_layer[target].append((source, target, segments))
            initial, count = score_strip(order, source, target, segments)
            winding.update(initial)
            scores[source, target] = count

    for _ in range(rounds):
        improved = False
        for layer in layers:
            adjacent = by_layer[layer]
            best_score = sum(scores[u, v] for u, v, _ in adjacent)
            for node in list(order[layer]):
                if best_score == 0:
                    break
                best_order = order[layer]
                original_position = best_order.index(node)
                remaining = [other for other in best_order if other != node]
                best_strips = None
                for position in range(len(best_order)):
                    if position == original_position:
                        continue
                    candidate = remaining[:position] + [node] + remaining[position:]
                    order[layer] = candidate
                    trial = [score_strip(order, u, v, segments) for u, v, segments in adjacent]
                    trial_score = sum(count for _, count in trial)
                    if trial_score < best_score:
                        best_score, best_order, best_strips = trial_score, candidate, trial
                order[layer] = best_order
                if best_strips is not None:
                    improved = True
                    for (u, v, _), (offsets, count) in zip(adjacent, best_strips, strict=True):
                        winding.update(offsets)
                        scores[u, v] = count
        if not improved:
            break
    return winding


def score_strip(order: Layers, source: int, target: int, edges: list[Edge]) -> tuple[Winding, int]:
    source_positions, target_positions = pair_positions(order, source, target)
    source_size, target_size = len(source_positions), len(target_positions)
    period = source_size * target_size
    winding = {}
    for u, v in edges:
        # Compare normalized angles exactly. On a half-turn tie, use zero as in radial.
        displacement = target_positions[v] * source_size - source_positions[u] * target_size
        winding[u, v] = -1 if 2 * displacement > period else 1 if 2 * displacement < -period else 0
    return winding, pair_crossings(order, winding, source, target, edges)
