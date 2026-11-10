"""Compatibility exports for the shared random_graph implementation."""

from generator.random_oriented_watts_strogatz import (
    DEFAULT_NEIGHBOR_COUNT,
    DEFAULT_REWIRING_PROBABILITY,
    generate_watts_strogatz_digraph,
)

__all__ = ['DEFAULT_NEIGHBOR_COUNT', 'DEFAULT_REWIRING_PROBABILITY', 'generate_watts_strogatz_digraph']
