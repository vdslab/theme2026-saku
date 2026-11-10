"""手法名と生成パラメータを受け取り、対応する生成関数へ振り分ける。"""

from .cyclic import generate_cyclic_graph
from .dag import generate_dag
from .lib.randomness import resolve_seed
from .lib.types import SeededGraph
from .mixed import generate_mixed_graph
from .random_connected import generate_random_connected_graph
from .watts_strogatz import generate_watts_strogatz_graph

_GENERATORS = {
    "random": generate_random_connected_graph,
    "dag": generate_dag,
    "cyclic": generate_cyclic_graph,
    "mixed": generate_mixed_graph,
    "watts_strogatz": generate_watts_strogatz_graph,
}


def generate_graph(
    graph_type: str,
    n: int,
    *,
    seed: int | None = None,
    **parameters,
) -> SeededGraph:
    """手法固有の引数を転送し、常に (頂点, 有向辺, シード) を返す。

    graph_type は random / dag / cyclic / mixed / watts_strogatz。
    seed未指定時も確定したシードを返し、同じ入力を再生成できる。
    未知の手法は ValueError、手法にない引数は TypeError となる。
    """
    try:
        generator = _GENERATORS[graph_type]
    except KeyError:
        choices = ", ".join(_GENERATORS)
        raise ValueError(
            f"unknown graph_type: {graph_type!r}; choose from {choices}"
        ) from None

    resolved_seed = resolve_seed(seed)
    vertices, edges = generator(n, seed=resolved_seed, **parameters)
    return vertices, edges, resolved_seed
