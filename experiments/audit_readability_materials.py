"""Verify stimulus answers, form counterbalancing and scorer behavior."""

import argparse
from collections import Counter
import csv
from itertools import product
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import networkx as nx

from prepare_torus_readability import CONDITIONS, SIZES, TASKS, load, score


def audit(stimuli, presentation):
    key = {row["trial"]: row for row in load(stimuli / "answer_key.csv")}
    assert len(key) == 24
    for item in key.values():
        manifest = json.loads(item["layout_manifest"])["graph"]
        graph = nx.DiGraph(manifest["edges"])
        a, b = int(item["a"]), int(item["b"])
        if item["task"] == "direction":
            assert graph.has_edge(a, b) != graph.has_edge(b, a)
            answer = "A_to_B" if graph.has_edge(a, b) else "B_to_A"
        else:
            paths = list(nx.all_shortest_paths(graph, a, b))
            assert len(paths) == 1
            answer = str(len(paths[0]) - 1)
        assert item["answer"] == answer

    forms = [load(stimuli / f"form_{group}.csv") for group in range(3)]
    html = (presentation / "index.html").read_text(encoding="utf-8")
    embedded, = re.findall(r'<script type="application/json" id="forms">(.*?)</script>', html, re.S)
    published = json.loads(embedded)
    assert set(published) == {"0", "1", "2"}
    seen = Counter()
    for group, form in enumerate(forms):
        assert len(form) == len(key) and {r["trial"] for r in form} == key.keys()
        assert published[str(group)] == [
            {field: row[field] for field in ("trial", "image", "prompt")}
            | {"task": key[row["trial"]]["task"]} for row in form
        ]
        cells = Counter()
        for row in form:
            item = key[row["trial"]]
            cells[int(item["size"]), item["task"], item["wraps"], row["condition"]] += 1
            seen[row["trial"], row["condition"]] += 1
            image = Path(row["image"])
            assert (stimuli / image).read_bytes() == (presentation / image).read_bytes()
        assert cells == dict.fromkeys(product(SIZES, TASKS, ("0", "1"), CONDITIONS), 1)
    assert seen == dict.fromkeys(product(key, CONDITIONS), 1)

    # Run synthetic responses in a temporary directory. They are never study data.
    responses = []
    for person, group, form in (
        ("fixture-0", 0, forms[0]), ("fixture-1", 1, forms[1]),
        ("fixture-2", 2, forms[2]), ("fixture-interrupted", 0, forms[0]),
        ("fixture-incomplete", 1, forms[1][:-1]),
    ):
        for index, row in enumerate(form):
            correct = row["condition"] == "torus_context"
            responses.append({
                "participant": person, "group": group, "trial": row["trial"],
                "answer": key[row["trial"]]["answer"] if correct else "fixture-wrong",
                "seconds": 2, "interrupted": int(person == "fixture-interrupted" and index == 0),
            })
    with TemporaryDirectory() as directory:
        path = Path(directory)
        with (path / "fixture.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(responses[0]))
            writer.writeheader()
            writer.writerows(responses)
        aggregate = path / "aggregate.csv"
        score(SimpleNamespace(stimuli=stimuli, responses=path / "fixture.csv",
                              output=aggregate, exclude_interrupted=True))
        rows = load(aggregate)
        primary, = [r for r in rows if (r["task"], r["torus_path_wraps"], r["metric"],
                                       r["treatment"], r["control"]) ==
                    ("distance", "1", "accuracy", "torus_context", "torus_base")]
        assert all(int(primary[field]) == expected for field, expected in {
            "participants": 5, "complete_participants": 4,
            "excluded_interrupted_participants": 1, "paired_participants": 3,
        }.items())
        assert all(float(primary[field]) == 1 for field in ("delta_mean", "ci_low", "ci_high"))
    return {"verified_answers": len(key), "verified_published_forms": len(forms),
            "verified_copied_images": len(seen),
            "items_per_size_task_wrap_condition_per_form": 1,
            "synthetic_scoring_fixture": "passed", "participant_responses_used": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stimuli", type=Path)
    parser.add_argument("presentation", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.stimuli, args.presentation), indent=2))


if __name__ == "__main__":
    main()
