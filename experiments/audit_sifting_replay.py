"""Compare work-limited sifting replays across execution schedules."""

import argparse
import json
from pathlib import Path


def records(path, key):
    with path.open(encoding="utf-8") as source:
        result = {}
        for row in map(json.loads, source):
            identity = key(row)
            if identity in result:
                raise ValueError(f"duplicate record: {identity}")
            result[identity] = row
        return result


def audit(first, second):
    manifest = lambda path: records(path / "inputs.jsonl", lambda row: row["id"])
    if manifest(first) != manifest(second):
        raise ValueError("input manifests differ")
    settings = [json.loads((p / "settings.json").read_text()) for p in (first, second)]
    for key in ("source_sha256", "case_ids", "sifting_check_limits", "wall_seconds", "solver_seconds"):
        if settings[0][key] != settings[1][key]:
            raise ValueError(f"settings differ for {key}")
    layouts = [records(p / "rows.jsonl", lambda row: (row["case"], row["variant"])) for p in (first, second)]
    if layouts[0].keys() != layouts[1].keys():
        raise ValueError("trial coverage differs")
    for case, variant in sorted(layouts[0]):
        left, right = (rows[case, variant] for rows in layouts)
        if "sifting_check_limit" not in left:
            continue
        assert left["status"] == right["status"] == "ok"
        assert left["sifting_cutoff"] and right["sifting_cutoff"]
        for key in ("sifting_stop_checks", "embedding_sha256", "crossings"):
            assert left[key] == right[key], (case, variant, key)
        assert left["sifting_stop_checks"] == left["sifting_check_limit"]
        left_quality, right_quality = (rows[case, variant + "_geometry"] for rows in layouts)
        assert left_quality["status"] == right_quality["status"] == "ok"
        for key in ("geometric_crossings", "bends", "either_seam_edges"):
            assert left_quality[key] == right_quality[key], (case, variant, key)
        yield {"case": case, "variant": variant, "checks": left["sifting_stop_checks"],
               "embedding_sha256": left["embedding_sha256"],
               "geometric_crossings": left_quality["geometric_crossings"],
               "bends": left_quality["bends"], "worker_counts": [s["jobs"] for s in settings]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    for row in audit(args.first, args.second):
        print(json.dumps(row))


if __name__ == "__main__":
    main()
