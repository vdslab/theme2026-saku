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
