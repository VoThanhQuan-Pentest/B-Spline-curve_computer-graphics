from __future__ import annotations

from pathlib import Path
from typing import Sequence

from bspline_math import Point2D, generate_clamped_knots


def export_bsplinecurve_dat(
    path: str | Path,
    control_points: Sequence[Point2D],
    degree: int,
    knots: Sequence[float] | None = None,
) -> None:
    if not control_points:
        raise ValueError("Khong co diem dieu khien de xuat bsplinecurve.dat.")

    if knots is None:
        knots = generate_clamped_knots(len(control_points), degree)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        # DUTMod/DISCO teaching format used by this project:
        # Unum, Udegree, Uknot vector, then P4 control points (x y z w).
        file.write(f"{len(control_points)}\n")
        file.write(f"{int(degree)}\n")
        file.write(" ".join(f"{k:.12g}" for k in knots) + "\n")
        for point in control_points:
            file.write(f"{point.x:.12g} {point.y:.12g} 0 1\n")


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
