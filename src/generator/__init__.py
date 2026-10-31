"""グラフ生成の公開入口。手法名による振り分けには generate_graph を使う。"""

from .cyclic import generate_cyclic_graph
from .dag import generate_dag
from .mixed import generate_mixed_graph
from .random_connected import generate_random_connected_graph
from .router import generate_graph
from .watts_strogatz import generate_watts_strogatz_graph

__all__ = [
    "generate_graph",
    "generate_random_connected_graph",
    "generate_dag",
    "generate_cyclic_graph",
    "generate_mixed_graph",
    "generate_watts_strogatz_graph",
]
