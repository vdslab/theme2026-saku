"""公開されている型を実際に利用し、型解決と通常importを確認する。"""
from torus_layout import Graph
from torus_layout.models import LayerAssignmentResult

def check_imports() -> None:
    graph = Graph((0, 1), ((0, 1),))
    assignment = LayerAssignmentResult({0: 0, 1: 1}, {(0, 1): False}, 0.0)
    assert graph.edges == ((0, 1),)
    assert assignment.layers == {0: [0], 1: [1]}

if __name__ == "__main__":
    check_imports()
