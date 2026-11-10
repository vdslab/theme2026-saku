# 比較実験用の旧トーラス実装

過去に試した方式を比較・再利用するために、旧実装一式をこのパッケージに保存しています。
現行実装は隣の `src/torus_layout/` です。移動に合わせてimportと実行入口を更新し、
旧手法の目的関数・制約・アルゴリズムは維持しています。

| 配置 | 内容 |
| --- | --- |
| `main.py` | 旧パイプラインとCLI |
| `layer_assignment/` | 一括モデル、ILP、IQP、ヒューリスティック、二段階法、二分探索、バランス調整 |
| `layer_length/` | 直径・閉路・FAS・SCCなどによる階層数推定 |
| `crossing_reduction/` | 交差最小化ILP、重心法、radial sifting |
| `coordinate_assignment/` | 旧BK系座標割当 |
| `drawing/` | 旧トーラス描画・周辺タイル処理 |
| `lib/` | 旧生成器、ダミー挿入、SCC分解、Gurobi環境生成 |

## 実行

リポジトリルートから実行します。旧 `src/main.py` は `src/old_torus_layout/main.py` に移動しました。

```sh
./theme2026-saku/bin/python src/old_torus_layout/main.py --help
PYTHONPATH=src ./theme2026-saku/bin/python -m old_torus_layout --help

# 入力を固定して旧パイプラインを実行する例。
PYTHONPATH=src ./theme2026-saku/bin/python -m old_torus_layout \
  --node 25 --seed 42 --no_show --save_path /private/tmp/old_torus_layout.png
```

Gurobiの設定には従来どおりルート `.env` を利用します。

## 実験からの利用

旧来の `layer_assignment` などのトップレベルimportは、`old_torus_layout` 配下に変更しました。
`experiments/` の既存スクリプトと新旧比較テストも同じ参照先を使用します。

```python
from old_torus_layout.layer_assignment.torus_ilp import torus_ilp
from old_torus_layout.layer_assignment.torus_balance import balance_layer_assignment
from old_torus_layout.crossing_reduction.radial import radial_sifting_global_guard_heuristic
from old_torus_layout.lib.generate_torus_graph import generate_cyclic_graph
```

実験スクリプトは、これまでと同様に `PYTHONPATH=src` を付けて実行できます。

```sh
PYTHONPATH=src ./theme2026-saku/bin/python experiments/evaluate_crossing_reduction.py
```

各方式の狙いと現在の位置づけは [試行錯誤の整理](../../documents/research_history.md) を参照してください。
旧実装単体のテストは `src/old_torus_layout/tests/`、現行実装との比較テストは
`src/torus_layout/tests/` にあります。全体の配置と実行方法は [テスト案内](../../documents/testing.md) を参照してください。
