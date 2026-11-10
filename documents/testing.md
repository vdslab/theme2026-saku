# テストの配置と実行

テストは検証対象のパッケージの `tests/` に配置する。実験スクリプトの検証は
`experiments/tests/` に置く。旧 `src/test/` に混在していた8ファイルは、以下の配置へ移動した。

| 配置 | 対象 |
| --- | --- |
| `src/old_torus_layout/tests/` | 旧トーラスの交差計算・sifting・座標割当・描画の回帰ケース |
| `src/torus_layout/tests/` | 現行トーラス各工程・CLI・切れ目DP・座標最適化、および旧実装との比較 |
| `src/generator/tests/` | 生成器の性質・再現性・旧生成器との互換性 |
| `src/layout_common/tests/` | 共通処理の契約、杉山・放射型描画の統合テストとimportの独立性 |
| `src/radial_layout/tests/` | 放射型描画固有の階層・ダミー挿入・描画 |
| `experiments/tests/` | トーラス交差削減の掃引スケジュール、比較条件、WS100の入力設計 |

複数手法の公開APIや共通処理とのつながりを比較するテストは `layout_common/tests/` に置く。
新旧比較は検証する現行パッケージに残し、旧実装への依存を通常実装へ持ち込まない。
現行座標割当へ旧回帰ケースを適用するテストも維持している。

## 全件実行

リポジトリルートから実行する。

```sh
PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/torus-layout-mpl PYTHONPATH=src ./theme2026-saku/bin/python -m pytest src experiments/tests -q -p no:cacheprovider
```

`pytest src` だけでは `experiments/tests/` が含まれないため、全件実行時は両方を指定する。
特定対象だけを実行する場合は、その `tests/` を指定する。

```sh
PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/torus-layout-mpl ./theme2026-saku/bin/python -m pytest src/old_torus_layout/tests -q
PYTHONPATH=src ./theme2026-saku/bin/python -m pytest experiments/tests -q
```

Gurobiを利用する新旧比較テストでは、小規模問題をローカル環境で求解する既存fixtureを利用する。
アプリケーションの `.env` やライセンス設定は変更しない。

## 保護対象の確認

`src/torus_layout/tests/fixtures/protected_files.json` で記録済みソースのハッシュを確認する。
今回のテスト移動では保護対象の件数を維持し、移動先のパスに置き換えている。

```sh
./theme2026-saku/bin/python src/torus_layout/checks/check_legacy_files.py
```
