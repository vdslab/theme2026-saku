# 放射型階層描画の検証計画

Bachmaier (2007) §III–V と `radial_layout` を照合する。対象は放射型の通常の CLI と比較実験の `radial` 条件。基準はコミット `259964f8` の実装。

- 原著の二層 sifting、回転、巻きの除去、Brandes–Köpf 法、螺旋の式を順に照合する。多層の掃引と描画近似は実装側の選択として記録する。
- 手計算可能な二層グラフ、閉路・長辺・中心頂点を含む多層グラフ、Watts–Strogatz の固定種、既存の公開グラフ入力を確認する。前後で入力のノード・辺集合を固定する。
- 総交差（埋め込みと完成図の中心線）、交差辺ペア、内部区間交差、接触と重なり、辺長、最大角度幅、描画時間を確認する。中心から出る区間と共有端点の扱いを明記する。分布と外れ値を残す。
- 同じ入力で完成 PNG を生成し、外周の巻き、長辺の接続、ノードとラベルの位置、反転辺を含む矢印を目視する。比較値が異なる場合は、座標・曲線・測定器のどこで差が出たかを特定する。
- 既知の再現ケースと境界条件を回帰テストに加え、全件テストを実行する。

## 再実行

リポジトリルートから実行する。入力は手作り3件、Watts–Strogatz 18件（再配線確率0.3）、既存の比較用生成入力48件と公開入力11件の計80件。既存入力は `output/torus_goal_20261126/{framework,public}/inputs.jsonl` に出典とグラフを保存している。比較環境に Gurobi の求解は含まれない。

```sh
export MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/torus-layout-mpl
PYTHONPATH=src ./theme2026-saku/bin/python experiments/audit_radial_drawing.py \
  --verify --output output/radial_drawing_rerun/after

radial_reference=$(mktemp -d)
git archive 259964f8 src/radial_layout experiments/torus_study | tar -x -C "$radial_reference"
PYTHONPATH="$radial_reference/src:src:$radial_reference/experiments" \
  ./theme2026-saku/bin/python -c 'import runpy; runpy.run_path("experiments/audit_radial_drawing.py", run_name="__main__")' \
  --output output/radial_drawing_rerun/before
```

`--verify` は、螺旋の角度差が両端の半径の間で整数周を通過する回数を解析的に数え、埋め込みとポリラインの中心線交差数を照合する。相互辺は交差した中心線の本数に応じて元の有向辺のペアへ展開し、相互辺同士の重なりを1ペアとして数える。共通端点は交差から除外する。ダミー位置で接線の向きが1度を超えて変わったときに折れとし、各元辺の折れが2箇所以内か確認する。辺長は描画座標単位の折れ線長、最大巻きは1区間の絶対角度差を周で表した値。

## 実行結果

80件が完走し、埋め込み・式 (4) の解析値・描画中心線の交差数が全件で一致した。元の有向辺単位でも交差数と交差辺ペアが解析値と一致した。長辺の内部区間はすべて放射方向に整列し、1辺あたりの折れは最大2。接触は0で、共有経路の重なりは相互辺のペア数と一致した。旧版は4件で描画交差と解析値がずれ、33件で共有経路上の接触を報告していた。

旧版からの埋め込み交差数の変化は減少26件、同数29件、増加25件。代表例 `ws-20-8-7` は1652から276に減少し、同じ図のエッジ総延長は6377から1833に減少した。`ws-20-8-0` は交差が285から298に増えた。`ws-20-4-1` では内部区間の整列を保った埋め込みに1.08周の区間が残り、総延長は687から1091に増加した。これらは固定4往復のヒューリスティックの品質差として記録した。

前後の11組のPNGを開き、長辺のつながり、両向きの矢印、外周の巻き、頂点とラベルを確認した。30頂点の内周では、旧版で重なっていた頂点とラベルが修正後の図で分離した。矢印が螺旋を横切る短い弦も解消した。描画の幾何計測は頂点記号と矢印を除いた中心線を対象とする。

生データと画像は [output/radial_drawing_audit_20261127](../output/radial_drawing_audit_20261127/) に保存した。実行環境は Python 3.13、NetworkX 3.6.1、Matplotlib 3.10.8。
