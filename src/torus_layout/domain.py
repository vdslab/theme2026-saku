"""Shared vertical bounds for coordinates, drawing, and measurements."""

def vertical_bounds(period: float, max_layer_size: int) -> tuple[float, float]:
    lower = -period / (2 * max(1, max_layer_size))
    return lower, lower + period
