from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, List, Sequence, Tuple


@dataclass
class Point2D:
    x: float
    y: float

    def as_tuple(self) -> Tuple[float, float]:
        return self.x, self.y


@dataclass
class Point3D:
    x: float
    y: float
    z: float


@dataclass
class BSplineFit:
    degree: int
    knots: List[float]
    control_points: List[Point2D]
    parameters: List[float]


def clamp_degree(degree: int, control_count: int) -> int:
    if control_count <= 1:
        return 1
    return max(1, min(int(degree), control_count - 1))


def generate_clamped_knots(control_count: int, degree: int) -> List[float]:
    degree = clamp_degree(degree, control_count)
    if control_count <= degree:
        return []

    internal_count = control_count - degree - 1
    knots = [0.0] * (degree + 1)
    for i in range(1, internal_count + 1):
        knots.append(i / (internal_count + 1))
    knots.extend([1.0] * (degree + 1))
    return knots


def generate_averaged_knots(parameters: Sequence[float], control_count: int, degree: int) -> List[float]:
    degree = clamp_degree(degree, control_count)
    if control_count <= degree:
        return []

    data_last = len(parameters) - 1
    control_last = control_count - 1
    knot_count = control_count + degree + 1
    knots = [0.0] * knot_count

    for i in range(degree + 1):
        knots[i] = 0.0
        knots[knot_count - 1 - i] = 1.0

    internal_count = control_last - degree
    if internal_count <= 0:
        return knots

    # Global least-square approximation knot placement from The NURBS Book:
    # distribute internal knots over the chord-length parameters.
    d = data_last / (internal_count + 1)
    for j in range(1, internal_count + 1):
        value = j * d
        idx = int(value)
        alpha = value - idx
        left = parameters[max(0, min(idx, data_last))]
        right = parameters[max(0, min(idx + 1, data_last))]
        knots[j + degree] = (1.0 - alpha) * left + alpha * right

    return knots


def basis_function(i: int, degree: int, u: float, knots: Sequence[float]) -> float:
    control_count = len(knots) - degree - 1
    if degree == 0:
        if knots[i] <= u < knots[i + 1]:
            return 1.0
        if u == knots[-1] and i == control_count - 1:
            return 1.0
        return 0.0

    left = 0.0
    left_den = knots[i + degree] - knots[i]
    if left_den > 1e-12:
        left = (u - knots[i]) / left_den * basis_function(i, degree - 1, u, knots)

    right = 0.0
    right_den = knots[i + degree + 1] - knots[i + 1]
    if right_den > 1e-12:
        right = (knots[i + degree + 1] - u) / right_den * basis_function(i + 1, degree - 1, u, knots)

    return left + right


def basis_row(u: float, control_count: int, degree: int, knots: Sequence[float]) -> List[float]:
    u = max(knots[0], min(knots[-1], u))
    if u >= knots[-1] - 1e-12:
        row = [0.0] * control_count
        if control_count:
            row[-1] = 1.0
        return row
    return [basis_function(i, degree, u, knots) for i in range(control_count)]


def evaluate_curve(control_points: Sequence[Point2D], degree: int, knots: Sequence[float], u: float) -> Point2D:
    if not control_points:
        return Point2D(0.0, 0.0)

    degree = clamp_degree(degree, len(control_points))
    row = basis_row(u, len(control_points), degree, knots)
    x = sum(b * p.x for b, p in zip(row, control_points))
    y = sum(b * p.y for b, p in zip(row, control_points))
    return Point2D(x, y)


def sample_curve(
    control_points: Sequence[Point2D],
    degree: int,
    knots: Sequence[float] | None = None,
    samples: int = 240,
) -> List[Point2D]:
    if len(control_points) < 2:
        return list(control_points)

    degree = clamp_degree(degree, len(control_points))
    if knots is None:
        knots = generate_clamped_knots(len(control_points), degree)
    if not knots:
        return list(control_points)

    count = max(2, int(samples))
    return [evaluate_curve(control_points, degree, knots, i / (count - 1)) for i in range(count)]


def evaluate_surface(
    grid: Sequence[Sequence[Point3D]],
    degree_u: int,
    degree_v: int,
    knots_u: Sequence[float],
    knots_v: Sequence[float],
    u: float,
    v: float,
) -> Point3D:
    if not grid or not grid[0]:
        return Point3D(0.0, 0.0, 0.0)

    count_u = len(grid)
    count_v = len(grid[0])
    row_u = basis_row(u, count_u, degree_u, knots_u)
    row_v = basis_row(v, count_v, degree_v, knots_v)

    x = y = z = 0.0
    for i in range(count_u):
        for j in range(count_v):
            b = row_u[i] * row_v[j]
            p = grid[i][j]
            x += b * p.x
            y += b * p.y
            z += b * p.z
    return Point3D(x, y, z)


def chord_length_parameters(points: Sequence[Point2D]) -> List[float]:
    if len(points) <= 1:
        return [0.0] * len(points)

    distances = [0.0]
    total = 0.0
    for prev, curr in zip(points, points[1:]):
        total += hypot(curr.x - prev.x, curr.y - prev.y)
        distances.append(total)

    if total <= 1e-12:
        last = len(points) - 1
        return [i / last for i in range(len(points))]
    return [d / total for d in distances]


def solve_linear_system(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> List[float]:
    n = len(rhs)
    a = [list(row) + [float(rhs[i])] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-10:
            a[pivot][col] = 1e-10
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]

        pivot_value = a[col][col]
        for row in range(col + 1, n):
            factor = a[row][col] / pivot_value
            if abs(factor) <= 1e-15:
                continue
            for k in range(col, n + 1):
                a[row][k] -= factor * a[col][k]

    x = [0.0] * n
    for row in range(n - 1, -1, -1):
        value = a[row][n]
        for col in range(row + 1, n):
            value -= a[row][col] * x[col]
        denom = a[row][row]
        x[row] = value / denom if abs(denom) > 1e-12 else 0.0
    return x


def least_squares_approximation(
    data_points: Sequence[Point2D],
    degree: int = 3,
    control_count: int = 18,
    endpoint_weight: float = 20.0,
    regularization: float = 1e-8,
) -> BSplineFit:
    if len(data_points) < 2:
        raise ValueError("Can it nhat 2 diem du lieu de tai tao B-spline.")

    control_count = max(2, min(int(control_count), len(data_points)))
    degree = clamp_degree(degree, control_count)
    parameters = chord_length_parameters(data_points)
    knots = generate_averaged_knots(parameters, control_count, degree)

    normal = [[0.0 for _ in range(control_count)] for _ in range(control_count)]
    bx = [0.0 for _ in range(control_count)]
    by = [0.0 for _ in range(control_count)]

    for idx, (u, point) in enumerate(zip(parameters, data_points)):
        weight = endpoint_weight if idx == 0 or idx == len(data_points) - 1 else 1.0
        row = basis_row(u, control_count, degree, knots)
        for i in range(control_count):
            bi = row[i] * weight
            bx[i] += bi * point.x
            by[i] += bi * point.y
            for j in range(control_count):
                normal[i][j] += bi * row[j]

    for i in range(control_count):
        normal[i][i] += regularization

    xs = solve_linear_system(normal, bx)
    ys = solve_linear_system(normal, by)
    controls = [Point2D(x, y) for x, y in zip(xs, ys)]
    return BSplineFit(degree=degree, knots=knots, control_points=controls, parameters=parameters)


def moving_average(points: Sequence[Point2D], radius: int = 2) -> List[Point2D]:
    if radius <= 0 or len(points) < 3:
        return list(points)

    result: List[Point2D] = []
    for i in range(len(points)):
        lo = max(0, i - radius)
        hi = min(len(points), i + radius + 1)
        segment = points[lo:hi]
        result.append(
            Point2D(
                sum(p.x for p in segment) / len(segment),
                sum(p.y for p in segment) / len(segment),
            )
        )
    return result


def _perpendicular_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    denom = hypot(dx, dy)
    if denom <= 1e-12:
        return hypot(point.x - start.x, point.y - start.y)
    return abs(dy * point.x - dx * point.y + end.x * start.y - end.y * start.x) / denom


def ramer_douglas_peucker(points: Sequence[Point2D], epsilon: float) -> List[Point2D]:
    if epsilon <= 0.0 or len(points) < 3:
        return list(points)

    max_dist = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        dist = _perpendicular_distance(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            index = i

    if max_dist > epsilon:
        left = ramer_douglas_peucker(points[: index + 1], epsilon)
        right = ramer_douglas_peucker(points[index:], epsilon)
        return left[:-1] + right
    return [points[0], points[-1]]
