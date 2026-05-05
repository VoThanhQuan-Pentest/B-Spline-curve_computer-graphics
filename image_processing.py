from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import struct
import tkinter as tk
from typing import List, Sequence

from bspline_math import Point2D, moving_average, ramer_douglas_peucker

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


@dataclass
class PixelExtractionInfo:
    source_path: str
    width: int
    height: int
    threshold: int
    auto_threshold: bool
    raw_foreground_count: int
    filtered_foreground_count: int
    output_point_count: int
    min_component_area: int
    components_kept: int
    components_removed: int
    bbox: tuple[float, float, float, float] | None
    reconstruction_mode: str = "outline"
    quality: str = "balanced"


@dataclass
class PixelExtractionResult:
    points: List[Point2D]
    strokes: List[List[Point2D]]
    info: PixelExtractionInfo


def read_pixel_points(path: str | Path) -> List[Point2D]:
    points: List[Point2D] = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                points.append(Point2D(float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return points


def write_pixel_points(path: str | Path, points: Sequence[Point2D], comments: Sequence[str] | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        if comments:
            for comment in comments:
                file.write(f"# {comment}\n")
        for point in points:
            file.write(f"{point.x:.6f} {point.y:.6f}\n")


def _rgb_to_gray(red: int, green: int, blue: int) -> int:
    return int(0.299 * red + 0.587 * green + 0.114 * blue)


def _photo_value_to_gray(value: object) -> int:
    if isinstance(value, tuple):
        red, green, blue = value[:3]
        return _rgb_to_gray(int(red), int(green), int(blue))

    text = str(value)
    if text.startswith("#") and len(text) >= 7:
        red = int(text[1:3], 16)
        green = int(text[3:5], 16)
        blue = int(text[5:7], 16)
        return _rgb_to_gray(red, green, blue)

    parts = text.replace(",", " ").split()
    if len(parts) >= 3:
        return _rgb_to_gray(int(parts[0]), int(parts[1]), int(parts[2]))

    number = int(float(text))
    return max(0, min(255, number))


def _load_with_tk(path: Path) -> tuple[int, int, List[int]]:
    root = tk._default_root
    owns_root = False
    if root is None:
        root = tk.Tk()
        root.withdraw()
        owns_root = True

    try:
        image = tk.PhotoImage(file=str(path))
        width = image.width()
        height = image.height()
        values = [_photo_value_to_gray(image.get(x, y)) for y in range(height) for x in range(width)]
        return width, height, values
    finally:
        if owns_root:
            root.destroy()


def _load_bmp(path: Path) -> tuple[int, int, List[int]]:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("Khong phai file BMP hop le.")

    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    width = struct.unpack_from("<i", data, 18)[0]
    raw_height = struct.unpack_from("<i", data, 22)[0]
    planes = struct.unpack_from("<H", data, 26)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]

    if planes != 1 or compression != 0:
        raise ValueError("Chi ho tro BMP khong nen BI_RGB.")
    if width <= 0 or raw_height == 0:
        raise ValueError("Kich thuoc BMP khong hop le.")

    height = abs(raw_height)
    top_down = raw_height < 0
    row_stride = ((bpp * width + 31) // 32) * 4
    values = [255 for _ in range(width * height)]

    palette: list[tuple[int, int, int]] = []
    if bpp == 8:
        palette_offset = 14 + dib_size
        palette_count = min(256, (pixel_offset - palette_offset) // 4)
        for i in range(palette_count):
            blue, green, red, _reserved = struct.unpack_from("<BBBB", data, palette_offset + i * 4)
            palette.append((red, green, blue))
    elif bpp not in (24, 32):
        raise ValueError("Chi ho tro BMP 8-bit, 24-bit hoac 32-bit.")

    for y in range(height):
        stored_y = y if top_down else height - 1 - y
        row_start = pixel_offset + stored_y * row_stride
        for x in range(width):
            if bpp == 24:
                blue, green, red = struct.unpack_from("<BBB", data, row_start + x * 3)
            elif bpp == 32:
                blue, green, red, _alpha = struct.unpack_from("<BBBB", data, row_start + x * 4)
            else:
                index = data[row_start + x]
                red, green, blue = palette[index] if index < len(palette) else (index, index, index)
            values[y * width + x] = _rgb_to_gray(red, green, blue)

    return width, height, values


def _load_grayscale_image(image_path: str | Path) -> tuple[int, int, List[int]]:
    path = Path(image_path)
    if path.suffix.lower() == ".bmp":
        return _load_bmp(path)
    try:
        return _load_with_tk(path)
    except tk.TclError as exc:
        raise ValueError(
            "Khong doc duoc anh bang Python thuan. Hay dung PNG/GIF/PPM/PGM/BMP, "
            "hoac chuyen JPG/JPEG sang PNG truoc."
        ) from exc


def _median_filter_3x3(width: int, height: int, values: Sequence[int]) -> List[int]:
    result = list(values)
    for y in range(height):
        for x in range(width):
            samples = []
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= height:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < width:
                        samples.append(values[yy * width + xx])
            samples.sort()
            result[y * width + x] = samples[len(samples) // 2]
    return result


def _histogram(values: Sequence[int]) -> List[int]:
    hist = [0] * 256
    for value in values:
        hist[max(0, min(255, int(value)))] += 1
    return hist


def _otsu_threshold(hist: Sequence[int], total: int) -> int:
    if total <= 0:
        return 128

    sum_total = sum(i * count for i, count in enumerate(hist))
    sum_background = 0.0
    weight_background = 0
    best_variance = -1.0
    best_threshold = 128

    for threshold, count in enumerate(hist):
        weight_background += count
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break

        sum_background += threshold * count
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        variance = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold

    return best_threshold


def _percentile_threshold(hist: Sequence[int], total: int, percentile: float) -> int:
    target = max(1, int(total * percentile))
    cumulative = 0
    for value, count in enumerate(hist):
        cumulative += count
        if cumulative >= target:
            return value
    return 255


def _auto_dark_threshold(values: Sequence[int]) -> int:
    hist = _histogram(values)
    total = len(values)
    otsu = _otsu_threshold(hist, total)
    dark_percentile = _percentile_threshold(hist, total, 0.015)

    # Photos of paper often have a textured grey background. Otsu can drift too
    # high and select the paper texture, so cap it with a dark-percentile estimate.
    conservative = dark_percentile + 14
    return max(12, min(otsu, conservative, 170))


def _foreground_indices(values: Sequence[int], threshold: int, use_dark_as_foreground: bool) -> List[int]:
    if use_dark_as_foreground:
        return [idx for idx, value in enumerate(values) if value < threshold]
    return [idx for idx, value in enumerate(values) if value >= threshold]


def _filter_connected_components(
    width: int,
    height: int,
    indices: Sequence[int],
    min_component_area: int,
) -> tuple[List[int], List[List[int]], int]:
    if min_component_area <= 1:
        all_indices = list(indices)
        return all_indices, [all_indices] if all_indices else [], 0

    remaining = set(indices)
    components: list[tuple[List[int], int, int, int, int, int, float, float]] = []
    removed_count = 0
    neighbor_offsets = (
        (-1, -1), (0, -1), (1, -1),
        (-1, 0),           (1, 0),
        (-1, 1),  (0, 1),  (1, 1),
    )

    while remaining:
        start = remaining.pop()
        component = [start]
        stack = [start]

        while stack:
            current = stack.pop()
            x = current % width
            y = current // width
            for dx, dy in neighbor_offsets:
                nx = x + dx
                ny = y + dy
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    continue
                neighbor = ny * width + nx
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.append(neighbor)
                    stack.append(neighbor)

        if len(component) < min_component_area:
            removed_count += 1
            continue

        xs = [idx % width for idx in component]
        ys = [idx // width for idx in component]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        center_x = (min_x + max_x) * 0.5
        center_y = (min_y + max_y) * 0.5
        components.append((component, len(component), min_x, min_y, max_x, max_y, center_x, center_y))

    if len(components) > 2:
        center_y = _weighted_median([(comp[7], comp[1]) for comp in components])
        center_x = _weighted_median([(comp[6], comp[1]) for comp in components])
        y_band = max(height * 0.18, 120.0)
        x_band = max(width * 0.45, 250.0)
        clustered = [
            comp
            for comp in components
            if abs(comp[7] - center_y) <= y_band and abs(comp[6] - center_x) <= x_band
        ]
        clustered_area = sum(comp[1] for comp in clustered)
        total_area = sum(comp[1] for comp in components)
        if clustered and clustered_area >= total_area * 0.35:
            removed_count += len(components) - len(clustered)
            components = clustered

    kept: List[int] = []
    kept_components: List[List[int]] = []
    components.sort(key=lambda comp: (comp[2], comp[3]))
    for component, *_stats in components:
        kept.extend(component)
        kept_components.append(sorted(component))

    kept.sort()
    return kept, kept_components, removed_count


def _thin_foreground(width: int, height: int, indices: Sequence[int], max_iterations: int = 80) -> List[int]:
    pixels = set(indices)
    if not pixels:
        return []

    def value(x: int, y: int) -> int:
        return 1 if 0 <= x < width and 0 <= y < height and (y * width + x) in pixels else 0

    def neighbors(idx: int) -> tuple[int, int, int, int, int, int, int, int]:
        x = idx % width
        y = idx // width
        return (
            value(x, y - 1),      # p2
            value(x + 1, y - 1),  # p3
            value(x + 1, y),      # p4
            value(x + 1, y + 1),  # p5
            value(x, y + 1),      # p6
            value(x - 1, y + 1),  # p7
            value(x - 1, y),      # p8
            value(x - 1, y - 1),  # p9
        )

    for _iteration in range(max_iterations):
        removed_any = False
        for step in (0, 1):
            to_remove: list[int] = []
            for idx in list(pixels):
                n = neighbors(idx)
                neighbor_count = sum(n)
                if neighbor_count < 2 or neighbor_count > 6:
                    continue
                transitions = sum(1 for a, b in zip(n, n[1:] + n[:1]) if a == 0 and b == 1)
                if transitions != 1:
                    continue
                p2, _p3, p4, _p5, p6, _p7, p8, _p9 = n
                if step == 0:
                    if p2 * p4 * p6 != 0 or p4 * p6 * p8 != 0:
                        continue
                else:
                    if p2 * p4 * p8 != 0 or p2 * p6 * p8 != 0:
                        continue
                to_remove.append(idx)

            if to_remove:
                pixels.difference_update(to_remove)
                removed_any = True
        if not removed_any:
            break

    return sorted(pixels)


def _boundary_indices(width: int, height: int, indices: Sequence[int]) -> List[int]:
    foreground = set(indices)
    boundary: List[int] = []
    for idx in foreground:
        x = idx % width
        y = idx // width
        if (
            x == 0 or x == width - 1 or y == 0 or y == height - 1
            or (idx - 1) not in foreground
            or (idx + 1) not in foreground
            or (idx - width) not in foreground
            or (idx + width) not in foreground
        ):
            boundary.append(idx)
    boundary.sort()
    return boundary


def _weighted_median(values_and_weights: Sequence[tuple[float, int]]) -> float:
    if not values_and_weights:
        return 0.0
    ordered = sorted(values_and_weights, key=lambda item: item[0])
    total = sum(weight for _value, weight in ordered)
    midpoint = total * 0.5
    running = 0
    for value, weight in ordered:
        running += weight
        if running >= midpoint:
            return value
    return ordered[-1][0]


def _normalise_quality(value: str | None) -> str:
    quality = (value or "balanced").lower().strip()
    if quality not in {"fast", "balanced", "high"}:
        return "balanced"
    return quality


def _smooth_closed_points(points: Sequence[Point2D], radius: int) -> List[Point2D]:
    if radius <= 0 or len(points) < 4:
        return list(points)
    count = len(points)
    smoothed: List[Point2D] = []
    for index in range(count):
        sx = 0.0
        sy = 0.0
        samples = 0
        for offset in range(-radius, radius + 1):
            point = points[(index + offset) % count]
            sx += point.x
            sy += point.y
            samples += 1
        smoothed.append(Point2D(sx / samples, sy / samples))
    return smoothed


def _preprocess_for_threshold(gray, quality: str):
    if cv2 is None or np is None:
        return gray
    if quality == "fast":
        return cv2.medianBlur(gray, 3)

    work = cv2.medianBlur(gray, 3)
    height, width = work.shape[:2]
    sigma = max(18.0, min(width, height) / (22.0 if quality == "balanced" else 18.0))
    background = cv2.GaussianBlur(work, (0, 0), sigmaX=sigma, sigmaY=sigma)
    background = np.maximum(background, 1)
    normalised = cv2.divide(work, background, scale=255)
    normalised = cv2.normalize(normalised, None, 0, 255, cv2.NORM_MINMAX)
    normalised = cv2.medianBlur(normalised.astype(np.uint8), 3)
    if quality == "high":
        clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
        normalised = clahe.apply(normalised)
    return normalised


def _threshold_text_mask(gray, threshold: int | None, invert: bool | None, auto_threshold: bool, quality: str):
    work = _preprocess_for_threshold(gray, quality)
    if auto_threshold or threshold is None:
        threshold_used, mask = cv2.threshold(work, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        threshold_used = int(threshold_used)
    else:
        threshold_used = max(0, min(255, int(threshold)))
        if invert:
            mask = np.where(work >= threshold_used, 255, 0).astype(np.uint8)
        else:
            mask = np.where(work < threshold_used, 255, 0).astype(np.uint8)

    raw_count = int(mask.sum() // 255)
    kernel = np.ones((2, 2), np.uint8)
    if quality == "high":
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    else:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return threshold_used, mask, raw_count


def _opencv_component_mask(mask, min_component_area: int, quality: str):
    height, width = mask.shape[:2]
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    min_area = max(3, int(min_component_area))
    items = []
    removed = 0
    min_size = 2 if quality == "high" else 3
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area or w < min_size or h < min_size:
            removed += 1
            continue
        cx, cy = centroids[label]
        items.append((label, area, x, y, w, h, float(cx), float(cy)))

    if len(items) > 2:
        total_area = sum(item[1] for item in items)
        core: list[tuple[int, int, int, int, int, int, float, float]] = []
        running_area = 0
        for item in sorted(items, key=lambda current: current[1], reverse=True):
            core.append(item)
            running_area += item[1]
            if len(core) >= 3 and running_area >= total_area * 0.80:
                break
        if core:
            left = min(item[2] for item in core)
            top = min(item[3] for item in core)
            right = max(item[2] + item[4] for item in core)
            bottom = max(item[3] + item[5] for item in core)
            margin_x = max(24.0, (right - left) * (0.10 if quality != "fast" else 0.14))
            margin_y = max(24.0, (bottom - top) * (0.60 if quality == "high" else 0.48))
            crop_left = max(0.0, left - margin_x)
            crop_top = max(0.0, top - margin_y)
            crop_right = min(float(width), right + margin_x)
            crop_bottom = min(float(height), bottom + margin_y)
            cropped = [
                item
                for item in items
                if crop_left <= item[6] <= crop_right and crop_top <= item[7] <= crop_bottom
            ]
            cropped_area = sum(item[1] for item in cropped)
            if cropped and cropped_area >= total_area * 0.55:
                removed += len(items) - len(cropped)
                items = cropped

    filtered = np.zeros_like(mask)
    for label, *_stats in items:
        filtered[labels == label] = 255
    return filtered, items, removed


def _mask_indices(mask) -> List[int]:
    ys, xs = np.where(mask > 0)
    width = mask.shape[1]
    return [int(y) * width + int(x) for y, x in zip(ys, xs)]


def _indices_to_points(width: int, height: int, indices: Sequence[int]) -> List[Point2D]:
    return [Point2D(float(idx % width), float(height - 1 - idx // width)) for idx in indices]


def _indices_to_ordered_strokes(
    width: int,
    height: int,
    components: Sequence[Sequence[int]],
    max_points_per_stroke: int,
    smooth_radius: int,
    simplify_epsilon: float,
    order_mode: str = "nearest",
) -> List[List[Point2D]]:
    strokes: List[List[Point2D]] = []
    for component in components:
        points = _indices_to_points(width, height, component)
        if len(points) < 2:
            continue
        if order_mode == "angle":
            ordered = _angle_order_points(points)
            ordered = _limit_ordered_points(ordered, max_points=max_points_per_stroke)
        else:
            ordered = _nearest_neighbor_order(points, max_points=max_points_per_stroke)
        if smooth_radius > 0 and order_mode != "angle":
            ordered = moving_average(ordered, radius=smooth_radius)
        if simplify_epsilon > 0:
            ordered = ramer_douglas_peucker(ordered, simplify_epsilon)
        if len(ordered) >= 2:
            strokes.append(ordered)
    return strokes


def _angle_order_points(points: Sequence[Point2D]) -> List[Point2D]:
    if len(points) < 3:
        return list(points)

    cx = sum(point.x for point in points) / len(points)
    cy = sum(point.y for point in points) / len(points)
    ordered = sorted(points, key=lambda point: math.atan2(point.y - cy, point.x - cx))
    start_index = min(range(len(ordered)), key=lambda idx: (ordered[idx].x, -ordered[idx].y))
    return ordered[start_index:] + ordered[:start_index]


def _limit_ordered_points(points: Sequence[Point2D], max_points: int) -> List[Point2D]:
    if len(points) <= max_points:
        return list(points)
    max_points = max(2, int(max_points))
    last = len(points) - 1
    return [points[round(i * last / (max_points - 1))] for i in range(max_points)]


def _extract_handwriting_pixels_opencv(
    image_path: str | Path,
    threshold: int | None,
    max_points: int,
    invert: bool | None,
    auto_threshold: bool,
    min_component_area: int,
    reconstruction_mode: str,
    quality: str,
    return_info: bool,
) -> List[Point2D] | PixelExtractionResult:
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV/NumPy chua duoc cai dat.")

    path = Path(image_path)
    data = np.fromfile(str(path), dtype=np.uint8)
    gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"Khong doc duoc anh: {image_path}")

    height, width = gray.shape[:2]
    max_points = max(100, int(max_points))
    quality = _normalise_quality(quality)
    threshold_used, mask, raw_count = _threshold_text_mask(gray, threshold, invert, auto_threshold, quality)
    filtered_mask, component_items, removed_components = _opencv_component_mask(
        mask,
        min_component_area=max(1, int(min_component_area)),
        quality=quality,
    )

    strokes: List[List[Point2D]] = []
    if reconstruction_mode == "centerline":
        skeleton = _thin_foreground(
            width,
            height,
            _mask_indices(filtered_mask),
            max_iterations=90 if quality == "high" else 70,
        )
        skeleton, skeleton_components, skeleton_removed = _filter_connected_components(
            width,
            height,
            skeleton,
            min_component_area=max(2, int(min_component_area) // 2),
        )
        removed_components += skeleton_removed
        max_points_per_stroke = max(12, max_points // max(1, len(skeleton_components)))
        strokes = _indices_to_ordered_strokes(
            width,
            height,
            skeleton_components,
            max_points_per_stroke=max_points_per_stroke,
            smooth_radius=2 if quality == "high" else 1,
            simplify_epsilon=0.3 if quality == "high" else 0.55,
            order_mode="nearest",
        )
    else:
        contours, _hierarchy = cv2.findContours(filtered_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        contour_items = []
        min_area = max(2.0, float(min_component_area) * 0.5)
        for contour in contours:
            area = float(cv2.contourArea(contour))
            x, y, w, h = cv2.boundingRect(contour)
            if area < min_area or w < 2 or h < 2 or len(contour) < 4:
                removed_components += 1
                continue
            contour_items.append((contour, area, x, y, w, h))

        contour_items.sort(key=lambda item: (item[2], item[3]))
        total_contour_points = max(1, sum(len(item[0]) for item in contour_items))
        smooth_radius = 3 if quality == "high" else (2 if quality == "balanced" else 1)
        for contour, _area, _x, _y, _w, _h in contour_items:
            contour_points = contour[:, 0, :]
            points = [Point2D(float(x), float(height - 1 - y)) for x, y in contour_points]
            points = _smooth_closed_points(points, radius=smooth_radius)
            stroke_budget = max(18, int(max_points * (len(contour_points) / total_contour_points)))
            points = _limit_ordered_points(points, max_points=stroke_budget)
            if len(points) >= 4:
                strokes.append(points)

    ordered = [point for stroke in strokes for point in stroke]
    if len(ordered) > max_points:
        ordered = _limit_ordered_points(ordered, max_points=max_points)

    info = PixelExtractionInfo(
        source_path=str(image_path),
        width=width,
        height=height,
        threshold=int(threshold_used),
        auto_threshold=bool(auto_threshold or threshold is None),
        raw_foreground_count=raw_count,
        filtered_foreground_count=sum(len(stroke) for stroke in strokes),
        output_point_count=len(ordered),
        min_component_area=max(1, int(min_component_area)),
        components_kept=len(component_items),
        components_removed=removed_components,
        bbox=_point_bbox(ordered),
        reconstruction_mode=reconstruction_mode,
        quality=quality,
    )
    if return_info:
        return PixelExtractionResult(points=ordered, strokes=strokes, info=info)
    return ordered


def _point_bbox(points: Sequence[Point2D]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    return (
        min(point.x for point in points),
        min(point.y for point in points),
        max(point.x for point in points),
        max(point.y for point in points),
    )


def _nearest_neighbor_order(points: Sequence[Point2D], max_points: int) -> List[Point2D]:
    if not points:
        return []

    if len(points) > max_points:
        stride = max(1, len(points) // max_points)
        points = points[::stride]

    remaining = set(range(len(points)))
    current = min(remaining, key=lambda i: (points[i].x, -points[i].y))
    ordered = [points[current]]
    remaining.remove(current)

    while remaining:
        cx, cy = points[current].x, points[current].y
        current = min(
            remaining,
            key=lambda i: (points[i].x - cx) * (points[i].x - cx) + (points[i].y - cy) * (points[i].y - cy),
        )
        ordered.append(points[current])
        remaining.remove(current)

    return ordered


def extract_handwriting_pixels(
    image_path: str | Path,
    threshold: int | None = 180,
    max_points: int = 2400,
    median_filter: bool = True,
    invert: bool | None = None,
    auto_threshold: bool = False,
    min_component_area: int = 8,
    skeletonize: bool = True,
    reconstruction_mode: str = "outline",
    quality: str = "balanced",
    smooth_radius: int = 1,
    simplify_epsilon: float = 0.75,
    return_info: bool = False,
) -> List[Point2D] | PixelExtractionResult:
    mode = reconstruction_mode.lower().strip()
    if mode not in {"outline", "centerline"}:
        mode = "outline"
    quality = _normalise_quality(quality)

    if cv2 is not None and np is not None:
        return _extract_handwriting_pixels_opencv(
            image_path=image_path,
            threshold=threshold,
            max_points=max_points,
            invert=invert,
            auto_threshold=auto_threshold,
            min_component_area=min_component_area,
            reconstruction_mode=mode,
            quality=quality,
            return_info=return_info,
        )

    width, height, values = _load_grayscale_image(image_path)
    if median_filter:
        values = _median_filter_3x3(width, height, values)

    threshold_used = _auto_dark_threshold(values) if auto_threshold or threshold is None else int(threshold)
    threshold_used = max(0, min(255, threshold_used))

    dark_count = 0
    light_count = 0
    for value in values:
        if value < threshold_used:
            dark_count += 1
        else:
            light_count += 1

    if invert is None:
        use_dark_as_foreground = dark_count <= light_count
    else:
        use_dark_as_foreground = not invert

    raw_indices = _foreground_indices(values, threshold_used, use_dark_as_foreground)
    filtered_indices, component_indices, removed_components = _filter_connected_components(
        width,
        height,
        raw_indices,
        min_component_area=max(1, int(min_component_area)),
    )
    if mode == "outline":
        curve_indices = _boundary_indices(width, height, filtered_indices)
    else:
        curve_indices = _thin_foreground(width, height, filtered_indices) if skeletonize else filtered_indices

    curve_indices, curve_component_indices, _curve_removed = _filter_connected_components(
        width,
        height,
        curve_indices,
        min_component_area=max(2, int(min_component_area) // 2 if mode == "centerline" else int(min_component_area)),
    )
    raw = _indices_to_points(width, height, curve_indices)
    stroke_budget = max(20, int(max_points))
    max_points_per_stroke = max(12, stroke_budget // max(1, len(curve_component_indices)))
    strokes = _indices_to_ordered_strokes(
        width,
        height,
        curve_component_indices,
        max_points_per_stroke=max_points_per_stroke,
        smooth_radius=0 if mode == "outline" else smooth_radius,
        simplify_epsilon=0.0,
        order_mode="angle" if mode == "outline" else "nearest",
    )

    ordered = _nearest_neighbor_order(raw, max_points=max_points)
    if smooth_radius > 0:
        ordered = moving_average(ordered, radius=smooth_radius)
    if simplify_epsilon > 0:
        ordered = ramer_douglas_peucker(ordered, simplify_epsilon)

    info = PixelExtractionInfo(
        source_path=str(image_path),
        width=width,
        height=height,
        threshold=threshold_used,
        auto_threshold=bool(auto_threshold or threshold is None),
        raw_foreground_count=len(raw_indices),
        filtered_foreground_count=len(curve_indices),
        output_point_count=len(ordered),
        min_component_area=max(1, int(min_component_area)),
        components_kept=len(curve_component_indices),
        components_removed=removed_components,
        bbox=_point_bbox(raw),
        reconstruction_mode=mode,
        quality=quality,
    )
    if return_info:
        return PixelExtractionResult(points=ordered, strokes=strokes, info=info)
    return ordered
