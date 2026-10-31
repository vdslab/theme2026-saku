"""Radial交差削減の公開入口。"""
from .api import reduce_crossings as reduce_crossings, count_crossings as count_crossings
__all__ = ["reduce_crossings", "count_crossings"]
