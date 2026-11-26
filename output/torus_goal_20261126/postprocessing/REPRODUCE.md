# 再実行手順

リポジトリルートで、以下を順に実行する。階層割当は実験ごとに各入力1回。局所Gurobiライセンス、モデルごとに3秒、1スレッド、ソルバーseed 0を前回の比較コードに合わせた。バランス法は現在の既定値 `diff_square`。両条件の後段予算は1試行につき60秒の壁時計時間で、既定フォールバックも同じ予算内に含む。

```sh
export MPLBACKEND=Agg PYTHONHASHSEED=0
export MPLCONFIGDIR=/private/tmp/saku-post-mpl XDG_CACHE_HOME=/private/tmp/saku-post-cache
./theme2026-saku/bin/python experiments/compare_pipeline_postprocessing.py output/torus_goal_20261126/postprocessing_smoke --smoke
./theme2026-saku/bin/python experiments/compare_pipeline_postprocessing.py output/torus_goal_20261126/postprocessing
./theme2026-saku/bin/python experiments/report_pipeline_postprocessing.py output/torus_goal_20261126/postprocessing
```

計測結果を保持したまま、保存済みの入力と階層割当で再実行する場合は以下を使う。ダミー分割を復元し、保存したチェーンと照合する。

```sh
./theme2026-saku/bin/python experiments/compare_pipeline_postprocessing.py output/torus_goal_20261126/postprocessing_replay --replay output/torus_goal_20261126/postprocessing
./theme2026-saku/bin/python experiments/report_pipeline_postprocessing.py output/torus_goal_20261126/postprocessing_replay
```

集計と図だけを作り直す場合は、対象ディレクトリに対して `report_pipeline_postprocessing.py` のみを実行する。図は保存した分割済み中心線と頂点座標を使い、左右とも1層72 pxで描く。

- `inputs.json` に全入力のID、族、頂点、順序付き有向辺、辺集合の照合先を保存した。
- `settings.json` に両条件の全設定と時間上限を保存した。
- 入力ごとのJSONに共通の階層割当、折り返しフラグ、ダミーチェーンと、各方式の実行順、実際の関数呼び出し、反復数、段階別の層順・巻き数・交差・境界通過、失敗工程、座標割当試行、完成図の中心線を保存した。
- `measurements.csv` は試行ごとの平坦化データ。`paired.csv` は入力ごとの差。`summary.csv` は全体・群別の対応集計。`completion.csv` は完走集計。`timing_all_trials.csv` は失敗を含む試行時間の集計。
- 後段全体はsiftingの初期化、Algo2、境界処理、座標割当と実行されたフォールバックを含む。階層割当、ダミー挿入、メトリクス集計、保存と描画は計測外。独立した反復計測は行わず、入力順に単独試行して先行方式を毎回交代した。埋め込みコピーの時間は後段全体の記録から差し引いた。
- 幾何交差は前回と同じ中心線の横断イベント数、折れはダミー位置での方向変化が1度を超えた回数を数えた。境界を通る元辺は左右か上下のいずれかを通る元辺の和集合。長さは巻きを戻した中心線の長さで、層間隔1を単位とする。

補足比較は、保存済みの後処理後の埋め込みに対し両方式で分割ありBKを適用する。境界処理の設定と埋め込みを固定し、座標割当だけを差し替える。結果は `split_bk/` に保存する。

```sh
./theme2026-saku/bin/python experiments/compare_split_bk_supplement.py output/torus_goal_20261126/postprocessing
```
