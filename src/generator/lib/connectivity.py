"""有向辺の向きを無視して、グラフの弱連結性を調べる。"""

from collections import deque

from .types import Edge


def is_connected(vertices: list[int], edges: list[Edge]) -> bool:
    """無向グラフとして全頂点へ到達できるかを幅優先探索で判定する。

    空グラフは既存実装と同じく連結とみなす。
    """
    if not vertices:
        return True

    adjacency = {vertex: [] for vertex in vertices}
    for source, target in edges:
        adjacency[source].append(target)
        adjacency[target].append(source)

    visited = {vertices[0]}
    queue = deque([vertices[0]])
    while queue:
        for neighbor in adjacency[queue.popleft()]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return len(visited) == len(vertices)
