"""Render the layer-count audit tables from the saved solver and case records."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from statistics import median


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def table(title, columns, rows):
    lines = [f"## {title}", "", "| " + " | ".join(columns) + " |",
             "|" + "|".join("---" for _ in columns) + "|"]
    lines += ["| " + " | ".join(map(str, row)) + " |" for row in rows]
    return "\n".join(lines)


def count_verification(rows, key):
    counts = Counter(row["verification"].get(key) for row in rows)
    return (counts["match"] + counts["mismatch"], counts["match"],
            counts["mismatch"], counts["unverified"])


def format_check(rows, key):
    checked, match, mismatch, unresolved = count_verification(rows, key)
    return f"{match}/{mismatch}/{unresolved}" if checked + unresolved else "—"


def paired(rows):
    return [row for row in rows if row["binary"]["completed"] and row["fixed"]["completed"]]


def difference(row, metric):
    return row["binary"][metric] - row["fixed"][metric]


def median_delta(rows, metric):
    if not rows:
        return "—"
    delta = median(difference(row, metric) for row in rows)
    return f"{delta:+.3f}" if metric == "seconds" else f"{delta:+g}"


def comparison(rows):
    pairs = paired(rows)
    improved = [r for r in pairs if difference(r, "wraps") < 0]
    counts = Counter((delta > 0) - (delta < 0) for delta in
                     (difference(row, "wraps") for row in pairs))
    proven = [
        row for row in pairs
        if row["verification"]["result"] == "match"
        and row["fixed"]["terminations"] == ["optimal"]
    ]
    counts_proven = Counter((delta > 0) - (delta < 0) for delta in
                            (difference(row, "wraps") for row in proven))
    return [
        len(pairs), f"{counts[-1]}/{counts[0]}/{counts[1]}",
        f"{counts_proven[-1]}/{counts_proven[0]}/{counts_proven[1]}",
        median_delta(improved, "wraps"),
        median_delta(pairs, "layers"), median_delta(pairs, "seconds"),
        median_delta(improved, "layers"), median_delta(improved, "seconds"),
    ]


def performance(rows, phase):
    measurements = [row[phase] for row in rows]
    completed = [row for row in measurements if row["completed"]]
    timeout = [row for row in measurements if "time_limit" in row["terminations"]]
    return [
        f"{len(completed)}/{len(rows)}", f"{len(completed)/len(rows):.0%}",
        len(timeout), sum(not r["completed"] for r in timeout),
        sum("license_size" in r["terminations"] for r in measurements),
        f"{median(r['calls'] for r in measurements):g}",
        f"{median(r['seconds'] for r in measurements):.3f}",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    results = read_jsonl(directory / "results.jsonl")
    calls = read_jsonl(directory / "calls.jsonl")
    inputs = read_jsonl(directory / "inputs.jsonl")
    settings = json.loads((directory / "settings.json").read_text())
    seeds_by_family = settings.get("seeds_by_family")
    if seeds_by_family is None:
        seeds_by_family = dict.fromkeys(settings["families"], settings["seeds"])
    expected_cases = {(n, family, seed) for n in settings["sizes"]
                      for family, seeds in seeds_by_family.items() for seed in seeds}
    expected = len(expected_cases)
    assert {(r["nodes"], r["family"], r["seed"]) for r in results} == expected_cases
    assert len(results) == len(inputs) == expected
    assert len({r["case"] for r in results}) == expected
    assert {r["case"] for r in results} == {r["id"] for r in inputs}

    groups = defaultdict(list)
    sizes = defaultdict(list)
    by_case_phase = defaultdict(list)
    for call in calls:
        by_case_phase[call["case"], call["phase"]].append(call)
    for row in results:
        groups[row["nodes"], row["family"]].append(row)
        sizes[row["nodes"]].append(row)
        assert row["edges"] == row["nodes"] * settings["edges_per_node"]
        for phase in ("binary", "fixed"):
            assert row[phase]["calls"] == len(by_case_phase[row["case"], phase])
        if row["nodes"] == min(settings["sizes"]):
            assert [r["layers"] for r in by_case_phase[row["case"], "enumeration"]] == list(
                range(1, row["nodes"] + 1))
    with (directory / "paired.csv").open("w", newline="") as stream:
        rows = []
        for r in paired(results):
            rows.append({
                "case": r["case"], "nodes": r["nodes"], "edges": r["edges"],
                "family": r["family"], "seed": r["seed"],
                **{f"{method}_{key}": r[method][key]
                   for method in ("binary", "fixed")
                   for key in ("wraps", "layers", "seconds", "calls")},
                **{f"delta_{key}": difference(r, key)
                   for key in ("wraps", "layers", "seconds", "calls")},
                "verification": r["verification"]["result"],
                "fixed_termination": r["fixed"]["terminations"][0],
            })
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    text = [
        "# レイヤー数探索の実測集計", "",
        table("入力", ["頂点", "辺", *settings["families"], "計"], [
            (n, rows[0]["edges"], *(len(groups[n, f]) for f in settings["families"]), len(rows))
            for n, rows in sizes.items()
        ]),
        table("正しさの照合", ["頂点", "系列", "照合済み", "一致", "不一致", "未確認",
                                "上限 一致/不一致/未確認", "直前 一致/不一致/未確認"], [
            (n, f, *count_verification(rows, "result"),
             format_check(rows, "upper_result"), format_check(rows, "predecessor_result"))
            for (n, f), rows in groups.items()
        ]),
        table("固定層数法との対応比較", [
            "頂点", "系列", "完了ペア", "折返し 減/同/増", "両方式証明済み 減/同/増",
            "減少例 Δ折返し", "全ペア Δ層", "全ペア Δ秒", "減少例 Δ層", "減少例 Δ秒",
        ], [(n, f, *comparison(rows)) for (n, f), rows in groups.items()] +
           [("全体", "全系列", *comparison(results))]),
        table("探索コストと完了率", [
            "頂点", "系列", "方式", "結果あり", "完了率", "時間切れあり", "時間切れ・結果なし",
            "ライセンス上限", "呼出数中央値", "壁時計秒中央値",
        ], [(n, f, phase, *performance(rows, phase))
            for (n, f), rows in groups.items() for phase in ("binary", "fixed")] +
           [(n, "全系列", phase, *performance(rows, phase))
            for n, rows in sizes.items() for phase in ("binary", "fixed")]),
        table("求解単位の終了内訳", [
            "工程", "最適", "実行不能", "時間切れ・解あり", "時間切れ・解なし",
            "ライセンス上限", "その他",
        ], [(phase, *(sum(r["termination"] == status for r in rows)
                      for status in ("optimal", "infeasible")),
             *(sum(r["termination"] == "time_limit" and
                   (r["wraps"] is not None) == feasible for r in rows)
               for feasible in (True, False)),
             sum(r["termination"] == "license_size" for r in rows),
             sum(r["termination"] not in {"optimal", "infeasible", "time_limit", "license_size"}
                 for r in rows))
            for phase in dict.fromkeys(r["phase"] for r in calls)
            for rows in [[r for r in calls if r["phase"] == phase]]]),
    ]
    (directory / "tables.md").write_text("\n\n".join(text) + "\n")


if __name__ == "__main__":
    main()
