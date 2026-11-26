# トーラス階層描画の実験監査

2026-11-26（日本時間）。実験の生データとログは [今回の出力](../output/torus_goal_20261126/) に保存する。11月20日の [統合報告](../output/torus_complete_20261120/index.html) と [追試の設計](experiment_validation.md) は当時の実装・条件の証拠として参照する。

今回の判定対象は、ローカルライセンスで動く既定の数理計画モデルを含む計算機実験と、現行工程の妥当性・有用性・限界である。WLS接続失敗やローカルライセンスのサイズ上限で進めない既定モデルの実験は、復旧後の手順を残す。読解・主観評価は今後の研究課題とする。既に取得した固定階層・代替求解・代替採点の結果は、既定モデルと既定パイプラインの結果と区別して参照する。

## 比較対象と主張

循環階層割当 → ダミーによる単位スパン化 → 層順と巻き数の決定 → 切れ目と共通整数巻きの最適化 → 座標割当 → 描画の順に実行する。層割当なしに隣接層間やダミー列は定まらない。分割なしBKはダミー列の共通座標と各層の順序制約を同時に課すため、切れ目候補の評価と座標の実行可能性を別々に測る。Algo2と整数巻き除去は層順確定後の順序比較が可能。詳細は [現行の仕様](../src/torus_layout/README.md) を参照。

循環階層で有向サイクルを同一方向に表示する発想には先行例がある。層横断のブロック sifting にも循環・放射レイアウトへの拡張がある。新規性の候補は、二方向の周期を持つ実装における境界と共通巻きの同時最適化および座標制約との結合である。 [Drawing Recurrent Hierarchies](https://doi.org/10.7155/jgaa.00254) · [Global k-Level Crossing Reduction](https://jgaa-v5.cs.brown.edu/index.php/jgaa/article/view/paper242)

比較ではレイヤ内の順序から得る埋め込み交差と、完成図の中心線から得る幾何交差を併記する。平面の外部対照は Graphviz dot、内部対照は杉山型と放射型を用いる。論文での他の比較軸とデータ選択の根拠は [関連研究レビュー](sugiyama_experiment_literature_review.md) を参照。 [A Technique for Drawing Directed Graphs](https://graphviz.org/documentation/TSE93.pdf)

| 仮説 | 判定と残る検証 |
| --- | --- |
| 階層探索と配分が意図した解を返す | 小規模での全探索と目的値・可否を照合する。打ち切り時は incumbent と bound を記録し、層数、ダミー数、時間、下流の交差を分けて評価する。 |
| global sifting が実図の交差を減らす | 階層・後処理・座標方式を共有し、同一入力ごとの幾何交差差を評価する。負の差が多いか、タイプ2の差と一致するか、曲がりや時間との交換があるかを調べる。失敗率を併記し、公開グラフのスナップショットを独立なネットワークの反復として数えない。 |
| joint が同じ埋め込みで境界負担を減らす | 小規模で切れ目と共通巻きを列挙し、交差保存と最適値を照合する。境界を通る線分・元辺・イベントを分けて測る。分割なしBKで実行不可能になる割合と legacy への切替を記録する。 |
| トーラスの効果が入力の循環構造に依存する | 同じ無向骨格で向きを操作し、さらにSCCを固定した比較を行う。元の向きのある公開ネットワークで追試する。全体比較においても交差、曲がり、同方向性、実行時間、境界負担を併記する。 |

### 論文の主張と対応する結果

| 実験から述べられること | 根拠と適用範囲 |
| --- | --- |
| 階層配分と境界最適化の目的値は、小規模の列挙で照合できた | 階層探索、切れ目選択、共同補正をそれぞれの探索空間で照合した。二層のjointでは共通補正の制約が最適値に影響する。 [厳密照合](../output/torus_goal_20261126/oracles/results.csv) · [二層の反例](../output/torus_goal_20261126/audit_retake/two_layer_joint_scope.json) |
| global siftingは、同じ階層と座標方式でradial siftingより交差を減らす場合が多い | 幾何交差は30件中22件で減少、4件で同数、4件で増加。公開11条件では交差が減り、sifting時間が増えた。 [対応表](../output/torus_goal_20261126/matched_split/paired.csv) |
| siftingで層内方向の巻き数を選べると、多くの合成入力で交差が減る | 同じ階層・global sifting・分割ありBKで巻き数だけを変えた。幾何交差は48件中44件で減り、2件で同数、2件で増えた。境界通過辺は全件で増えた。 [全試行](../output/torus_winding_ablation_checked_20261126/rows.jsonl) |
| 固定階層でもsiftingの結果は初期層順に依存する | 6・9頂点の全列挙で24件中1件に2交差の差が残った。12頂点の長辺追試では、初期層順を3つ追加すると24件中15件で幾何交差が減り、折れと境界通過の非増加も求めると9件で減った。sifting時間の対応比は中央値4.38倍。 [反例の描画](../output/torus_sifting_winding_oracle_20261126/counterexample.svg) · [長辺追試と時間計測](../output/torus_sifting_winding_oracle_20261126/restarts_long_edge_holdout_timing.jsonl) |
| 層幅の分布は、元の接続を保ってもsiftingの採点候補数を変える | ダミーなしでは各層の幅の二乗和が1回の採点候補数の上限。層数と平均幅を固定した5グラフで、交互幅と均一幅の全10条件が各上限に達した。交互幅のsiftingは逆順の測定でも5組すべてで遅かった。 [候補数と上限](../output/torus_fixed_rank_width_variation_20261126/sifting_work_with_bound.jsonl) · [逆順の対応表](../output/torus_fixed_rank_width_reverse_20261126/width_pairs.csv) |
| jointは境界通過を減らし、後からの回転でその効果が弱まる場合がある | 合成12件中10件で従来処理より境界通過線分が減り、2件は同数。順序比較16件中14件でjoint後の回転が境界通過線分を増やした。 [横断比較](../output/torus_goal_20261126/joint_seam_synthetic.csv) · [順序比較](../output/torus_goal_20261126/crossing_order/paired.csv) |
| dotとの交差差はグラフの向きに依存する | 入次数・出次数とSCCを固定した混合弦の15骨格で、弦を反転すると12件でトーラスの相対交差差が悪化した。対象はこの生成条件に限る。 [方向の対応集計](../output/torus_goal_20261126/figures/degree_control_random/orientation_summary.csv) |
| 全体比較では交差と折れの結果が分かれる | dotより幾何交差が少ない、同数、多い条件は合成48件で15、6、27件。公開追試の完走21件では全件でdotの交差が少なかった。折れは合成48件と公開追試の完走21件すべてでトーラスが少なかった。公開追試は24件中3件が打ち切りで、同じ元ネットワークからの抽出には重なりがある。 [合成の対応表](../output/torus_goal_20261126/framework/paired.csv) · [公開の元ネットワーク別集計](../output/torus_holdout_20261126/run/by_network.csv) |
| 大規模描画ではsiftingの予算と品質の関係を計測できた | 500頂点の選定入力は代替階層を使って5回上限のsiftingまで完走。独立の90・120頂点入力では12件すべてで20秒条件が0秒条件より幾何交差を減らし、境界を通る元辺数を増やした。 [時間予算別の結果](../output/torus_budget_sweep_20261126/budget_summary.csv) · [独立入力の対応表](../output/torus_budget_holdout_20261126/pairs_with_dot.csv) |

大規模の既定パイプラインはローカルライセンスのサイズ上限を記録しており、後段の完走結果は固定または代替階層に対する評価である。

## 現行実装で確認した結果

- [描画領域の監査](../output/torus_goal_20261126/audit/drawing_domain.csv) は、16入力 × 3周期倍率 × 3座標条件の全144条件で描画準備に成功した。旧監査の領域外エラー39件を再現しなかった。対象は保存済みの小規模入力と2種の座標方式に限る。
- [二層の反例](../output/torus_goal_20261126/audit/two_layer_crossing.json) では層をまたぐ2本が異なる帯を通る。帯をまとめた局所計数は1、現行の埋め込み計数と幾何計数はともに0。帯を識別する根拠にはなるが、sifting の全候補の評価を検証するには独立列挙が必要。
- [後処理を揃えた分割なしBKの比較](../output/torus_goal_20261126/matched/measurements.csv) では、一部入力で層順制約の循環により座標割当に失敗する。両方式に分割ありBKを適用する追試を別出力に保存し、失敗を含む元の条件と比較する。同一座標方式での比較はステージ実験であり、CLIの既定パイプラインにあるフォールバックを含まない。
- 初回の全体比較を起動した際、既存ランナーがメタデータ採取のために読み取り専用の Git コマンドを自動実行した。その呼び出しを両ランナーから削除し、メタデータにはソース内容のハッシュを使う。初回実行の設定には当時のメタデータが残る。

## 再実行と再開

既存出力とは別のディレクトリを指定する。ローカルライセンスで得た結果は求解上限付きの運用点として解釈する。並行実行中の実測時間には競合が含まれるため、確定版の時間比較は単独で反復する。

```sh
export PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/torus-goal-mpl XDG_CACHE_HOME=/tmp/torus-goal-cache
PYTHONPATH=src ./theme2026-saku/bin/python experiments/audit_torus_report.py output/torus_retake/audit
./theme2026-saku/bin/python experiments/compare_global_sifting.py output/torus_retake/matched_split \
  --matched-postprocessing --coordinate-method brandes_koepf_blocks
./theme2026-saku/bin/python experiments/run_torus_study.py framework --local-license --graphviz \
  --sizes 12 18 24 --seed-count 4 --solver-seconds 2 --comparison-seconds 15 \
  --case-seconds 65 --jobs 2 --output output/torus_retake/framework
```

次は、座標失敗を方式別に記録できる比較表と、失敗を含む共通予算での品質・時間・メモリ比較を作る。切れ目・巻き・座標の組み合わせは実行可能性と幾何交差を同時に追う。公開入力の依存を考慮した解析、独立入力による確認、参加者による読解評価が残る。

## 追試の結果

### 全体比較と構造への依存

12・18・24頂点、頂点あたり2辺、4系列、系列・サイズごとに4種の生成入力を比較した。既定トーラス、リポジトリの杉山型と放射型、dotはいずれも48入力を完走した。表は幾何交差で、同じ入力におけるトーラスから比較対象を引いた差を示す。 [対応集計](../output/torus_goal_20261126/framework/paired.csv) · [全試行](../output/torus_goal_20261126/framework/results.csv)

| 比較対象 | 減少 | 同数 | 増加 | 差の中央値 |
| --- | ---: | ---: | ---: | ---: |
| 杉山型 | 22 | 7 | 19 | 0 |
| 放射型 | 32 | 3 | 13 | −3 |
| dot | 15 | 6 | 27 | +2 |
| 境界最適化とUNWINDを省略 | 0 | 48 | 0 | 0 |

dotに対してWatts–Strogatzは9減・3同数、SCC連結の系列は12増だった。系列ごとに方向、次数や長辺数も変わり得るため、これだけで原因をSCC構造に帰属できない。境界処理の有無で交差は全件同じだった一方、曲がりは39減・3同数・6増だった。曲がりの数はルーティング方式にも依存するため、他方式との直接的な可読性の主張には使えない。円筒対照は4件、凝縮型の杉山対照は12件が実行失敗した。

### 小規模厳密照合と二層の制約

[厳密照合](../output/torus_goal_20261126/oracles/results.csv) では6頂点の3入力で二分探索の層数・循環辺数が候補層数の列挙と一致した。各層2頂点の3層グラフ2入力で、巻き数固定の sifting と切れ目DPはそれぞれの列挙最適値と一致した。この実験のDPは切れ目のみを扱う。joint DPについては全探索を含む回帰テストがあり、全体テスト1435件が通過した。

[二層の境界最適化の反例](../output/torus_goal_20261126/audit_retake/two_layer_joint_scope.json) では、互いに逆向きの2辺が別の帯を走り、初期巻き数は両方とも1。現行jointは二層間で共通の補正を使い、境界通過線分を2本から1本にする。帯ごとに独立補正を許せば0本で、いずれも交差は0。ただし独立補正は閉路の総巻き数を2から0へ変える。最適性を述べる際は許す補正の範囲を明記する。

### 実行コストと環境制約

[規模実験](../output/torus_goal_20261126/scaling/results.csv) では24・48頂点の各8件が完走。実行時間中央値は約0.58秒と4.66秒、プロセスのピークRSS中央値は96と100 MiBだった。72頂点は8件ともローカル求解環境のGurobiエラーで完走しなかった。[線形配分の追試](../output/torus_goal_20261126/linear_scaling/rows.jsonl) では90・120頂点で二乗和配分がライセンスのサイズ上限に達した条件も記録した。線形配分・1回掃引は計算予算を下げる別条件で、既定設定の規模上限を推定する根拠には含めない。[WLS確認](../output/torus_goal_20261126/wls_probe/rows.jsonl) はホスト名解決で失敗した。

全体・規模比較を監査中、legacyへのフォールバックで旧計測器が最後の交差削減呼び出しの時間だけを保存する問題を確認した。計測器はパイプラインが積算した時間と、利用した切れ目方式を記録するよう更新した。上記の全体レイアウト時間は旧計測器でも最初から最後まで計測している。旧実行の工程別時間でフォールバックを含む比較は再実行が必要。

### 同じ骨格で向きを変えた追試

20のWatts–Strogatz骨格（12・16頂点、再配線率0.10・0.35、各5 seed）で、各方向条件のトーラスとdotはすべて完走した。トーラス−dotの交差差の中央値は円環沿い−3、4分の1反転−1、ランダム向き+5、DAG向き0。円環沿いからランダム向きに変更すると、同一骨格20件中19件でトーラスの相対交差差が悪化した（対応差の中央値+8）。 [対応表](../output/torus_goal_20261126/figures/topology/orientation_pairs.csv) · [分布図](../output/torus_goal_20261126/figures/topology/orientation_pairs.pdf)

別の10骨格で全頂点を含む有向閉路を固定した。追加辺を円環沿いからランダム向きに変えると、10件すべてで相対交差差が悪化した（中央値+5.5）。この集合ではSCCが常に1つなので、SCC数と最大SCC比だけでは交差差を説明できない。方向の操作は頂点ごとの入次数・出次数も変えるため、その寄与と方向の整合性の寄与は分離していない。 [対応表](../output/torus_goal_20261126/figures/scc_control/orientation_pairs.csv) · [分布図](../output/torus_goal_20261126/figures/scc_control/orientation_pairs.pdf)

### 工程ごとの寄与と相互作用

- 16入力で線形配分と比較すると、二乗和配分は6件でスパン二乗和を減らし、10件は同値だった。総スパンは2件で増えた。ダミー挿入比較の16入力では単位スパン違反を記録しなかった。 [階層の対応表](../output/torus_goal_20261126/layering/paired.csv) · [ダミー挿入の生データ](../output/torus_goal_20261126/subdivision/results.csv)
- 16入力の局所 sifting 対照では、全体最良の保持を外すと7件で初期埋め込みより交差が増えた。回転は16件で交差を保存したが、境界通過線分を9件で増やした。従来順序の比較では、後段でも巻き除去と切れ目の再選択を試す構成が4件で境界通過線分を減らし、12件で同数だった。これは最大でもとの構成と追加候補の両方を比較する実験で、純粋な順序交換の効果は示さない。 [交差処理の対応表](../output/torus_goal_20261126/crossing/paired.csv)
- 現行のUNWINDと切れ目最適化の両方を有効にすると、完走ペア15件すべてで境界通過線分が減った（中央値−9）。埋め込み・幾何交差は全件同数。曲がりは10件で減り、3件で増え、2件で同数。両方を有効にした条件には1件の失敗があり、切れ目のみの条件には3件の失敗があった。この比較は座標APIを直接呼び、CLIのフォールバックを経ない。 [失敗を含む全試行](../output/torus_goal_20261126/crossing/results.csv)
- 固定埋め込みで通常BKと比べ、分割ありBKは16件中9件、分割なしBKは完走15件中12件で曲がりが減った。増加は両方式とも0件。幾何交差は完走ペアすべてで一致した。分割なしは1件で層順制約の循環を報告した。射影なし対照では16件中13件で最小間隔に違反した。3×3 BKでは交差差がなく、15件で中心線総延長が増加した。 [座標の全試行](../output/torus_goal_20261126/coordinates_blocks/results.csv)
- 合成グラフで層幅2・4・8・16、各3 seedを用いると、jointは従来境界処理より12件中10件で境界通過線分を減らし、2件で同数だった。幅2の3件は切れ目・補正の列挙に一致した。この入力集合の比較では交差を保存した。 [jointの生データ](../output/torus_goal_20261126/joint_seam_synthetic.csv)

### 入次数・出次数も揃えた追加実験

12・16・20頂点、弦のステップ2・3・4の9骨格で、前向きのハミルトン閉路を維持し、弦だけを全部反転した。各頂点の入次数と出次数はともに2で一定。両条件の無向辺集合とSCCの一致を確認した。反転によりトーラス−dotの交差差が6件で悪化、1件で同値、2件で改善した。差の変化の中央値は+3、骨格単位で復元抽出した探索的な95% bootstrap区間は[−1, 8]。20骨格・10骨格で同様に求めたランダム方向の区間はそれぞれ[4, 11.5]、[3, 9]だった。 [追加実験の図](../output/torus_goal_20261126/figures/degree_control/orientation_pairs.pdf) · [次数固定の集計](../output/torus_goal_20261126/figures/degree_control/orientation_summary.csv)

一定間隔の弦だけで作った9骨格では区間が0を含んだため、弦の終点を入れ替えて距離を2〜4に混ぜた別の15骨格で追試した。入次数・出次数・無向骨格・SCCの固定条件は同じ。反転後の相対差は12件で悪化、1件で同値、2件で改善（中央値+9、探索的区間[4, 14]）。この生成条件では、次数やSCCを変えずに相対性能が変化した。区間は選んだサイズと生成器の範囲に限って解釈する。 [混合弦の分布図](../output/torus_goal_20261126/figures/degree_control_random/orientation_pairs.pdf) · [対応集計](../output/torus_goal_20261126/figures/degree_control_random/orientation_summary.csv)

### 回転とjointの実行順

同じglobal埋め込みと分割ありBKを使い、jointのみ、Algo2→joint、joint→Algo2を16入力で比較した。Algo2→jointとjointのみの境界通過線分数・幾何交差は全件で一致した。jointの後にAlgo2を実行すると、交差数は保存されたが、境界通過線分が14件で増え、8件でダミー同士の境界通過が再発した。分割なしBKとの組み合わせは、その制約を満たすか別途判定する必要がある。 [順序の対応表](../output/torus_goal_20261126/crossing_order/paired.csv)

### sifting と公開データ

同じ層、同じ後処理、同じ分割ありBKでglobalとradial siftingを比較した。幾何交差は30件中22件で減少、4件で同数、4件で増加（中央値−10、範囲−918〜+2）。タイプ2は10件で減少、20件で同数で、global側では0だった。幾何交差は公開11条件すべてで減った一方、siftingの計測時間は同じ11条件すべてで増えた。公開条件は3つの元ネットワークに由来し、独立な11ネットワークへの一般化には使えない。分割なしBKを両方式に要求した最初の比較では、30件中14件で少なくとも一方が座標割当に失敗した。 [分割ありBKの対応表](../output/torus_goal_20261126/matched_split/paired.csv) · [代表描画](../output/torus_goal_20261126/matched_split/example_1.png) · [分割なしBKの対応表](../output/torus_goal_20261126/matched/paired.csv)

現行トーラス全体の公開条件では、15秒上限で7件完走、4件タイムアウト。40秒での再試行では4件すべて完走した。線形配分・1回掃引はこの4件すべてで短時間だったが、幾何交差はいずれも増加した。既定トーラスは計11件の幾何交差がdotより多かった。4件の比較は予算を延長して得た補足結果である。局所siftingの改善が全体の外部対照に対する改善を意味するかは、両比較で別々に判断する。 [公開データの主試行](../output/torus_goal_20261126/public/results.csv) · [タイムアウトの再試行](../output/torus_goal_20261126/public_retry/results.csv)

### 論文で扱える範囲と残作業

- 同一の帯にある異なるダミー列について、共通ブロック順が両端で同じ相対順を与え、内部線分の巻き数が0なら、線分同士は帯内で交差しない。jointの帯内共通補正では相対巻き数が変わらない。切れ目による座標の持ち上げの変更と合わせ、交差保存の論証では計数器と同じ帯の定義を使う。幅・巻き数・重複辺の全許容域を定理の仮定として明示する必要がある。
- 現行実装の支持を得た主張は、後処理を揃えた条件でのglobal siftingによる改善、境界最適化による境界通過線分の減少、周回に沿う向きを持つ特定系列での相対的な交差の良さである。全体の交差に関してはSCC連結生成系列と公開サンプルでdotへの劣位が確認された。
- 公開データが3ネットワークに偏り、方向固定・次数固定の統制実験も小規模なので、独立なネットワークへの外的妥当性が残る。密度と層幅を独立に広げた条件で、求解予算・失敗率・品質を再評価する。既定の二乗和配分の大規模比較には制約なしに利用できる求解環境が必要。
- 周辺タイルが有向経路読解を改善するか、同じ数の交差を持つ配置のどちらが理解しやすいかは、匿名の参加者データが必要。既存の [提示用の刺激と実施手順](experiment_validation.md) は実行可能だが、ここで扱った計算実験から読解の効果は推定できない。
- 工程別の時間・ピークRSSは測定方法とライセンス限界を記録した。確定版の性能表は同じ予算と並行度で全比較対象のRSSを測定し、複数反復で分散を示す。局所ステージ実験のAPI呼び出しにはCLIのフォールバックを含まない条件がある。

### 新しい図表の再生成

```sh
./theme2026-saku/bin/python experiments/summarize_sifting_pairs.py \
  output/torus_goal_20261126/matched_split/measurements.csv output/sifting_retake.csv
MPLCONFIGDIR=/tmp/torus-goal-mpl ./theme2026-saku/bin/python experiments/summarize_orientation_pairs.py \
  output/torus_goal_20261126/degree_control/rows.jsonl output/orientation_retake
```

最後のコマンドで入力をtopology、scc_controlに換えると対応する図も再生成できる。検証ランナーの `settings.json` に各実験の入力、時間上限、並行度、ソースハッシュを保存している。各入力の頂点・有向辺は `inputs.jsonl`、失敗を含む各試行は `rows.jsonl` を参照。

### 座標失敗の帰属と単独実行時のコスト

分割なしBKの座標失敗を方式別に記録するよう比較コードを更新し、同じ30入力を再実行した。失敗はradialが12件、globalが7件で、5件は両方式で失敗した。公開11条件ではradialが11件、globalが5件失敗。失敗行の埋め込み交差・タイプ2・境界通過線分は保存される。これらは同一後処理を課したステージ実験の結果で、既定パイプラインのjointからlegacyへの切替率とは異なる。 [方式別の全試行](../output/torus_goal_20261126/matched_unsplit_audit/measurements.csv)

12・18・24頂点、4系列、各2 seedの24入力を、並行度1かつ方式ごとに独立プロセスで測定した。トーラス・杉山・放射・dotのレイアウト時間中央値は0.190・0.047・0.115・0.077秒。ワーカーのピークRSS中央値は93.5・86.8・87.6・87.7 MiB。ワーカー側はPythonランタイム、共通ライブラリと計測器を含む。dotの子プロセスの中央値は28.8 MiB。子と親の個別ピークは発生時刻が違うため合算していない。トーラスは24件のうち21件でjointを採用し、3件でlegacyに切り替えた。報告した工程別時間は両方の試行を積算している。 [単独実行の全試行](../output/torus_goal_20261126/framework_memory/results.csv) · [フォールバックの計測確認](../output/torus_goal_20261126/fallback_timing_check.json)

### 再開時の確認項目

1. 大規模な二乗和配分を比較できる求解環境で、規模・密度・タイムアウト予算の交互作用を再計測する。ローカル環境では線形配分の実験を再利用できる。
2. 実データの独立単位を元ネットワークとして追加収集し、方向が観測されたグラフにおける有効条件を確認する。読解の主張には、参加者実験の回収・採点・解析が必要。
3. 原稿では、二層の補正自由度、埋め込みと幾何の計数条件、フォールバックと失敗率を明示する。図の点は骨格ごとの対応差、菱形は中央値、右端は結果が得られた骨格数と総骨格数を示す。

### 独立した公開ネットワークでの確認

前回使ったSampson・UKfaculty・macaqueに加え、Krackhardtの組織ネットワーク、SocioPatternsの高校友情、SNAPの欧州研究機関メールを採用した。Krackhardtの助言・友情は同じ参加者に由来するため、まとめて一つの元ネットワークとして扱う。各関係種別につき最大弱連結成分から固定乱数で三つの中心を選び、弱連結BFSの先頭12・16頂点が誘導する有向部分グラフを比較した。探索時だけ辺を無向として扱い、レイアウト入力では観測方向を保持した。中心・サイズ間で頂点が重なるため、入力数を独立な標本数とみなさない。

メールの配布元SNAPはこのシェルから名前解決できなかった。使用した公開ミラーは元データ公表値の1,005頂点・25,571辺と一致し、自己ループ642本を除くと986頂点・24,929辺になった。各入力の元ファイルSHA-256、抽出頂点、密度を再計算できる有向辺リストは実行マニフェストに記録した。 [Krackhardtのデータ](https://inarwhal.github.io/NetworkAnalysisR-book/ch7-Dyads-Triads-R.html) · [SocioPatternsのデータ](https://github.com/SocioPatterns/sociopatterns.github.io/blob/main/_datasets/high-school-contact-and-friendship-networks.md) · [SNAPのデータ仕様](https://snap.stanford.edu/data/email-Eu-core.html) · [抽出マニフェスト](../output/torus_holdout_20261126/run/inputs.jsonl)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py public_holdout \
  --public output/torus_holdout_20261126/sources --solver-seconds 2 --wall-seconds 25 \
  --jobs 2 --output output/torus_holdout_retake
./theme2026-saku/bin/python experiments/summarize_public_holdout.py \
  output/torus_holdout_retake/rows.jsonl output/torus_holdout_retake/by_network.csv
```

24入力のうちdotは全件を完走し、既定トーラスは21件で幾何交差を計測できた。比較可能な21件すべてでdotの交差数が少なかった。トーラスの壁時計上限は25秒、dotの外部プロセス上限は8秒、Gurobiの各呼び出し上限は2秒。タイムアウト3件はすべてKrackhardt助言の16頂点条件で、差の集計には交差数を補完せず、完走率の分母に含めた。

| 元ネットワーク | 対応比較／試行 | トーラス−dotの幾何交差差の中央値 | 完走ペアでトーラスの交差が多い条件 |
| --- | ---: | ---: | ---: |
| Krackhardt | 9／12 | +65 | 9 |
| SocioPatterns高校友情 | 6／6 | +65.5 | 6 |
| 欧州研究機関メール | 6／6 | +108.5 | 6 |

元ネットワークを単位に見ると、追加3件すべてで既存の公開データ比較と同じ方向だった。観測された向きの有向部分グラフにおける交差数の劣位が、先行3ネットワークだけの結果ではないことを支持する。サンプルは弱連結近傍に限られ、短い閉路や相互辺を多く含む社会・通信ネットワークに偏る。元ネットワーク全体の描画品質や、境界をまたぐ経路の読み取りやすさは未評価。 [元ネットワーク単位の集計](../output/torus_holdout_20261126/run/by_network.csv) · [全試行](../output/torus_holdout_20261126/run/rows.jsonl)

### 二乗和配分の規模評価

既定の二次定式化を参照として残し、同じ整数目的を求める線形定式化を実験コードに追加した。層数と折返し辺数を探索で一度決め、すべての配分方式に共通に与える。各辺の整数スパンを `s`、補助変数を `z` とすると、`z ≥ (2k+1)s − k(k+1)` を整数 `k` ごとに課す。`s²` から右辺を引くと `(s−k)(s−k−1)` になる。整数スパンではこの差は非負で、`k=s` のとき0になるため、最小化では `z=s²` が成り立つ。実装では整数候補解で違反した不等式を遅延追加し、返された解について目的値を層割当から再計算する。線形スパン和の配分結果を初期解に使う。

5頂点・6辺の12生成入力について、層数3・4と実行可能な折返し辺数の109条件を全列挙と照合し、全条件で最適値と制約検査が一致した。DAG・Watts–Strogatzの12〜120頂点の12入力では、既定の二次定式化が解けた8件で同じ二乗和を得た。90・120頂点の4件では二次定式化がライセンス上限に達した一方、整数線形定式化は丸めた整数下界に達し、1回の交差削減を経た描画指標まで計測できた。実験で固定した層数・折返し辺数に対する最適値であり、タイブレークで選ぶ配置は両定式化で異なりうる。 [全列挙照合](../output/torus_square_20261126/oracle.jsonl) · [配分の比較](../output/torus_square_20261126/objective_comparison.csv)

```sh
PYTHONPATH=src ./theme2026-saku/bin/python experiments/check_square_epigraph.py
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py square_scaling \
  --solver-seconds 4 --wall-seconds 30 --jobs 2 --output output/torus_square_retake
./theme2026-saku/bin/python experiments/summarize_square_scaling.py output/torus_square_retake/rows.jsonl
```

次に、DAG・Watts–Strogatz、90・120頂点、頂点当たり2・4辺、乱数種322・323の16条件を追加した。各Gurobi呼び出しの上限は4秒、実験段階ごとの壁時計上限は30秒。層数・折返し辺数の探索は14件で値を返し、そのうち3件で求解制限に達した呼び出しがあった。120頂点・頂点当たり4辺のWatts–Strogatzの2件は探索段階で打ち切られた。

共通の探索結果を得た14件では二次定式化がすべてライセンス上限に達した。整数線形定式化は14件すべてで実行可能解を返し、10件で二乗和が丸めた整数下界と一致した。残る4件の整数ギャップは1・11,104・19,081・19,214だった。スパン和の配分と比べて、整数線形定式化の二乗和は13件で減り、1件で同値だった。

下流では線形スパン和・整数線形の二乗和の両方で9件が完走した。1回の交差削減後の埋め込み交差は、二乗和側で3件減少、2件同数、4件増加。両方式でDAGの高密度4件が打ち切られ、Watts–Strogatzの1件では分割なしBKの順序制約が失敗した。この下流比較は座標APIを直接呼び、CLIのフォールバックを適用していない。二乗和の低下だけでは下流の交差減少を予測できない。 [密度と乱数種を変えた対応表](../output/torus_square_holdout_20261126/objective_comparison.csv) · [求解下界と打ち切りを含む全試行](../output/torus_square_holdout_20261126/rows.jsonl)

大規模入力で二乗和の目的を評価する経路は確保した。高密度での探索の完走率、最適性が未確定の入力、CLIの既定回数とフォールバックを含めた下流実験が残る。

## 完了条件と証拠の対応

| 区分 | 現在の判断 |
| --- | --- |
| 十分な検証がある項目 | ローカル求解可能な範囲での階層探索と配分の小規模照合、単位スパン化、siftingの解品質、境界処理の順序、座標の実行可能性、既定パイプラインの同一入力比較、構造を制御した比較、実行時間・RSS・失敗の記録。下表に対応する。 |
| 主要な主張に必要だった残存実験 | 補助の円筒比較では巻き数と同時にsifting方式や境界処理も変えていた。同じ階層・global sifting・座標方式を使い、巻き数の自由度を単独で変えた48入力の比較が全件完走した。 [全試行](../output/torus_winding_ablation_checked_20261126/rows.jsonl) |
| WLS復旧後 | 72・90・120・500頂点における既定モデルの規模評価。環境上の制約による未実施として記録する。 |
| 今後の研究課題 | 参加者による読解効果、より多様な実ネットワークへの一般化、実験で判明した改善候補の製品実装。 |

| 完了条件 | 現時点で確認できる証拠 | 残る範囲 |
| --- | --- | --- |
| アルゴリズムの妥当性・有用性 | [厳密照合の出力](../output/torus_goal_20261126/oracles/)と[二乗和配分の全列挙](../output/torus_square_20261126/oracle.jsonl)で限定された探索空間の最適値を照合。 [座標](../output/torus_goal_20261126/coordinates_blocks/)と[描画](../output/torus_goal_20261126/drawing/)で実行可能性を検査 | 打ち切り条件と同値解の影響を分けて解釈する |
| 各工程の寄与、順序・組合せ | [順序比較](../output/torus_goal_20261126/crossing_order/)と[後処理を揃えたsifting比較](../output/torus_goal_20261126/matched_split/) | 高密度で完走した組合せが限られる |
| 既存手法・描画品質 | [合成グラフ全体比較](../output/torus_goal_20261126/framework/)、[公開ネットワークの追試](../output/torus_holdout_20261126/run/)、[巻き数のみを変えた比較](../output/torus_winding_ablation_checked_20261126/rows.jsonl) | 幾何指標から読解性能は推定しない。補助対照の失敗も記録する |
| 実行時間・メモリ・規模 | [単独実行の計測](../output/torus_goal_20261126/framework_memory/)、[90・120頂点の工程診断](../output/torus_square_pipeline_traced_20261126/terminal_stages.csv)、[500頂点の時間予算別結果](../output/torus_budget_sweep_20261126/budget_summary.csv) | 大規模の既定構成はライセンス制約で未検証。500頂点のsifting完走は代替階層を使った選定入力に限る。1000頂点は既取得の時間制限付き実験を報告する |
| 入力構造との関係 | [向き・SCC・次数を制御した比較](../output/torus_goal_20261126/figures/)と元ネットワーク単位の[公開データ集計](../output/torus_holdout_20261126/run/by_network.csv) | 元ネットワークの分野に偏りがあり、近傍結果から全ネットワークの性能は推定できない |
| 主張と根拠・妥当性・再現性 | 本報告の仮説表と各節の生データ、条件、再実行手順。 [既存成果物の整合性チェック](../output/torus_goal_20261126/artifact_check.json) | 先行計画より小規模・少数の実験と、ライセンス別の限界を論文にも明記する |
| 論文で使う成果物 | [再生成可能な図](../output/torus_goal_20261126/figures/)、[比較描画の例](../output/torus_goal_20261126/matched_split/)、[高密度条件を含む工程別ログ](../output/torus_square_pipeline_traced_20261126/layout_stages.csv)、本報告の条件別結論 | 本報告にWLS復旧後の実行条件と評価指標を併記した |

[読解実験の提示・採点手順](experiment_validation.md#参加者実験の実施と採点)は今後の研究用に保存している。

工程診断の追加後に `PYTHONPATH=src ./theme2026-saku/bin/python -m pytest -q src experiments/tests` を実行し、1,447件が通過した。32経路の終端表を16入力のマニフェストに照合し、sifting打ち切り16経路すべてが工程トレースの未完了イベントと一致することを確認した。 [テストログ](../output/torus_square_pipeline_traced_20261126/pytest.log)

層幅・初期層順の追試を追加した現行コードでも、同じテスト1,447件が通過した。長辺追試での改善件数・時間比と、層幅比較での候補数の上限到達を生データから再集計し、冒頭の主張表の記述と照合した。 [現行コードのテストログ](../output/torus_sifting_winding_oracle_20261126/pytest.log)

巻き数の対応比較を追加した最終状態で、同じテスト1,447件が通過した。既定トーラス、杉山型、放射型、dotが同じ合成48入力に幾何計測を持つこと、公開追試ではdotが24件、既定トーラスが21件を完走したことを生データで再照合した。今回の範囲で主要な主張を検証するために必要な実験は完了した。完走しなかった条件は失敗として保持し、WLS復旧後の計測と参加者研究は上の表に記載した。 [最終テストログ](../output/torus_winding_ablation_checked_20261126/pytest.log)

### 既定パイプラインでの大規模比較

同じ16条件を再実行し、層数と折返し辺数を両配分方式で共有した。配分後は実運用の `run_pipeline` に割当を渡し、既定の交差削減5回、joint、分割なしBK、必要時のlegacyへのフォールバックを適用した。描画品質の幾何評価は別タイマーで測定した。画像の保存やCLI起動時間は測定対象外。

| 同一入力での結果 | 件数 |
| --- | ---: |
| 層数・折返し辺数の探索が30秒で打ち切り | 2 |
| 両方式とも下流が30秒で打ち切り | 7 |
| 線形スパン和のみ下流完走 | 2 |
| 両方式とも下流完走し、幾何交差を計測 | 5 |

完走ペアでの幾何交差差（整数線形の二乗和 − 線形スパン和）は +4、+5、+4、0、−6。埋め込み交差の差も同じだった。Watts–Strogatz・120頂点・種323では、先の座標API直呼び条件では両方式が失敗したが、既定パイプラインでは両方式が完走し、二乗和側でlegacyへの切替を記録した。前回と今回で交差削減回数と並行度が異なるため、この完走差をフォールバック単独の効果量とは扱わない。今回の並行度4での壁時計時間は、単独実行の性能推定に用いない。完走ペアが5件に限られるため、描画品質の比較はこの標本内の記述に留める。 [対応集計](../output/torus_square_pipeline_20261126/objective_comparison.csv) · [全試行](../output/torus_square_pipeline_20261126/rows.jsonl) · [ログ](../output/torus_square_pipeline_20261126/run.log)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py square_pipeline \
  --solver-seconds 4 --wall-seconds 30 --jobs 4 --output output/torus_square_pipeline_retake
./theme2026-saku/bin/python experiments/summarize_square_scaling.py \
  output/torus_square_pipeline_retake/rows.jsonl
```

### 打ち切りの工程と固定階層での500・1000頂点評価

90・120頂点の4入力を、下流の各呼び出しの開始・完了を記録して再実行した。15秒予算下で、90頂点のDAG2件は両配分方式とも初回のglobal sifting中に打ち切られた。ダミー挿入と層内順の初期化は完了していた。90頂点・頂点当たり4辺のWatts–Strogatzは階層探索で打ち切られた。120頂点・頂点当たり2辺のWatts–Strogatzは両方式が完走し、二乗和側では初回の座標割当の例外からlegacyへ切り替えた。トレースの `complete=false` はその呼び出しが正常に戻らなかったことを表す。フォールバックによる回復後は試行全体を完走として数えた。 [工程トレース](../output/torus_square_diagnosis_20261126/layout_stages.csv) · [全試行](../output/torus_square_diagnosis_20261126/rows.jsonl)

30秒予算で全16入力を再実行し、線形スパン和と整数線形二乗和の計32経路を工程別に追跡した。頂点当たり4辺のWatts–Strogatz 2入力は共有の階層探索で打ち切られ、表では両経路に反映した。階層を得た28経路のうち16経路はsiftingで打ち切られ、残り12経路は幾何計測まで完走した。

| 入力系列・頂点当たりの辺数 | 階層探索で打ち切り | siftingで打ち切り | 幾何計測まで完走 |
| --- | ---: | ---: | ---: |
| DAG・2辺 | 0 | 5 | 3 |
| DAG・4辺 | 0 | 8 | 0 |
| Watts–Strogatz・2辺 | 0 | 0 | 8 |
| Watts–Strogatz・4辺 | 4 | 3 | 1 |

高密度のDAGは両配分でsiftingまで進んだ。高密度のWatts–Strogatzは入力により階層探索とsiftingの両方で打ち切りが生じた。二乗和側の2経路で初回の座標割当に失敗し、legacyに切り替えた。120頂点・2辺・種323では完走し、90頂点・4辺・種322では再度のsiftingで時間上限に達した。線形の7完走と整数線形二乗和の5完走は並行度4での結果であり、単独実行の速度差はこの集計から推定しない。 [各経路の終端](../output/torus_square_pipeline_traced_20261126/terminal_stages.csv) · [全工程のトレース](../output/torus_square_pipeline_traced_20261126/layout_stages.csv) · [実行ログ](../output/torus_square_pipeline_traced_20261126/run.log)

元の頂点数・辺数を120・240に揃えても、線形配分のDAG（種323）は11層・分割後457辺でsiftingが打ち切られ、Watts–Strogatz（種322）は108層・分割後982辺で完走した。ダミー込みの1層当たり平均頂点数は約30.6と8.0だった。これは分割後の辺数だけで打ち切りを予測できない例である。層数、層幅の分布、辺の接続と向きが同時に異なるため、層幅の単独効果はここから推定できない。 [階層探索と全工程の生データ](../output/torus_square_pipeline_traced_20261126/rows.jsonl)

この2入力を並行度1に変えて再実行した。DAGは両配分とも30秒でsifting中に打ち切られ、Watts–Strogatzは両配分とも幾何計測まで完走した。Watts–Strogatzのsiftingは線形配分で3.48秒、整数線形二乗和配分で3.66秒だった。この選定ペアでは、完走の差は同じランナー内で他入力を並行実行しなくても再現した。 [単独再実行の工程トレース](../output/torus_square_sifting_serial_20261126/layout_stages.csv) · [終端表](../output/torus_square_sifting_serial_20261126/terminal_stages.csv)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py square_pipeline \
  --solver-seconds 4 --wall-seconds 30 --jobs 4 --output output/torus_square_pipeline_traced_retake
./theme2026-saku/bin/python experiments/summarize_layout_trace.py \
  output/torus_square_pipeline_traced_retake/rows.jsonl
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py square_pipeline \
  --solver-seconds 4 --wall-seconds 30 --jobs 1 --case-id dag-120-2-323 \
  --case-id watts_strogatz-120-2-322 --output output/torus_square_sifting_serial_retake
./theme2026-saku/bin/python experiments/summarize_square_pipeline_failures.py \
  output/torus_square_pipeline_traced_retake/rows.jsonl
```

階層探索の上限と後段の規模効果を切り分けるため、各頂点から2辺を出す100・500・1000頂点の循環グラフを構成し、層幅5・10の割当を事前に固定した。元辺数は各サイズで同じ。全辺が次層へ進む条件と、半数が1層を飛び越えて頂点数と同数のダミーを生じる条件を比べた。幅と元辺数を揃えても、飛び越しによって接続先、ダミー数、初期交差が同時に変わるため、ダミー数だけの因果効果には帰属しない。

| 入力 | 隣接層のみ | 半数が1層を飛び越える |
| --- | ---: | ---: |
| 100頂点 | 2／2完走、埋め込み交差0 | 2／2完走、埋め込み交差125・94 |
| 500頂点 | 2／2完走、埋め込み交差0 | 2／2がglobal sifting中に10秒で打ち切り |
| 1000頂点 | 2／2完走、埋め込み交差0 | 2／2がglobal sifting中に10秒で打ち切り |

飛び越し条件でglobal siftingを0・1・5回に変更して再試行した。100頂点・幅5で埋め込み交差は305→129→125、幅10では640→198→94だった。500・1000頂点の4条件は0回なら完走し、交差は811〜2437。1回と5回は同じ10秒予算内で全件打ち切られた。これらは固定階層での後段の結果で、500・1000頂点での層探索、二乗和配分、または幾何交差の評価は含まない。一部の計測は実験間で並行したため、時間値は上限下の完走状況と工程の特定に用いる。 [固定階層の全試行](../output/torus_fixed_rank_scaling_20261126/rows.jsonl) · [反復数の全試行](../output/torus_fixed_rank_rounds_20261126/rows.jsonl)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py square_diagnosis \
  --solver-seconds 4 --wall-seconds 15 --jobs 1 --output output/torus_square_diagnosis_retake
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py fixed_rank_scaling \
  --wall-seconds 10 --jobs 2 --output output/torus_fixed_rank_retake
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py fixed_rank_rounds \
  --wall-seconds 10 --jobs 2 --output output/torus_fixed_rank_rounds_retake
./theme2026-saku/bin/python experiments/summarize_layout_trace.py output/torus_fixed_rank_retake/rows.jsonl
```

### global siftingの候補列挙を変えた追試

現行のglobal siftingは、全ブロック順の各挿入位置から対象層の順序を組み立て、すでに見た層順をスキップする。代替条件では、移動ブロックと層を共有するブロックを通過する位置と先頭だけを列挙した。区間内では移動ブロックより前にある同層ブロックの集合が不変で、候補の層順とスコア計算の入力も同じになる。各区間で最初の挿入位置を選んで候補の順序と厳密改善の判定を維持するため、採用時の全ブロック順と巻き数も一致する。現行の列挙は既定条件として維持し、実験ランナーだけが代替条件を選ぶ。

半数の辺が1層を飛び越える固定階層6条件を、既定の5回・各方式10秒で比較した。両方式が完走した100頂点の2条件では、層順・巻き数・座標が一致し、埋め込み交差数は125・94だった。観測した時間は層幅5で3.32秒から1.44秒、幅10で5.90秒から4.32秒。500頂点・幅5は代替条件だけが完走し、埋め込み交差543、9.51秒だった。500頂点・幅10と、1000頂点の2条件は両方式とも打ち切られた。並行度2で各条件を1回計測した値であり、一般的な速度向上率を推定するには単独での反復が必要。別途、2〜5層の12生成入力で同一初期順からの層順と巻き数の一致も検査した。 [工程トレース](../output/torus_fixed_rank_sparse_20261126/layout_stages.csv) · [全試行](../output/torus_fixed_rank_sparse_20261126/rows.jsonl)

### 500・1000頂点での階層探索の制約

DAG・一般有向・SCC連結・Watts–Strogatzの4族について、500・1000頂点、頂点当たり2・4辺、種0の16入力を現行のパイプラインに渡した。ローカルライセンスでは全件が最初の `Torus_Minimize_Torus_Edges` でサイズ上限を返した。エラー位置はサイズ上限だけを再送出する分岐で、後続の配分、交差削減、座標割当には進んでいない。固定階層での完走結果は後段の評価に使えるが、同規模の自動階層探索を含む評価にはライセンス制約のない求解環境か、照合済みの代替ソルバーが必要。 [全試行とソルバートレース](../output/torus_native_large_20261126/rows.jsonl)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py fixed_rank_sparse \
  --wall-seconds 10 --jobs 2 --output output/torus_fixed_rank_sparse_retake
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_study.py scaling --local-license \
  --sizes 500 1000 --densities 2 4 --seed-count 1 --solver-seconds 4 --case-seconds 20 \
  --jobs 2 --output output/torus_native_large_retake
```

比較図では三角を打ち切りとして示す。全体テストは1,447件通過。 [sifting時間の比較図](../output/torus_fixed_rank_sparse_20261126/sifting_scaling.pdf) · [回帰テストのログ](../output/torus_fixed_rank_sparse_20261126/pytest.log)

#### WLS復旧後の再開手順

目的は、既定の循環階層探索と二乗和配分を含む一連の処理について、元の頂点数と辺密度が完走率・工程時間・ピークRSS・品質にどう関係するかを調べること。ルートの `.env` を通常どおり参照する。まず接続確認が `ok` になった状態で、DAG・一般有向・SCC連結・Watts–Strogatzの4系列を頂点当たり2・4辺、各3種、並行度1で測る。72・90・120頂点を先行させ、500頂点は規模計測に加える。1000頂点の追加試行は今回の範囲に含めない。

```sh
./theme2026-saku/bin/python experiments/run_torus_validation.py wls_probe \
  --wls --output output/torus_wls_ready
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_study.py scaling \
  --sizes 72 90 120 500 --densities 2 4 --seed-count 3 --solver-seconds 15 \
  --case-seconds 120 --jobs 1 --output output/torus_wls_native_scaling
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_study.py framework \
  --external-only --dot dot --sizes 72 90 120 --densities 2 4 --seed-count 3 \
  --solver-seconds 15 --comparison-seconds 120 --case-seconds 250 \
  --jobs 1 --output output/torus_wls_native_geometry
```

規模計測では層数、折返し辺、二乗和、ダミー数、座標完走率、工程別時間、ピークRSS、求解ステータス・上下界を集計する。完成図比較では完走ペアの幾何交差、折れ、境界通過、実行時間を集計し、失敗件数と分母も示す。接続の名前解決とライセンスのサイズ上限は環境上の失敗とし、利用可能なモデルでの求解時間上限、工程の壁時計打ち切り、座標の実行不能は別に報告する。固定階層や代替求解の既取得結果は別表に置く。

```sh
MPLCONFIGDIR=/tmp/torus-goal-mpl ./theme2026-saku/bin/python experiments/plot_sifting_scaling.py \
  output/torus_fixed_rank_sparse_20261126/rows.jsonl output/sifting_scaling_retake.pdf
```

### 大規模入力の階層探索を構造別に検証

ローカル環境でHiGHSの取得を試みたが、PyPIの名前解決ができず実験には使用しなかった。汎用の階層探索と分けて、DAGと小さい強連結成分の連結グラフで利用できる条件を検証した。本体の既定設定は維持している。

DAGでは折返し辺数の下界は0。最大の有向経路が `h` 辺の場合、折返し0で描くには経路上に少なくとも `h+1` 層が必要である。杉山型実装の最長経路階層割当はこの下界に達する。12・36頂点の4条件すべてでGurobi探索の層数と折返し辺数に一致し、500・1000頂点の4条件すべてで制約違反0の階層割当を得た。この割当は最小層数を保証するが、二乗スパン和の配分を追加していない。

一般の有向グラフでは、各強連結成分内で必要な最小折返し辺数の和が下界になる。各成分の局所問題には成分の頂点数と同じ層数を許すため、任意の頂点全順序を収容できる。凝縮DAGのトポロジカル順に成分の層を連結すると、成分間の全辺が前進する。すべての局所求解が最適と確認できれば、構成した割当はその下界に達する。空層を詰めてから連結するが、成分をまたいで層を共有する場合の最小層数や、二乗スパン和は最適化しない。長いダミー列が生じる可能性もある。

DAGでは500・1000頂点の4条件すべてで、既定の5回条件がglobal sifting中に15秒で打ち切られた。0回条件は頂点当たり2辺の2件で完走し、埋め込み交差は82,573・316,558。頂点当たり4辺では500頂点が座標割当中、1000頂点が境界処理中に打ち切られた。 [DAGの生データ](../output/torus_dag_large_reuse_20261126/rows.jsonl) · [工程トレース](../output/torus_dag_large_reuse_20261126/layout_stages.csv)

SCC連結型の12・36頂点の4条件では、成分分解の折返し辺数が一括のGurobi探索と一致した。500・1000頂点の4条件では、各入力の10成分をすべて最適に解き、折返し辺数29・57・42・89を得た。次に、その折返し辺集合を構成上だけ逆向きにしたDAGの最長経路順位で層を詰めた。元辺と折返しフラグは維持される。この圧縮は選んだ折返し辺集合に対する最小層数を与える。別の同数の折返し辺集合も含めた最小層数は比較していない。

| 頂点数 | 頂点当たりの辺数 | 連結時の層数 → 圧縮後 | 連結時のダミー数 → 圧縮後 |
| ---: | ---: | ---: | ---: |
| 500 | 2 | 372 → 217 | 67,620 → 35,890 |
| 500 | 4 | 282 → 190 | 143,232 → 89,890 |
| 1000 | 2 | 555 → 290 | 196,991 → 94,954 |
| 1000 | 4 | 503 → 357 | 499,603 → 354,247 |

両構成とも大規模4条件の後段は、交差削減0回・5回の双方で15秒以内に完走しなかった。したがって折返し辺数の最適性と階層割当の可否は確認できたが、同規模の全体比較や二乗和配分の評価は引き続き未達。SCCが大きい入力では分解によるライセンス制約の緩和も期待できない。時間上限と並行度の下での結果であり、所要時間の分布や最大完走規模は推定していない。 [成分ごとの求解と連結](../output/torus_scc_large_20261126/rows.jsonl) · [圧縮と後段の生データ](../output/torus_scc_compact_20261126/rows.jsonl)

```sh
for group in dag_large scc_large scc_compact
do
  PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py "$group" \
    --solver-seconds 4 --wall-seconds 15 --jobs 2 --output "output/${group}_retake"
  ./theme2026-saku/bin/python experiments/summarize_layout_trace.py "output/${group}_retake/rows.jsonl"
done
```

### 固定折返し条件での二乗和配分を最小カットで求解

層数と折返し辺集合を固定し、実行可能な整数階層から出発する。折返し辺だけ制約上の向きを反転すると、すべての制約を「宛先層 − 始点層が1以上」として扱える。目的関数は各辺についてその差 `d` の二乗、折返し辺では `(d−L)²` の和である。全頂点の部分集合を一斉に1層上げる場合と下げる場合について、それぞれ最良の集合を最小カットで求めた。各辺のコスト差は、両端の移動有無に対する線形項と、片端だけを動かすときの費用1に分解できる。層の上下限と、差が1の辺の制約は、実行不能なカットを排除する容量で表現した。

別の実行可能解への整数変位は、正および負の閾値ごとの部分集合の単位移動に分解できる。現在の解で制約が等号の辺では、実行可能な最終変位が各閾値の移動でも順位制約を守る。各辺に対して閾値の移動はスパンを一方向に変えるため、凸性により各単位移動の初期点でのコスト差の和が、全移動のコスト差の下界となる。よって上下どちらにも改善する部分集合がなくなれば、固定条件で大域最適である。DAGでは折返し辺数0の集合は一意なので、最小層数での二乗和配分もこの結果に含まれる。SCC連結型は成分探索で選んだ折返し辺集合を固定した最適値である。

5頂点、層数3・4の40条件で全割当の列挙と一致した。DAGの12・36頂点の4条件ではGurobiの二次定式化と同じ目的値を得た。実装は実験用で、本体の階層探索・配分の既定値は変更していない。 [小規模全列挙](../output/torus_dag_square_cut_20261126/oracle.jsonl)

500・1000頂点のDAG4条件では、固定層数・折返し0の二乗和配分が全件で最適解を返した。最長経路の初期割当と比べ、ダミー数はそれぞれ2,111→1,611、9,448→6,951、3,244→2,311、17,945→13,624。交差削減0回は4件中3件で完走し、未調整の最長経路順位で完走した2件との共通条件で埋め込み交差は82,573→82,201、316,558→296,253だった。既定の5回はいずれも15秒以内に完走しなかった。SCC連結型の大規模4条件では、単位移動だけの二乗和配分が全件で15秒までに証明を終えなかった。 [DAGの全試行](../output/torus_dag_square_cut_20261126/rows.jsonl) · [SCC連結型の全試行](../output/torus_scc_square_cut_20261126/rows.jsonl)

```sh
PYTHONPATH=src ./theme2026-saku/bin/python experiments/check_square_cut.py
for group in dag_square_cut scc_square_cut scc_square_scaled
do
  PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py "$group" \
    --solver-seconds 4 --wall-seconds 15 --jobs 2 --output "output/${group}_retake"
  ./theme2026-saku/bin/python experiments/summarize_layout_trace.py "output/${group}_retake/rows.jsonl"
done
```

単位移動の打ち切りを受け、移動幅を2の累乗から半減し、最後に1で改善がないことを検査する条件も追加した。移動幅 `q` では線形項を `q` 倍、片端だけを動かす費用を `q²` とし、制約もその幅で検査する。1の終了判定は変わらないため、最適性の対象は同じ。全列挙40条件と、単位移動で解けたSCC連結型の小規模4条件で目的値が一致した。

| SCC連結型の大規模入力 | 圧縮順位の二乗和 → 最適値 | ダミー数 | 配分の壁時計時間 |
| --- | ---: | ---: | ---: |
| 500頂点・頂点当たり2辺 | 4,071,120 → 3,086,494 | 35,890 → 31,758 | 4.07秒 |
| 500頂点・頂点当たり4辺 | 8,820,542 → 7,886,521 | 89,890 → 84,893 | 3.44秒 |
| 1000頂点・頂点当たり2辺 | 14,217,362 → 11,053,806 | 94,954 → 85,640 | 10.07秒 |
| 1000頂点・頂点当たり4辺 | 67,312,999 → 60,252,279 | 354,247 → 335,191 | 14.16秒 |

段階的な移動では大規模4入力すべてで固定条件の最適解を得た。後段は交差削減0回・5回とも4件すべて15秒で打ち切られた。時間は並行度2で観測した値。大規模の層探索と二乗和配分の証拠はDAGおよび小さいSCCの連結型に限られ、大きい単一SCCの最小折返し辺数と、500・1000頂点での既定の完成描画比較は残る。 [段階的移動の全試行](../output/torus_scc_square_scaled_20261126/rows.jsonl) · [双方の全列挙照合](../output/torus_dag_square_cut_20261126/oracle_scaled.jsonl)

### 大きなSCCを持つ入力の折返し辺数の上下界

大規模な一括整数求解がローカルライセンスの上限に達するため、折返し辺数の上下界を構成した。頂点を共有していても元辺を共有しない有向閉路は、それぞれ少なくとも1本の折返しを必要とする。下界は貪欲な閉路除去で得た集合と、逆行辺を起点に残余グラフの最短帰路を選ぶ集合のうち、大きい方である。元辺への所属、閉路の連続性、辺の非共有をマニフェストに対して再検査した。

上界は閉路除去ヒューリスティックを入力順5通りで実行し、同じグラフ上で逆行辺数が厳密に減る頂点挿入を最大4周適用して求めた。選んだ逆行辺を制約上だけ反転したDAGを最長経路法で層に割り当て、元の向き、折返し辺数、スパン制約を検査した。その層数は選んだ折返し辺集合に対する値である。小規模8件では、求解打ち切りなしの6件のGurobi参照値をすべて上下界に含んだ。小規模Watts–Strogatzの4件では上下界が一致した。

| 500・1000頂点の入力 | 頂点当たりの辺数 | 下界 → 改善後の下界 | 上界 → 改善後の上界 |
| --- | ---: | ---: | ---: |
| 有向閉路と追加辺 500 | 2 | 25 → 43 | 118 → 111 |
| 有向閉路と追加辺 500 | 4 | 70 → 178 | 450 → 381 |
| 有向閉路と追加辺 1000 | 2 | 34 → 69 | 240 → 208 |
| 有向閉路と追加辺 1000 | 4 | 95 → 300 | 881 → 740 |
| Watts–Strogatz 500 | 2 | 9 → 11 | 62 → 46 |
| Watts–Strogatz 500 | 4 | 30 → 48 | 315 → 123 |
| Watts–Strogatz 1000 | 2 | 12 → 21 | 144 → 88 |
| Watts–Strogatz 1000 | 4 | 46 → 87 | 692 → 334 |

有向閉路に辺を追加した入力は全件が単一SCCで、Watts–Strogatzは最大SCCが頂点の98.3%以上を占めた。大規模8件すべてで上下界は改善したが、差は35〜440本残り、折返し辺数の最適性を確定できた入力はなかった。改善後の折返し辺集合と層数を固定した二乗和配分は8件すべてで完了した。後段は交差削減5回では全件が12秒で打ち切り。0回では500頂点・頂点当たり2辺の各族1件が完走し、埋め込み交差は76,248・12,520だった。時間上限下での比較であり、完成描画の品質や単独実行時間には一般化しない。 [上下界と証明用閉路](../output/torus_wrap_bounds_short_cycles_20261126/rows.jsonl) · [上下界の対応表](../output/torus_wrap_bounds_short_cycles_20261126/bounds.csv) · [配分と後段の全試行](../output/torus_wrap_bounds_refine_20261126/rows.jsonl)

```sh
for group in wrap_bounds wrap_bounds_refine wrap_bounds_short_cycles
do
  PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py "$group" \
    --solver-seconds 4 --wall-seconds 12 --jobs 4 --output "output/${group}_retake"
  ./theme2026-saku/bin/python experiments/summarize_wrap_bounds.py "output/${group}_retake"
done
```

保存済みの短い閉路の試行は並行度2で、階層配分以後を実行する二つの試行は並行度4。各実行の設定を参照して時間を解釈する。

### 交差・折れ・境界通過の同一入力での比較

既存の全体比較と独立公開データから、dotとトーラスの両方が完走した入力を対応づけ直し、交差以外の品質も集計した。生成48件と独立公開21件の全ペアで、計測した中心線の折れ数はトーラスの方が少なかった。生成系列ごとの「トーラス−dot」の折れ数差の中央値は−24〜−38.5、独立公開各ネットワークでは−105.5〜−120。dotの折れはポリライン出力の制御点から定義し、トーラス側では分割された元辺のリフト上で角度変化を数えた。描画系ごとのルーティングによる差を含む。

周期方向にリフトしたトーラスでは逆向きに進む元辺が全ペアで0だった。独立公開データでは、dotの始点より終点が左にある元辺の割合の中央値がネットワークごとに37.5〜48.2%。トーラスでは階層方向の境界を通る元辺の割合が25.7〜40.4%、いずれかの境界を通る割合は38.2〜49.7%だった。軸の向きを統一することと、表示枠内で辺を途切れず追えることは別の品質である。

公開21ペアすべてではdotの方が交差が少なかった。入力ごとの枠対角長で正規化した辺長についても、トーラス側が短い件と長い件が混在した。折れの少なさや方向の統一だけから視認性や読解成績は推定しない。比較は完走ペアに限り、公開データの失敗3件と同じ元ネットワーク内での近傍の重複を考慮する。 [生成データの対応集計](../output/torus_goal_20261126/framework/direction_tradeoff.csv) · [独立公開データの対応集計](../output/torus_holdout_20261126/run/direction_tradeoff.csv) · [再集計コード](../experiments/summarize_direction_tradeoff.py)

### 読解実験の教材と採点の独立照合

保存済みの有向辺リストから、24問の辺方向と一意な最短有向経路の正答を再計算し、すべて一致した。配布用HTMLに含まれる3フォームは出題表と一致し、各フォームに規模・課題・境界通過・描画条件の各組合せが1問ずつあった。各問に3種類の描画を割り付け、提示先の72画像が元画像とバイト単位で一致することも確認した。

既知の正誤を与えた合成入力で、採点コードが未完了と中断の回答を除外し、主比較の対応差と区間を計算することを確認した。この照合には実参加者の回答を使用していない。読解への効果は回答収集後に判定する。 [教材・採点の監査結果](../output/torus_readability_audit_20261126/audit.json) · [再監査コード](../experiments/audit_readability_materials.py) · [実施手順](experiment_validation.md#参加者実験の実施と採点)

### 500・1000頂点での描画比較

有向閉路と追加辺、Watts–Strogatzの2系列について、500・1000頂点、頂点当たり2辺、種0の4入力を比較した。トーラス側は局所改善した折返し辺集合と、その集合での最小層数・最適二乗和配分を共通に使った。交差削減0回、現行の5回、同じ層順の重複候補を省く5回を試した。境界・座標の既定処理は全条件で共通。各実験段階の壁時計上限は35秒、並行度2。dotを後段評価と分けた実行も行い、階層方向を持たないsfdpを補足対照に加えた。

| 入力 | dotの幾何交差 | sfdpの幾何交差 | トーラス0回の幾何交差 |
| --- | ---: | ---: | ---: |
| 有向閉路と追加辺・500頂点 | 配置で打ち切り | 15,433 | 76,248 |
| 有向閉路と追加辺・1000頂点 | 配置で打ち切り | 58,801 | 境界処理で打ち切り |
| Watts–Strogatz・500頂点 | 2,080 | 2,097 | 12,520 |
| Watts–Strogatz・1000頂点 | 配置で打ち切り | 8,652 | 52,561 |

トーラスの5回条件は、候補列挙の両方式で4件すべてglobal sifting中に打ち切られた。0回とdotが両方完走した500頂点のWatts–Strogatzでは、トーラスの幾何交差が多く、折れは869対2,364と少なかった。dotの幾何交差と折れは、配置と評価を分けた再実行でも同じ値だった。sfdpで測れた交差は階層方向や折返し制約の異なる方式との比較である。先の12秒条件と比べ、今回の35秒条件では0回の完走が2件から3件に増えたが、比較できた入力は少数で、既定の階層探索と5回siftingを含む完走時の描画品質は未評価。 [トーラスとdotの全試行](../output/torus_large_geometry_20261126/rows.jsonl) · [工程トレース](../output/torus_large_geometry_20261126/layout_stages.csv) · [dot・sfdpの配置と評価の分離](../output/torus_large_graphviz_20261126/rows.jsonl)

```sh
for group in large_geometry large_graphviz
do
  PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py "$group" \
    --wall-seconds 35 --jobs 2 --output "output/${group}_retake"
done
```

### 500頂点での時間上限の延長と層間採点の変更

35秒条件でdotとトーラス0回が完走したWatts–Strogatz・500頂点・頂点当たり2辺・種0を選び、1ワーカー・段階ごと120秒で再試行した。dotの幾何交差2,080件とトーラス0回の12,520件は再現した。現行の候補列挙と重複候補を省く列挙は、5回条件では両方ともglobal sifting中に120秒で打ち切られた。比較入力は前回結果から選んだ1件で、追加の独立標本とは扱わない。

採点時の巻き数のコピーを対象層間の辺に限定する条件も試した。候補採点はその層間の固定辺と可変辺だけを参照するため、参照する値は変わらない。小規模12入力で既定の層順・巻き数と一致し、関連テストは77件通過した。層間幅24・64・128の合成データで1呼出し当たりの中央値を交互に測ると、0.747→0.597 ms、1.624→1.548 ms、2.836→2.804 msだった。大規模試行と分けた局所計測であり、完成描画の加速率には使わない。500頂点の同じ入力で重複候補の削減と併用した5回条件も、90秒以内に完走しなかった。二つの大規模試行は一部で実行が重なったため、時間上限は完走状況にのみ用いる。 [120秒の試行](../output/torus_large_geometry_extended_20261126/rows.jsonl) · [層間に限定した試行](../output/torus_large_local_winding_20261126/rows.jsonl) · [局所計測](../output/torus_large_local_winding_20261126/strip_benchmark.jsonl) · [テストログ](../output/torus_large_local_winding_20261126/pytest.log)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_geometry \
  --case-id watts_strogatz-500-2-0 --wall-seconds 120 --jobs 1 --output output/torus_extended_retake
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_local_winding \
  --case-id watts_strogatz-500-2-0 --wall-seconds 90 --jobs 1 --output output/torus_local_winding_retake
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/benchmark_local_winding.py
```

### 整数採点と、時間を区切ったglobal sifting

交差式の端点順位差の符号を `a,b`、巻き数差を `d` とすると、現行の式は整数演算 `max(0, (abs(2d+b−a)+abs(a)+abs(b)−2) // 2)` で評価できる。分子は偶数である。3通りの巻き数を比較するときは同じ端点比較を再利用した。既定の採点を残し、実験条件でこの変更と重複候補の削減を選んだ。小規模の12入力と、100頂点・層幅5／10で5回通した2入力で層順と巻き数が一致した。関連テスト77件が通過した。

52・132・260線分の合成層間において、採点1呼出しの中央値は0.621→0.175 ms、1.481→0.450 ms、2.847→0.890 ms。実測500頂点では、この変更を組み合わせた5回条件もglobal sifting中に120秒で打ち切られた。局所計測から全体の高速化率は推定しない。 [合成計測](../output/torus_large_integer_scoring_20261126/strip_benchmark.jsonl) · [100頂点の完全一致](../output/torus_large_integer_scoring_20261126/fixed_rank_parity.jsonl) · [500頂点の試行](../output/torus_large_integer_scoring_20261126/rows.jsonl)

そこでsiftingの各呼出しを20秒で止め、その時点までに反映したブロック順・巻き数で既定の境界・座標処理を続ける条件を試した。中途のブロック移動は反映しない。Watts–Strogatzの500・1000頂点、頂点当たり2辺、種0の2入力で、どちらもsiftingが上限に達した後に描画と幾何計測を完了した。

| 頂点数 | 幾何交差 0回 → 20秒条件 | 折れ 0回 → 20秒条件 | 20秒条件の下流処理 |
| ---: | ---: | ---: | ---: |
| 500 | 12,520 → 10,905 | 869 → 877 | 22.43秒 |
| 1000 | 52,561 → 52,171 | 1,680 → 1,682 | 32.06秒 |

両条件で幾何交差が減ったが、折れは増えた。500頂点でdotの幾何交差は2,080件だった。1000頂点のdotは35秒条件で配置が打ち切られている。0回と20秒条件は別実行の品質比較で、同一の時間計測条件ではない。20秒はsifting呼出しごとの予算で、下流全体の上限は60秒、並行度は2。5回完走時の結果は依然として未計測である。 [時間制限付き全試行](../output/torus_large_budgeted_scoring_20261126/rows.jsonl) · [工程トレース](../output/torus_large_budgeted_scoring_20261126/layout_stages.csv) · [停止条件を含む回帰テスト](../output/torus_large_budgeted_scoring_20261126/pytest.log)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/benchmark_local_winding.py
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/benchmark_local_winding.py --fixed-rank-check
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_budgeted_scoring \
  --case-id watts_strogatz-500-2-0 --case-id watts_strogatz-1000-2-0 \
  --wall-seconds 60 --jobs 2 --output output/torus_budgeted_retake
```

### 大規模siftingの時間予算と再現性

前回のWatts–Strogatz 2入力で、同じ折返し辺集合、二乗和配分、境界処理、座標割当を使い、siftingの呼出し当たり予算を0・5・20・45秒に変えた。0秒は初期配置のみ。正の予算では、全ブロック順における同じ層順の候補を省き、整数採点を使う。各段階の壁時計上限は70秒、並行度は2。8条件全件が描画・幾何計測まで完走し、正の予算の全件でsiftingを時間上限で止めた。

| 頂点数 | 0秒 | 5秒 | 20秒 | 45秒 | 45秒条件の下流壁時計 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 500 | 12,520 | 12,261 | 10,905 | 9,854 | 47.28秒 |
| 1000 | 52,561 | 52,368 | 52,171 | 51,308 | 57.14秒 |

表の品質値は幾何交差数。45秒では0秒と比べ約21.3%・2.4%少なかった。折れは500頂点で869→875、1000頂点で1,680→1,679。いずれかの境界を通る元辺数は全条件で46・88本だった。これらは2入力での計測であり、各時間で1回だけ実行した。 [対応集計](../output/torus_budget_sweep_20261126/budget_summary.csv) · [図](../output/torus_budget_sweep_20261126/budget_crossings.pdf) · [全試行](../output/torus_budget_sweep_20261126/rows.jsonl)

時間予算で処理できる候補数は負荷で変わる。停止判定を呼ぶ回数に上限を設ける方式も追加した。判定は各ブロックの開始時と各候補の採点前に呼ばれるため、ここでの回数は候補数や完了した反復数とは異なる。フォールバックが起きる場合も回数は累積する。1,000・3,000回の上限を2入力に適用し、1ワーカーと2ワーカーで再実行した。4条件すべてで全層順・巻き数のハッシュが一致し、幾何交差、折れ、境界通過元辺数も一致した。時間値の一致は要件としていない。 [再実行の照合](../output/torus_check_limits_replay_20261126/replay_verification.jsonl)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_budgeted_scoring \
  --case-id watts_strogatz-500-2-0 --case-id watts_strogatz-1000-2-0 \
  --sifting-budgets 0 5 20 45 --wall-seconds 70 --jobs 2 --output output/torus_budget_sweep_retake
MPLCONFIGDIR=/tmp/torus-goal-mpl ./theme2026-saku/bin/python experiments/plot_sifting_budget.py \
  output/torus_budget_sweep_retake
for jobs in 1 2
do
  PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_budgeted_scoring \
    --case-id watts_strogatz-500-2-0 --case-id watts_strogatz-1000-2-0 \
    --sifting-check-limits 1000 3000 --wall-seconds 70 --jobs "$jobs" --output "output/torus_checks_$jobs"
done
./theme2026-saku/bin/python experiments/audit_sifting_replay.py output/torus_checks_1 output/torus_checks_2
```

### 層間の候補採点の一括計算と再利用

巻き数3候補の採点について、端点順位と巻き数を整数配列にして辺対の費用を一括計算した。採用済み巻き数での交差と、可変辺以外の交差の採点は既存の整数方式を使う。さらに、1ブロックの候補探索中は、対象層間の移動ブロックの挿入位置が同じなら両層の順序と採点入力が一致するため、同じ費用と巻き数候補を再利用する条件も追加した。再利用はブロックを確定するたびに破棄する。比較順と採用条件は従来どおりで、本体の既定動作はそのまま。

合成層間3条件で返り値は一致し、配列を使う採点は整数方式の0.180・0.458・0.928 msに対して0.135・0.295・0.535 msだった。一方、100頂点の固定階層2条件では、配列と再利用を組み合わせた5回後の層順・巻き数は一致したが、実測時間は重複候補削減と整数採点のみの0.59・1.97秒に対して1.04・2.10秒だった。局所採点の短縮から、sifting全体の短縮は予測できない。各入力での全体時間は1回の観測で、他の実験と一部並行した。関連テストは77件通過した。 [層間計測](../output/torus_large_cached_scoring_20261126/strip_benchmark.jsonl) · [層順と巻き数の照合](../output/torus_large_cached_scoring_20261126/fixed_rank_parity.jsonl) · [テストログ](../output/torus_large_cached_scoring_20261126/pytest.log)

500頂点では配列による採点だけを追加した5回条件も120秒で打ち切られた。配列による採点と層間の再利用を併用した500・1000頂点の2条件も、同じ入力でいずれもglobal sifting中に120秒で打ち切られた。圧縮や境界処理より前の打ち切りであり、完成描画の交差数は欠測として扱う。 [配列による採点の試行](../output/torus_large_vector_scoring_20261126/rows.jsonl) · [再利用を加えた全試行](../output/torus_large_cached_scoring_20261126/rows.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/benchmark_local_winding.py --vector
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/benchmark_local_winding.py --vector --fixed-rank-check
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_cached_scoring \
  --case-id watts_strogatz-500-2-0 --case-id watts_strogatz-1000-2-0 \
  --wall-seconds 120 --jobs 2 --output output/torus_cached_retake
```

### 500頂点の等作業量プロファイル

Watts–Strogatz・500頂点の保存済み入力から同じ階層と初期順を再構成した。停止判定の最初の3,000回までを `cProfile` で測り、各比較で終了時の層順と巻き数が一致することを確認した。計測値にはプロファイラの負荷を含み、同時に長時間実験も稼働していた。以下は特定の探索区間で、完成描画全体の速度は示さない。

- 整数採点と配列採点を比較した区間では、層間採点の呼出しはどちらも194,764回、siftingの累積計測は25.03秒・25.53秒。配列を使う三つの巻き数候補の評価だけを高速化しても、現在の巻き数で数える辺対が多く残った。
- 同じ層間順序の採点を再利用すると、採点の呼出しは23,951回に減った。同じ3,000回区間の累積計測は5.29秒で、そのうち候補層順の構成に2.01秒を使った。
- 層順を差分で更新する候補列挙を追加した。次の候補位置へ進む際に、移動ブロックが通過する頂点のある層だけで隣接交換する。各候補が独立した層順を持つよう、新しい順序を作って保存し、候補順は維持する。別の対応計測で、候補順の構成が2.037秒から0.023秒、sifting全体が5.33秒から3.27秒になった。
- 影響する層間だけで採点合計を更新する方式も試した。直前と同じ層間の費用・巻き数候補を保持し、候補を採用するときは従来の層間順で巻き数候補を統合する。同じ区間で3.27秒から3.03秒。旧方式を既定とし、差分更新は実験条件だけで使用する。

同一の区間内で終了時の層順と巻き数が一致し、差分の層順更新までの関連テストは77件通過した。 [全プロファイルと集計](../output/torus_large_profile_20261126/) · [工程別の図](../output/torus_large_profile_20261126/profile_phases.pdf)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/profile_large_sifting.py \
  output/torus_large_cached_scoring_20261126/inputs.jsonl watts_strogatz-500-2-0 --checks 3000
```

1000頂点の同じ系列でも最初の停止判定1,000回を照合した。層間スコア再利用のみの5.05秒に対し、層順と採点合計の差分更新を併用すると3.18秒で、終了時の層順と巻き数は一致した。1000頂点の描画完走時の品質は、この区間プロファイルから推定しない。差分採点まで含む関連テストは77件通過した。 [1000頂点の区間計測](../output/torus_large_profile_20261126/profile_1000.jsonl) · [テスト結果](../output/torus_large_profile_20261126/pytest.log)

### 500頂点で上限5回のsiftingまで完走

同じWatts–Strogatz・500頂点入力で、以前120秒で打ち切られた条件を延長した。層間スコア再利用方式は上限600秒で、候補層順を差分更新する方式は上限300秒で、それぞれ上限5回のsifting、境界と座標割当、幾何計測まで完走した。前段は両方式とも、同じ実行可能な折返し辺集合と、それを固定した最適二乗和配分である。全層順・巻き数のハッシュが両方式で一致し、幾何交差3,441件、折れ775件、境界通過元辺62本も一致した。下流の観測時間は299.52秒と227.45秒。試行は一部並行し、上限とソース構成も異なるため、時間差を反復実験による速度推定には用いない。 [層間スコア再利用の完走](../output/torus_cached_long_20261126/rows.jsonl) · [層順差分更新の完走](../output/torus_incremental_large_20261126/rows.jsonl)

| 同一500頂点入力の条件 | 幾何交差 | 折れ | 境界通過元辺 |
| --- | ---: | ---: | ---: |
| トーラス・0回 | 12,520 | 869 | 46 |
| トーラス・45秒予算 | 9,854 | 875 | 46 |
| トーラス・上限5回完走 | 3,441 | 775 | 62 |
| Graphviz dot | 2,080 | 2,364 | 0 |

この入力では完走したsiftingで交差と折れが減り、境界を通る元辺が16本増えた。dotとの比較では交差が1,361件多く、折れが1,589件少なかった。打ち切りが続いた入力から選んだ1件なので、500頂点全般、1000頂点、あるいはネイティブのGurobi階層探索を含む既定パイプラインの結論には広げない。 [0回とdotの生データ](../output/torus_large_geometry_20261126/rows.jsonl) · [45秒の生データ](../output/torus_budget_sweep_20261126/rows.jsonl)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_cached_scoring \
  --case-id watts_strogatz-500-2-0 --wall-seconds 600 --jobs 1 --output output/torus_cached_long_retake
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py large_incremental_scoring \
  --case-id watts_strogatz-500-2-0 --wall-seconds 300 --jobs 1 --output output/torus_incremental_retake
```

### 時間予算を固定した独立入力での確認

先の予算比較を踏まえ、追加入力での条件をsifting 0秒・20秒とし、結果に応じた再調整をせずに比較した。有向閉路に辺を追加する系列とWatts–Strogatzについて、90・120頂点、頂点当たり2辺、乱数種811・812・813の計12入力。同じ入力ごとに折返し辺集合と二乗和配分を共用し、0秒には初期配置、20秒には候補の重複排除と整数採点を使った。既存80マニフェストに含まれる辺リスト付き1,608入力のノード・辺を正規化して照合し、同一のグラフを検出しなかった。この照合は頂点名を置換した同型の検査を含まない。 [入力照合](../output/torus_budget_holdout_20261126/holdout_inputs_audit.json)

全12入力で0秒・20秒・dotの幾何計測に成功した。20秒では0秒に対し全12入力で幾何交差と折れが減り、境界を通る元辺数が増えた。幾何交差の各入力での減少率の中央値は、有向閉路と追加辺の系列で70.2%、Watts–Strogatzで71.8%。有向閉路と追加辺の6件はsiftingの20秒上限に達し、Watts–Strogatzの6件は上限前にsiftingが終了した。

dotに対して、20秒条件は有向閉路と追加辺の6件すべてで幾何交差が多かった。Watts–Strogatzでは6件中1件で少なく、5件で多かった。折れは12件すべてでトーラスの方が少なかった。別の規模・乱数種でsiftingの効果を確認した結果であり、20秒が最適だという根拠や、読解成績の測定にはならない。 [入力ごとの対応表](../output/torus_budget_holdout_20261126/pairs_with_dot.csv) · [系列別集計](../output/torus_budget_holdout_20261126/by_family_with_dot.jsonl) · [幾何交差の対応図](../output/torus_budget_holdout_20261126/crossings_holdout.pdf)

```sh
for group in budget_scoring_holdout budget_holdout_dot
do
  PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py "$group" \
    --wall-seconds 45 --jobs 3 --output "output/${group}_retake"
done
./theme2026-saku/bin/python experiments/summarize_budget_holdout.py output/budget_scoring_holdout_retake \
  --dot-run output/budget_holdout_dot_retake
MPLCONFIGDIR=/tmp/torus-goal-mpl ./theme2026-saku/bin/python experiments/plot_budget_holdout.py \
  output/budget_scoring_holdout_retake/pairs_with_dot.csv output/budget_holdout_retake.pdf
```

### 大規模条件の評価範囲

上限5回のsiftingを完走した大規模条件の比較には、500頂点のWatts–Strogatz入力を用いる。1000頂点の追加長時間試行は、配置と幾何計測の結果が出る前に中断した。1000頂点については、取得済みの時間制限付き描画と区間計測を報告する。 [中断した試行の設定](../output/torus_delta_1000_20261126/settings.json) · [中断ログ](../output/torus_delta_1000_20261126/run.log) · [時間予算別の結果](../output/torus_budget_sweep_20261126/budget_summary.csv)

### 同じ有向グラフに対する層幅の比較

長さ24の循環に各位置4頂点を置き、次の位置にだけ進む2本の出辺を各頂点に与えた。乱数種941・942・943で接続を変え、各グラフの96頂点・192有向辺を固定したまま、位置を4・8・12・24層に周期的に割り当てた。全条件でスパン1、ダミー0、入次数と出次数は各2、SCCは1つ。層数を変えると各層の幅に加えて、垂直周期境界を通る元辺数と初期交差も変わる。

| 層幅 | 層数 | 1回のsifting時間の中央値（3入力の範囲、秒） | 0回から1回への埋め込み交差の減少数の中央値 |
| ---: | ---: | ---: | ---: |
| 4 | 24 | 0.067（0.062–0.072） | 103 |
| 8 | 12 | 0.232（0.212–0.242） | 84 |
| 12 | 8 | 0.414（0.409–0.457） | 124 |
| 24 | 4 | 1.460（1.443–1.506） | 352 |

単独実行で全24経路が完走し、各乱数種で幅が増えるほどsifting時間が増えた。幅4と24の時間中央値には約22倍の差があった。各幅で1回条件は0回条件より埋め込み交差が減った。元の接続とダミー数を揃えても階層割当が計算コストに影響する例である。この結果は特定の周期的割当を比較しており、任意のグラフにおける層幅だけの効果や、幾何交差への効果は推定していない。 [入力と階層](../output/torus_fixed_rank_width_20261126/inputs.jsonl) · [全試行](../output/torus_fixed_rank_width_20261126/rows.jsonl) · [工程トレース](../output/torus_fixed_rank_width_20261126/layout_stages.csv)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py fixed_rank_width \
  --wall-seconds 20 --jobs 1 --output output/torus_fixed_rank_width_retake
./theme2026-saku/bin/python experiments/summarize_layout_trace.py \
  output/torus_fixed_rank_width_retake/rows.jsonl
```

#### 完成図の品質

同じ12入力・階層条件を再実行し、0回・1回の全24描画で完成図を計測した。1回のsiftingで幾何交差は全12条件で減り、各条件の減少数は埋め込み交差と一致した。減少数は83〜365件。折れ、接触、重複辺対は全描画で0だった。いずれかの境界を通る元辺の数は10条件で増え、2条件で同じだった。増加は最大24本。X境界を通る元辺数は全12条件で不変、Y境界を通る元辺数は全12条件で増えた。この交換関係の適用範囲は全辺が単位スパンの周期的割当に限る。 [入力別の前後比較](../output/torus_fixed_rank_width_geometry_20261126/width_pairs.csv) · [幾何計測を含む全試行](../output/torus_fixed_rank_width_geometry_20261126/rows.jsonl)

同じ再実行コマンドで幾何計測行も出力する。対応表は次のコマンドで再生成できる。

```sh
./theme2026-saku/bin/python experiments/summarize_fixed_rank_width.py \
  output/torus_fixed_rank_width_retake/rows.jsonl
MPLCONFIGDIR=/tmp/torus-goal-mpl ./theme2026-saku/bin/python experiments/plot_fixed_rank_width.py \
  output/torus_fixed_rank_width_retake/width_pairs.csv \
  output/torus_fixed_rank_width_retake/width_tradeoffs.svg
```

[論文用の比較図（SVG）](../output/torus_fixed_rank_width_geometry_20261126/width_tradeoffs.svg) · [プレビュー（PNG）](../output/torus_fixed_rank_width_geometry_20261126/width_tradeoffs.png)

図の各線は同じ有向辺集合を持つ一つの乱数種を結ぶ。左は1回のsiftingに要した時間。中央と右はそれぞれ0回から1回に変えたときの幾何交差の減少数と、境界を通る元辺の増加数を示す。層幅24では各種で交差の減少数が最大だった。境界通過の増加数は幅4で20〜24本、幅24で0〜4本だった。これらの増分はそれぞれの幅の0回条件を基準にしている。

### 層数を固定した幅のばらつきの比較

8層の周期的な2成分からなる有向グラフを5種（種951〜955）生成した。各グラフの128頂点・384辺を固定し、第2成分の層を1つずらすことで、層幅8・24が交互に現れる割当と、全層が幅16の割当を比較した。両割当とも8層、平均幅16、各層間48辺、階層割当上の折返し48辺、全辺スパン1、ダミー0を確認した。

全20描画が完走した。1回のsifting時間の中央値は交互幅1.954秒、均一幅1.852秒。5組すべてで交互幅が遅かった。実行順は種ごとに交互幅、均一幅の順で固定したため、この時間差には順序の影響も含み得る。どちらの割当でも1回で全5種の幾何交差が減った。1回後の幾何交差は5組中4組で交互幅のほうが少なく、減少数は初期配置の違いにも依存した。0回から1回への変更で境界を通る元辺数は全10条件で同数だった。比較は、独立した成分の相対位置を変えられる周期グラフに限る。 [入力と階層](../output/torus_fixed_rank_width_variation_20261126/inputs.jsonl) · [対応表](../output/torus_fixed_rank_width_variation_20261126/width_pairs.csv) · [全工程のトレース](../output/torus_fixed_rank_width_variation_20261126/layout_stages.csv)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py fixed_rank_width_variation \
  --wall-seconds 20 --jobs 1 --output output/torus_fixed_rank_width_variation_retake
./theme2026-saku/bin/python experiments/summarize_fixed_rank_width.py \
  output/torus_fixed_rank_width_variation_retake/rows.jsonl
```

#### 実行順を逆にした再計測

10条件の投入順を逆にし、各種で均一幅を先に測った。保存した入力列が初回のちょうど逆順であることを照合した。逆順でも5組すべてで交互幅が遅く、各種の時間比（交互幅÷均一幅）の中央値は初回1.055、逆順1.047だった。比の範囲は初回1.029〜1.072、逆順1.027〜1.060。両実行で全描画が完走し、埋め込み交差、幾何交差、折れ、各方向の境界通過辺数は各条件で一致した。同じ5グラフの再計測なので、独立なグラフは5つのままである。 [逆順の入力列](../output/torus_fixed_rank_width_reverse_20261126/inputs.jsonl) · [逆順の対応表](../output/torus_fixed_rank_width_reverse_20261126/width_pairs.csv)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py fixed_rank_width_variation \
  --wall-seconds 20 --jobs 1 --reverse-order --output output/torus_fixed_rank_width_reverse_retake
./theme2026-saku/bin/python experiments/summarize_fixed_rank_width.py \
  output/torus_fixed_rank_width_reverse_retake/rows.jsonl
```

#### 候補採点の実行回数

同じ10条件の既定global siftingを1回実行し、停止判定用コールバックで候補数を数え、プロファイラで帯の採点と辺対交差判定の呼び出しを数えた。全辺が単位スパンなので、各頂点が単独ブロックになる。コールバックの総数からブロックごとの128回を引くと、採点を開始した候補数になる。計数付きと通常実行で、返された層順と巻き数が一致することを各条件で照合した。

| 割当 | 採点候補 | 帯の採点呼び出し | 辺対交差判定の呼び出し |
| --- | ---: | ---: | ---: |
| 交互幅 | 2,560 | 5,376 | 2,259,072 |
| 均一幅 | 2,048 | 4,352 | 2,216,064 |

各割当の数値は5種すべてで一致した。交互幅で候補が25%増えた一方、辺対交差判定の増加は約1.9%だった。この計測で候補探索と交差判定の仕事量が異なる割合で増えることを確認した。計測対象は呼び出し回数で、各処理が壁時計時間差に占める割合は求めていない。 [全条件の計数](../output/torus_fixed_rank_width_variation_20261126/sifting_work.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/profile_fixed_rank_width.py \
  output/torus_fixed_rank_width_variation_20261126/inputs.jsonl
```

#### 層幅から求める候補数の上限

全辺が単位スパンでダミーがないと、各ブロックは頂点1個である。幅 \(w_i\) の層で頂点を1個取り出すと、残る \(w_i-1\) 個の相対順序を保つ挿入位置は \(w_i\) 個ある。既定実装は全体の順序で挿入位置を走査し、同じ層内順序を重複採点しない。そのため1回のsiftingで実際に採点する候補数の上限は \(\sum_i w_i^2\) になる。交差が0のブロックや、途中で交差0の候補に達したブロックでは、採点数が上限より少なくなり得る。

層数を \(L\)、平均幅を \(\bar w\) とすると、この上限は \(L(\bar w^2+\operatorname{Var}(w))\) である。8層・平均幅16では、交互幅の分散は64、均一幅の分散は0で、上限はそれぞれ2,560と2,048。入力マニフェストの層割当から計算し、全10条件の採点数がこの上限に達したことを照合した。この式は単独頂点ブロックの採点候補の上限で、全体順序の走査コスト、巻き数の組合せ、複数層にまたがるダミーブロックの候補数は含まない。 [入力と階層](../output/torus_fixed_rank_width_variation_20261126/inputs.jsonl) · [候補数の計測](../output/torus_fixed_rank_width_variation_20261126/sifting_work_with_bound.jsonl)

#### 複数層にまたがるブロックの候補数

移動するブロックを含む層に現れるブロックの和集合を考える。この集合には移動ブロック自身も含まれる。他のブロックを通過したときに層内順序が変わるのは、そのブロックが和集合に属するときだけである。全体順序の先頭への挿入も含めると、早期終了を適用する前の異なる候補数は和集合の大きさに等しい。同じ相手が複数層に現れても、その相手を全体順序で通過するのは1回である。

保存済みの長辺を含む36入力（504ブロック、うち151ブロックが2層にまたがる）と、100・500頂点の固定階層4入力（2,400ブロック）で確認した。初期層順から各ブロックを動かし、既定の全体順序走査、候補を絞る列挙、層順を差分更新する列挙の3方式が、計38,834候補で同じ挿入位置と層内順序を同じ順に返した。各ブロックの候補数も和集合の大きさと一致した。この照合は列挙器を最後まで実行するもので、採点や早期終了を含む実行時間、完成図の品質は計測していない。 [長辺入力の結果](../output/torus_fixed_rank_sparse_20261126/long_edge_candidate_audit.jsonl) · [100・500頂点の結果](../output/torus_fixed_rank_sparse_20261126/candidate_audit.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/audit_sifting_candidates.py \
  output/torus_validation_20261120/seam_stress/inputs.jsonl
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/audit_sifting_candidates.py \
  output/torus_fixed_rank_sparse_20261126/inputs.jsonl \
  fixed-ring-100-5-2 fixed-ring-100-10-2 fixed-ring-500-5-2 fixed-ring-500-10-2
```

#### 採点・境界処理・座標割当までの照合

6頂点の長辺入力36件で、上限5回のglobal siftingを3方式で実行した。既定の全体順序走査、候補を絞る列挙、層順と採点合計を差分更新する列挙が、全件で同じ層順と巻き数を返した。各方式を同じ境界処理と分割ありBKに通すと、最終埋め込みと座標も全件で一致した。完成図の幾何指標を生データに保存した。階層は入力に与えた固定割当で、分割なしBKのフォールバックや大規模時の時間差はこの照合の範囲外である。 [完成図までの照合結果](../output/torus_fixed_rank_sparse_20261126/long_edge_sifting_equivalence.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/audit_sifting_candidates.py \
  output/torus_validation_20261120/seam_stress/inputs.jsonl --rounds 5
```

#### 既定の分割なしBKとlegacyへの切り替え

同じ36入力を固定階層から既定パイプラインに渡し、3方式とも全件でjointを使い、最終埋め込みと座標が一致した。legacyへの切り替えも確認するため、別の全体比較で切り替えが発生した3入力を選び、ローカル求解で得た階層を保存して共用した。この3入力では、3方式すべてがlegacyへ切り替えたうえで同じ埋め込みと座標を返した。3入力は切り替えの再現を目的に選定しているため、この結果から発生率は推定しない。 [jointの照合](../output/torus_fixed_rank_sparse_20261126/long_edge_default_equivalence.jsonl) · [切り替え確認用の固定階層](../output/torus_fixed_rank_sparse_20261126/fallback_inputs.jsonl) · [legacyの照合](../output/torus_fixed_rank_sparse_20261126/fallback_equivalence.jsonl) · [実行ログ](../output/torus_fixed_rank_sparse_20261126/fallback_equivalence.log)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/audit_sifting_candidates.py \
  output/torus_fixed_rank_sparse_20261126/fallback_inputs.jsonl --rounds 5
```

### 層順と巻き数の全列挙によるsiftingの解品質

3層の隣接層間だけに辺を置き、幅2・層間3辺と幅3・層間5辺をそれぞれ12種（961〜972）生成した。固定階層で全層の順列を列挙し、順序ごとに各帯の辺の整数巻き数を全列挙した。辺対を持ち上げたときの端点高の差を有理数で計算し、その間に厳密に入る整数の個数で交差を数えた。各帯の巻き数を独立に選べるため、帯ごとの最小値の和がその層順における最小値になる。最小値を達成する層順と巻き数を保存し、実装の交差計数でも同じ値になることを照合した。

既定siftingは0回条件より24件中19件で交差を減らした。1回上限と5回上限の交差数は全件で同数だった。巻き数を−1〜1に制限した全列挙の最適値と、5回上限の結果は幅2の12件すべて、幅3の12件中11件で一致した。幅3・種962では6交差から2交差まで減ったが、全列挙には0交差の配置があった。巻き数を−2〜2まで広げても全24件で最適値は変わらなかった。0交差の証人がある種962は、巻き数の範囲を問わずsiftingの最適性への反例となる。ほかの正の最小値は列挙範囲内での結果であり、この評価は固定階層・ダミーなしの埋め込み交差に限る。 [入力・証人・比較結果](../output/torus_sifting_winding_oracle_20261126/rows.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/oracle_sifting_winding.py
```

#### 反例の完成図

幅3・種962のsifting結果と全列挙の証人を、同じ分割ありBKで座標化した。境界最適化は適用せず、比較する層順と巻き数をそのまま座標割当に渡した。完成図の幾何交差も2対0だった。境界を通る元辺は両者9本、折れは両者0、中心線総延長は25.10対22.02描画単位だった。交差0の証人は、この描画条件では境界通過数を増やさずに交差を除去できる例になった。 [比較図（SVG）](../output/torus_sifting_winding_oracle_20261126/counterexample.svg) · [比較図（PNG）](../output/torus_sifting_winding_oracle_20261126/counterexample.png) · [幾何計測](../output/torus_sifting_winding_oracle_20261126/counterexample_geometry.jsonl)

```sh
PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/plot_sifting_counterexample.py \
  output/torus_sifting_winding_oracle_20261126/rows.jsonl \
  output/torus_sifting_winding_oracle_20261126/counterexample_retake.svg
```

#### 初期層順の変更と反復上限の比較

既定の初期層順での探索に、同じ層内で頂点を並べ替えた初期層順を3つ追加した。候補は既定順を除いた層順の組合せから、入力種に100,000を加えた別の乱数種で重複なしに選んだ。巻き数の初期値はすべて0とし、各開始順で最大5回のsiftingを行った。対照には、既定順のまま上限を5回から20回へ増やす条件を使った。追試は各幅12件とし、元の24入力および追試の他入力と同一の有向辺集合を除いた。この照合は頂点名を置換した同型性までは検査していない。

複数の初期層順から最良を選ぶと、元の24件中1件、追試の24件中4件で交差が減った。改善した5件はすべて幅3で、各集合の全24件が巻き数−1〜1での列挙最適値に達した。既定順の上限を20回に増やした条件では、両集合の全48件で交差数が変わらなかった。種962では代替3順の結果が0・1・0交差だった。停止判定の呼び出し回数の比（4開始順の合計÷既定順のみ）の中央値は元の集合で4.60倍、追試で4.08倍だった。この計数にはブロックと採点候補の両方の判定が含まれ、実行時間の倍率は表さない。結果は小規模な固定階層の埋め込み交差に限る。 [元の集合](../output/torus_sifting_winding_oracle_20261126/restarts_original.jsonl) · [重複を除いた追試](../output/torus_sifting_winding_oracle_20261126/restarts_holdout_distinct.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/oracle_sifting_winding.py --restarts
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/oracle_sifting_winding.py --restarts --holdout
```

#### 初期層順を変更した完成図の比較

固定階層を共有する48入力で、既定の初期層順による描画と、4つの開始順から埋め込み交差が最小のものを選んだ描画を比較した。同数の場合は試行順で先の候補を選び、既定順を優先した。両条件とも境界処理と分割なしBKを使い、全件がjointで完走した。幾何交差の値は埋め込み交差と全件で一致し、改善した5件では完成図でも1〜2交差減った。その5件のうち3件で境界を通る元辺が1〜2本減り、残る2件では同数だった。折れは全描画で0だった。種962では幾何交差が2から0、境界を通る元辺が7本から5本になった。この結果はダミーなしの小規模条件での比較で、初期順の追加が長辺を含む場合にも有効かは別の検証を要する。 [元の集合の幾何計測](../output/torus_sifting_winding_oracle_20261126/restarts_geometry_original.jsonl) · [追試の幾何計測](../output/torus_sifting_winding_oracle_20261126/restarts_geometry_holdout_distinct.jsonl)

```sh
for cohort in original holdout_distinct
do
  PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
    ./theme2026-saku/bin/python experiments/evaluate_sifting_restarts.py \
    "output/torus_sifting_winding_oracle_20261126/restarts_$cohort.jsonl"
done
```

#### 長辺を含む入力での初期層順の変更

固定4層の長辺入力36件（各6頂点、ダミー10〜14個）で、初期層順を3つ追加した。元の順序を含む4候補を最大5回のsiftingで評価し、埋め込み交差が最小の候補を選んだ。同数なら先に試した候補を優先した。既定順と選択順を既定パイプラインに渡すと全件がjointで完走し、埋め込み交差と完成図の幾何交差は全件で一致した。

幾何交差は17件で1〜3減り、19件は既定順のままだった。改善した17件では、折れが5件で減り、3件で同数、9件で増えた。境界を通る元辺は3件で減り、8件で同数、6件で増えた。停止判定の呼び出し回数の比は中央値4.28倍だった。初期層順の追加はこの条件でも交差を減らす場合があったが、交差だけで選ぶと折れや境界通過が増える場合もあった。入力は長辺の境界処理を検査するために生成した固定階層の6頂点グラフである。 [試行ごとの候補と完成図の計測](../output/torus_sifting_winding_oracle_20261126/restarts_long_edges.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/evaluate_sifting_restarts.py \
  output/torus_validation_20261120/seam_stress/inputs.jsonl --long-edges
```

#### 折れと境界通過を増やさない候補の選択

長辺入力36件で、各4開始順の全144描画がjointで完走した。既定順の描画に比べて折れと境界を通る元辺の両方が増えない候補に絞り、幾何交差が最小の候補を選んだ。同数では既定順を含め、先に試した候補を優先した。

交差だけで選んだ場合に改善した17件のうち、制約付きでも改善したのは6件だった。5件で同じ1交差減少を維持し、1件では交差の減少幅が3から1に縮まった。残る11件では、試した4候補の中に両制約を満たしながら交差を減らす配置がなかった。この内訳は選んだ開始順の集合での結果であり、他の層順や巻き数まで探索した場合の改善可能性は示さない。 [全144描画と選択結果](../output/torus_sifting_winding_oracle_20261126/restarts_long_edges_all_drawings.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/evaluate_sifting_restarts.py \
  output/torus_validation_20261120/seam_stress/inputs.jsonl --long-edges --all-drawings
```

#### 別の長辺グラフによる追試

固定4層で12頂点すべてを通る有向閉路に、2層先への辺8本と3層先への辺4本を追加した。種1201〜1224で辺を選び、24入力の有向辺集合がすべて異なることを確認した。各入力は24辺、ダミー16個、SCCは1つ。先の6頂点条件と同じ4開始順と候補選択規則を用いた。

全96描画がjointで完走し、埋め込み交差と完成図の幾何交差が全候補で一致した。交差だけで選ぶと24入力中15件で1〜7交差減った。折れと境界を通る元辺を両方増やさない制約を加えると、9件で交差が減り、減少数はいずれも制約なしと同じだった。残る6件では4候補に制約を満たす改善案がなかった。停止判定回数の比は中央値4.41倍だった。有向閉路を共有し長辺数を揃えた生成条件での追試であり、一般のグラフへの改善率は推定しない。 [追試の入力](../output/torus_sifting_winding_oracle_20261126/restarts_long_edge_holdout_inputs.jsonl) · [全96描画と選択結果](../output/torus_sifting_winding_oracle_20261126/restarts_long_edge_holdout.jsonl)

```sh
./theme2026-saku/bin/python experiments/generate_long_edge_restart_holdout.py > /tmp/torus_restart_holdout_inputs.jsonl
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/evaluate_sifting_restarts.py \
  /tmp/torus_restart_holdout_inputs.jsonl --long-edges --all-drawings
```

#### 初期層順を追加する時間コスト

12頂点の追試24件を単独実行し、各開始順のsiftingを停止判定コールバックなしで3回測った。測定順は正順、逆順、正順とし、各開始順で3回の中央値を取った。既定順だけの時間の入力間中央値は0.054秒。4開始順の時間を入力ごとに合計した中央値は0.232秒だった。対応する時間比は中央値4.38倍、範囲3.22〜7.44倍で、停止判定回数の比の中央値4.41倍と近かった。候補ごとの交差数と完成図の指標は先の追試と一致した。時間には固定階層の準備、境界処理、座標割当、幾何計測を含めていない。 [全測定と各開始順の時間](../output/torus_sifting_winding_oracle_20261126/restarts_long_edge_holdout_timing.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/evaluate_sifting_restarts.py \
  output/torus_sifting_winding_oracle_20261126/restarts_long_edge_holdout_inputs.jsonl \
  --long-edges --all-drawings --timing
```

#### 観測方向を持つ公開ネットワークでの追試

公開データの追試から12頂点の全12入力を使った。Krackhardtの助言・友情、SocioPatternsの高校友情、欧州研究機関メールの3元ネットワークに由来し、保存済みのdot比較と頂点・有向辺が入力ごとに一致することを確認した。各入力で既定の階層割当を1回実行し、得られた階層・折返し辺を全開始順で共有した。Gurobi呼び出しの上限は2秒、各実験工程の壁時計上限は40秒、並行度は2。抽出した近傍には重なりがある。

階層割当は12件すべてで完了した。4候補の探索と描画は助言の高密度2件で40秒に達し、残る10件の全40候補が完走した。うち2候補ではlegacyへの切り替えがあった。埋め込み交差だけで選ぶと、完走10件中6件で完成図の幾何交差が減った。折れと境界を通る元辺を増やさない候補に絞ると、4件で幾何交差が減った。どちらの選択規則でも、対応するdot描画の幾何交差は完走10件すべてで少なかった。打ち切り2件の交差は補完していない。保存ログには初回ランナーが同時に実行した補助の杉山型対照も含まれるが、この比較では使用していない。 [入力](../output/torus_public_restarts_20261126/inputs.jsonl) · [階層と候補ごとの結果](../output/torus_public_restarts_20261126/rows.jsonl) · [実行ログ](../output/torus_public_restarts_20261126/run.log)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py public_restart_holdout \
  --public output/torus_holdout_20261126/sources --solver-seconds 2 --wall-seconds 40 \
  --jobs 2 --output output/torus_public_restarts_retake
```

#### 公開データの打ち切り2件の再実行

打ち切られた2入力に保存済みの階層と折返し辺を与え、各候補のsifting結果を座標までの処理で再利用した。境界処理が層順や巻き数を書き換えても、legacy再試行が元の結果を受け取れるよう、呼び出しごとに複製を渡した。別の公開入力 `krackhardt-friendship-1-12` では、既定順のlegacyへの切り替えを含め、全4候補の幾何計測と選択結果が元の記録と一致した。

単独実行で両入力の全8候補が40秒以内に完走した。入力0は284交差の既定順が選ばれ、入力1は299から260交差に減った。入力1の選択結果は折れと境界を通る元辺の非増加も満たした。保存済みのdotはそれぞれ219・177交差で、いずれも少なかった。初回の並行度2の試行と条件が異なるため、約30秒で完走した再実行から再利用単独の速度効果は求めていない。 [再実行の入力](../output/torus_public_restarts_20261126/timeout_replay_inputs.jsonl) · [再実行の全候補](../output/torus_public_restarts_20261126/timeout_replay.jsonl) · [legacyを含む照合](../output/torus_public_restarts_20261126/reuse_control.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-goal-mpl \
  ./theme2026-saku/bin/python experiments/evaluate_sifting_restarts.py \
  output/torus_public_restarts_20261126/timeout_replay_inputs.jsonl \
  --long-edges --all-drawings --reuse-sifting --wall-seconds 40
```

単独実行で再利用しない条件も計測した。両入力の候補、選択、描画指標は再利用ありと一致した。観測時間は入力0で61.73秒から29.99秒、入力1で59.54秒から29.43秒。両条件とも完走した実測値で、測定は各1回、同じ入力での観測に限る。 [同一入力の時間比較](../output/torus_public_restarts_20261126/reuse_comparison.jsonl)

### 層内方向の巻き数だけを変えた対応比較

全体比較で使った48入力に対し、各入力でローカルライセンスの既定階層モデルを1回実行し、同じ層と折返し辺を両描画に渡した。両条件で既定global sifting、回転・UNWIND・切れ目最適化なし、分割ありBKを用いた。固定側はsiftingの採点に巻き数の変更候補を渡さず、初期値0を保つ。自由側では既定どおり巻き数を選ぶ。階層方向の折返しは両方で残した。先行の補助円筒比較では複数の工程を変更していたため、この対応比較を巻き数の効果の根拠とする。

両方式が48入力すべてで完走した。幾何交差と埋め込み交差は全96描画で一致し、固定側では非ゼロ巻き数とY境界を通る元辺がともに0だった。自由側から固定側を引いた差を示す。

| 指標 | 減少 | 同数 | 増加 | 差の中央値 |
| --- | ---: | ---: | ---: | ---: |
| 幾何交差 | 44 | 2 | 2 | −6 |
| 折れ | 6 | 3 | 39 | +4.5 |
| いずれかの境界を通る元辺 | 0 | 0 | 48 | +9 |

巻き数の自由度により交差は多くの入力で減った一方、境界通過は増えた。この比較は境界の最適化を適用する前の寄与を調べるための固定条件であり、既定パイプライン全体と円筒の一般的な優劣は表さない。初回は計測器が描画APIの返り値を取り違えたため評価を修正し、全件を再実行した。 [照合済みの入力](../output/torus_winding_ablation_checked_20261126/inputs.jsonl) · [全試行と求解トレース](../output/torus_winding_ablation_checked_20261126/rows.jsonl) · [実行ログ](../output/torus_winding_ablation_checked_20261126/run.log)

```sh
PYTHONHASHSEED=0 ./theme2026-saku/bin/python experiments/run_torus_validation.py winding_ablation \
  --previous output/torus_goal_20261126/framework --solver-seconds 4 --wall-seconds 20 \
  --jobs 2 --output output/torus_winding_ablation_retake
```

### レイヤー数探索の規模・乱数種を拡張した追試

12〜100頂点の100入力について、現行二分探索の正しさ、固定層数法との対応差、ローカルGurobiでの時間切れと完了率を計測した。 [実験結果・生データ・再実行手順](torus_layer_search_20261126.md)

### 長辺36入力でのjoint DPの最適性照合

切れ目のみのDPで使った6頂点・8辺・固定4層の有向グラフ36件を再利用した。以前と同じ乱数による層順・巻き数と、境界処理を無効化した現行global sifting直後の埋め込みを、各入力で別々に検証した。全列挙は各入力で240〜600通りの切れ目を調べ、各層間でダミー同士の線分の上下境界通過を0にできる共通巻き補正の中で、全通過線分数を最小化した。

乱数埋め込みは14件で実行可能、22件で実行不能。global sifting直後は36件すべてで実行可能だった。実行可能な計50条件でjoint DPと全列挙の差は0本で、埋め込み交差数も処理前後で保存された。実行不能な22条件では解なしの判定が一致した。同じ36グラフを二つの埋め込みで検証しており、独立のグラフ数は36件。 [全72条件](../output/torus_joint_stress_oracle_20261126/rows.jsonl)

```sh
PYTHONHASHSEED=0 PYTHONPATH=src ./theme2026-saku/bin/python experiments/check_joint_seam_stress.py \
  output/torus_validation_20261120/seam_stress/inputs.jsonl
```
