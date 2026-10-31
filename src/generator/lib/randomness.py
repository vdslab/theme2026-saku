"""生成ごとに独立した乱数器を作り、使用するシードを確定する。"""

import random


def resolve_seed(seed: int | None) -> int:
    """未指定なら、再生成に利用できる32ビットのシードを発行する。"""
    return random.SystemRandom().randrange(2**32) if seed is None else seed


def create_random(seed: int | None) -> tuple[random.Random, int]:
    """グローバルな random の状態を変更せずに乱数器を作る。"""
    resolved_seed = resolve_seed(seed)
    return random.Random(resolved_seed), resolved_seed
