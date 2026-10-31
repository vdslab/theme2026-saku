"""公開されている型を実際に利用し、型解決と通常importを確認する。"""
from torus_layout import Graph
from torus_layout.crossing import reduce_crossings, count_crossings
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.models import LayerAssignmentResult
from torus_layout.layering import balance_diff, find_minimum_configuration

def check_imports() -> None:
    graph = Graph((0, 1), ((0, 1),))
    assignment = LayerAssignmentResult({0: 0, 1: 1}, {(0, 1): False}, 0.0)
    assert callable(balance_diff) and callable(find_minimum_configuration)
    divided = insert_dummy_nodes(graph, assignment)
    crossing = reduce_crossings(divided, rounds=0)
    count: int = count_crossings(divided, crossing)
    assert count == 0
    assert graph.edges == ((0, 1),)
    assert assignment.layers == {0: [0], 1: [1]}

if __name__ == "__main__":
    check_imports()
