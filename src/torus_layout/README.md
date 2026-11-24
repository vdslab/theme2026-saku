# 独立したトーラス階層レイアウト

## 既定値の変更

この方式のCLI入力、階層割当・交差削減・座標割当、描画の既定値は
[`constants.py`](constants.py) にまとめています。反復数は `DEFAULT_ROUNDS`、
最小頂点間隔は `MIN_NODE_GAP` です。
配色・線種は `drawing/styles.py` にあります。
定数を編集した場合はプロセスを起動し直してください。CLI引数やAPI引数の明示指定が優先されます。
CLIと描画APIで従来から異なる周辺タイル表示の既定値は、別の定数で維持しています。

比較実験用の旧実装は [`src/old_torus_layout/`](../old_torus_layout/README.md) にまとめています。
旧モジュールのimportは `old_torus_layout.layer_assignment` などを使用します。

## フレームワーク全体を実行する

リポジトリルートから、以下のどちらかを実行します。

```sh
./theme2026-saku/bin/python src/torus_layout/main.py
# モジュールとして実行する場合:
PYTHONPATH=src ./theme2026-saku/bin/python -m torus_layout
```

グラフ生成 → 階層割当 → ダミー挿入 → sifting → 必要に応じて層回転 → 切れ目と整数周の同時最適化 →
BK系による座標割当 → 評価表示・描画保存、まで実行します。
既定値はwatts_strogatz、25ノード、近傍数4、再配線率0.1、seed未指定、
階層バランス`diff_square`、siftingは`global`で最大5回、UNWINDと境界最適化は有効、座標方式は`brandes_koepf_blocks_unsplit`です。

`radial` は原著のAlgorithm 1に沿い、片側の層を固定して、もう片側の頂点位置と辺の巻き数を差分で評価します。移動前の位置と巻き数を最初の最良候補とし、重み付き交差数が厳密に減った場合に更新します。最終層から第1層への接続も固有の層間として処理し、2層のときも両方向の帯を分けます。局所処理後は隣の層間や全体の交差が増えることがあります。

`--sifting-method parting` は全体最良の保存とダミー間線分の重み付けを行う従来方式、`--sifting-method shortest` は候補ごとに最短の巻き数を選び、前後両方の層間を評価する方式です。

`--sifting-method global` は Bachmaier ら（2011）の Global Sifting §5.4 をトーラスに適用した方式です。
元頂点を単独のブロック、元の長辺のダミー頂点列を一つのブロックとして、全層で共有する順序の中で動かします。
各候補で影響する帯の交差を評価し、入辺側と出辺側の外部線分には帯ごとに parting を試します。
内部線分の巻き数を共有の切れ目で 0 に保つことで、最終層と第1層の間も含め、内部線分同士の交差を予防します。
層回転（Algorithm 2）は既定で無効です。`--algo2`、`PipelineConfig(algo2=True)`、または `reduce_crossings(..., algo2=True)` で有効化できます。
UNWINDとは独立した設定で、併用時は層回転を先に実行します。
この実装は候補位置ごとに parting を列挙し、論文の差分高速化をそのまま再現したものではありません。

`radial` では [原著 §V-A](https://www.infosun.fim.uni-passau.de/~chris/down/RadialVisualization.pdf#page=9) に従い、両方の線分がダミー頂点間の線分である交差（タイプ2）を、対象層間の辺数 `|E|` で重み付けします。タイプ0・1の交差は重み1です。採否に使うのは、この重み付き交差数です。
`--seed` で乱数seedを固定すると同じ入力を再生成できます。

出力先の既定値は `output/torus_layout/` です。
全ての画像・`result.json` の保存と結果出力を終えてから、保存した最終図をウィンドウで表示します。
ウィンドウを閉じると終了します。`--no-show` で表示を無効にして保存のみ実行できます。
周辺タイルは既定で有効です。`--no-tile-surroundings` で無効化できます。
周辺はグレーアウトし、中央は元の色のまま表示します。ウィンドウは画像の縦横比に合わせ、
上下の余白を付けません。周辺の濃さは `constants.DEFAULT_SURROUNDING_OPACITY` で調整できます。
ノードの円が境界にかかる場合は、描画時に円の半径分の余白を確保します。

| 出力 | 内容 |
| --- | --- |
| `layout.png` | 提案手法による描画 |
| `result.json` | 設定、生成入力グラフ、階層割当、層内順序、各線分の巻き数、座標、評価値、時間 |
| `before_seam.png` | `--compare-seams` 指定時の境界最適化前の描画 |

同じ出力先への再実行では、今回の出力ファイルを上書きします。
比較したい実行は `--output-dir` を分けてください。

```sh
# 同じ階層割当を使って境界最適化前後を比較・描画する。
./theme2026-saku/bin/python src/torus_layout/main.py \
  --nodes 25 --seed 2 --edge-prob 0.01 --compare-seams \
  --output-dir output/torus_layout_seed2

# Watts–Strogatz生成器とBK座標割当を使う。
./theme2026-saku/bin/python src/torus_layout/main.py \
  --graph watts_strogatz --nodes 25 --neighbors 4 --rewire-prob 0.1 \
  --coordinate-method brandes_koepf --output-dir output/torus_layout_ws

# 全オプションの一覧。
./theme2026-saku/bin/python src/torus_layout/main.py --help
```

生成器は `cyclic` / `watts_strogatz` / `random` / `dag` / `mixed`、
座標方式は `torus_qp` / `torus_lp` / `brandes_koepf` /
`brandes_koepf_blocks_unsplit` / `brandes_koepf_blocks` /
`brandes_koepf_3x3` から選べます。
`brandes_koepf_3x3` は周囲8方向にコピーを置き、巻き数に応じてコピー間を接続し、
4方向BKの中央値統合後に中央のタイルだけを取り出す実験方式です。
周期射影を使わず、描画周期を座標の広がりに合わせます。
コピーの座標は独立で、周期的に同じ配置となる制約は課していません。
3×3の外側へ出るセグメントは除外します（巻き数の絶対値が2以上だと、
中央タイルから出る辺も一部対象外になります）。
実行例：

```sh
./theme2026-saku/bin/python src/torus_layout/main.py \
  --coordinate-method brandes_koepf_3x3 --seed 1569070748 \
  --no-show --output-dir output/torus_layout_3x3
```

境界処理の既定は `--seam-method joint` です。従来の巻き戻しとDPを使うには `--seam-method legacy` を指定します。
`--no-unwind` では整数周を固定して切れ目だけを最適化し、`--no-optimize-seams` では従来のUNWIND-LEVELだけを適用します。
比較モードでは、境界最適化の評価値と辺同士の交差数を検証します。

通常はルート `.env` のGurobi WLS設定を使います。ローカルライセンスを明示的に
選ぶ場合だけ `--local-license` を付けます。接続失敗時の自動切替はしません。
ローカルライセンスには問題サイズの制限がある場合があります。

この環境では、変更前のQP設定に `--local-license --compare-seams` を付けた実行で、
25ノードの入力から境界通過線分数4→2、交差数0→0を確認しました。
Watts–Strogatz・8ノードのLP座標割当も保存まで実行しています。

追加した入口は `main.py` と `__main__.py`、テストは `tests/test_main.py` です。

CLIの引数定義・検証は `cli_arguments.py`、境界最適化の比較は `seam_comparison.py`、
画像・JSONの保存と保存後の表示は `cli_output.py` に分離しています。
`main.py` はグラフ生成と設定の組み立て、各処理の呼び出し、エラー処理を担当します。
明示的なローカルライセンス選択を `layering/lib/solver.py` に追加し、
その選択は実行スコープを抜けると元に戻るようにしています。

> 既定の `brandes_koepf_blocks_unsplit` は、長辺ごとに全ダミー頂点で同じ `y` を共有します。層順と最小間隔を満たす最小の周期を使います。元の切れ目で内部線分の巻き数がすべて0なら、境界最適化後も各ブロックの頂点は同じ側に残るか、まとめて切れ目の反対側へ移ります。層内順序の制約が循環する場合は `--coordinate-method brandes_koepf_blocks` で分割を許可できます。
> `--coordinate-method brandes_koepf_blocks` は、長辺の連続するダミー頂点を同じ `y` に揃えます。層順・間隔の制約と両立しない箇所や、層内方向の巻きがある線分ではブロックを分けます。
> ブロックBKは射影前のBK座標を目標にし、各ブロックの配置時に周期境界を含む最小間隔を確保します。通常BKは周期射影で最小間隔を確保します。
> `--coordinate-method torus_qp` または `torus_lp` でQP・LPを明示的に選べます。
> `PipelineConfig(coordinate_method="torus_qp")` と `coordinate_bend_weight` も利用可能です。
> [定式化・比較実験・手法選定](../../documents/torus_coordinate_assignment.md)を参照してください。
> 旧実装と比較する場合は、現行側に `brandes_koepf` を指定し、
> 境界最適化とUNWINDを無効にします。座標は旧実装の平滑化0回に対応します。

## 従来方式のUNWIND-LEVEL

Algo2を有効にした場合は層回転の後に、いずれの場合も切れ目DPの前に、層間の共通の整数巻きを取り除きます。
各層間でダミー間線分の最小巻き数 `m` を求め、その層間の全線分から `m` を引きます。
内部線分がない層間では、同じ向きに換算した全線分の巻き数の最頻値を `m` とします。
この選択は、その層間の非ゼロ巻き数を持つ線分の本数を最小にします。重複線分も本数に含めます。
同数なら絶対値の小さい補正を優先し、0が同点なら変更しません。
この補正は切れ目に依存するため、DP前に適用する場合と、内部線分のルール→DP→全辺の補正→DPの
順に適用する場合を比較し、境界通過線分数が少ない結果を採用します。同数なら前者を維持します。
これは原論文の対象外だった層間にも共通巻きの除去を適用する拡張です。
逆向き辺は同じ向きに換算し、重複辺の巻き数は一度だけ更新します。
頂点順序は変わらず、交差評価に使う巻き数の差も保存されます。

原論文のAlgorithm 3の操作を循環階層へ適用したもので、原論文のタイプ3競合除去全体の実装ではありません。
任意の入力で境界通過線分数が必ず減るという保証はありません。
指摘画像の再現例では、上下の境界通過線分数3→0、交差数0→0を確認しました。
[Algo2との違い・検証記録](../../documents/algo2_common_turn_check.md)も参照してください。

`PipelineConfig(unwind_levels=False)` または `reduce_crossings(..., unwind=False)` で無効化できます。
旧版を再現する場合は、さらに `optimize_seams=False` を指定します。
`--compare-seams` の比較前後には同じUNWIND設定を適用します。

## 境界通過線分数の最適化

既定の `joint` は `crossing/joint_seam.py` の循環DPで、各層の切れ目と隣接層ペアごとの共通整数巻きを選びます。
ダミー同士の境界通過を0本にする組合せの中で、上下境界を通る全線分数を最小化します。
0本にできる組合せがなければエラーで報告します。
分割なしBKの層内順序制約が循環した場合は、従来方式でもダミー同士の通過を0本に保って座標を割り当てられるときに限り、警告を出して従来方式を適用します。
CLIの `result.json` では `settings.seam_method_used` に実際の方式を記録します。

従来方式の `legacy` はUNWIND-LEVELと `crossing/seam.py` の差分更新DPを順に適用します。
このDPは各呼び出しに与えられた整数周を固定し、全隣接ペアの密な表を持たずに切れ目を選びます。
既定の分割なし座標方式では内部線分数、全線分数の順に最小化し、ほかの座標方式では全線分数を最小化します。

```python
config = PipelineConfig(seam_method="legacy")
crossing = reduce_crossings(subdivided, seam_method="legacy")
```

`crossing.optimize_joint_seam(subdivided, crossing)` で同時最適化を単独適用でき、解がない場合は `None` を返します。
`crossing.optimize_seam(subdivided, crossing)` で固定した整数周に対する切れ目DPを適用でき、
`crossing.count_seam_segments(subdivided, crossing)` で通過線分数を数えられます。
入力は循環隣接レイヤー間の辺に分割済みであることが必要です。
空レイヤーは動かさない1候補とし、0・1レイヤーの場合は入力を維持します。
この追加によって、デフォルトの切れ目と座標は旧経路と異なる場合があります。
旧 `src/old_torus_layout/main.py` の処理は変更していません。

理論と実行結果は [境界最適化の検討](../../documents/torus_seam_optimization.md)、
再実行には `experiments/evaluate_seam_optimization.py` を参照してください。

## 移植時の構成

既存の `main.py` の計算を、責務ごとの小さなモジュールへ移植したパッケージです。
既存ファイル・実行経路はそのまま残し、通常実行コードから旧実装をimportしません。
変更したのは構造と入出力の表現です。目的関数、制約、初期化、探索・反復順、同点の選択、
QPの丸め、巻き数、座標計算、表示・保存の仕様を維持しています。

## 使用例

リポジトリルートから `PYTHONPATH=src` とプロジェクトのPython環境を使います。
通常実行では従来と同じ `.env` のGurobiライセンス設定が必要です。

```python
from generator import generate_graph
from torus_layout import Graph
from torus_layout.models import PipelineConfig
from torus_layout.pipeline import run_pipeline
from torus_layout.reporting import report_pipeline
from torus_layout.drawing import DrawingOptions, draw_layout

nodes, edges, used_seed = generate_graph("cyclic", n=8, num_cycles=2, edge_prob=0.01, seed=42)
result = run_pipeline(Graph(tuple(nodes), tuple(edges)), PipelineConfig(
    balance_method="diff_square", rounds=5,
))
if result is not None:
    report_pipeline(result)
    draw_layout(
        result.subdivided, result.crossing, result.coordinates,
        options=DrawingOptions(tile_surroundings=True, surrounding_opacity=0.5),
        save_path="layout.png", show=False,
    )
```

計算だけの場合は `run_pipeline` まで実行します。階層割当に失敗した場合は、
旧経路と同じく `None` が返ります。生成器や描画はパイプラインの依存先に含みません。
rootの `__init__.py` は `Graph` だけを公開し、ソルバーやMatplotlibを一括で読み込みません。

## 工程とファイルの役割

| 入口 | 処理と主なファイル |
| --- | --- |
| `layering.find_minimum_configuration` | `search.py` の二分探索と `minimize_wraps.py` のトーラス辺数最小化。現在の上限・判定を維持する |
| `layering.balance_layers` | `balance/` から4手法を選ぶ。`lib/model.py` と `lib/results.py` が共通の制約・解の取得を担当する |
| `layering.assign_layers` | 現在の階層数探索とバランス調整を順に実行する |
| `subdivision.insert_dummy_nodes` | 長距離辺を分割し、重みとトーラスフラグを引き継ぐ |
| `crossing.reduce_crossings` | `initialization.py` の円形重心初期順序、`sifting.py` などのsifting、指定に応じて `lib/embedding.py` の層回転を適用する |
| `crossing.count_crossings` | `lib/crossings.py` で現在のradial交差数を評価する |
| `coordinates.assign_coordinates` | `brandes_koepf.py` の4方向BK系整列・圧縮・中央値統合と、`periodic.py` の周期的な射影を行う |
| `drawing.create_figure` | `preparation.py` の検証・補完、`geometry.py` の周期境界処理、`artists.py` の図形描画を組み立て、Figureを返す |
| `drawing.draw_layout` | `output.py` で従来相当の保存・表示を行い、Figureを閉じる。周辺タイルは `tiles.py` が担当する |
| `pipeline.run_pipeline` | 各工程の順序と既存相当の計測を担当する |
| `reporting.report_pipeline` | 現在の階層・巻き数・交差数・計算時間を表示する |

バランスの4手法は次のとおりです。

- `diff`: 周期スパンの重み付き和を最小化するILP。
- `diff_square`: 周期スパンの重み付き二乗和を最小化するIQP。
- `qp`: 階層変数を連続緩和し、Pythonの `round` で整数化する。
- `barycenter`: `diff` の初期解を、現在の重心法の反復・補正で更新する。

`lib` は各工程内の共通処理に限定しています。工程間の依存は `models.py` の小さな型と
公開関数を通します。`validation.py` は型注釈のないPython呼び出し元への既存の実行時チェックを保ちます。

## 入出力の契約

- `Graph` は頂点列と有向辺列をtupleで保持し、入口でソート・重複除去しません。
  現行の使用例と比較ケースの頂点IDは整数・文字列です。各アルゴリズム内にある重複除去は元の順序で維持します。
- `LayerAssignmentResult.node_to_layer` が階層割当の基準です。
  `layers` プロパティは割当の反復順で層別一覧を作り、空レイヤーを補完しません。
- `LayerSearchResult.layer_count` は探索結果のレイヤー数です。
  実際の階層辞書のキー数や、描画領域の周期とは別に扱います。
- `SubdividedGraph` はダミー挿入後の頂点・辺・層・フラグ・重みと元頂点を保持します。
  `insert_dummy_nodes(..., layers=...)` に明示した空レイヤーも維持します。
  整数の最大IDの次からダミーを作り、所属不明の辺をそのまま残す既存の扱いも維持します。
- `CrossingResult` は、そのダミー挿入済みグラフの層内順序と巻き数です。
  通常の辺とsifting中の一時ID付き辺は別の型で扱います。
- `CoordinateResult` は座標と実際の計算に使った周期です。
  `min_gap` の既定値は1.0です。
- 公開関数は入力を作業用に変更しません。`frozen=True` は辞書の中身まで不変にするものではありません。
- `create_figure` の呼び出し側はFigureをcloseします。
  `draw_layout` は従来同様に出力後のcloseまで行います。座標を省略した場合の描画内の補完も維持します。

## 計測と既知の問題

CLIは層数探索・層調整・ダミー挿入・交差削減・座標割当を壁時計時間で計測します。
層数探索と層調整では、Gurobiの求解時間も内訳として出力します。
`computation_wall_seconds` はレイアウト本体の計算時間で、切れ目の比較と画像出力は別処理です。
境界通過は左右・上下ごとに元辺数、分割後の線分数、通過回数を出力します。

層割当は時間切れでも、実行可能解が得られた場合に変数値を読み取ります。
層数探索は従来の判定を使い、途中の候補で解が得られなければ、より多い層数を調べます。
時間切れの暫定解を含む探索結果には最適性の保証がありません。
`qp` の丸め後に制約違反が生じる既知の例も、旧実装との一致を確認して維持しています。

ダミー挿入の所属検索だけは、毎辺でのレイヤー走査を対応表に置き換えました。
300辺・30層の比較でリストへの所属確認が18,000回から0回になり、全出力が一致します。
前処理で所属一覧を一度走査し、各端点を辞書で検索します。複数層への重複所属では、
元と同じくソートされた層順で最後の所属を採用します。

## 検証

描画器は境界最適化後の巻き数をそのまま使い、`|ψ| > 1` の辺も全ての境界で分割します。
旧描画器は巻き数を符号だけで扱っていたため、複数巻きの辺については旧版と画像が異なります。
回帰テストは実際の描画線分の変位・終点・矢印を検証し、単一巻きの既存描画との一致も維持しています。

```sh
PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/torus-layout-mpl PYTHONPATH=src ./theme2026-saku/bin/python -m pytest src/torus_layout/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/torus-layout-mpl PYTHONPATH=src ./theme2026-saku/bin/python -m torus_layout.checks.check_imports
./theme2026-saku/bin/python src/torus_layout/checks/check_legacy_files.py
```

比較テストは、新旧双方の環境生成をテスト中だけ同一のローカルGurobi環境へ差し替えて実求解します。
通常実装のライセンス設定は変更しません。
通常描画・タイル描画・ダミー表示・座標省略の8組、および旧mainから保存した画像を、RGBAピクセル単位で比較します。

既存mainをそのまま実行する検証は、実装前後とも `token.gurobi.com` の名前解決で停止します。
ネットワーク接続を伴う通常のライセンス環境での完走は未確認です。
ローカルGurobi環境をテスト内で渡した旧mainは、画像保存まで実行・比較しています。

`tests/fixtures/protected_files.json` は移植時の既存ソースと設定のハッシュです。
`check_legacy_files` で変更がないことを確認できます。
このハッシュは旧コードを意図的に更新する将来の移行時に、比較基準とともに更新する対象です。
不要テストの整理に伴い、旧IQPの実行例、画面表示のみの描画テスト、
現行テストと重複する旧階層割当・生成器のテスト計4ファイルを削除し、保護対象からも外しました。
交差・座標・描画の固有の回帰ケースと、現行パッケージ・実験コードのテストは維持しています。
現在の保護対象は50ファイルです。残したテストは次のコマンドでまとめて実行できます。

旧実装の `old_torus_layout` への移動に合わせ、保護対象のパスとimport変更後のハッシュを更新しています。
テストは対象ごとの `tests/` に配置し、移動した保護対象のパスも更新しています。
配置の詳細は [テスト案内](../../documents/testing.md) を参照してください。

```sh
PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/torus-layout-mpl PYTHONPATH=src ./theme2026-saku/bin/python -m pytest src experiments/tests -q -p no:cacheprovider
```

### 型検査

Pyright CLIの取得はDNSエラーで実行できませんでしたが、インストール済みの
VS Code / Pylance 2026.4.1で、新パッケージを別ワークスペースとして検査し、型診断0件を確認しています。
`src/torus_layout` を別ウィンドウで開き、プロジェクトのPythonインタープリタを選択します。
新パッケージ内の `.vscode/settings.json` と `pyrightconfig.json` により、ワークスペース全体をstrictで検査します。
元のVS Code設定を変更する必要はありません。

公開関数は通常の定義と明示的な再エクスポートを使い、`check_imports.py` で型付きの呼び出しも確認します。
実行時の型注釈解決と、旧実装へのimportが通常コードにないこともテストします。

`typings/` はMatplotlibの使用APIだけの型宣言です。
ライブラリ同梱型の `**kwargs: Unknown` が伝播する箇所を限定的な宣言で補っています。
実装・実行時importや警告レベルは変更していません。詳細は `typings/README.md` を参照してください。

実装完了時の検証: 新パッケージの163テストが成功し、既存ソース・設定74ファイルのハッシュが一致しました。
