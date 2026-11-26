"""Summarize matched linear and square results by graph size."""
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

root = Path(__file__).resolve().parent
groups = defaultdict(lambda: defaultdict(dict))
with (root / "per_graph_metrics.csv").open(encoding="utf-8", newline="") as source:
    for row in csv.DictReader(source):
        groups[int(row["nodes"])][row["case"]][row["method"]] = row

lines = [
    "# 線形配分と二乗和配分の比較", "",
    "各セルは実測値の中央値を **線形 / 二乗和** の順に表示します。総辺長は完成図の辺中心線の総延長（座標単位）です。各サイズ20件のうち10件はWSです。", "",
    "| 頂点数 | ダミー数 | 最大スパン | 幾何交差数 | 総辺長 | 配分時間 (秒) | 後段時間 (秒) |",
    "|---:|---:|---:|---:|---:|---:|---:|",
]
metrics = (
    "actual_dummy_count", "max_span", "geometric_crossings", "total_edge_length",
    "allocation_seconds", "drawing_seconds",
)
for size, cases in sorted(groups.items()):
    if size not in (20, 40, 60):
        continue
    pairs = [
        (case["linear"], case["square"]) for case in cases.values()
        if all(case[method]["drawing_status"] == "ok" for method in ("linear", "square"))
    ]
    cells = [str(size)]
    for metric in metrics:
        values = []
        for index in range(2):
            rows = [pair[index] for pair in pairs]
            scores = [float(row[metric]) for row in rows if row[metric]]
            values.append(f"{median(scores):.5g}" if scores else "—")
        cells.append(" / ".join(values))
    lines.append("| " + " | ".join(cells) + " |")

lines.extend([
    "",
    "- **配分時間**は、レイヤー数と折り返す辺の本数が決まったあと、各頂点をどの層に置くかを求める時間です。",
    "- **後段時間**は、配分結果から完成図を作る時間です。ダミー挿入、交差削減、境界最適化、座標割当を含みます。",
    "",
    "共通のレイヤー数探索と、完成図の交差数や辺長を測る時間は別計測です。", "",
    "[系列別の結果](report.md) · [全指標の元データ](per_graph_metrics.csv) · "
    "[比較図1](drawings/presentation_v5/random-20-2-928000.png) · "
    "[比較図2](drawings/presentation_v5/watts_strogatz-40-2-930029.png)", "",
])
(root / "comparison_tables.md").write_text("\n".join(lines), encoding="utf-8")
