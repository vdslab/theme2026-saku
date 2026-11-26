import json
from collections import defaultdict, Counter
from pathlib import Path
from statistics import median
d=json.loads(Path(__file__).with_name('results.json').read_text())
g=defaultdict(list)
for r in d['rows']: g[r['method']].append(r)
def valid(r):
    return 'error' not in r and not any(r[k] for k in ('order_violations','gap_violations','domain_violations'))
common=set.intersection(*({r['case'] for r in rows if valid(r)} for m,rows in g.items() if m!='3x3'))
bas={r['case']:r for r in g['BK']}
print('setup failures',d['failures'],'case count',len(bas),'core common cases',len(common))
for m, rows in sorted(g.items()):
    ok=[r for r in rows if 'error' not in r]
    sub=[r for r in rows if r['case'] in common and 'error' not in r]
    print(m,len(ok),sum(map(valid,rows)), 'common',len(sub), 'ms',round(median(r['ms'] for r in sub),3) if sub else None,
          'length %',round(100*median(r['total_edge_length']/bas[r['case']]['total_edge_length'] for r in sub),1) if sub else None,
          'bends',round(sum(r['bends'] for r in sub)/len(sub),2) if sub else None,
          'period %',round(100*median(r['period']/bas[r['case']]['period'] for r in sub),1) if sub else None,
          'period enlargements',sum(r['period']>bas[r['case']]['period'] for r in sub),
          'cross diff',sum(r['geometric_crossings']!=r['embedding_crossings'] for r in ok),
          'straight %',round(100*sum(r['aligned_inner_segments'] for r in sub)/max(1,sum(r['inner_segments'] for r in sub)),1),
          'errs',Counter(r.get('error','') for r in rows if 'error' in r),
          'bad', [sum(bool(r[k]) for r in ok) for k in ('order_violations','gap_violations','domain_violations')])
for case in sorted(bas):
    if not case.startswith('watts_strogatz-25-'): continue
    print(case,[(m,[(round(r['total_edge_length'],1),r['bends'],r['period']) for r in rows if r['case']==case and 'error' not in r]) for m,rows in sorted(g.items())])
for family in sorted({r['family'] for r in bas.values()}):
    print('family',family,[(m,round(sum(r['bends'] for r in rows if r['family']==family and r['case'] in common)/sum(1 for r in rows if r['family']==family and r['case'] in common),1)) for m,rows in sorted(g.items()) if m!='3x3' and any(r['family']==family and r['case'] in common for r in rows)])
