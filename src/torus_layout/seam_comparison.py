"""Measure layout quality and optionally validate seam optimization."""

from dataclasses import dataclass

from .coordinates import assign_coordinates
from .crossing import count_crossings, count_seam_segments, reduce_crossings
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
        unwind=config.unwind_levels,
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
    return SeamComparison(
        after_seams, after_crossings, before_seams, before_crossings,
        baseline, baseline_coordinates,
    )
