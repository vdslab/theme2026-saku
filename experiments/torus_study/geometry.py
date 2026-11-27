"""Common centerline measurements in each layout's local drawing units."""

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations, product
import math

from torus_layout.domain import vertical_bounds
from torus_layout.drawing.geometry import periodic_edge_segments, validate_positions

# Keep event tolerance below the coordinate optimizer's distance from the cut.
EPS = 1e-10


@dataclass(frozen=True)
class Route:
    edge: tuple[int, int]
    points: list
    pieces: list
    corners: list
    x_wraps: int = 0
    y_wraps: int = 0
    x_segments: int = 0
    y_segments: int = 0


def planar_route(edge, points, corners=None):
    segments = list(zip(points, points[1:]))
    return Route(edge, points, segments, points if corners is None else corners)


def torus_routes(chains, graph, crossing, coordinates):
    width, height = len(graph.layers), coordinates.period
    ymin, ymax = vertical_bounds(height, max(map(len, graph.layers.values())))
    bounds = (-0.5, ymin, width, height)
    validate_positions(coordinates.positions, graph.layers, graph.graph.edges,
                       -0.5, width - 0.5, ymin, ymax)
    routes = []
    for edge, chain in chains.items():
        points = [coordinates.positions[chain[0]]]
        pieces, wx, wy = [], [], []
        for u, v in zip(chain, chain[1:]):
            horizontal = int(graph.torus_flags.get((u, v), False))
            vertical = crossing.winding_numbers.get((u, v), 0)
            wx.append(horizontal)
            wy.append(vertical)
            start, end = coordinates.positions[u], coordinates.positions[v]
            pieces.extend(periodic_edge_segments(
                start, end, x_min=-0.5, x_max=width - 0.5, y_min=ymin,
                y_max=ymax, horizontal_winding=horizontal,
                vertical_winding=vertical,
            ))
            dx, dy = displacement(start, end)
            points.append((points[-1][0] + dx + horizontal * width,
                           points[-1][1] + dy + vertical * height))
        routes.append(Route(edge, points, pieces, points, sum(wx), sum(map(abs, wy)),
                            sum(bool(v) for v in wx), sum(bool(v) for v in wy)))
    return routes, bounds


def displacement(a, b):
    return b[0] - a[0], b[1] - a[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def turns(points):
    count = 0
    for a, b, c in zip(points, points[1:], points[2:]):
        left, right = displacement(a, b), displacement(b, c)
        if min(math.hypot(*left), math.hypot(*right)) <= EPS:
            continue
        angle = math.atan2(abs(cross(left, right)), math.fsum(x*y for x, y in zip(left, right)))
        count += angle > math.radians(1)
    return count


def canonical_point(point, bounds):
    if bounds is None:
        return tuple(point)
    xmin, ymin, width, height = bounds
    return tuple(
        low if min(abs(value - low), abs(value - high)) <= EPS else value
        for value, low, high in zip(point, (xmin, ymin), (xmin + width, ymin + height))
    )


def hit(a, b, c, d):
    """Inclusive intersection, with a separate report for positive overlap."""
    r, s, offset = displacement(a, b), displacement(c, d), displacement(a, c)
    denominator = cross(r, s)
    if abs(denominator) <= EPS * math.hypot(*r) * math.hypot(*s):
        if abs(cross(offset, r)) > EPS * math.hypot(*r):
            return None, False
        axis = max(range(2), key=lambda i: abs(r[i]))
        span = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
        span -= max(min(a[axis], b[axis]), min(c[axis], d[axis]))
        return None, span > EPS
    t, u = cross(offset, s) / denominator, cross(offset, r) / denominator
    eps_t, eps_u = EPS / math.hypot(*r), EPS / math.hypot(*s)
    if -eps_t <= t <= 1 + eps_t and -eps_u <= u <= 1 + eps_u:
        return (a[0] + min(1, max(0, t)) * r[0], a[1] + min(1, max(0, t)) * r[1]), False
    return None, False


def rays(point, *ends):
    return [math.atan2(y, x) % math.tau for x, y in
            (displacement(point, end) for end in ends) if math.hypot(x, y) > EPS]


def alternate(left, right):
    def distinct(angles):
        result = []
        for angle in sorted(angles):
            if not result or angle - result[-1] > EPS:
                result.append(angle)
        if len(result) > 1 and result[0] - result[-1] + math.tau <= EPS:
            result.pop()
        return result

    left, right = distinct(left), distinct(right)
    if len(left) != 2 or len(right) != 2:
        return False
    order = sorted([(a, 0) for a in left] + [(a, 1) for a in right])
    return all(order[i-1][1] != side and
               (angle - order[i-1][0]) % math.tau > EPS
               for i, (angle, side) in enumerate(order))


def crossing_metrics(routes, bounds, *, multiplicities=None):
    """Count transverse events, including at dummy nodes and on the cut."""
    copies = multiplicities or {}
    endpoints = defaultdict(lambda: defaultdict(set))
    events = defaultdict(lambda: defaultdict(set))
    overlaps = set()
    segments = []
    buckets = defaultdict(list)

    def point_key(point):
        point = canonical_point(point, bounds)
        ix, iy = (math.floor(value / EPS) for value in point)
        for dx, dy in product((-1, 0, 1), repeat=2):
            for candidate in buckets.get((ix + dx, iy + dy), ()):
                if math.dist(point, candidate) <= EPS:
                    return candidate
        buckets[ix, iy].append(point)
        return point

    for route in routes:
        for a, b in route.pieces:
            if math.dist(a, b) <= EPS:
                continue
            endpoints[point_key(a)][route.edge].update(rays(a, b))
            endpoints[point_key(b)][route.edge].update(rays(b, a))
            segments.append((min(a[0], b[0]), max(a[0], b[0]),
                             min(a[1], b[1]), max(a[1], b[1]), route.edge, a, b))
    for point, edges in endpoints.items():
        if len(edges) > 1:
            events[point].update(edges)
    active = []
    for segment in sorted(segments):
        left, _, bottom, top, edge, a, b = segment
        active = [other for other in active if other[1] + EPS >= left]
        for _, _, low, high, other_edge, c, d in active:
            if edge == other_edge or top + EPS < low or high + EPS < bottom:
                continue
            point, overlap = hit(a, b, c, d)
            if overlap:
                overlaps.add(tuple(sorted((edge, other_edge))))
            if point is not None:
                key = point_key(point)
                contributions = events[key]
                contributions[edge].update(endpoints.get(key, {}).get(edge, ()))
                contributions[edge].update(rays(point, a, b))
                contributions[other_edge].update(endpoints.get(key, {}).get(other_edge, ()))
                contributions[other_edge].update(rays(point, c, d))
        active.append(segment)
    pairs, crossings, touches, centerline_crossings = set(), 0, 0, 0
    route_endpoints = {
        route.edge: {point_key(route.pieces[0][0]), point_key(route.pieces[-1][-1])}
        for route in routes if route.pieces
    }
    for point, contributions in events.items():
        for (edge, a), (other, b) in combinations(contributions.items(), 2):
            if point in route_endpoints[edge] and point in route_endpoints[other] and set(edge) & set(other):
                continue
            weight = copies.get(edge, 1) * copies.get(other, 1)
            if alternate(a, b):
                centerline_crossings += 1
                crossings += weight
                pairs.add(tuple(sorted((edge, other))))
            else:
                touches += weight

    def original_pair_count(pairs):
        return sum(copies.get(edge, 1) * copies.get(other, 1) for edge, other in pairs)

    shared_pairs = sum(count * (count - 1) // 2 for count in copies.values())
    result = {
        "geometric_crossings": crossings, "crossing_edge_pairs": original_pair_count(pairs),
        "contact_events": touches, "overlapping_edge_pairs": original_pair_count(overlaps) + shared_pairs,
    }
    if multiplicities is not None:
        result["geometric_crossings_on_layout_edges"] = centerline_crossings
    return result


def route_metrics(routes, bounds=None, *, bends=True, geometry=True):
    lengths = [sum(math.dist(a, b) for a, b in zip(route.points, route.points[1:]))
               for route in routes]
    points = [point for route in routes for pair in route.pieces for point in pair]
    width = (max(x for x, _ in points) - min(x for x, _ in points)) if points else 0
    height = (max(y for _, y in points) - min(y for _, y in points)) if points else 0
    result = {
        "total_edge_length": sum(lengths), "max_edge_length": max(lengths, default=0),
        "centerline_bbox_area": width * height,
        "centerline_bbox_width": width, "centerline_bbox_height": height,
        "x_seam_edges": sum(bool(r.x_wraps) for r in routes),
        "y_seam_edges": sum(bool(r.y_wraps) for r in routes),
        "either_seam_edges": sum(bool(r.x_wraps or r.y_wraps) for r in routes),
        "x_seam_segments": sum(r.x_segments for r in routes),
        "y_seam_segments": sum(r.y_segments for r in routes),
        "x_seam_events": sum(r.x_wraps for r in routes),
        "y_seam_events": sum(r.y_wraps for r in routes),
    }
    if bounds is not None:
        result["fundamental_area"] = bounds[2] * bounds[3]
    if bends:
        result["bends"] = sum(turns(route.corners) for route in routes)
    if geometry:
        result.update(crossing_metrics(routes, bounds))
    return result
