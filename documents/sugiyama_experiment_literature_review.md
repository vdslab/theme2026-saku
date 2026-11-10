# 階層グラフ描画における実験評価の文献調査

## 杉山フレームワークの各工程と全体評価

- 調査日: 2026-09-29
- 対象: 杉山フレームワーク、その平面・放射・円環・トーラス系の拡張
- 目的: 各論文が「何を最適化し、どの入力で、何と比較し、何を測ったか」を整理し、本プロジェクトの実験計画へ接続する
- 選定方針: 各工程の代表的な厳密法・ヒューリスティック・実験研究と、全体比較・ユーザ研究を優先した。網羅的な書誌ではなく、実験設計を再利用できる論文の重点調査である

## 1. 要約

杉山フレームワークの実験は、概ね次の三層に分かれる。

1. **工程単体の評価**: 逆向き辺数、ダミー頂点数、交差数、幅、辺長など、その工程の目的関数と実行時間を測る。
2. **下流まで含めた評価**: 例えば階層割当を変えた後に、ダミー頂点数、交差数、面積、曲がり数まで測る。
3. **描画全体の評価**: 複数の工程を含む完成描画について、交差、曲がり、面積、実行時間、さらにユーザ課題の正答率や選好を測る。

文献から得られる最も重要な設計原則は以下である。

- ある工程の局所目的だけでは描画品質を説明できない。例えば、逆向き辺を最小化しても階層間距離や交差数が良くなるとは限らない。
- 交差削減のような NP 困難な工程では、**小規模問題で厳密解とのギャップを測り、大規模問題で品質と時間のスケーリングを測る**二段構成が標準的である。
- 階層割当では、ダミー頂点数だけでなく、幅・高さ・面積・辺密度・実行時間を併記する研究が多い。
- 座標割当では、幅と水平辺長の一方だけを最適化すると他方が悪化するため、二目的のトレードオフとして評価するのが適切である。
- 完成描画の評価は、交差数だけでなく、曲がり数、辺長、面積、アスペクト比、実行時間を含めるべきである。人による読み取りを主張するなら、ユーザ実験が必要である。
- 公開ベンチマーク、全パラメータ、乱数 seed、生データ、タイムアウト、失敗件数を残すことが再現性の基本である。

本プロジェクトの既存評価は、同一入力を使う対応比較、100 グラフでのサイズ別集計、勝ち・同率・負け、paired bootstrap 信頼区間、proper hierarchy 上での交差の定義、実行時間の工程別分解をすでに備えている。一方で、入力が主に Watts--Strogatz グラフ、平均次数がほぼ固定、規模が交差比較では 50 頂点までである。次に優先すべきなのは、**小規模厳密解との照合、グラフ族・密度・循環性の拡張、工程間のアブレーション、公開データセットでの外的妥当性**である。

## 2. 杉山フレームワークと評価対象

典型的な処理は次の通りである。

```text
有向グラフ
  -> (1) サイクル除去
  -> (2) 階層割当
  -> (3) 長辺の正規化・ダミー頂点挿入
  -> (4) 階層内順序付け・交差削減
  -> (5) 座標割当
  -> (6) エッジ配線・ポート処理
  -> 完成描画
```

[Sugiyama, Tagawa, and Toda (1981)](https://doi.org/10.1109/TSMC.1981.4308636) はこの分解の基礎を与え、[Gansner et al. (1993)](https://doi.org/10.1109/32.221135) は network simplex による階層割当、反復的な交差削減、補助グラフによる座標最適化、spline 配線を組み合わせた実用的パイプラインを示した。前者は、8 条件それぞれ 100 件、計 800 件のランダム階層で交差削減を厳密最小値と比較し、5 件の実階層でも交差数と CPU 時間を測っている。したがって「完成例だけ」の研究ではない。ただし、現代的な公開ベンチマーク、seed、分散・信頼区間はなく、後年の研究ほど再現可能な実験設計ではない。後者は、広い統制ベンチマークよりも実装方式、図例、個別の処理時間を中心に報告している。

以下では、再現可能性の程度を便宜上、次のように表す。

- **A**: 入力、規模、反復、比較法、指標が明確で、厳密解または公開ベンチマークを含む
- **B**: 統制された計算実験があるが、入力または統計報告に制限がある
- **C**: 少数例・定性的比較・予備実験が中心

## 3. 論文マップ

| 工程 | 論文 | 主な比較 | 入力と規模 | 主な指標 | 証拠 |
|---|---|---|---|---|---|
| 原典・交差削減・座標 | Sugiyama et al. (1981) | BC の phase 1/2 と厳密最小、QP と PR | ランダム階層 8 条件 × 100、実階層 5 件 | 交差、改善率、CPU 時間 | B |
| サイクル除去 | Eades, Lin, Smyth (1993) | feedback arc set ヒューリスティック | 主に理論解析 | 反転辺数、計算量 | C |
| 階層割当 | Nikolov, Tarassov (2006) | longest path、Gansner、promotion | Rome 5,911、AT&T 1,277、GDorg 909、ランダム 3,932 | ダミー数、幅、高さ、面積、辺密度、時間 | A |
| 幅制約階層化 | Nikolov, Tarassov, Branke (2005) | 複数の最小幅ヒューリスティック | 約 6,000 DAG | 幅、高さ、ダミー数、辺密度、時間 | A |
| 円環階層割当 | Bachmaier et al. (2008) | BFS、MST、force-based、厳密解 | 小規模 4--18、大規模 50--500 頂点 | 円環 span、最適値との差、時間 | A |
| 正規化 | Eiglsperger et al. (2005) | VCG、Dot、従来正規化、新方式 | 合成 40--160、ランダム 100--3,000 | dummy 数、交差、反復時間、メモリ | A |
| 2 層交差削減 | Jünger, Mutzel (1997) | exact、barycenter、median ほか | 密度 sweep、疎グラフ scaling | 交差数、最適値比、時間 | A |
| 多層交差削減 | Bachmaier et al. (2011) | median/barycenter/sifting の局所・大域版 | ランダム 910、1,000--10,000 頂点 | 交差削減比、type-2 conflict、時間 | A |
| 多層交差削減 | Chimani et al. (2011) | ILP、SDP、ヒューリスティック | 合成、Rome 11,528、North 1,158 | 上下界、最適性、時間、gap | A |
| 座標割当 | Brandes, Köpf (2002) | 既存配置法との図例比較 | 少数の固定階層・順序 | 幅、辺長、長辺の直線性 | C |
| 座標割当 | Jünger, Mutzel, Spisla (2018) | MCF、Gansner、LP、BJL、BK | AT&T 1,277 | 最小幅比、最小辺長比、時間 | A |
| ポート・配線 | KIELER/ KLay Layered (2014) | ポート制約処理法 | 実例と生成グラフ | 交差、bend、時間 | B |
| 全体 | Di Battista et al. (2000) | 4 種の DAG 描画法 | AT&T 1,277、ランダム PERT | 面積、交差、bend、辺長等 | A |
| 全体＋ユーザ | Lionakis et al. (2022) | Path-Based Framework、OGDF Sugiyama | ランダム、GD.org、72 人 | 交差、bend、面積、時間、正答率、選好 | A |
| 円環描画 | Bachmaier et al. (2012) | cyclic と通常の階層描画 | ランダム最大 500 頂点 | bend、幅、外側 segment 移動量 | B |
| 放射描画 | Bachmaier, Forster (2007) | 放射型と水平型 | 二部グラフ 5,000 件、座標割当 50,000 頂点 | 交差数、round、時間 | B |

## 4. 工程別の実験

### 4.1 サイクル除去

#### Eades, Lin, and Smyth (1993)

[A Fast and Effective Heuristic for the Feedback Arc Set Problem](https://doi.org/10.1016/0020-0190(93)90079-O) は、辺を反転して DAG を得る feedback arc set 問題に対する線形時間ヒューリスティックと理論的な保証を示す。杉山法のサイクル除去として広く参照されるが、現代的な意味での大規模な描画ベンチマーク、下流工程の交差や面積の測定は中心ではない。

この工程の文献上の弱点は、**反転辺数の小ささと、完成描画の良さが同一ではない**点である。したがって、サイクル除去の評価は次の二段に分けるべきである。

- 局所指標: 反転辺数・重み、feedback arc set の既知下界または最適値との gap、時間
- 下流指標: 階層 span、dummy 数、交差数、bend 数、描画高さ

大規模 FAS 自体の現代的な評価設計については、[Koehler et al. (2024), Finding small feedback arc sets on large graphs](https://doi.org/10.1016/j.cor.2024.106724) が、実ネットワーク、縮約、分割統治、既知解の改善率を扱う。ただし、これは描画パイプラインの評価ではなく、サイクル除去単体の補助資料として位置づけるべきである。

**本プロジェクトへの示唆**: 通常の杉山法との比較で cycle-removal 法を変える場合、反転辺数だけで優劣を決めず、同じ後段を通した交差数まで追う。トーラス法は辺反転を不要にすること自体が利点なので、「逆転を避けた辺数」と「その代わりに基本領域境界を跨ぐ辺数」を別々に報告する。

### 4.2 階層割当

#### Nikolov and Tarassov (2006): promotion による階層化

[Graph Layering by Promotion of Nodes](https://doi.org/10.1016/j.dam.2005.05.023) は、longest-path layering を初期解とし、頂点を上位層へ promotion して総 edge span、したがって dummy 数を減らす。

実験設計は次の通りである。

- 比較: longest path (LPath)、Gansner の最適化 (Gans)、LPath + promotion (LPath+PL)
- 公開系データ: Rome 5,911 DAG、AT&T 1,277 DAG、GDorg 909 DAG
- 大規模生成データ: 3,932 DAG、100--809 頂点、概ね `m <= 3n`
- 集計: Rome は頂点数 5 刻み、生成 DAG は 10 刻みの群にして平均を描画
- 指標: 正規化 dummy 数、edge density、幅、高さ、面積、アスペクト比、実行時間
- レイアウト占有面積について、dummy 頂点の幅を 0 とみなす場合と 1 とみなす場合の両方を評価
- 大規模入力では promotion の反復を 80 回に制限

重要なのは、目的関数である dummy 数だけでなく、最終的な幅・高さ・面積まで追っている点である。`LPath+PL` は最小 dummy 数に近く、edge density と面積でも良い場合が多かった。

#### Nikolov, Tarassov, and Branke (2005): 最小幅

[In Search for Efficient Heuristics for Minimum-Width Graph Layering with Consideration of Dummy Nodes](https://doi.org/10.1145/1064546.1180618) は、約 6,000 グラフを用いる広いパラメータ研究である。layering width、dummy を簡略化した幅、高さ、正規化 dummy 数、正規化 edge density、実行時間を併記する。単一の「幅」だけでなく、辺を収容する dummy が実際の幅を増やすことを評価へ組み込む点が重要である。

#### Bachmaier et al. (2008): cyclic leveling

[Cyclic Leveling of Directed Graphs](https://www.infosun.fim.uni-passau.de/~chris/down/CyclicLeveling.pdf) は、階層番号を円環上で扱うという意味で本研究に最も近い。

- 比較: BFS、MST 系、force-based (SE) ヒューリスティック
- 小規模: `n=4,...,18`、`m=2n`。branch-and-bound の最適値と比較
- 大規模: `n=50,100,...,500`、各サイズ 10 グラフ、`m=5n`
- 層数 `k` と各層容量 `omega` は概ね `sqrt(2n)`、総配置容量を約 `2n` に設定
- 各ヒューリスティックは `min(n,30)` 個の開始解を試す
- 指標: cyclic span と実行時間。小規模では最適値との差も測定

force-based 法は MST 初期化との組み合わせで良い span を得る一方、多点開始による改善は実行時間とほぼ比例する。ここから、トーラス階層割当でも **単一開始の時間** と **best-of-r starts の品質**を分けて報告すべきだと分かる。

**本プロジェクトへの示唆**: `torus_edges` だけでなく、円環 span の総和・二乗和、層占有の最大値と分散、dummy 数、時間、厳密解 gap を測る。小規模では全探索または ILP/IQP を基準にし、大規模では heuristic の scaling を測る。

### 4.3 正規化とダミー頂点

#### Eiglsperger, Siebenhaller, and Kaufmann (2005)

[An Efficient Implementation of Sugiyama's Algorithm for Layered Graph Drawing](https://www.maths.tcd.ie/EMIS/journals/JGAA/accepted/2005/EiglspergerSiebenhallerKaufmann2005.9.3.pdf) は、長辺を全層の dummy 列へ単純展開するとグラフが巨大化する問題に対し、疎な正規化構造を提案する。

- 比較: VCG、Dot、traditional normalization、提案する new normalization
- 合成長辺グラフ: 半数の頂点を垂直列、半数を水平列とし、多数の長辺を作る。`n=40,...,160`
- ランダム連結グラフ: `m=2.5n`、`n=100,...,3000`
- 共通設定: network simplex layering、交差削減 10 passes
- 指標: 交差削減の 1 反復当たり時間、dummy 数、交差数、メモリ不足の有無

提案方式は 3,000 頂点まで処理し、従来方式がメモリ不足になる領域でも動作した。交差数を悪化させずに時間・空間を削減できるかを測る、実装研究の良い例である。

**本プロジェクトへの示唆**: 元グラフの `(n,m)` だけでなく、正規化後の `(n',m')`、dummy 数、基本領域を跨ぐ長辺の分割数を必ず保存する。交差削減の時間は `n` より `n'` に強く依存する可能性があるため、両方に対する scaling を描く。

### 4.4 階層内順序付け・交差削減

#### Jünger and Mutzel (1997): 二層問題の厳密解とヒューリスティック

[2-Layer Straightline Crossing Minimization: Performance of Exact and Heuristic Algorithms](https://doi.org/10.7155/jgaa.00001) は、工程単体の実験設計として特に完成度が高い。

- 比較: branch-and-cut、barycenter、median、stochastic、greedy-insert、greedy-switch、split、assign
- 一側固定: 各側 20 頂点、密度 0.1--0.9、各密度 100 instance
- 疎グラフ scaling: 各側 10--100 頂点、平均次数 2、各サイズ 10 instance
- 二側可変: 各側 10 頂点の密度 sweep。1 開始と 10 ランダム開始を比較
- 指標: 交差数、最適値に対する相対差、実行時間

疎な一側固定問題では barycenter は高速で最適値に近いが、二側を交互に最適化しても全体最適から遠いことがある。複数開始は品質を改善する。ここで使われる「小規模 exact anchor + 大規模 scaling」という構成は、radial sifting の評価にも直接使える。

#### Martí and Laguna (2003): metaheuristics

[Heuristics and Meta-Heuristics for 2-Layer Straight Line Crossing Minimization](https://doi.org/10.1016/S0166-218X(02)00397-9) は 12 種のヒューリスティックと 2 種のメタヒューリスティックを広く比較する。単純ヒューリスティックは特に疎グラフで性能が落ち、dense では tabu search、sparse では GRASP が良いという、密度ごとの層別評価の必要性を示す。

#### Bachmaier et al. (2011): global k-level crossing reduction

[Global k-Level Crossing Reduction](https://doi.org/10.7155/jgaa.00242) は、局所的な level-by-level 法と global sifting を比較する。

- 8 法: barycenter、median、sifting とそれらの反復・global 版
- 910 ランダムグラフ
- 1,000--10,000 頂点、100 頂点刻み、各サイズ 10 instance
- proper hierarchy の約 75% を dummy 頂点とする長辺の多い条件
- level-by-level は上下 10 sweeps、global 法は 10 rounds
- 指標: 初期値に対する交差比、実行時間、type-2 conflict
- ランダム初期化を含む方式は各 instance を 2 回実行

global sifting は交差をさらに約 5--10% 改善し、type-2 conflict を避ける一方、二次的な実行時間を要する。品質だけでなく、特定種類の交差と計算量を分けている点が参考になる。

#### Chimani et al. (2011): ILP と SDP

[An SDP Approach to Multi-level Crossing Minimization](https://tcs.uos.de/_media/pubs/alnx11_preprint_mlcm_sdp_pdf.pdf) は、厳密 ILP と半正定値緩和を比較する。

- 合成: 2--20 層、各層 8--25 頂点、密度 0.1--0.9、各組合せ 10 instance
- 実データ: Rome 11,528、North 1,158
- 階層割当: GKNV と upward-planarization layering の双方
- ILP timeout: 合成では 1 時間、実データでは問題規模に応じ 4 または 16 時間
- 指標: 解けた件数、上界・下界、optimality gap、交差数、実行時間、ヒューリスティックの最適値差

疎な問題では ILP が強く、密になると SDP がより頑健だった。さらに、交差削減器だけでなく、入力となる layering を変えている。これは、**交差削減の結果が前段の階層割当に依存する**ことを実験要因として扱う好例である。

**本プロジェクトへの示唆**: 共通の階層割当と dummy 展開を固定して `barycenter`, `radial_sifting`, `radial_sifting_guard` を比較する現在の設計は妥当である。追加すべきなのは、(a) 小規模 exact gap、(b) 密度別・循環性別、(c) 1/5/10 starts、(d) 局所交差と境界跨ぎに関係する交差の内訳、(e) 品質対時間曲線である。

### 4.5 座標割当

#### Brandes and Köpf (2002)

[Fast and Simple Horizontal Coordinate Assignment](https://doi.org/10.1007/3-540-45848-4_3) は、短い辺、均衡した配置、長辺の垂直性を狙う線形時間法である。固定した階層と順序に対し、daVinci、AGD の既存法、提案法を図で比較する。論文自身が preliminary computational experiments と位置づけており、大規模な数値ベンチマークではない。後年、特定条件の不具合に対する[訂正](https://arxiv.org/abs/2008.01252)があるため、実装比較では訂正版を使う必要がある。

#### Jünger, Mutzel, and Spisla (2018)

[A Flow Formulation for Horizontal Coordinate Assignment with Prescribed Width](https://arxiv.org/abs/1806.06617) は、幅制約下で水平辺長を最小化する min-cost flow 法を評価する。

- 比較: MCF、Gansner、LP、BJL、Brandes--Köpf
- 入力: AT&T の 1,277 グラフ、10--100 頂点
- 共通条件: 固定した階層・順序、長辺の内部 segment の垂直性を維持
- 指標: 最小可能幅に対する幅の比、最小可能水平辺長に対する辺長の比、実行時間
- 可視化: 分布を箱ひげで示し、95% 範囲と外れ値を区別

MCF は最小幅を保ちながら、平均水平辺長が下界より約 2.2% 長い程度だった。一方 Gansner 法は辺長に強いが幅が最小より平均約 8.9% 大きかった。平均実行時間は数 ms の範囲であり、品質のトレードオフを実用コストと共に示している。

**本プロジェクトへの示唆**: トーラス座標割当も、半径または基本領域幅だけを単独評価せず、円周方向辺長、層間辺長、最小角度、節点間隔、境界での連続性、bend 数と併記する。座標割当の比較では前段の階層と順序を完全に固定する。

### 4.6 エッジ配線・ポート制約

[Drawing Layered Graphs with Port Constraints](https://doi.org/10.1016/j.jvlc.2013.11.005) は、KLay Layered におけるポート順序・辺方向制約を、交差削減と配線へ統合する。評価指標は交差数、bend 数、実行時間である。ポート制約を満たすこと自体を可否条件とし、その上で美的指標と時間を比較する。

[Layered Drawing of Undirected Graphs with Generalized Port Constraints](https://arxiv.org/abs/2008.10583) は、実データと統制した生成データを用い、既存 KIELER 法に対し交差を 10--30% 程度減らしつつ、bend と時間の変化を測る。制約充足法では、成功率、違反数、交差・bend、時間を分離して報告する設計が有効である。

トーラス描画では、基本領域境界で同一辺の入口と出口が幾何的に連続しているか、矢印方向が一貫するか、重複 segment がないかを追加の可否条件とするべきである。

## 5. フレームワーク全体の実験

### 5.1 Di Battista et al. (2000): DAG 描画法の総合比較

[Drawing Directed Acyclic Graphs: An Experimental Study](https://doi.org/10.1142/S0218195900000358) は、2 種の layered 法と 2 種の grid 法を比較する。

- データ: 1,277 件の AT&T/Bell 系 DAG と、PERT 型の生成 DAG
- 指標: 面積、交差、bend、辺長、アスペクト比など
- 多数の図表で、規模・グラフ型による傾向を分ける

結論は「全指標で常に勝つ単一アルゴリズムはない」というものだった。完成描画の比較では、多目的ベクトルと trade-off を示す必要がある。

### 5.2 Lionakis, Kritikakis, and Tollis (2022): 計算実験とユーザ実験

[Experiments and a User Study for Hierarchical Drawings of Graphs](https://arxiv.org/abs/2209.04522) は、拡張 Path-Based Framework (PBF) と OGDF の Sugiyama 実装を比較する。

計算実験:

- OGDF: longest-path ranking、barycenter、15 repeats から最良を選択、FastHierarchyLayout
- データ: ランダム DAG 20 件、および graphdrawing.org の 10--100 頂点ベンチマーク
- 指標: 交差、bend、distinct-x 幅、distinct-y 高さ、bounding area、実行時間
- 傾向: PBF は面積・bend・時間で優れ、OGDF は特に疎グラフの交差数で優れる

ユーザ実験:

- 参加者 72 名。グラフに習熟した開発者・研究者と上級学生
- 20・50 頂点を課題ベース比較に、100 頂点を満足度・容易さ・選好の直接比較に使用。平均次数は約 1.6
- 課題: 到達可能性、最短路長、長さ 3 以下の経路の有無、後続頂点集合
- 各方式 16 問、合計 32 問。提示順をランダム化
- 指標: 正答率、「分からない」、全体選好

PBF の正答率は 90% 超、OGDF は 84% 超で、PBF を選好した参加者は 58.3% だった。ただし選好の exact 95% 信頼区間は 48--72% で 50% を含み、決定的な選好差とは言いにくい。また時間制限を設けなかったため、課題完了時間の比較はない。このように、平均値だけでなく信頼区間と実験制約まで読む必要がある。

### 5.3 円環・放射型への拡張

[Drawing Recurrent Hierarchies](https://doi.org/10.7155/jgaa.00254) は、周期的な座標割当を通常の階層描画と比較する。最大 500 頂点、750 辺のランダムグラフで、1 辺当たり bend が平均約 0.85 から 0.7 に減る一方、幅と外側 segment の移動量は約 10% 増えるという trade-off を報告する。

[A Radial Adaptation of the Sugiyama Framework for Visualizing Hierarchical Information](https://doi.org/10.1109/TVCG.2007.1000) は、階層割当と 3 種の交差削減ヒューリスティックを放射描画へ適応する。水平型に比べ、両方向への配線自由度により平均交差数が約 30% 減ると報告する。平面長方形と放射領域では利用可能な経路が異なるため、交差数の差を「同一曲面上の最適性」ではなく、各描画モデルにおける可視交差の操作的比較として解釈する必要がある。

### 5.4 美的指標と読み取り性能

[Purchase (1997)](https://doi.org/10.1007/3-540-63938-1_67) は、交差、bend、対称性、最小角、直交性という 5 種の美的基準を変えた図に対し、被験者の課題時間と誤答を測った。交差数の影響が最も大きく、bend と対称性にはより小さい効果が見られた一方、最小角と直交性の効果は明確でなかった。この研究は階層描画だけを対象にしたものではないが、交差を主指標に置く根拠になる。同時に、アルゴリズム上の交差削減率をそのまま「可読性の改善率」と呼ぶことはできず、後者には人を用いた課題実験が必要である。

## 6. データセットと入力要因

### 公開データセット

[Graphdrawing.org の graph collections](https://www.graphdrawing.org/data.html) には、AT&T、Rome、North、DAGmar、ランダム DAG など、過去研究との比較に使いやすいデータがある。

| データ | 特徴 | 適した評価 |
|---|---|---|
| Rome | 多数の小規模疎グラフ | exact/heuristic gap、総合品質 |
| AT&T | 10--100 頂点程度の実系統グラフ | 階層割当、座標割当、総合比較 |
| North | 小中規模の実グラフ | 多層交差削減、厳密法 |
| DAGmar / RandDAG | パラメータ付き DAG | density、width、height の統制 |

これらは DAG が中心である。トーラス法の利点を測るには、公開 DAG に逆向き辺を規則的に追加した派生データだけでなく、もともと強連結成分を含む実有向グラフも必要である。派生データを使う場合は、元データと辺追加規則を保存する。

### 最低限統制すべき生成要因

- 頂点数 `n`
- 辺数または平均次数 `m/n`
- SCC の個数、最大 SCC 比率
- cycle rank、feedback arc set の近似サイズなどの循環性
- 長辺率と正規化後 dummy 比率
- 次数分布: 一様、small-world、scale-free
- 向き付け: random、潜在順序に沿う、円環に沿う、混合
- 層数または層容量
- 乱数 seed

Watts--Strogatz だけでなく、Erdős--Rényi、Barabási--Albert、block/community 型、grid/PERT 型を加えると、クラスタ係数、次数分布、方向性の影響を分離しやすい。

## 7. 指標の整理

### 工程単体

| 工程 | 必須指標 | 補助指標 |
|---|---|---|
| サイクル除去 | 反転辺数・重み、最適値 gap、時間 | 下流 span、dummy、交差 |
| 階層割当 | 総 span、dummy 数、層数、最大層幅 | span 二乗和、層占有分散、面積 |
| 正規化 | `n'/n`, `m'/m`, dummy 数、メモリ、時間 | 長辺率、segment 数 |
| 交差削減 | 交差数、初期値からの削減率、時間 | exact gap、type 別交差、starts 数 |
| 座標割当 | 幅、高さ、総辺長、時間 | 最小角度、分散、直線 segment 比 |
| 配線 | bend 数、交差、制約違反、時間 | bundle 数、重なり、境界連続性 |

### 完成描画

- 交差数: 総数、1 辺当たり、交差を持つ辺の割合
- bend 数: 総数、1 辺当たり、最大値
- 長さ: 総辺長、中央値、最大長、長さの変動
- 形状: 幅、高さ、面積、アスペクト比、角度分解能
- 方向性: 上向き辺率、反転辺数、境界跨ぎ辺数
- 可読性: node/edge overlap、ラベル衝突、交差角
- 計算: wall-clock、CPU、メモリ、timeout/失敗率
- 人: 正答率、完了時間、確信度、主観選好

交差数は数え方を明記する。元の長辺同士の交差と、dummy segment 同士の交差をどう集約するか、node-edge 接触を含めるか、基本領域境界で同一交差を二重計上しないかを仕様化する。

平面杉山描画とトーラス描画の交差数は、異なる表示領域上の操作的な値であり、同一曲面上の crossing number ではない。この注意は既存レポートと同様、全比較表に付ける。

## 8. 実験報告の統計と再現性

[Di Bartolomeo et al. (2024)](https://doi.org/10.1111/CGF.15073) は、206 件の graph layout 研究を系統的に調べ、データセット、規模、品質指標、評価形式の不統一を指摘する。これを踏まえ、次を推奨する。

- 同一グラフへ全方式を適用する対応比較を基本とする。
- 平均だけでなく、中央値、四分位範囲、95% 信頼区間、勝ち・同率・負けを報告する。
- 差分または相対差の paired bootstrap/permutation を用いる。
- 相対改善率は基準値 0 のケースを除外し、その件数を別掲する。総和比も併記する。
- 多数のグラフを同じ生成条件から作った場合、seed を独立な反復単位として扱う。
- solver timeout は失敗として消さず、解けた件数、incumbent、下界、MIP gap を保存する。
- JIT、キャッシュ、並列数、solver threads、ハードウェア、ソフトウェア版を記録する。
- 生 CSV、生成器、seed、集計コード、失敗ログを保存する。

アルゴリズムが確率的なら、入力 seed とアルゴリズム seed を分ける。`best-of-r` と単一実行を混同せず、品質対総計算時間で比較する。

## 9. 本プロジェクトの既存実験の位置づけ

### 現在できていること

| 既存実験 | 文献上の対応 | 良い点 |
|---|---|---|
| `evaluate_framework_crossings.py` | 全体比較 | 同一 100 グラフ、サイズ層別、向き層別、paired bootstrap、勝敗数 |
| `evaluate_crossing_reduction.py` | 交差削減単体 | 共通 layering を固定、guard の悪化防止、時間も測定 |
| `evaluate_layer_count_search.py` | 階層割当 | 全探索を正解として 100/100 照合、固定 `k` との excess 比較 |
| `evaluate_pipeline_runtime.py` | 全体 scaling | 200 グラフ、10--100 頂点、工程別 wall-clock |
| `evaluate_torus_framework_ablation.py` | 工程間寄与 | 構成要素の寄与を分離できる枠組み |
| `evaluate_rotation_geometry.py` | 座標・幾何 | 表示モデル固有の幾何を単体確認できる |

交差数の全体比較は、5 サイズ × 2 向き付け × 10 seed の 100 グラフで、平均次数 4、再配線確率 0.25 の Watts--Strogatz を用いている。全体平均では提案法の相対削減率 24.11%、95% paired-bootstrap CI は 16.08--32.03% である。ただし random orientation では 2.23% `[-6.90, 10.90]`、clockwise では 46.45% `[35.83, 55.86]` であり、入力の円環整合性が結果を強く左右する。この層別結果は、手法の適用範囲を示す重要な証拠である。

### 現時点の限界

1. 主な入力が Watts--Strogatz 一族で、次数分布と構造の多様性が小さい。
2. framework crossing 比較は最大 50 頂点である。
3. 平均次数がほぼ固定され、密度と長辺率の効果を十分に分離していない。
4. `random` と `clockwise` の間を連続的につなぐ「方向ノイズ率」がない。
5. 交差以外の完成描画指標、特に bend、総辺長、面積、角度、境界連続性がまだ主比較に入っていない。
6. 交差削減は初期配置に対する比較が中心で、小規模最適値との gap がない。
7. 公開データと実有向ネットワークによる外的妥当性が未確認である。
8. 100 件は有用だが、条件セル当たり 10 seed なので交互作用の推定は不安定になり得る。

## 10. 推奨する実験計画

### E0. 正当性と小規模厳密解

目的は、ヒューリスティックの品質に絶対的な基準を置くことである。

- `n=6,8,...,20` 程度
- 3 graph families × 3 densities × 3 cycle strengths × 20 seeds
- 階層割当: ILP/IQP または全探索と heuristic/two-stage を比較
- 交差削減: 二層または小規模多層の exact 法と比較
- 指標: 最適一致率、additive gap、relative gap、時間、timeout

既存の layer-count 全探索照合を、`k` の正当性だけでなく、span、balance、交差の各目的へ広げる。

### E1. 循環階層割当の要因実験

| 要因 | 水準例 |
|---|---|
| `n` | 20, 50, 100, 200, 500 |
| 平均次数 | 2, 4, 8 |
| graph family | WS, ER, BA, block/PERT |
| 方向ノイズ率 | 0, 0.1, 0.25, 0.5, 1.0 |
| 層数 | 自動、`sqrt(2n)`、固定小、固定大 |
| 方法 | ILP, IQP, heuristic, two-stage |

主指標は torus edge 数、cyclic span 総和・二乗和、最大層幅、占有分散、dummy 数、時間である。下流へ同じ交差削減を通し、交差数も測る。すべての完全直積が重すぎる場合は、graph family と方向ノイズを優先し、規模ごとに Latin hypercube または分割計画を使う。

### E2. 交差削減の quality--time 曲線

- 共通の layering、dummy graph、初期順序を保存
- 方法: barycenter、median、radial sifting、guard 付き、可能なら exact/ILP
- rounds: 1, 2, 5, 10
- starts: 1, 5, 10
- 指標: 総交差、境界近傍交差、改善率、最適 gap、時間

「5 rounds の結果」だけでなく、各時点の best-so-far を保存すれば、同じ時間予算で比較できる。guard 付き法は悪化件数 0 という性質に加え、その保証に払う時間増を報告する。

### E3. パイプライン・アブレーション

以下を一つずつ切り替え、差分を同一 graph/seed 上で測る。

- torus-aware layering の有無
- `diff_square` balance の有無
- 自動層数と固定層数
- dummy insertion の方式
- barycenter 初期化
- local/global radial sifting
- guard の有無
- 座標回転・境界処理

交差だけでなく、torus edge、span、dummy、bend、面積、時間を各段階で保存する。これにより「最終交差差がどの工程から生じたか」を説明できる。

### E4. 完成描画の外的妥当性

データを三群にする。

1. 現在の WS グラフ
2. ER、BA、block/PERT など統制した生成グラフ
3. graphdrawing.org と実有向循環グラフ

比較は、通常 Sugiyama、提案トーラス法、可能なら OGDF/Graphviz 等の標準実装を含める。各方式で利用する計算予算を揃え、内部実装と外部実装の差を明記する。

主結果は次の表を条件別に出す。

- median `[IQR]`
- paired mean/median difference と 95% CI
- wins/ties/losses
- timeout/invalid 件数
- crossing、bend、edge length、area、runtime の Pareto front

### E5. 必要ならユーザ実験

「読みやすい」「循環構造を理解しやすい」と主張する段階で行う。

- within-subject で同一グラフを両描画方式に割り当て、方式と問題順を counterbalance
- 課題: 到達可能性、最短路、閉路の有無、閉路に属する頂点、後続集合
- 指標: 正答率、完了時間、確信度、選好
- 規模: 20、50、100 頂点。課題ごとに難易度を事前校正
- 事前登録: 除外基準、主仮説、主指標、分析モデル

円環・トーラスの利点に合わせ、「閉路発見」と「境界を跨ぐ経路追跡」を含めることが重要である。静止画だけでなく、境界の複製表示や回転操作を許す条件は別要因として扱う。

## 11. 優先順位

### 優先度 A: すぐ実施する

1. 現行 CSV に `n'`, `m'`, dummy 数、総 cyclic span、最大層占有、bend 数を追加する。
2. 交差削減について `n<=20` の exact gap を作る。
3. 方向ノイズ率を 5 水準にし、clockwise から random への性能変化を描く。
4. ER と BA を追加し、平均次数 2/4/8 を交差させる。
5. アブレーションを同一 seed の対応比較に統一する。

### 優先度 B: 論文の中核を強くする

1. Rome/AT&T/North または DAGmar と、実循環グラフを追加する。
2. crossing、bend、edge length、area、runtime の多目的結果を示す。
3. `rounds × starts` の品質対時間曲線を出す。
4. solver の gap、timeout、threads を含む再現性情報を固定する。

### 優先度 C: 可読性の主張を行う場合

1. 認知課題を事前調査で校正する。
2. counterbalanced within-subject user study を行う。
3. 静止トーラス、境界複製、回転可能表示を別条件として比較する。

## 12. 結論

杉山フレームワークの良い実験は、工程の目的関数だけを測るのではなく、その変更が後段と完成描画へどう伝播するかを示している。とりわけ、階層割当では dummy・幅・面積、交差削減では exact gap・複数開始・時間、座標割当では幅と辺長の trade-off、全体では交差・bend・面積・時間を併記する設計が確立している。

本プロジェクトは、対応比較と統計的不確実性、工程別時間、全探索照合という強い土台をすでに持つ。次の決定的な改善は、グラフ族・密度・循環性を広げ、小規模厳密解を anchor にし、正規化後サイズと多目的品質を追跡することである。これにより、「円環に沿う入力では強い」という現状の結果を、どの構造条件で、どの工程によって、どれだけ強いのかという一般化可能な主張へ変えられる。

## 13. Zotero ライブラリ全件調査

### 13.1 調査範囲と完全性

ローカル Zotero ライブラリのトップレベル 17 アイテムを全件確認した。内訳は、書誌レコード 16 件と、親書誌を持たない PDF 添付 1 件である。`Beyond Level Planarity` は同一内容のレコードが 2 件あるため、書誌レコードの実質的な文献数は 15 件である。単独 PDF の尾上 (2018) を加えると、**異なる内容を持つ資料は計 16 件**となる。

調査では、タイトル・著者・年・DOI 等のメタデータだけでなく、各添付 PDF の全文を対象に、次を確認した。

- 杉山フレームワークのどの工程に関係するか
- 計算実験、理論評価、ユーザ実験、解説・サーベイのいずれか
- 入力、規模、反復数、比較法、指標、実行環境
- 本プロジェクトで再利用できる実験設計

15 件の固有書誌レコードにはすべて PDF があり、全文索引を取得できた。ただし Bachmaier の habilitation thesis は 194 頁中 100 頁までの索引である。本文の統合的な議論と中核実験はこの範囲に含まれる。単独の日本語 PDF は Zotero 全文 API に索引がなかったため、Zotero が管理するローカル PDF 全 7 頁を直接確認した。

以下の `item key` は Zotero 内部でレコードを識別するためのキーであり、文献引用キーではない。

| # | item key | Zotero 上のタイトル | 実体・重複 | 主な位置づけ |
|---:|---|---|---|---|
| 1 | `4L7MP5RZ` | A Generalized Framework for Drawing Directed Graphs | 2009 年 habilitation thesis。Zotero は journal article と誤分類 | 杉山法の平面・放射・円環拡張の統合 |
| 2 | `9H6KNKZL` | A Radial Adaptation of the Sugiyama Framework for Visualizing Hierarchical Information | 固有 | 放射型の交差削減・座標割当 |
| 3 | `TTZP3WKE` | A Technique for Drawing Directed Graphs | 固有 | 実用的な全体パイプライン |
| 4 | `VGHJQV6C` | Beyond Level Planarity | `D6M4BJEB` と重複 | level planarity の理論 |
| 5 | `D6M4BJEB` | Beyond Level Planarity | `VGHJQV6C` と重複 | 同上 |
| 6 | `WNBE2YTU` | Cyclic Leveling of Directed Graphs | 固有 | 円環階層割当 |
| 7 | `R9KRLRFH` | Drawing Recurrent Hierarchies | 固有 | 円環型の全体描画 |
| 8 | `Z7VARNJC` | Erratum: Fast and Simple Horizontal Coordinate Assignment | 固有 | 座標割当の訂正 |
| 9 | `2NVHSYYF` | Fast and Simple Horizontal Coordinate Assignment | 固有。Zotero の creator に編者も混在 | 座標割当 |
| 10 | `TDTAG563` | Finding All the Elementary Circuits of a Directed Graph | 固有 | 閉路列挙。サイクル指標の補助 |
| 11 | `P8AR6L7Y` | Generalized Layerings for Arbitrary and Fixed Drawing Areas | 固有 | サイクル除去と階層割当の統合 |
| 12 | `N2UI3KZI` | Hierarchical Drawing Algorithms | 2013 年 handbook chapter。Zotero の年が欠落 | 杉山法のサーベイ |
| 13 | `CFKT9QPV` | It’s a Wrap: Toroidal Wrapping of Network Visualisations Supports Cluster Understanding Tasks | 固有 | トーラス表示の計算・ユーザ実験 |
| 14 | `KPAJNTTM` | Layered Graph Drawing for Visualizing Evaluation Structures | 固有 | 応用別階層割当と選好実験 |
| 15 | `NTSHFT3W` | Methods for Visual Understanding of Hierarchical System Structures | 固有 | 杉山法原典 |
| 16 | `B3K2GNMH` | Optimal Sankey Diagrams Via Integer Programming | 固有 | 重み付き交差の厳密最適化 |
| 17 | `7BXK55XI` | 階層グラフの可視化 | 親書誌のない PDF 添付 | 日本語解説・サーベイ |

### 13.2 文献ごとの実験内容

#### Sugiyama, Tagawa, and Toda (1981): 原典にも統制実験がある

BC 法による交差削減を、8 種類の階層条件それぞれで 100 個、合計 800 個のランダム行列から生成した階層に適用している。条件は 2 層または 4 層、各層 3--6 頂点または 4 頂点、密度パラメータ 0.3、0.5、0.7 の組合せである。

- 初期交差数、全探索による厳密最小交差数、phase 1/2 後の交差数を比較
- 到達可能な改善量のうち何割を実現したかという performance index を使用
- 5 件の実階層でも交差数と FACOM M-190 上の CPU 時間を報告
- 座標割当では quadratic programming (QP) と priority (PR) heuristic を比較
- 例によっては QP が数十秒から 1,108 秒を要する一方、PR は約 0.1 秒であり、実応用では BC+PR を採用
- 500 頂点を超える問題への適用例を報告

現在の基準ではデータ・seed・分散が公開されていないが、**小規模厳密解、生成実験、実例、実行時間**を組み合わせた先駆的な設計である。

#### Gansner et al. (1993): 工学的な全体パイプライン

4-pass 構成、network simplex、交差削減、補助グラフによる座標割当、spline 配線を統合する。評価は完成図と実装経験が中心で、広い要因実験ではない。有限状態機械の例では Sun 4/280 上で 0.15 秒という処理時間を示す。サイクル除去では、循環辺を多く含む辺を優先して反転する方法より、安定した DFS ベースの方法を実用上選んでいる。これは局所的な循環指標の最小化が完成描画の改善を保証しない例でもある。

#### Bachmaier (2009): 平面・放射・円環を統合する thesis

[A Generalized Framework for Drawing Directed Graphs](https://www.infosun.fim.uni-passau.de/~chris/down/FrameworkForDAGs.pdf) は、個別論文の結果を統合した 194 頁の habilitation thesis である。独立な追加実験として二重計上せず、複数の拡張を同じ設計思想で比較する総合資料として扱う。

- global sifting: 1,000--10,000 頂点を 100 頂点刻み、各 10 件、合計 910 件。proper graph の約 75% が dummy 頂点となる条件で、10 sweeps/rounds を比較
- global sifting は通常法より交差を約 5--10%減らし、type-2 conflict を生じないが、時間は増加
- 小規模では正規化後頂点数がおおむね 35 以下の厳密解とも比較
- 放射型、円環階層割当、recurrent hierarchy の結果は各原論文と重複

#### Bachmaier and Forster (2007): 放射型 Sugiyama

[A Radial Adaptation of the Sugiyama Framework for Visualizing Hierarchical Information](https://doi.org/10.1109/TVCG.2007.1000) は、水平型の barycenter、median、sifting と、放射型へ適応した各方式を比較する。

- ランダム二部グラフ 5,000 件
- 両側の頂点数を 20、40、60、80、100、平均次数相当の密度を 1--20 とし、各組合せ 50 件
- 放射型は水平型の約 0.7 倍の交差数、すなわち約 30%減を報告
- radial sifting が最良だが最も遅く、改善の大半は第 1 round、通常 3--5 rounds で飽和
- proper graph 50,000 頂点の座標割当を 1.8 GHz PC、768 MB、Java/Gravisto で 50 秒未満

本プロジェクトでは、radial sifting の round 数を固定した単一点だけでなく、round ごとの quality--time 曲線を出す根拠になる。

#### Bachmaier et al. (2008): cyclic leveling

小規模では `n=4,...,18`, `m=2n`、各サイズ 10 件を branch-and-bound の厳密解と比較する。大規模では `n=50,100,...,500`, `m=5n`、各サイズ 10 件を用いる。層数 `k` と容量 `omega` はおおむね `sqrt(2n)`、各方式は `min(n,30)` 個の開始解を試す。MST 初期化を使う force-based 法が最も良い cyclic span を得る一方、多点開始は時間との交換条件になる。

#### Bachmaier et al. (2012): recurrent hierarchy の完成描画

[Drawing Recurrent Hierarchies](https://doi.org/10.7155/jgaa.00254) は、最大 500 頂点・750 辺のランダムグラフで、円環型と通常の階層描画を比較する。1 辺当たり bend は平均約 0.85 から 0.7 へ減る一方、幅と外側 segment の移動量は約 10%増える。円環化の利点を交差だけでなく bend で示し、代償も併記する全体評価である。

#### Brandes and Köpf (2002) と Erratum (2020): 座標割当

原論文は線形時間の水平座標割当を提案するが、評価は固定した少数の階層・順序による図例と preliminary computational experiments が中心である。[Erratum](https://arxiv.org/abs/2008.01252) は compaction に関する 2 つの不具合を示して修正する。計算量を実質的に変える新ベンチマークではない。したがって、座標割当の比較では原論文の疑似コードを無条件に再現せず、訂正版を実装基準にする。

#### Johnson (1975): 閉路列挙は補助的な exact anchor

[Finding All the Elementary Circuits of a Directed Graph](https://doi.org/10.1137/0204007) は、全 elementary circuit を `O((n+e)(c+1))` 時間、`O(n+e)` 空間で列挙する。IBM 370/168、ALGOL W 実装で Tarjan 法と比較している。

- worst-case family の `n=5,10,20,40,60,80` で、提案法は 0.03、0.11、0.32、1.17、2.61、4.46 秒、Tarjan 法は 0.06、0.27、1.67、11.51、36.89、86.66 秒
- 完全有向グラフ `n=2,...,9` では、`n=9` の 125,664 閉路を 20.17 秒、Tarjan 法は 30.13 秒
- 各値は 2 回の平均、時計の分解能は 1/60 秒

これは杉山法のサイクル除去アルゴリズムではない。小規模グラフの閉路数・閉路長分布を厳密に測る用途には使えるが、出力自体が指数的になり得るため、大規模な循環性指標や FAS 法の代替にはしない。

#### Rüegg et al. (2017): サイクル除去と階層割当を共同最適化

[Generalized Layerings for Arbitrary and Fixed Drawing Areas](https://doi.org/10.7155/jgaa.00441) は、feedback arc set と directed layering を別工程にせず、generalized layering problem (GLP) として統合する。逐次法 `EaGa` と、重みを変えた ILP、ヒューリスティックを比較する。

- ランダム 160 件: 17--60 頂点、平均 1.5 辺/頂点
- North 146 件: 20 頂点以上などの条件で選別
- 指標: 反転辺、dummy、層数、最大層幅、推定・実描画の幅・高さ・面積・アスペクト比、1 辺当たり交差、時間
- 後段では Brandes--Köpf または linear segments、polyline または orthogonal routing を組み合わせる
- North では dummy 平均が `EaGa` の 141.3 から重み `1-10-GLP` の 39.9 へ減る一方、反転辺は増える
- 推定面積の優劣が実描画面積と逆になるグラフが 64%あり、dummy を除いても 54%ある
- CPLEX 12.6 では 19 頂点 476 ms から 58 頂点 541 秒へ増加。ヒューリスティックは標準法の約 2.3 倍だが、試験範囲では 0.3--19.7 ms
- 1,000 頂点・1,500 辺の 5 件では `EaGa` 374 ms、提案ヒューリスティック 666 ms
- 固定描画領域の実験は North 112 件、目標アスペクト比 0.5、1、2。最大 scale は平均 2 倍以上になるが、約 4 分の 1 の辺を反転

この研究は、局所目的の代理値だけでなく、**同じ後段を通した実描画を測る必要性**を最も直接的に示す。トーラス階層割当も、`torus_edges` や span だけでなく完成描画の面積・交差まで追うべきである。

#### Healy and Nikolov (2013): handbook chapter

[Hierarchical Drawing Algorithms](https://cs.brown.edu/people/rtamassi/gdhandbook/chapters/hierarchical.pdf) は、階層割当、交差削減、座標割当、制約、orthogonal drawing 等を整理するサーベイであり、新しい計算実験は行わない。工程の分類や代表手法を確認する二次資料として用い、実験結果の証拠には各原論文を用いる。

#### Angelini et al. (2016): Beyond Level Planarity

[Beyond Level Planarity](https://arxiv.org/abs/1510.08274) は理論論文で、計算実験はない。Torus Level Planarity と Cyclic Level Planarity を多項式時間で判定できることを示し、proper instance では二次、辺の subdivision を要する non-proper instance では四次の時間計算量を与える。また simultaneous level planarity は 3 グラフ・2 層、または 2 グラフ・3 層で NP-complete、2 グラフ・2 層では多項式時間である。

本プロジェクトでは、交差 0 が可能な小規模入力に対する feasibility oracle、あるいはテストケースの理論分類に使える。ヒューリスティックの平均性能を示すベンチマークではない。Zotero 内の 2 レコードは重複なので、集計時に 2 本として数えない。

#### Chen et al. (2021): トーラス表示の計算実験とユーザ実験

[It’s a Wrap](https://doi.org/10.1145/3411764.3445439) は一般ネットワークの force-directed layout であり杉山法ではないが、トーラス表示を「見た目」ではなく、計算指標と認知課題の両方で検証する設計が参考になる。

計算実験:

- NetworkX の Random Partition / Gaussian Random Partition で 200 グラフを生成
- modularity 0.25--0.45、small 68--80 頂点・710--925 辺、large 126--134 頂点・2,310--2,590 辺、3--8 clusters
- 4 方式、各グラフ 20 初期配置を比較
- runtime、stress、crossing、incidence angle、cluster distance を測定
- Friedman 検定と Nemenyi 多重比較、95% 水準

ユーザ実験:

- 参加者 32 名、監督付きオンライン、within-subject
- 2 techniques × 2 tasks × 2 difficulties × 2 sizes × 5 repeats = 1 人 80 試行、合計 2,560 試行
- 課題は cluster 数と指定 node の cluster。20 秒 timeout、事前登録あり
- 誤答率には Friedman/Tukey、時間には 3-way repeated-measures ANOVA と Bonferroni 補正、主観評価には Wilcoxon 検定
- torus は cluster 数課題の誤りを 42.3%、node cluster 課題の誤りを 62.7%、後者の時間を 32.3%低減

対象課題は階層や経路ではなく cluster 理解なので、効果量を本研究へ直接移せない。しかし、E5 の参加者内計画、難易度校正、反復、timeout、事前登録、分析法の具体的な雛形になる。

#### Onoue et al. (2017): evaluation structure 向け階層割当

[Layered Graph Drawing for Visualizing Evaluation Structures](https://doi.org/10.1109/MCG.2016.40) は、source/sink を最外層へ置き、辺 span の二乗和を目的とする階層割当を IQP/ILP で解く。

- 実データ 12 件: 41--400 頂点、41--373 辺、6--17 層
- Gurobi 5.6、1.8 GHz、4 GB、Linux
- ILP は全件 0.2 秒未満。中間的 IQP は遅く、301、320、400 頂点の 3 件を 1 時間以内に解けない
- 代表 3 件で longest path、tight-tree、network simplex、提案法の完成図を比較
- サイクル除去は Eades、座標割当は Brandes--Köpf、実装は D3/dagre を使用

12 名による選好実験では、評価グリッド法に習熟した研究者 4 名、企業参加者 5 名、学生 3 名が 5 方式を比較し、Scheffé の一対比較法を用いる。提案法は、longest-path を除く各法より 1% 水準で好まれた。ただし課題正答率や時間ではなく、主観選好だけを測っている。図面積の増加や、実際の交差数と知覚される交差のずれもあり、アルゴリズム指標と選好を分離して読む必要がある。

#### Zarate et al. (2018): weighted crossing の厳密最適化

[Optimal Sankey Diagrams Via Integer Programming](https://doi.org/10.1109/PacificVis.2018.00025) は、固定層上の crossing を、2 辺の重みの積で重み付けした「交差面積」として最小化する ILP を提案する。

- World GHG 実データ: dummy 挿入後 4 層、55 頂点、100 辺。3 秒で最適解と証明を得る
- 合成データ: 層数と層当たり頂点数を変え、辺密度 20%、各設定 10 件
- 最適解を最初に見つけた時間と、最適性を証明した時間を別に報告
- Gurobi 7.5.1、Zimpl 3.3.4、single-thread、AMD Opteron 6272 2.7 GHz、32 GB、Ubuntu
- 分枝優先度の指定により、小規模で約 2 倍、大規模で最大約 10 倍高速化

本プロジェクトで辺に重要度・流量がある場合、無重み交差数だけでなく `w(e)w(f)` による weighted crossing を追加できる。また exact 法は、time-to-best-incumbent と time-to-proof を分けて記録するべきである。

#### 尾上 (2018): 日本語による工程・拡張・ソフトウェアの解説

[「階層グラフの可視化」](https://jglobal.jst.go.jp/detail?JGLOBAL_ID=201802230578310609) は『オペレーションズ・リサーチ』63 巻 1 号、20--26 頁の解説であり、新規の実験はない。サイクル除去、階層割当、交差削減、座標割当を概説し、width 制約、span 二乗和、edge concentration、circular/radial/compound graph への拡張を整理する。実装として Graphviz、Tulip、OGDF、igraph、dagre を挙げる。日本語で工程全体を説明する導入資料として有用だが、定量値の根拠には原論文を用いる。

### 13.3 Zotero 全件から得られた実験設計上の追加結論

1. **原典を過小評価しない**: Sugiyama et al. (1981) は 800 件の生成実験と厳密解比較を含む。現代的再現性には不足があるが、E0 の構成は原典にも遡れる。
2. **逐次工程だけでなく共同最適化を比較する**: GLP はサイクル除去と階層割当の統合が dummy を大きく減らす一方、反転辺を増やすことを示す。E1 に `sequential` 対 `joint/two-stage` を明示的な要因として加える。
3. **代理目的と実図面を両方測る**: GLP では推定面積と実面積の優劣が半数以上で一致しない。span、`torus_edges`、層占有だけで結論せず、後段固定の交差・bend・面積を必ず測る。
4. **重み付き交差を検討する**: Sankey の実験は、重要な辺同士の交差をより重く扱う exact anchor を提供する。無重みと重み付きの双方を保存すれば、特定の主要経路を読みやすくする主張が可能になる。
5. **円環法の計算予算を揃える**: cyclic leveling と radial sifting は、多点開始や rounds が品質を改善する。方式ごとの既定反復ではなく、1/5/10 starts、1/2/5/10 rounds と wall-clock budget の双方で比較する。
6. **ユーザ実験は課題をモデルに合わせる**: `It’s a Wrap` の cluster 課題をそのまま用いず、到達可能性、閉路発見、境界跨ぎ経路追跡へ置き換える。実験構造は 32 名、参加者内、反復、難易度、timeout、事前登録を参考にする。
7. **選好と課題成績を混同しない**: evaluation structure 論文は選好を示すが、正答率・時間は測っていない。E5 では主観評価を副次指標とし、正答率と時間を主指標にする。
8. **理論的なゼロ交差可能性をテストに使う**: Beyond Level Planarity は empirical baseline ではないが、交差 0 が可能な torus/cyclic instance の正当性テストに使える。
9. **閉路数は小規模限定の説明変数にする**: Johnson 法で elementary circuit 数を厳密に得られるが、大規模では指数的出力になる。大規模では SCC 比率、cycle rank、FAS 近似量を用いる。
10. **書誌と実装版を固定する**: Brandes--Köpf は erratum 後の版を使い、論文名だけでなく修正内容・コード commit を実験記録へ残す。

### 13.4 Zotero データ品質上の注意

- `Beyond Level Planarity` は 2 レコードあるため、文献数や evidence count で重複除去する。
- `A Generalized Framework for Drawing Directed Graphs` は journal article ではなく habilitation thesis であり、年・機関を手動補完する必要がある。
- `Hierarchical Drawing Algorithms` は 2013 年の handbook chapter で、Zotero の年が欠落している。
- `Fast and Simple Horizontal Coordinate Assignment` の creator には論文著者以外の編者が混在している。引用時の著者は Ulrik Brandes と Boris Köpfである。
- `階層グラフの可視化` は親書誌のない attachment のため、著者、雑誌、巻号、頁、年を親レコードとして登録すると管理しやすい。
- thesis は Zotero 全文索引が 100/194 頁で止まっているため、引用箇所が後半にある場合は PDF を再確認する。

## 14. 参考文献

1. Sugiyama, K., Tagawa, S., Toda, M. (1981). [Methods for Visual Understanding of Hierarchical System Structures](https://doi.org/10.1109/TSMC.1981.4308636).
2. Gansner, E. R., Koutsofios, E., North, S. C., Vo, K.-P. (1993). [A Technique for Drawing Directed Graphs](https://doi.org/10.1109/32.221135).
3. Eades, P., Lin, X., Smyth, W. F. (1993). [A Fast and Effective Heuristic for the Feedback Arc Set Problem](https://doi.org/10.1016/0020-0190(93)90079-O).
4. Nikolov, N. S., Tarassov, A. (2006). [Graph Layering by Promotion of Nodes](https://doi.org/10.1016/j.dam.2005.05.023).
5. Nikolov, N. S., Tarassov, A., Branke, J. (2005). [In Search for Efficient Heuristics for Minimum-Width Graph Layering with Consideration of Dummy Nodes](https://doi.org/10.1145/1064546.1180618).
6. Bachmaier, C., Brandenburg, F. J., Brunner, W., Lovász, G. (2008). [Cyclic Leveling of Directed Graphs](https://www.infosun.fim.uni-passau.de/~chris/down/CyclicLeveling.pdf).
7. Eiglsperger, M., Siebenhaller, M., Kaufmann, M. (2005). [An Efficient Implementation of Sugiyama's Algorithm for Layered Graph Drawing](https://www.maths.tcd.ie/EMIS/journals/JGAA/accepted/2005/EiglspergerSiebenhallerKaufmann2005.9.3.pdf).
8. Jünger, M., Mutzel, P. (1997). [2-Layer Straightline Crossing Minimization: Performance of Exact and Heuristic Algorithms](https://doi.org/10.7155/jgaa.00001).
9. Martí, R., Laguna, M. (2003). [Heuristics and Meta-Heuristics for 2-Layer Straight Line Crossing Minimization](https://doi.org/10.1016/S0166-218X(02)00397-9).
10. Bachmaier, C. et al. (2011). [Global k-Level Crossing Reduction](https://doi.org/10.7155/jgaa.00242).
11. Chimani, M., Hungerländer, P., Jünger, M., Mutzel, P. (2011). [An SDP Approach to Multi-level Crossing Minimization](https://tcs.uos.de/_media/pubs/alnx11_preprint_mlcm_sdp_pdf.pdf).
12. Brandes, U., Köpf, B. (2002). [Fast and Simple Horizontal Coordinate Assignment](https://doi.org/10.1007/3-540-45848-4_3).
13. Jünger, M., Mutzel, P., Spisla, C. (2018). [A Flow Formulation for Horizontal Coordinate Assignment with Prescribed Width](https://arxiv.org/abs/1806.06617).
14. Schulze, C. D., Spönemann, M., von Hanxleden, R. (2014). [Drawing Layered Graphs with Port Constraints](https://doi.org/10.1016/j.jvlc.2013.11.005).
15. Di Battista, G. et al. (2000). [Drawing Directed Acyclic Graphs: An Experimental Study](https://doi.org/10.1142/S0218195900000358).
16. Lionakis, G., Kritikakis, G., Tollis, I. G. (2022). [Experiments and a User Study for Hierarchical Drawings of Graphs](https://arxiv.org/abs/2209.04522).
17. Bachmaier, C. et al. (2012). [Drawing Recurrent Hierarchies](https://doi.org/10.7155/jgaa.00254).
18. Di Bartolomeo, S. et al. (2024). [Evaluating Graph Layout Algorithms: A Systematic Review of Methods and Best Practices](https://doi.org/10.1111/CGF.15073).
19. Purchase, H. C. (1997). [Which Aesthetic Has the Greatest Effect on Human Understanding?](https://doi.org/10.1007/3-540-63938-1_67).
20. Bachmaier, C., Forster, M. (2007). [A Radial Adaptation of the Sugiyama Framework for Visualizing Hierarchical Information](https://doi.org/10.1109/TVCG.2007.1000).
21. Di Giacomo, E. et al. (2020). [Layered Drawing of Undirected Graphs with Generalized Port Constraints](https://arxiv.org/abs/2008.10583).
22. Koehler, F. et al. (2024). [Finding Small Feedback Arc Sets on Large Graphs](https://doi.org/10.1016/j.cor.2024.106724).
23. Bachmaier, C. (2009). [A Generalized Framework for Drawing Directed Graphs](https://www.infosun.fim.uni-passau.de/~chris/down/FrameworkForDAGs.pdf). Habilitation thesis, University of Passau.
24. Angelini, P. et al. (2016). [Beyond Level Planarity](https://arxiv.org/abs/1510.08274).
25. Brandes, U., Walter, M., Zink, J. (2020). [Erratum: Fast and Simple Horizontal Coordinate Assignment](https://arxiv.org/abs/2008.01252).
26. Johnson, D. B. (1975). [Finding All the Elementary Circuits of a Directed Graph](https://doi.org/10.1137/0204007).
27. Rüegg, U. et al. (2017). [Generalized Layerings for Arbitrary and Fixed Drawing Areas](https://doi.org/10.7155/jgaa.00441).
28. Healy, P., Nikolov, N. S. (2013). [Hierarchical Drawing Algorithms](https://cs.brown.edu/people/rtamassi/gdhandbook/chapters/hierarchical.pdf).
29. Chen, S. et al. (2021). [It’s a Wrap: Toroidal Wrapping of Network Visualisations Supports Cluster Understanding Tasks](https://doi.org/10.1145/3411764.3445439).
30. Onoue, Y. et al. (2017). [Layered Graph Drawing for Visualizing Evaluation Structures](https://doi.org/10.1109/MCG.2016.40).
31. Zarate, D. et al. (2018). [Optimal Sankey Diagrams Via Integer Programming](https://doi.org/10.1109/PacificVis.2018.00025).
32. 尾上洋介 (2018). [階層グラフの可視化](https://jglobal.jst.go.jp/detail?JGLOBAL_ID=201802230578310609). 『オペレーションズ・リサーチ』63(1), 20--26.
