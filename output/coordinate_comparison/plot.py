import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt

folder = Path(__file__).parent
data = json.loads((folder / 'results.json').read_text())
groups = defaultdict(dict)
for row in data['rows']:
    if 'error' not in row and not any(row[k] for k in ('order_violations', 'gap_violations', 'domain_violations')):
        groups[row['method']][row['case']] = row
cases = sorted(set.intersection(*(set(rows) for method, rows in groups.items() if method != '3x3')))
methods = ['BK', 'BK 0', 'Blocks', 'Blocks 0', 'Unsplit', 'Unsplit 0', '3x3',
           'QP', 'QP bend 1', 'LP', 'LP bend 1']
fig, axes = plt.subplots(1, 3, figsize=(11, 5.3), layout='constrained')
metrics = [[], [], []]
for method in methods:
    eligible = [groups[method][case] for case in cases if case in groups[method]]
    metrics[0].append(median(row['total_edge_length'] / groups['BK'][row['case']]['total_edge_length'] for row in eligible) * 100)
    metrics[1].append(mean(row['bends'] for row in eligible))
    metrics[2].append(median(row['ms'] for row in eligible))
colors = ['#356675' if method in ('Unsplit', 'Unsplit 0', 'LP bend 1', 'QP') else '#9eadae' for method in methods]
for i, (axis, points, title) in enumerate(zip(axes, metrics, ('Total edge length (% of BK)', 'Bends per graph (mean)', 'Coordinate assignment (ms)'))):
    marks = axis.barh(methods, points, color=colors)
    axis.invert_yaxis()
    axis.set_title(title)
    axis.bar_label(marks, fmt='%.1f', padding=3, fontsize=8)
    axis.set_xlim(0, max(points)*1.18)
    axis.spines[['top', 'right', 'left']].set_visible(False)
    axis.tick_params(axis='y', length=0, labelleft=i==0)
    if i == 0:
        axis.axvline(100, color='#33424a', linewidth=.9, linestyle='--')
fig.suptitle(f'Toroidal coordinate assignment · {len(cases)} matched graphs')
fig.savefig(folder / 'comparison.png', dpi=160)
