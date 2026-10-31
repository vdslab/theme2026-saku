"""各手法で共通の入力条件を検証する。"""


def validate_node_count(n: int, *, minimum: int = 0) -> None:
    """頂点数が指定の下限以上の整数であることを確認する。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < minimum:
        raise ValueError(f"n must be an integer at least {minimum}")


def validate_probability(value: float, name: str) -> None:
    """辺追加・頂点選択・張り替えの確率を検証する。"""
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
