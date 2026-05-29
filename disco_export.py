from __future__ import annotations

from pathlib import Path
from typing import Sequence

from bspline_math import Point2D, generate_clamped_knots


def _curve_bbox(curves: Sequence[Sequence[Point2D]]) -> tuple[float, float, float, float] | None:
    points = [point for curve in curves for point in curve]
    if not points:
        return None
    return (
        min(point.x for point in points),
        min(point.y for point in points),
        max(point.x for point in points),
        max(point.y for point in points),
    )


def _normalise_curves_for_disco(curves: Sequence[Sequence[Point2D]], target_span: float = 160.0) -> list[list[Point2D]]:
    bbox = _curve_bbox(curves)
    if bbox is None:
        return [list(curve) for curve in curves]
    min_x, min_y, max_x, max_y = bbox
    span = max(max_x - min_x, max_y - min_y, 1.0)
    scale = target_span / span
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    normalised: list[list[Point2D]] = []
    for curve in curves:
        normalised.append([
            Point2D((point.x - center_x) * scale, (point.y - center_y) * scale)
            for point in curve
        ])
    return normalised


def export_bsplinecurve_dat(
    path: str | Path,
    control_points: Sequence[Point2D],
    degree: int,
    knots: Sequence[float] | None = None,
    normalise_for_disco: bool = True,
) -> None:
    if not control_points:
        raise ValueError("Khong co diem dieu khien de xuat bsplinecurve.dat.")

    if knots is None:
        knots = generate_clamped_knots(len(control_points), degree)
    curves = _normalise_curves_for_disco([control_points]) if normalise_for_disco else [list(control_points)]

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        _write_disco_curve_block(file, curves[0], degree, knots)


def export_bsplinecurves_dat(
    path: str | Path,
    curves: Sequence[Sequence[Point2D]],
    degrees: Sequence[int],
    knots_list: Sequence[Sequence[float]],
    normalise_for_disco: bool = True,
) -> None:
    valid = [
        (list(points), int(degree), list(knots))
        for points, degree, knots in zip(curves, degrees, knots_list)
        if points
    ]
    if not valid:
        raise ValueError("Khong co duong cong hop le de xuat bsplinecurve.dat.")

    export_curves = [item[0] for item in valid]
    if normalise_for_disco:
        export_curves = _normalise_curves_for_disco(export_curves)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        for index, ((points, degree, knots), export_points) in enumerate(zip(valid, export_curves)):
            if index:
                file.write("\n")
            _write_disco_curve_block(file, export_points, degree, knots)


def _write_disco_curve_block(file, control_points: Sequence[Point2D], degree: int, knots: Sequence[float]) -> None:
    # Exact block shape used by DUTModeling/DISCO sample files.
    file.write("=============\n\n")
    file.write("[BSPLINECURVE]\n\n\n")
    file.write(f"{len(control_points)}, {int(degree)}, 1 // UNum, UDegree, UKnotType\n\n\n")
    file.write("// Control Points\n\n")
    for point in control_points:
        file.write(f"{point.x:.3f} {point.y:.3f} 0.000 1.000 0\n\n")
    file.write("// UKnot Vector\n\n")
    for knot in knots:
        file.write(f"{float(knot):.3f}\n\n")


def export_readable_report(
    path: str | Path,
    control_points: Sequence[Point2D],
    degree: int,
    knots: Sequence[float],
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write("# B-spline curve data\n")
        file.write(f"Unum = {len(control_points)}\n")
        file.write(f"Udegree = {int(degree)}\n")
        file.write("Uknot = " + " ".join(f"{k:.12g}" for k in knots) + "\n")
        file.write("P4:\n")
        for i, point in enumerate(control_points):
            file.write(f"P4[{i}] = ({point.x:.12g}, {point.y:.12g}, 0, 1)\n")
