"""型注釈のない呼び出し元にも適用する既存の実行時チェック。"""

from os import PathLike
from typing import TypeGuard


def is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float))


def is_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int)


def is_tuple(value: object) -> bool:
    return isinstance(value, tuple)


def is_sequence(value: object) -> bool:
    return isinstance(value, (tuple, list))


def is_image_path(value: object) -> TypeGuard[str | PathLike[str]]:
    return isinstance(value, (str, PathLike))
