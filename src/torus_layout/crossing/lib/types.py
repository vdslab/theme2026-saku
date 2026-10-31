"""Siftingが使う一時辺ID。元の有向辺と区別する。"""
from ...models import Node, Edge
type OrientedEdge = tuple[Node, Node, int]
type EdgeLike = Edge | OrientedEdge
