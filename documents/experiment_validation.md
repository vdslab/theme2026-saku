# トーラス階層グラフ描画の追試

2026-11-20（日本時間）。前回の実験で残った問いを、結論に影響する順に追試した。生成グラフの新しい乱数種を固定し、前回の入力は時間切れの再試行に限って再利用した。

[HTML追試報告書](../output/torus_validation_20261120/index.html) · [前回の報告書](../output/torus_experiment_20261120/index.html)

## 追試の範囲

| グループ | 目的と制御 |
| --- | --- |
| `topology` | 20の同一無向骨格で、円環沿い、部分反転、ランダム、DAGを比較。dotに対する交差差が方向の操作で変わるか |
| `scc_control` | 全頂点を有向閉路でつないで1つのSCCを維持し、同じ追加辺の方向のみ変える |
| `public` | 方向が元データに存在するSampson、UKfaculty、macaqueの11条件。実在の循環に効果が転用できるか |
| `public_retry` | 初回のトーラス未完走4条件を長い予算で再試行し、既定法と線形分配・1回掃引で原因と回復率を測る。残る1条件は求解8秒まで再試行 |
| `budget` | 既存比較から欠測と対照を選び、平面・放射・dot・トーラスを同じ壁時計予算で再比較 |
| `ranks` | 層数と左右通過辺数を固定。WorkLimit下のMIP startの有無、線形／二乗和、最大2層追加を比較 |
| `winding` | 層内順序と±1の巻き数を独立に全列挙。前回の巻き数0の照合を拡張 |
| `sifting` | 前段を固定し1回、既定、巻き数固定と自由、複数初期順の計算費用と品質を比較 |
| `seams` | 新しい入力でDP単独候補を保持し、通過線分・通過元辺・回数を個別に評価 |
| `seam_stress` | 長辺と複数巻きの人工例で全切れ目を列挙し、線分最小と元辺最小が異なることがあるかを調べる |
| `coordinates` | 周期を制御してBKの反復、LPの曲がり罰則、同周期の3×3 BKを比較 |
| `coordinate_audit` | 固定埋め込みでLP系に出た微小な交差差を、リフトした層間帯の独立計数と照合 |
| `scaling` | 36–120頂点で二次・線形分配を比較し、分配の可否と後段の1回掃引の時間を分けて測定 |
| `subdivision` | 長い辺が多い50–800頂点で、ダミー挿入が同じ出力を保つかと索引化の実時間を確認 |
| `geometry` | 人工36例の境界回転・移動前後と層順ベースの交差数を照合 |
| `wls_probe` | 201変数の二次モデルでフルライセンスの実行可否を確認。WLSのホスト名解決で停止 |

## 再実行

計算グループの生データには solver 状態、エラーの型、時間制限を保存した。Chrome等で開く報告書は同じディレクトリ内のCSVと画像を参照する。

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py topology \
  --jobs 3 --wall-seconds 10 --solver-seconds 1.25 --output output/retake/topology

MPLCONFIGDIR=/tmp/torus-study-mpl ./theme2026-saku/bin/python experiments/report_torus_validation.py \
  output/torus_validation_20261120
```

グループを置換して実行できる。実行時の上限と並行数は各グループの `settings.json` を参照。`public_retry` は `--public` が指す sources ディレクトリの親に `public/rows.jsonl` が先にできていることが前提。`--wls` は既存の WLS 構成を明示的に使う。環境変数の値は出力しない。

公開データの入力はNetworkXに同梱された [SampsonのZIP](https://github.com/networkx/networkx/blob/main/examples/drawing/sampson_data.zip) と、igraphdataの [UKfacultyとmacaque](https://github.com/igraph/igraphdata/tree/main/data)。Pajekで追加された無向データを混ぜていない。2つのRデータは、旧igraphリストの版を検査した後、先頭二列の端点ベクトルから整数のCSVに変換した。自己ループを除き、方向を保持して誘導部分グラフを作成した。入力番号はグラフごとに再割付した。元の頂点属性は評価に使っていない。
