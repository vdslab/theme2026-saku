# 独立したトーラスレイアウト

既存の実行経路を保存したまま、同じアルゴリズムを責務別に移植するパッケージ。
入力順、重複辺、空レイヤーの扱いは元実装に従います。
`Graph` の頂点は整数または文字列。`layers` は割当から導出し、空レイヤーを自動補完しません。

## 検証

リポジトリルートで実行します。Pythonは既存の仮想環境を使います。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ./theme2026-saku/bin/python -m pytest src/torus_layout/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ./theme2026-saku/bin/python -m torus_layout.checks.check_imports
./theme2026-saku/bin/python src/torus_layout/checks/check_legacy_files.py
```

比較テストは、新旧両方の環境生成をテスト中だけローカルGurobi環境へ差し替えます。
通常の実装は元と同じ `.env` のライセンス設定を使用します。
既存mainは実装前から `token.gurobi.com` の名前解決で停止するため、この接続を伴う検証は未完了です。

## 階層割当

`layering.find_minimum_configuration` は元と同じ判定で二分探索します。
`layering.balance_diff` は固定したレイヤー数・トーラス辺数でスパン和を最小化します。
失敗時や時間制限時の扱い、解の丸め、辺の重複除去順は元実装を維持します。
探索の時間は処理全体、diffの時間はGurobiのRuntimeです。

### 型検査

Pyright CLIの取得はDNSエラーで実行できませんでしたが、インストール済みの
VS Code / Pylance 2026.4.1で、新パッケージを別ワークスペースとして開いて検査しました。
プロジェクトのPython環境、strict設定、ワークスペース全体の診断を有効にし、
Pylanceの診断が0件であることを確認しています。元のVS Code設定は変更していません。

`typings/` はMatplotlibの使用APIだけを記述した型接続です。
ライブラリ同梱型の `**kwargs: Unknown` が伝播する箇所を限定的な宣言で補っています。
実装・実行時importや警告レベルは変更していません。

## ダミー挿入

`subdivision.insert_dummy_nodes` は階層割当から長距離辺を分割します。
`layers` を明示した場合は空レイヤーとキー順をそのまま保持します。
整数の最大IDの次からダミー頂点を作り、重み・境界フラグを引き継ぎます。
頂点の所属がない辺をそのまま残す既存の扱いも維持します。

ダミー挿入の所属検索は対応表で置き換えました。300辺・30層の比較では、
リストへの所属確認が18,000回から0回になり、全出力が一致します。
前処理は頂点の所属一覧を一度走査し、各端点を辞書で検索します。
複数層への重複所属では、旧実装同様、ソートされた層順で最後の所属を採用します。

## 交差削減

`crossing.reduce_crossings` はダミー挿入済みグラフから、円形重心の初期順序、
sifting、global guard、回転後処理を元と同じ順に実行します。
`count_crossings` は元と同じradial交差数を返します。入力の階層・辺は変更しません。
通常辺とsifting中の一時ID付き辺を別の型で扱います。

## 座標割当

`from torus_layout.coordinates import assign_coordinates` が公開入口です。
4方向のBK系整列とブロック圧縮、中央値の統合、周期的な射影・平滑化を元と同じ順に行います。
入力の順序と巻き数を変更せず、`CoordinateResult.positions` と `period` を返します。
`min_gap` と `smooth_iterations` の既定値は元の1.0と4です。

## 描画

`drawing.create_figure` はFigureを返し、保存・表示・closeは呼び出し側が行います。
`drawing.draw_layout` は元と同じ保存・表示・タイル処理を実行してFigureを閉じます。
`DrawingOptions` は既存の表示設定をまとめたものです。座標を省略した際の補完も維持します。
通常・タイル・ダミー表示・座標省略の8組で、旧画像とRGBAピクセルが完全一致しています。
