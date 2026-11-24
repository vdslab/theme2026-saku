"""Measure layout quality and optionally validate seam optimization."""

from dataclasses import dataclass

from .coordinates import assign_coordinates
from .crossing import count_crossings, count_seam_segments, reduce_crossings
from .crossing.seam import seam_score
from .models import CoordinateResult, CrossingResult, PipelineConfig, PipelineResult


@dataclass(frozen=True)
class SeamComparison:
    after_seams: int
    after_crossings: int
    before_seams: int | None = None
    before_crossings: int | None = None
    baseline: CrossingResult | None = None
    baseline_coordinates: CoordinateResult | None = None


def compare_seams(
    result: PipelineResult, config: PipelineConfig, *, enabled: bool
) -> SeamComparison:
    after_seams = count_seam_segments(result.subdivided, result.crossing)
    after_crossings = count_crossings(result.subdivided, result.crossing)
    if not enabled:
        return SeamComparison(after_seams, after_crossings)

    baseline = reduce_crossings(
        result.subdivided, rounds=config.rounds, optimize_seams=False,
        unwind=config.unwind_levels, sifting_method=config.sifting_method, algo2=config.algo2,
    )
    before_seams = count_seam_segments(result.subdivided, baseline)
    before_crossings = count_crossings(result.subdivided, baseline)
    prioritize_internal = config.coordinate_method == "brandes_koepf_blocks_unsplit"
    before_score = seam_score(result.subdivided, baseline, prioritize_internal)
    after_score = seam_score(result.subdivided, result.crossing, prioritize_internal)
    if after_score > before_score or after_crossings != before_crossings:
        raise RuntimeError(
            "境界最適化の検証失敗: 通過線分の評価値が悪化、または交差数が変化しました"
        )
    baseline_coordinates = assign_coordinates(
        result.subdivided,
        baseline,
        method=config.coordinate_method,
        bend_weight=config.coordinate_bend_weight,
    )
    if prioritize_internal:
        print(f"内部線分の境界通過数: {before_score[0]} → {after_score[0]}")
    print(f"境界通過線分数: {before_seams} → {after_seams}")
    print(f"辺同士の交差数: {before_crossings} → {after_crossings}")
    return SeamComparison(
        after_seams, after_crossings, before_seams, before_crossings,
        baseline, baseline_coordinates,
    )
