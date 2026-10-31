"""既存の描画処理が受け取る頂点リストと有向辺リストの型。"""

type Edge = tuple[int, int]
type Graph = tuple[list[int], list[Edge]]
type SeededGraph = tuple[list[int], list[Edge], int]
