# レイヤー数探索の再実験

各サイズ20入力。辺数は頂点数の2倍で、DAG・ランダム有向・SCC連結・Watts–Strogatzを各5件、種701〜705で生成した。20頂点は全候補を列挙し、40〜100頂点は上限と直前層を独立に求解した。

| 頂点数 | 照合 一致／不一致／未確認 | 折り返し辺 減／同／増 | 固定層数 | 壁時計時間の中央値 二分／固定 |
|---:|---:|---:|---:|---:|
| 20 | 20／0／0 | 10／10／0 | 7 | 0.039／0.006秒 |
| 40 | 20／0／0 | 13／7／0 | 9 | 0.106／0.018秒 |
| 60 | 20／0／0 | 16／4／0 | 11 | 0.200／0.084秒 |
| 80 | 20／0／0 | 16／4／0 | 13 | 0.473／0.860秒 |
| 100 | 20／0／0 | 16／4／0 | 15 | 0.721／1.013秒 |
| **全体** | **100／0／0** | **71／29／0** | — | — |

両方式とも100/100件で実行可能解を返し、ライセンス上限は0件だった。1秒条件で固定層数法は26件が時間切れとなった。両方式の最適性が確認できた74ペアでは、折り返し辺は45件で減少し、29件で同数だった。

1秒条件で未確認だった100頂点のWatts–Strogatz（種701）は、100層の独立求解だけを10秒上限で再試行し、約2.88秒で折り返し辺の最適値6本を証明した。壁時計時間の集計は1秒条件の方式比較を用いた。

[入力](inputs.jsonl) · [全試行](results.jsonl) · [求解ログ](calls.jsonl) · [補足照合](verification_retry.jsonl) · [設定](settings.json) · [1秒条件の系列別集計](tables.md)

```sh
PYTHONPATH=src ./theme2026-saku/bin/python experiments/audit_layer_count_search.py --sizes 20 40 60 80 100 --output output/torus_layer_search_steps20_rerun --time-limit 1
./theme2026-saku/bin/python experiments/summarize_layer_count_search.py output/torus_layer_search_steps20_rerun
```

[補足照合の再実行手順](../../documents/torus_layer_search_20261126.md#再実行)
