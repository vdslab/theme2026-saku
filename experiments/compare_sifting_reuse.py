"""Check drawing equality and compare wall times for fixed-input replays."""

import argparse
import json
from pathlib import Path


def load(path):
    with path.open(encoding="utf-8") as source:
        return {row["case"]: row for row in map(json.loads, source)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("without_reuse", type=Path)
    parser.add_argument("with_reuse", type=Path)
    args = parser.parse_args()
    baseline = load(args.without_reuse)
    reused = load(args.with_reuse)
    if baseline.keys() != reused.keys():
        raise ValueError("Replay inputs differ")
    for case, before in baseline.items():
        after = reused[case]
        result = {
            "case": case,
            "without_reuse_status": before.get("status", "ok"),
            "with_reuse_status": after.get("status", "ok"),
            "without_reuse_seconds": before["wall_seconds"],
            "with_reuse_seconds": after["wall_seconds"],
        }
        if "drawings" in before and "drawings" in after:
            fields = ("alternate_orders", "restart_attempts", "drawings", "selected_start",
                      "selected_without_extra_bends_or_seams")
            if any(before[field] != after[field] for field in fields):
                raise ValueError(f"Replay results differ for {case}")
            result.update(equal_drawings=True, speed_ratio=before["wall_seconds"] / after["wall_seconds"])
        print(json.dumps(result))


if __name__ == "__main__":
    main()
