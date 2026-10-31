# 独立したトーラス階層レイアウト

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

nodes, edges = generate_graph("cyclic", n=8, num_cycles=2, edge_prob=0.01, seed=42)
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
| `crossing.reduce_crossings` | `initialization.py` の円形重心初期順序、`sifting.py` のglobal guard付きsifting、`lib/embedding.py` の回転を順に適用する |
| `crossing.count_crossings` | `lib/crossings.py` で現在のradial交差数を評価する |
| `coordinates.assign_coordinates` | `brandes_koepf.py` の4方向BK系整列・圧縮・中央値統合と、`periodic.py` の周期的な射影・平滑化を行う |
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
  `min_gap` と `smooth_iterations` の既定値は現在の1.0と4です。
- 公開関数は入力を作業用に変更しません。`frozen=True` は辞書の中身まで不変にするものではありません。
- `create_figure` の呼び出し側はFigureをcloseします。
  `draw_layout` は従来同様に出力後のcloseまで行います。座標を省略した場合の描画内の補完も維持します。

## 計測と既知の問題

探索は探索処理全体の経過時間、`diff` / `diff_square` / `qp` はGurobiの `Runtime`、
重心法は初期求解時間と反復時間の和です。交差削減の計測はダミー挿入を含み、座標割当とともに
`perf_counter` を使います。各時間の定義は旧経路を維持しています。

TIME_LIMIT / SUBOPTIMAL時の扱いは元と同じです。探索結果の最適性を新たに保証する変更は行っていません。
`qp` の丸め後に制約違反が生じる既知の例も、旧実装との一致を確認して維持しています。

ダミー挿入の所属検索だけは、毎辺でのレイヤー走査を対応表に置き換えました。
300辺・30層の比較でリストへの所属確認が18,000回から0回になり、全出力が一致します。
前処理で所属一覧を一度走査し、各端点を辞書で検索します。複数層への重複所属では、
元と同じくソートされた層順で最後の所属を採用します。

## 検証

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

`tests/fixtures/protected_files.json` は実装開始時点の既存ソースと設定74ファイルのハッシュです。
`check_legacy_files` で変更がないことを確認できます。
このハッシュは旧コードを意図的に更新する将来の移行時に、比較基準とともに更新する対象です。

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
