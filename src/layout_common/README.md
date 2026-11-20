# 描画手法間の共通処理

`layout_common` は `sugiyama_layout` と `radial_layout` が利用する共通処理です。
各手法や Gurobi、Matplotlib をimport しません。
既存の公開 import パスは再エクスポートで維持します。
現行の `torus_layout` はこのパッケージを直接利用せず、循環階層に対応した専用処理を持ちます。

| 処理 | 共通化の範囲 | 分離する仕様 |
| --- | --- | --- |
| `cycle_removal` | 放射型と全頂点・全辺を採点する平面比較の辺反転 | torus は閉路を残す |
| `dag.topological_adjacency` | 杉山・radial の安定したトポロジカル走査 | 杉山は始点からの距離、radial は終点を最外層に揃える |
| `hierarchy` | 杉山・radial のダミー型・長辺分割・proper hierarchy の検証 | torus の循環層、整数ダミーID、境界フラグ・重みは専用実装 |

グラフ生成は既存の `generator` に集約します。
`generator.random_oriented_watts_strogatz` は杉山・radial 用のランダム方向付け、
`generator.watts_strogatz` は torus で使う時計回り方向付けです。
シード、既定値、辺順序、連結性の扱いが異なるので、それぞれの契約を保ちます。

3方式とも生成器のコードは `generator` を利用しますが、同じseedだけでは入力グラフは揃いません。
手法間の比較では、一度生成した頂点・辺を共通入力として渡します。

交差数計算（辺対の計算を含む）・交差削減・座標割当・描画・パイプラインの結果型は各手法に残します。
平面の非周期座標、radial の極座標、torus の周期座標と境界処理を
単一の型や条件分岐の多い処理に統合しません。旧 `src/old_torus_layout/main.py` の実装は維持します。

杉山・radial の `DummyNode` と `ProperHierarchy`、`CycleRemovalResult` は
共通の型になりました。既存モジュールからの import は引き続き利用できます。

`old_torus_layout` は過去の実験再現用に独立した旧実装を保持しているため、
生成器やダミー挿入なども現行共通処理へ置き換えていません。
現行トーラス内部では、階層割当の各方式がモデル構築・結果取得・Gurobi環境生成を共有し、
座標QP/LPも同じ環境生成処理を利用します。これは方式内部の共通化であり、3方式全体の共通化とは別です。
