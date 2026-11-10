# 描画手法間の共通処理

`layout_common` は `sugiyama_layout`、`radial_layout`、`torus_layout` の
下位に置く、描画方式に依存しない処理です。各手法や Gurobi、Matplotlib を
import しません。既存の公開 import パスは再エクスポートで維持します。

| 処理 | 共通化の範囲 | 分離する仕様 |
| --- | --- | --- |
| `cycle_removal` | 杉山・radial の閉路除去 | torus は閉路を残す |
| `dag.topological_adjacency` | 杉山・radial の安定したトポロジカル走査 | 杉山は始点からの距離、radial は終点を最外層に揃える |
| `hierarchy` | 杉山・radial のダミー型と長辺分割 | torus の循環層、整数ダミーID、境界フラグ・重みは専用実装 |

グラフ生成は既存の `generator` に集約します。
`generator.random_oriented_watts_strogatz` は杉山・radial 用のランダム方向付け、
`generator.watts_strogatz` は torus で使う時計回り方向付けです。
シード、既定値、辺順序、連結性の扱いが異なるので、それぞれの契約を保ちます。

交差数計算（辺対の計算を含む）・交差削減・座標割当・描画・パイプラインの結果型は各手法に残します。
平面の非周期座標、radial の極座標、torus の周期座標と境界処理を
単一の型や条件分岐の多い処理に統合しません。旧 `src/old_torus_layout/main.py` の実装は維持します。

杉山・radial の `DummyNode` と `ProperHierarchy`、`CycleRemovalResult` は
共通の型になりました。既存モジュールからの import は引き続き利用できます。
