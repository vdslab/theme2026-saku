# Sugiyama, Tagawa, Toda (1981) の平面階層描画

Zoteroの原著（アイテム `NTSHFT3W`）に基づき、実用例で使われた **BC＋PR** を実装しています。[原著 §I–V](https://doi.org/10.1109/TSMC.1981.4308636)

1. CLIでは閉路を強連結成分に縮約し、最長経路で層を割り当てます。長辺は各中間層にダミー頂点を挿入します。既に層が与えられている場合、交差削減と座標割当のAPIへ直接渡せます。
2. BC法のPhase 1は、層の片側にある隣接頂点の位置から重心を計算し、安定ソートを上下交互に適用します。Phase 2は同じ重心を持つグループを反転してPhase 1を再実行します。
3. PR法は方向別の次数とダミー頂点の優先度を使い、先行する層の隣接頂点の重心へ整数座標を近づけます。頂点の順序を保ちながら、優先度の低い頂点を必要な分だけ移動します。描画ではダミーを折れ点として元の長辺を復元します。

原著が初期値として指定する反復上限、PR法の最後のDOWNの開始層には、この実装でそれぞれ12と第2層を設定しました。BC法で参照層に隣接頂点がない頂点の位置は保持します。PR法の同優先度は層内順、整数の丸めで等距離なら偶数側を選びます。表示は既存APIに合わせて左から右へ進みます。PR法の詳細を参照する1979年の技術報告と著者の実行コードは入手できておらず、著者の実行結果との点ごとの一致は未検証です。

```sh
PYTHONPATH=src ./theme2026-saku/bin/python -m sugiyama_layout \
  --size 20 --seed 7 --neighbors 4 --prob 0.25
```

比較実験では `sugiyama_1981` が強連結成分を縮約する条件です。循環グラフ上で提案法と同じ全頂点・全辺を採点する `sugiyama` は、Eades–Lin–Smyth の辺反転を前処理に使うBC＋PR条件です。出力に前処理名と処理後の頂点・辺数を記録します。縮約条件と提案法の対応差はDAGだけで集計します。

公開実装ではGravistoの重心法とGrandalfの座標割当を照合しました。Gravistoは重心の同値を隣接位置による辞書順で解消し、GrandalfはBrandes–Köpf法で座標を割り当てます。[Gravistoの重心法](https://github.com/Gravisto/Gravisto/blob/ed688bbab011ae26ff25f9cf2d62d905070de1e3/Graffiti_Plugins/org/graffiti/plugins/algorithms/sugiyama/crossmin/BaryCenter.java) · [Grandalfの座標割当](https://github.com/bdcht/grandalf/blob/master/grandalf/layouts.py)
