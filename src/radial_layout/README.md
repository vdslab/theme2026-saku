# Bachmaier (2007) の放射型階層描画

Zoteroの原著（アイテム `9H6KNKZL`）の **radial sifting** を使う構成です。[原著 §3–5](https://doi.org/10.1109/TVCG.2007.1000)

1. 原著§3の最長経路レイヤリングでシンクを最外層に置き、長辺をダミーで分割します。循環入力の前処理には、原著が利用を認める標準法のうち既存のEades–Lin–Smyth法を使います。
2. Algorithm 1の隣接交換とparting更新で頂点位置と整数オフセットを探索します。原著§5.1.1に従い、長辺の内部ダミー区間同士の交差に重みを付けます。Algorithm 2の回転に合わせて前後の境界のオフセットを更新します。
3. Algorithm 3で層間の共通巻きを除き、レイを回転して内部ダミー区間のオフセットをゼロにします。切断区間を除いたグラフをBrandes–Köpf法で配置し、層半径に反比例した間隔で求めた座標を極座標に変換します。最内層が1頂点なら中心に置き、その頂点からの辺は直線になります。それ以外の辺は原著の式 (4) の螺旋に沿って、式 (5) の半径・角度幅に比例する点数で描画します。

二層の擬似コードを多層グラフへ適用するため、入力順・初期オフセット0から上下スイープを4往復まで実行します。上下各パスの後に、内部区間交差数、総交差数の順で最良の埋め込みを保持します。これらの実験設定とサンプリングの品質係数は実装側の選択です。Algorithm 2の角度差はIEEE掲載版の擬似コードの符号に従います。

`reduce_crossings` が返す `RadialEmbedding` を `assign_coordinates` に渡し、描画には座標割当後の `winding` を使用してください。層順だけを渡すAPIは等角度配置になります。`assign_winding_numbers` は最短角経路の計算用で、radial siftingでは使いません。

```sh
PYTHONPATH=src ./theme2026-saku/bin/python -m radial_layout \
  --size 20 --seed 7 --save radial-example.png --no-show
```

論文はJava実装を報告し、Gravisto上への実装について謝辞で言及しています。公開版では、社会ネットワーク分析プラグインで使われるradial siftingと、層番号を受け取って螺旋配線まで実行するコードを確認しました。公開版と論文の実験版の同一性は未確認です。 [Gravistoの交差削減](https://github.com/Gravisto/Gravisto/blob/ed688bbab011ae26ff25f9cf2d62d905070de1e3/Graffiti_Plugins/org/graffiti/plugins/algorithms/core/CrossingReduction.java) · [Gravistoの描画パイプライン](https://github.com/Gravisto/Gravisto/blob/ed688bbab011ae26ff25f9cf2d62d905070de1e3/Graffiti_Plugins/org/graffiti/plugins/algorithms/core/Sugiyama.java#L56-L95)
