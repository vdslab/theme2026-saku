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

### 型検査の環境制限

Pyrightの取得は通常・権限付きの双方でDNSエラーになっています。
strict設定と型付き公開APIを用意していますが、CLIの型検査は未実施です。
PylanceをVS Code外から起動する方法は利用条件に適合しないため使用しません。
通常import・コンパイル・比較テストは別途実施しています。

`layering.balance_layers` は4手法を選択し、`assign_layers` は探索とバランスを順に実行します。
- diff: 周期スパンの和を最小化するILP。
- diff_square: 周期スパンの二乗和を最小化するIQP。
- qp: 階層変数を連続緩和し、元と同じPythonのroundで整数化します。丸め後の既知の制約違反も維持します。
- barycenter: diffの初期解を重心法で更新します。反復・補正は元実装のままです。

TIME_LIMIT/SUBOPTIMAL時の扱いを維持しており、探索結果の最適性を新たに保証する変更は行っていません。
