from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from bspline_math import (
    Point2D,
    Point3D,
    BSplineFit,
    clamp_degree,
    evaluate_surface,
    generate_clamped_knots,
    least_squares_approximation,
    sample_curve,
)
from disco_export import export_bsplinecurve_dat, export_readable_report
from image_processing import PixelExtractionInfo, PixelExtractionResult, extract_handwriting_pixels, read_pixel_points, write_pixel_points


APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "output"


class ImageImportOptionsDialog:
    def __init__(self, parent: tk.Tk) -> None:
        self.result: dict[str, int | bool | str] | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("Import Image Options")
        self.window.transient(parent)
        self.window.resizable(False, False)

        self.auto_threshold = tk.BooleanVar(value=True)
        self.manual_threshold = tk.IntVar(value=140)
        self.max_points = tk.IntVar(value=9000)
        self.min_noise_area = tk.IntVar(value=8)
        self.reconstruction_mode = tk.StringVar(value="outline")
        self.quality = tk.StringVar(value="high")

        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Checkbutton(
            frame,
            text="Auto threshold",
            variable=self.auto_threshold,
            command=self._sync_state,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Manual threshold").grid(row=1, column=0, sticky="w", pady=3)
        self.threshold_spin = ttk.Spinbox(frame, from_=0, to=255, textvariable=self.manual_threshold, width=8)
        self.threshold_spin.grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Label(frame, text="Max points").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Spinbox(frame, from_=100, to=50000, increment=100, textvariable=self.max_points, width=8).grid(row=2, column=1, sticky="ew", pady=3)

        ttk.Label(frame, text="Min noise area").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(frame, from_=1, to=200, textvariable=self.min_noise_area, width=8).grid(row=3, column=1, sticky="ew", pady=3)

        ttk.Label(frame, text="Quality").grid(row=4, column=0, sticky="w", pady=3)
        quality_box = ttk.Combobox(frame, textvariable=self.quality, values=("high", "balanced", "fast"), width=10, state="readonly")
        quality_box.grid(row=4, column=1, sticky="ew", pady=3)

        ttk.Label(frame, text="Reconstruction").grid(row=5, column=0, sticky="w", pady=3)
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Radiobutton(mode_frame, text="Outline", value="outline", variable=self.reconstruction_mode).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="Centerline", value="centerline", variable=self.reconstruction_mode).pack(side=tk.LEFT, padx=(8, 0))

        actions = ttk.Frame(frame)
        actions.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(actions, text="Import", command=self._ok).pack(side=tk.RIGHT)

        frame.columnconfigure(1, weight=1)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self._sync_state()
        self.window.grab_set()
        self.window.wait_window()

    def _sync_state(self) -> None:
        state = "disabled" if self.auto_threshold.get() else "normal"
        self.threshold_spin.configure(state=state)

    def _ok(self) -> None:
        self.result = {
            "auto_threshold": bool(self.auto_threshold.get()),
            "manual_threshold": max(0, min(255, int(self.manual_threshold.get()))),
            "max_points": max(100, int(self.max_points.get())),
            "min_noise_area": max(1, int(self.min_noise_area.get())),
            "reconstruction_mode": self.reconstruction_mode.get(),
            "quality": self.quality.get(),
        }
        self.window.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.window.destroy()


class BSplineApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("B-Spline Python - Handwriting Reconstruction")
        self.root.geometry("1120x760")

        self.mode = "2d"
        self.curves: list[list[Point2D]] = [[]]
        self.fit_points: list[Point2D] = []
        self.pixel_strokes: list[list[Point2D]] = []
        self.fit_result: BSplineFit | None = None
        self.fit_results: list[BSplineFit] = []
        self.pixel_info: PixelExtractionInfo | None = None
        self.pixel_source_label = ""

        self.degree = 3
        self.line_width = 3.5
        self.curve_color = "#111111"
        self.point_color = "#ff4545"
        self.bg_color = "#ffffff"

        self.show_polygon = tk.BooleanVar(value=True)
        self.show_points = tk.BooleanVar(value=True)
        self.show_surface = tk.BooleanVar(value=True)
        self.show_viewbar = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=False)
        self.show_grid = tk.BooleanVar(value=False)
        self.snap_to_grid = tk.BooleanVar(value=False)
        self.is_closed = tk.BooleanVar(value=False)
        self.is_symmetric = tk.BooleanVar(value=False)
        self.is_animating = tk.BooleanVar(value=False)
        self.show_fit_pixels = tk.BooleanVar(value=True)

        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.anim_t = 0.0

        self.selected_stroke = -1
        self.selected_point = -1
        self.drawing = False
        self.panning = False
        self.pending_draw_start: Point2D | None = None
        self.pending_draw_screen: tuple[float, float] | None = None
        self.last_mouse = (0.0, 0.0)
        self.show_help = False
        self.expanded_strokes: set[int] = set()
        self.viewbar_rows: list[tuple[str, int, int | None]] = []

        self.grid_u = 5
        self.grid_v = 5
        self.degree_u = 3
        self.degree_v = 3
        self.surface_grid = self._create_surface_grid()
        self.cam_rot_x = 30.0
        self.cam_rot_y = -45.0
        self.cam_dist = 1200.0
        self.cam_pan_x = 0.0
        self.cam_pan_y = 0.0
        self.selected_grid = (-1, -1)
        self.rotating_3d = False
        self.panning_3d = False

        self._build_menu()
        self._build_layout()
        self._bind_events()
        self.update_viewbar()
        self.root.after(16, self._timer)

    def _build_layout(self) -> None:
        self.container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.viewbar = ttk.Frame(self.container, width=205)
        self.container.add(self.viewbar, weight=0)
        ttk.Label(self.viewbar, text="ViewBar", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 3))

        list_frame = ttk.Frame(self.viewbar)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.listbox = tk.Listbox(list_frame, font=("Consolas", 9), activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind("<Double-Button-1>", self.on_viewbar_double_click)

        quick = ttk.Frame(self.viewbar)
        quick.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Checkbutton(quick, text="Pts", variable=self.show_points, command=self.redraw).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(quick, text="Poly", variable=self.show_polygon, command=self.redraw).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(quick, text="Grid", variable=self.show_grid, command=self.redraw).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(quick, text="Snap", variable=self.snap_to_grid, command=self.redraw).grid(row=1, column=1, sticky="w")

        actions = ttk.Frame(self.viewbar)
        actions.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(actions, text="Fit", command=self.fit_view).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(actions, text="Clear", command=self.clear).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        self.status = ttk.Label(self.viewbar, text="", anchor="w", wraplength=185)
        self.status.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.canvas = tk.Canvas(self.container, bg=self.bg_color, highlightthickness=0)
        self.container.add(self.canvas, weight=1)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.configure(menu=menubar)

        mode = tk.Menu(menubar, tearoff=False)
        mode.add_command(label="2D Curve Editor", command=lambda: self.set_mode("2d"))
        mode.add_command(label="3D Surface Editor", command=lambda: self.set_mode("3d"))
        menubar.add_cascade(label="Mode", menu=mode)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Load TXT Points...", command=self.load_points)
        file_menu.add_command(label="Save TXT Points...", command=self.save_points)
        file_menu.add_command(label="Save Canvas Image...", command=self.save_canvas_image)
        file_menu.add_separator()
        file_menu.add_command(label="Open Image -> diempixel.dat...", command=self.extract_pixels_from_image)
        file_menu.add_command(label="Load diempixel.dat...", command=self.load_pixel_dat)
        file_menu.add_command(label="Least-Square Reconstruction...", command=self.reconstruct_from_pixels)
        file_menu.add_command(label="Export bsplinecurve.dat...", command=self.export_bsplinecurve)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        edit = tk.Menu(menubar, tearoff=False)
        edit.add_command(label="Undo", command=self.undo)
        edit.add_command(label="Clear Canvas", command=self.clear)
        edit.add_command(label="Fit View", command=self.fit_view)
        menubar.add_cascade(label="Edit", menu=edit)

        view = tk.Menu(menubar, tearoff=False)
        for label, var in [
            ("Control Polygon", self.show_polygon),
            ("Control Points", self.show_points),
            ("3D Surface Mesh", self.show_surface),
            ("Toggle ViewBar", self.show_viewbar),
            ("Point Labels", self.show_labels),
            ("Show Grid", self.show_grid),
            ("Show Extracted Pixels", self.show_fit_pixels),
        ]:
            view.add_checkbutton(label=label, variable=var, command=self.on_view_option_changed)
        view.add_separator()
        for label, var in [
            ("Snap to Grid", self.snap_to_grid),
            ("Closed Curve", self.is_closed),
            ("Toggle Symmetry", self.is_symmetric),
            ("Toggle Animation", self.is_animating),
        ]:
            view.add_checkbutton(label=label, variable=var, command=self.redraw)
        menubar.add_cascade(label="View", menu=view)

        tools = tk.Menu(menubar, tearoff=False)
        tools.add_command(label="Select Color...", command=self.choose_color)
        tools.add_command(label="Select Line Width...", command=self.choose_width)
        menubar.add_cascade(label="Tools", menu=tools)

        spline = tk.Menu(menubar, tearoff=False)
        spline.add_command(label="Increase Degree (+1)", command=lambda: self.change_degree(1))
        spline.add_command(label="Decrease Degree (-1)", command=lambda: self.change_degree(-1))
        menubar.add_cascade(label="B-Spline", menu=spline)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Instructions", command=self.toggle_help)
        menubar.add_cascade(label="Help", menu=help_menu)

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<ButtonPress-2>", self.on_middle_down)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_down)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.root.bind("<Escape>", lambda _event: self.close_help_or_exit())

    def _create_surface_grid(self) -> list[list[Point3D]]:
        grid: list[list[Point3D]] = []
        for i in range(self.grid_u):
            row: list[Point3D] = []
            for j in range(self.grid_v):
                x = -400.0 + i * 800.0 / (self.grid_u - 1)
                z = -400.0 + j * 800.0 / (self.grid_v - 1)
                row.append(Point3D(x, 0.0, z))
            grid.append(row)
        return grid

    def on_view_option_changed(self) -> None:
        if self.show_viewbar.get():
            if str(self.viewbar) not in self.container.panes():
                self.container.insert(0, self.viewbar, weight=0)
        else:
            if str(self.viewbar) in self.container.panes():
                self.container.forget(self.viewbar)
        self.redraw()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update_viewbar()
        self.redraw()

    def clear(self) -> None:
        self.curves = [[]]
        self.fit_points = []
        self.pixel_strokes = []
        self.fit_result = None
        self.fit_results = []
        self.pixel_info = None
        self.pixel_source_label = ""
        self.expanded_strokes.clear()
        self.selected_stroke = -1
        self.selected_point = -1
        self.pending_draw_start = None
        self.pending_draw_screen = None
        self.drawing = False

        if self.mode == "3d":
            self.surface_grid = self._create_surface_grid()
            self.selected_grid = (-1, -1)
        self.update_viewbar()
        self.redraw()

    def undo(self) -> None:
        if self.mode != "2d" or not self.curves:
            return

        while self.curves and not self.curves[-1]:
            self.curves.pop()
        if self.curves:
            self.curves.pop()
        if not self.curves:
            self.curves = [[]]

        self.expanded_strokes = {idx for idx in self.expanded_strokes if idx < len(self.curves)}
        self.update_viewbar()
        self.redraw()

    def change_degree(self, delta: int) -> None:
        self.degree = max(1, min(8, self.degree + delta))
        self.redraw()

    def choose_color(self) -> None:
        result = colorchooser.askcolor(color=self.curve_color, title="Select B-spline color")
        if result and result[1]:
            self.curve_color = result[1]
            self.redraw()

    def choose_width(self) -> None:
        value = simpledialog.askfloat("Line width", "Nhap do day net:", initialvalue=self.line_width, minvalue=1.0, maxvalue=20.0)
        if value is not None:
            self.line_width = value
            self.redraw()

    def toggle_help(self) -> None:
        self.show_help = not self.show_help
        self.redraw()

    def close_help_or_exit(self) -> None:
        if self.show_help:
            self.show_help = False
            self.redraw()
        else:
            self.root.destroy()

    def current_curve(self) -> list[Point2D]:
        if not self.curves:
            self.curves.append([])
        return self.curves[-1]

    def screen_to_world(self, sx: float, sy: float) -> Point2D:
        height = max(1, self.canvas.winfo_height())
        return Point2D((sx - self.pan_x) / self.zoom, ((height - sy) - self.pan_y) / self.zoom)

    def world_to_screen(self, point: Point2D) -> tuple[float, float]:
        height = max(1, self.canvas.winfo_height())
        return point.x * self.zoom + self.pan_x, height - (point.y * self.zoom + self.pan_y)

    def maybe_snap(self, point: Point2D) -> Point2D:
        if not self.snap_to_grid.get():
            return point
        grid = 40.0
        return Point2D(round(point.x / grid) * grid, round(point.y / grid) * grid)

    def add_point(self, point: Point2D) -> None:
        point = self.maybe_snap(point)
        current = self.current_curve()
        if current and math.hypot(current[-1].x - point.x, current[-1].y - point.y) < 6.0 / self.zoom:
            return
        current.append(point)
        self.update_viewbar()

    def begin_new_stroke(self, world: Point2D) -> None:
        if self.curves and self.curves[-1]:
            self.curves.append([])
        self.drawing = True
        self.add_point(world)

    def on_left_down(self, event: tk.Event) -> None:
        if self.show_help:
            self.toggle_help()
            return
        self.last_mouse = (event.x, event.y)
        if self.mode == "3d":
            self.rotating_3d = True
            return

        world = self.screen_to_world(event.x, event.y)
        self.selected_stroke = -1
        self.selected_point = -1
        threshold = 12.0 / self.zoom
        for si, stroke in enumerate(self.curves):
            for pi, point in enumerate(stroke):
                if math.hypot(point.x - world.x, point.y - world.y) < threshold:
                    self.selected_stroke = si
                    self.selected_point = pi
                    self.redraw()
                    return
        if self.find_nearest_stroke(event.x, event.y) is not None:
            self.pending_draw_start = world
            self.pending_draw_screen = (event.x, event.y)
            return

        self.begin_new_stroke(world)
        self.redraw()

    def on_viewbar_double_click(self, _event: tk.Event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        row = selection[0]
        if row >= len(self.viewbar_rows):
            return
        row_type, stroke_index, _point_index = self.viewbar_rows[row]
        if row_type not in {"stroke", "point"}:
            return
        self.toggle_stroke_details(stroke_index)

    def on_canvas_double_click(self, event: tk.Event) -> None:
        if self.mode != "2d":
            return
        self.pending_draw_start = None
        self.pending_draw_screen = None
        stroke_index = self.find_nearest_stroke(event.x, event.y)
        if stroke_index is not None:
            self.toggle_stroke_details(stroke_index)

    def toggle_stroke_details(self, stroke_index: int) -> None:
        if stroke_index in self.expanded_strokes:
            self.expanded_strokes.remove(stroke_index)
        else:
            self.expanded_strokes.add(stroke_index)
        self.update_viewbar()
        self.redraw()

    def find_nearest_stroke(self, sx: float, sy: float) -> int | None:
        world = self.screen_to_world(sx, sy)
        threshold = 16.0 / self.zoom
        best_stroke: int | None = None
        best_dist = threshold

        for stroke_index, stroke in enumerate(self.curves):
            if not stroke:
                continue
            if len(stroke) == 1:
                dist = math.hypot(stroke[0].x - world.x, stroke[0].y - world.y)
                if dist < best_dist:
                    best_dist = dist
                    best_stroke = stroke_index
                continue
            for idx in range(len(stroke) - 1):
                dist = self.distance_to_segment(world, stroke[idx], stroke[idx + 1])
                if dist < best_dist:
                    best_dist = dist
                    best_stroke = stroke_index
        return best_stroke

    @staticmethod
    def distance_to_segment(point: Point2D, start: Point2D, end: Point2D) -> float:
        dx = end.x - start.x
        dy = end.y - start.y
        length2 = dx * dx + dy * dy
        if length2 <= 1e-12:
            return math.hypot(point.x - start.x, point.y - start.y)
        t = max(0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length2))
        projection = Point2D(start.x + t * dx, start.y + t * dy)
        return math.hypot(point.x - projection.x, point.y - projection.y)

    def on_left_drag(self, event: tk.Event) -> None:
        if self.mode == "3d":
            if self.rotating_3d:
                last_x, last_y = self.last_mouse
                self.cam_rot_y += (event.x - last_x) * 0.5
                self.cam_rot_x += (event.y - last_y) * 0.5
                self.last_mouse = (event.x, event.y)
                self.redraw()
            return

        world = self.maybe_snap(self.screen_to_world(event.x, event.y))
        if self.pending_draw_start is not None and self.pending_draw_screen is not None:
            start_x, start_y = self.pending_draw_screen
            if math.hypot(event.x - start_x, event.y - start_y) < 4.0:
                return
            self.begin_new_stroke(self.pending_draw_start)
            self.pending_draw_start = None
            self.pending_draw_screen = None

        if self.selected_stroke != -1 and self.selected_point != -1:
            self.curves[self.selected_stroke][self.selected_point] = world
            self.update_viewbar()
        elif self.drawing:
            self.add_point(world)
        self.redraw()

    def on_left_up(self, _event: tk.Event) -> None:
        self.drawing = False
        self.rotating_3d = False
        self.pending_draw_start = None
        self.pending_draw_screen = None
        self.selected_stroke = -1
        self.selected_point = -1
        self.redraw()

    def on_middle_down(self, event: tk.Event) -> None:
        self.last_mouse = (event.x, event.y)
        if self.mode == "3d":
            self.panning_3d = True
            return

        world = self.screen_to_world(event.x, event.y)
        threshold = 15.0 / self.zoom
        for stroke in self.curves:
            for idx in range(len(stroke) - 1):
                p1 = stroke[idx]
                p2 = stroke[idx + 1]
                dx = p2.x - p1.x
                dy = p2.y - p1.y
                length2 = dx * dx + dy * dy
                if length2 <= 1e-12:
                    continue
                t = max(0.0, min(1.0, ((world.x - p1.x) * dx + (world.y - p1.y) * dy) / length2))
                projection = Point2D(p1.x + t * dx, p1.y + t * dy)
                if math.hypot(world.x - projection.x, world.y - projection.y) < threshold:
                    stroke.insert(idx + 1, self.maybe_snap(world))
                    self.update_viewbar()
                    self.redraw()
                    return
        self.panning = True

    def on_middle_drag(self, event: tk.Event) -> None:
        last_x, last_y = self.last_mouse
        if self.mode == "3d" and self.panning_3d:
            self.cam_pan_x += event.x - last_x
            self.cam_pan_y += event.y - last_y
        elif self.panning:
            self.pan_x += event.x - last_x
            self.pan_y -= event.y - last_y
        self.last_mouse = (event.x, event.y)
        self.redraw()

    def on_middle_up(self, _event: tk.Event) -> None:
        self.panning = False
        self.panning_3d = False

    def on_right_down(self, event: tk.Event) -> None:
        if self.mode == "3d":
            self.select_grid_point(event.x, event.y)
            return

        world = self.screen_to_world(event.x, event.y)
        threshold = 12.0 / self.zoom
        for stroke in self.curves:
            for idx, point in enumerate(stroke):
                if math.hypot(point.x - world.x, point.y - world.y) < threshold:
                    stroke.pop(idx)
                    self.update_viewbar()
                    self.redraw()
                    return
        if self.curves and self.curves[-1]:
            self.curves.append([])
        self.update_viewbar()
        self.redraw()

    def on_mouse_wheel(self, event: tk.Event) -> None:
        direction = 1 if event.delta > 0 else -1
        if self.mode == "3d":
            gu, gv = self.selected_grid
            if gu != -1 and gv != -1:
                self.surface_grid[gu][gv].y += direction * 30.0
                self.update_viewbar()
            else:
                self.cam_dist = max(100.0, self.cam_dist - direction * 90.0)
            self.redraw()
            return

        before = self.screen_to_world(event.x, event.y)
        self.zoom *= 1.1 if direction > 0 else 1 / 1.1
        self.zoom = max(0.05, min(20.0, self.zoom))
        after_sx, after_sy = self.world_to_screen(before)
        self.pan_x += event.x - after_sx
        self.pan_y -= event.y - after_sy
        self.redraw()

    def update_viewbar(self) -> None:
        self.listbox.delete(0, tk.END)
        self.viewbar_rows.clear()
        if self.mode == "2d":
            count = 0
            selected_global = -1
            for stroke_index, stroke in enumerate(self.curves):
                if not stroke:
                    continue

                start = count
                end = count + len(stroke) - 1
                marker = "[-]" if stroke_index in self.expanded_strokes else "[+]"
                label = f"{marker} Stroke {stroke_index + 1}: P{start}-P{end} ({len(stroke)} diem)"
                self.listbox.insert(tk.END, label)
                self.viewbar_rows.append(("stroke", stroke_index, None))

                if stroke_index in self.expanded_strokes:
                    for point_index, point in enumerate(stroke):
                        global_index = start + point_index
                        self.listbox.insert(tk.END, f"  P{global_index}: ({point.x:.1f}, {point.y:.1f})")
                        self.viewbar_rows.append(("point", stroke_index, point_index))

                if stroke_index == self.selected_stroke and self.selected_point != -1:
                    selected_global = start + self.selected_point
                    point = stroke[self.selected_point]
                    self.listbox.insert(tk.END, f"  Chon P{selected_global}: ({point.x:.1f}, {point.y:.1f})")
                    self.viewbar_rows.append(("selected", stroke_index, self.selected_point))

                count += len(stroke)

            if count == 0:
                self.listbox.insert(tk.END, "Chua co net ve.")
                self.viewbar_rows.append(("info", -1, None))
            if self.fit_points:
                self.listbox.insert(tk.END, "")
                self.viewbar_rows.append(("info", -1, None))
                if self.pixel_info:
                    source = Path(self.pixel_info.source_path).name
                    self.listbox.insert(tk.END, f"Source: {source}")
                    self.viewbar_rows.append(("info", -1, None))
                    self.listbox.insert(tk.END, f"Size: {self.pixel_info.width}x{self.pixel_info.height}")
                    self.viewbar_rows.append(("info", -1, None))
                    mode = "auto" if self.pixel_info.auto_threshold else "manual"
                    self.listbox.insert(tk.END, f"Threshold: {self.pixel_info.threshold} ({mode})")
                    self.viewbar_rows.append(("info", -1, None))
                    self.listbox.insert(tk.END, f"Reconstruct: {self.pixel_info.reconstruction_mode}")
                    self.viewbar_rows.append(("info", -1, None))
                    self.listbox.insert(tk.END, f"Quality: {self.pixel_info.quality}")
                    self.viewbar_rows.append(("info", -1, None))
                    self.listbox.insert(
                        tk.END,
                        f"Raw/filtered: {self.pixel_info.raw_foreground_count}/{self.pixel_info.filtered_foreground_count}",
                    )
                    self.viewbar_rows.append(("info", -1, None))
                    self.listbox.insert(
                        tk.END,
                        f"Components: {self.pixel_info.components_kept} kept, {self.pixel_info.components_removed} removed",
                    )
                    self.viewbar_rows.append(("info", -1, None))
                elif self.pixel_source_label:
                    self.listbox.insert(tk.END, f"Source: {self.pixel_source_label}")
                    self.viewbar_rows.append(("info", -1, None))
                self.listbox.insert(tk.END, f"Pixel points: {len(self.fit_points)}")
                self.viewbar_rows.append(("info", -1, None))
            if self.fit_result:
                self.listbox.insert(tk.END, f"LSQ curves: {len(self.fit_results) or 1}")
                self.viewbar_rows.append(("info", -1, None))
                self.listbox.insert(tk.END, f"LSQ controls: {sum(len(f.control_points) for f in self.fit_results) if self.fit_results else len(self.fit_result.control_points)}")
                self.viewbar_rows.append(("info", -1, None))
                self.listbox.insert(tk.END, f"Degree: {self.fit_result.degree}")
                self.viewbar_rows.append(("info", -1, None))
        else:
            for i, row in enumerate(self.surface_grid):
                for j, point in enumerate(row):
                    self.listbox.insert(tk.END, f"[{i},{j}]: Y={point.y:.1f}")
                    self.viewbar_rows.append(("grid", i, j))

        self.status.configure(text=f"Mode: {self.mode.upper()} | Degree: {self.degree} | Zoom: {self.zoom:.2f}x")

    def draw_grid_2d(self) -> None:
        if not self.show_grid.get():
            return
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        top_left = self.screen_to_world(0, 0)
        bottom_right = self.screen_to_world(width, height)
        grid = 40.0
        start_x = math.floor(top_left.x / grid) * grid
        end_x = math.ceil(bottom_right.x / grid) * grid
        start_y = math.floor(bottom_right.y / grid) * grid
        end_y = math.ceil(top_left.y / grid) * grid
        x = start_x
        while x <= end_x:
            sx, _ = self.world_to_screen(Point2D(x, 0))
            self.canvas.create_line(sx, 0, sx, height, fill="#e2e8f0")
            x += grid
        y = start_y
        while y <= end_y:
            _, sy = self.world_to_screen(Point2D(0, y))
            self.canvas.create_line(0, sy, width, sy, fill="#e2e8f0")
            y += grid

    def draw_2d(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        self.canvas.create_rectangle(0, 0, width, height, fill=self.bg_color, outline="")
        self.draw_grid_2d()

        if self.fit_points and self.show_fit_pixels.get():
            stride = max(1, len(self.fit_points) // 1500)
            for point in self.fit_points[::stride]:
                sx, sy = self.world_to_screen(point)
                self.canvas.create_oval(sx - 1, sy - 1, sx + 1, sy + 1, fill="#6b7280", outline="")

        if self.is_symmetric.get():
            center = self.screen_to_world(width / 2, height / 2).x
            sx, _ = self.world_to_screen(Point2D(center, 0))
            self.canvas.create_line(sx, 0, sx, height, fill="#ff6464", width=2)

        self.draw_curves_2d(mirrored=False)
        if self.is_symmetric.get():
            self.draw_curves_2d(mirrored=True)

        self.draw_axis_2d()
        if self.show_help:
            self.draw_help()

    def mirrored_points(self, points: list[Point2D]) -> list[Point2D]:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        center_x = self.screen_to_world(width / 2, height / 2).x
        return [Point2D(2 * center_x - p.x, p.y) for p in points]

    def draw_curves_2d(self, mirrored: bool) -> None:
        for stroke_index, stroke in enumerate(self.curves):
            if not stroke:
                continue
            draw_stroke = self.mirrored_points(stroke) if mirrored else list(stroke)

            if self.show_polygon.get() and len(draw_stroke) > 1:
                coords = []
                for point in draw_stroke:
                    coords.extend(self.world_to_screen(point))
                if self.is_closed.get() and len(draw_stroke) > 2:
                    coords.extend(self.world_to_screen(draw_stroke[0]))
                self.canvas.create_line(*coords, fill="#9ca3af", dash=(5, 5), width=1)

            if self.show_points.get():
                for point_index, point in enumerate(draw_stroke):
                    sx, sy = self.world_to_screen(point)
                    color = "#ffff44" if stroke_index == self.selected_stroke and point_index == self.selected_point and not mirrored else self.point_color
                    self.canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=color, outline="")
                    if self.show_labels.get() and not mirrored:
                        self.canvas.create_text(sx + 12, sy - 10, text=f"P{point_index}", fill="#111827", anchor="w", font=("Consolas", 9))

            curve_points = list(draw_stroke)
            degree = clamp_degree(self.degree, len(curve_points))
            if self.is_closed.get() and len(curve_points) > degree:
                curve_points.extend(curve_points[:degree])
            if len(curve_points) >= degree + 1:
                sample_count = max(360, min(1600, len(curve_points) * (12 if self.is_closed.get() else 18)))
                samples = sample_curve(curve_points, degree, samples=sample_count)
                coords = []
                for point in samples:
                    coords.extend(self.world_to_screen(point))
                self.canvas.create_line(*coords, fill=self.curve_color, width=self.line_width, smooth=True)

                if self.is_animating.get() and not mirrored:
                    knots = generate_clamped_knots(len(curve_points), degree)
                    anim_point = sample_curve(curve_points, degree, knots=knots, samples=101)[int(self.anim_t * 100)]
                    sx, sy = self.world_to_screen(anim_point)
                    self.canvas.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, fill="#ff0000", outline="")

    def draw_axis_2d(self) -> None:
        x0, y0 = 55, self.canvas.winfo_height() - 55
        self.canvas.create_oval(x0 - 4, y0 - 4, x0 + 4, y0 + 4, fill="#4c78ff", outline="")
        self.canvas.create_line(x0, y0, x0 + 45, y0, fill="#ff4545", width=2, arrow=tk.LAST)
        self.canvas.create_line(x0, y0, x0, y0 - 45, fill="#38d46a", width=2, arrow=tk.LAST)
        self.canvas.create_text(x0 + 55, y0, text="X", fill="#ff4545", font=("Segoe UI", 9, "bold"))
        self.canvas.create_text(x0, y0 - 55, text="Y", fill="#38d46a", font=("Segoe UI", 9, "bold"))

    def project_3d(self, point: Point3D) -> tuple[float, float]:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        rx = math.radians(self.cam_rot_x)
        ry = math.radians(self.cam_rot_y)
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)

        y1 = point.y * cx - point.z * sx
        z1 = point.y * sx + point.z * cx
        x2 = point.x * cy + z1 * sy
        z2 = -point.x * sy + z1 * cy

        scale = 750.0 / max(120.0, self.cam_dist + z2)
        return width / 2 + self.cam_pan_x + x2 * scale, height / 2 + self.cam_pan_y - y1 * scale

    def draw_3d(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        self.canvas.create_rectangle(0, 0, width, height, fill=self.bg_color, outline="")

        if self.show_grid.get():
            for value in range(-1000, 1001, 100):
                self.draw_3d_line(Point3D(value, -200, -1000), Point3D(value, -200, 1000), "#e5e7eb")
                self.draw_3d_line(Point3D(-1000, -200, value), Point3D(1000, -200, value), "#e5e7eb")

        if self.show_polygon.get():
            for row in self.surface_grid:
                self.draw_polyline_3d(row, "#9ca3af", width=1)
            for j in range(self.grid_v):
                self.draw_polyline_3d([self.surface_grid[i][j] for i in range(self.grid_u)], "#9ca3af", width=1)

        if self.show_surface.get():
            knots_u = generate_clamped_knots(self.grid_u, self.degree_u)
            knots_v = generate_clamped_knots(self.grid_v, self.degree_v)
            resolution = 24
            for i in range(resolution + 1):
                u = i / resolution
                row = [evaluate_surface(self.surface_grid, self.degree_u, self.degree_v, knots_u, knots_v, u, j / resolution) for j in range(resolution + 1)]
                self.draw_polyline_3d(row, self.curve_color, width=1)
            for j in range(resolution + 1):
                v = j / resolution
                col = [evaluate_surface(self.surface_grid, self.degree_u, self.degree_v, knots_u, knots_v, i / resolution, v) for i in range(resolution + 1)]
                self.draw_polyline_3d(col, self.curve_color, width=1)

        self.draw_2d_curves_in_3d()

        if self.show_points.get():
            for i, row in enumerate(self.surface_grid):
                for j, point in enumerate(row):
                    sx, sy = self.project_3d(point)
                    color = "#ffff44" if self.selected_grid == (i, j) else self.point_color
                    self.canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=color, outline="")

        self.draw_axis_3d()
        if self.show_help:
            self.draw_help()

    def curve_point_to_3d(self, point: Point2D) -> Point3D:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        return Point3D(point.x - width * 0.5, 35.0, point.y - height * 0.5)

    def draw_2d_curves_in_3d(self) -> None:
        for stroke in self.curves:
            if not stroke:
                continue

            if self.show_polygon.get() and len(stroke) > 1:
                poly = [self.curve_point_to_3d(point) for point in stroke]
                self.draw_polyline_3d(poly, "#9ca3af", width=1)

            curve_points = list(stroke)
            degree = clamp_degree(self.degree, len(curve_points))
            if self.is_closed.get() and len(curve_points) > degree:
                curve_points.extend(curve_points[:degree])
            if len(curve_points) >= degree + 1:
                sample_count = max(220, min(900, len(curve_points) * 10))
                sampled = sample_curve(curve_points, degree, samples=sample_count)
                self.draw_polyline_3d([self.curve_point_to_3d(point) for point in sampled], self.curve_color, width=max(1, int(self.line_width)))

            if self.show_points.get():
                for point in stroke:
                    sx, sy = self.project_3d(self.curve_point_to_3d(point))
                    self.canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill=self.point_color, outline="")

    def draw_3d_line(self, start: Point3D, end: Point3D, color: str, width: int = 1) -> None:
        x1, y1 = self.project_3d(start)
        x2, y2 = self.project_3d(end)
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

    def draw_polyline_3d(self, points: list[Point3D], color: str, width: int = 1) -> None:
        if len(points) < 2:
            return
        coords = []
        for point in points:
            coords.extend(self.project_3d(point))
        self.canvas.create_line(*coords, fill=color, width=width)

    def draw_axis_3d(self) -> None:
        x0, y0 = 55, self.canvas.winfo_height() - 55
        self.canvas.create_oval(x0 - 4, y0 - 4, x0 + 4, y0 + 4, fill="#4c78ff", outline="")
        self.canvas.create_line(x0, y0, x0 + 44, y0, fill="#ff4545", width=2, arrow=tk.LAST)
        self.canvas.create_line(x0, y0, x0, y0 - 44, fill="#38d46a", width=2, arrow=tk.LAST)
        self.canvas.create_line(x0, y0, x0 + 30, y0 + 28, fill="#55aaff", width=2, arrow=tk.LAST)
        self.canvas.create_text(x0 + 55, y0, text="X", fill="#ff4545", font=("Segoe UI", 9, "bold"))
        self.canvas.create_text(x0, y0 - 55, text="Y", fill="#38d46a", font=("Segoe UI", 9, "bold"))
        self.canvas.create_text(x0 + 38, y0 + 35, text="Z", fill="#55aaff", font=("Segoe UI", 9, "bold"))

    def select_grid_point(self, sx: float, sy: float) -> None:
        best = (-1, -1)
        best_dist = 999999.0
        for i, row in enumerate(self.surface_grid):
            for j, point in enumerate(row):
                px, py = self.project_3d(point)
                dist = math.hypot(px - sx, py - sy)
                if dist < 18.0 and dist < best_dist:
                    best_dist = dist
                    best = (i, j)
        self.selected_grid = best
        self.update_viewbar()
        self.redraw()

    def draw_help(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        x1, y1 = 60, 60
        x2, y2 = width - 60, height - 60
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#05080dcc", outline="#6aa6ff", width=3)
        lines = [
            "HUONG DAN SU DUNG B-SPLINE PYTHON",
            "",
            "2D: Chuot trai ve/keo diem, chuot phai xoa diem, chuot giua chen diem hoac pan.",
            "2D: Lan chuot de zoom. Menu View bat/tat grid, point, polygon, symmetry, animation.",
            "3D: Chuot trai xoay camera, chuot giua pan, chuot phai chon diem luoi.",
            "3D: Lan chuot khi da chon diem de nang/ha truc Y; neu chua chon thi zoom camera.",
            "",
            "De tai chu viet tay:",
            "File -> Open Image -> diempixel.dat de doc pixel anh chu viet tay.",
            "Import anh: nen dung Auto threshold, Quality high, Outline cho anh chup nen giay.",
            "File -> Least-Square Reconstruction de tai tao B-spline non-uniform.",
            "File -> Export bsplinecurve.dat de xuat Unum, Udegree, Uknot, P4.",
            "",
            "ESC dong bang nay hoac thoat chuong trinh.",
        ]
        y = y1 + 35
        for idx, line in enumerate(lines):
            font = ("Segoe UI", 13, "bold") if idx == 0 else ("Segoe UI", 11)
            self.canvas.create_text(x1 + 28, y, text=line, fill="#f2f6ff", anchor="w", font=font)
            y += 27

    def redraw(self) -> None:
        self.canvas.delete("all")
        if self.mode == "2d":
            self.draw_2d()
        else:
            self.draw_3d()

    def _timer(self) -> None:
        if self.is_animating.get():
            self.anim_t += 0.006
            if self.anim_t > 1.0:
                self.anim_t = 0.0
            self.redraw()
        self.root.after(16, self._timer)

    def load_points(self) -> None:
        path = filedialog.askopenfilename(
            title="Load TXT points",
            initialdir=str(APP_DIR),
            filetypes=[("Text files", "*.txt *.dat"), ("All files", "*.*")],
        )
        if not path:
            return

        curves: list[list[Point2D]] = []
        last_stroke = None
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    if "degree" in line.lower():
                        try:
                            self.degree = int(line.split()[-1])
                        except ValueError:
                            pass
                    continue
                parts = line.replace(",", " ").split()
                if len(parts) >= 3:
                    try:
                        stroke = int(float(parts[0]))
                        x = float(parts[1])
                        y = float(parts[2])
                    except ValueError:
                        continue
                    if stroke != last_stroke:
                        curves.append([])
                        last_stroke = stroke
                    curves[-1].append(Point2D(x, y))
                elif len(parts) >= 2:
                    try:
                        if not curves:
                            curves.append([])
                        curves[-1].append(Point2D(float(parts[0]), float(parts[1])))
                    except ValueError:
                        continue

        self.curves = curves or [[]]
        self.fit_points = []
        self.pixel_strokes = []
        self.fit_result = None
        self.fit_results = []
        self.pixel_info = None
        self.pixel_source_label = ""
        self.fit_view()
        self.update_viewbar()
        self.redraw()

    def save_points(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save TXT points",
            initialdir=str(APP_DIR),
            initialfile="points.txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            file.write(f"# B-Spline Multi-Stroke - degree {self.degree}\n")
            for stroke_id, stroke in enumerate(self.curves):
                for point in stroke:
                    file.write(f"{stroke_id} {point.x:.6f} {point.y:.6f}\n")
        messagebox.showinfo("Save TXT", f"Da luu: {path}")

    def save_canvas_image(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save canvas image",
            initialdir=str(APP_DIR),
            initialfile="bspline.ps",
            defaultextension=".ps",
            filetypes=[("PostScript", "*.ps"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.canvas.postscript(file=path, colormode="color")
            messagebox.showinfo("Save Image", f"Da luu anh: {path}")
        except Exception as exc:
            messagebox.showerror("Save Image", f"Khong luu duoc anh: {exc}")

    def extract_pixels_from_image(self) -> None:
        image_path = filedialog.askopenfilename(
            title="Open handwriting image",
            initialdir=str(APP_DIR),
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.ppm *.pgm"), ("All files", "*.*")],
        )
        if not image_path:
            return

        options = ImageImportOptionsDialog(self.root).result
        if options is None:
            return

        self.fit_points = []
        self.pixel_strokes = []
        self.fit_result = None
        self.fit_results = []
        self.pixel_info = None
        self.pixel_source_label = Path(image_path).name
        self.update_viewbar()
        self.redraw()

        try:
            result = extract_handwriting_pixels(
                image_path,
                threshold=None if options["auto_threshold"] else int(options["manual_threshold"]),
                auto_threshold=bool(options["auto_threshold"]),
                max_points=int(options["max_points"]),
                min_component_area=int(options["min_noise_area"]),
                reconstruction_mode=str(options["reconstruction_mode"]),
                quality=str(options["quality"]),
                return_info=True,
            )
        except Exception as exc:
            messagebox.showerror("Image Processing", f"Khong xu ly duoc anh: {exc}")
            return

        assert isinstance(result, PixelExtractionResult)
        points = result.points
        info = result.info
        output_path = OUTPUT_DIR / "diempixel.dat"
        write_pixel_points(
            output_path,
            points,
            comments=[
                f"source={info.source_path}",
                f"size={info.width}x{info.height}",
                f"threshold={info.threshold} auto={info.auto_threshold}",
                f"reconstruction_mode={info.reconstruction_mode}",
                f"quality={info.quality}",
                f"raw_foreground={info.raw_foreground_count} filtered_foreground={info.filtered_foreground_count}",
                f"components_kept={info.components_kept} components_removed={info.components_removed}",
            ],
        )
        self.fit_points = points
        self.pixel_strokes = result.strokes
        self.fit_result = None
        self.fit_results = []
        self.pixel_info = info
        self.pixel_source_label = Path(image_path).name
        self.reconstruct_pixel_strokes_auto()
        self.fit_view()
        self.update_viewbar()
        self.redraw()
        messagebox.showinfo(
            "diempixel.dat",
            "Da import anh va xuat pixel.\n\n"
            f"Source: {image_path}\n"
            f"Size: {info.width}x{info.height}\n"
            f"Threshold: {info.threshold} ({'auto' if info.auto_threshold else 'manual'})\n"
            f"Reconstruction: {info.reconstruction_mode}\n"
            f"Quality: {info.quality}\n"
            f"Raw/filtered/output: {info.raw_foreground_count}/{info.filtered_foreground_count}/{len(points)}\n"
            f"Output: {output_path}",
        )

    def load_pixel_dat(self) -> None:
        path = filedialog.askopenfilename(
            title="Load diempixel.dat",
            initialdir=str(OUTPUT_DIR if OUTPUT_DIR.exists() else APP_DIR),
            filetypes=[("DAT files", "*.dat"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        points = read_pixel_points(path)
        if len(points) < 2:
            messagebox.showwarning("diempixel.dat", "File khong co du diem pixel.")
            return
        self.fit_points = points
        self.pixel_strokes = [points]
        self.fit_result = None
        self.fit_results = []
        self.pixel_info = None
        self.pixel_source_label = Path(path).name
        self.fit_view()
        self.update_viewbar()
        self.redraw()

    def reconstruct_from_pixels(self) -> None:
        if len(self.fit_points) < 2:
            messagebox.showwarning(
                "Least-Square",
                "Chua co pixel trong bo nho. Hay import anh moi hoac dung File -> Load diempixel.dat truoc.",
            )
            return

        degree = simpledialog.askinteger("B-spline degree", "Nhap bac Udegree:", initialvalue=self.degree, minvalue=1, maxvalue=8)
        if degree is None:
            return
        source_strokes = self.pixel_strokes if self.pixel_strokes else [self.fit_points]
        longest = max((len(stroke) for stroke in source_strokes), default=len(self.fit_points))
        suggested = max(degree + 1, min(28, max(8, longest // 14)))
        control_count = simpledialog.askinteger(
            "Control points",
            "Nhap Unum - so diem dieu khien moi net:",
            initialvalue=suggested,
            minvalue=degree + 1,
            maxvalue=max(degree + 1, longest),
        )
        if control_count is None:
            return

        try:
            fits = self.fit_strokes_to_bspline(source_strokes, degree=degree, control_count=control_count)
        except Exception as exc:
            messagebox.showerror("Least-Square", f"Khong tai tao duoc duong cong: {exc}")
            return
        if not fits:
            messagebox.showwarning("Least-Square", "Khong co net pixel hop le de tai tao B-spline.")
            return

        self.degree = fits[0].degree
        self.fit_results = fits
        self.fit_result = fits[0]
        self.curves = [fit.control_points for fit in fits]
        self.fit_view()
        self.update_viewbar()
        self.redraw()
        messagebox.showinfo(
            "Least-Square",
            f"Da tai tao {len(fits)} duong cong B-spline voi Udegree={fits[0].degree}.",
        )

    def fit_strokes_to_bspline(
        self,
        strokes: list[list[Point2D]],
        degree: int,
        control_count: int | None = None,
    ) -> list[BSplineFit]:
        fits: list[BSplineFit] = []
        for stroke in strokes:
            if len(stroke) < max(6, degree + 1):
                continue
            local_degree = clamp_degree(degree, len(stroke))
            if control_count is None:
                is_outline = bool(self.pixel_info and self.pixel_info.reconstruction_mode == "outline")
                quality = self.pixel_info.quality if self.pixel_info else "balanced"
                if is_outline:
                    if quality == "high":
                        divisor, max_controls, min_controls = 6, 160, 10
                    elif quality == "fast":
                        divisor, max_controls, min_controls = 12, 80, 8
                    else:
                        divisor, max_controls, min_controls = 8, 120, 9
                else:
                    if quality == "high":
                        divisor, max_controls, min_controls = 5, 72, 8
                    elif quality == "fast":
                        divisor, max_controls, min_controls = 10, 28, 6
                    else:
                        divisor, max_controls, min_controls = 7, 48, 7
                local_controls = max(local_degree + 1, min(max_controls, max(min_controls, len(stroke) // divisor)))
            else:
                local_controls = max(local_degree + 1, min(int(control_count), len(stroke)))
            fits.append(least_squares_approximation(stroke, degree=local_degree, control_count=local_controls))
        return fits

    def reconstruct_pixel_strokes_auto(self) -> None:
        source_strokes = self.pixel_strokes if self.pixel_strokes else ([self.fit_points] if self.fit_points else [])
        try:
            fits = self.fit_strokes_to_bspline(source_strokes, degree=self.degree, control_count=None)
        except Exception:
            fits = []
        if not fits:
            self.curves = [[]]
            self.fit_result = None
            self.fit_results = []
            return
        self.fit_results = fits
        self.fit_result = fits[0]
        self.curves = [fit.control_points for fit in fits]
        self.is_closed.set(bool(self.pixel_info and self.pixel_info.reconstruction_mode == "outline"))
        if self.pixel_info:
            if self.pixel_info.reconstruction_mode == "outline":
                self.line_width = 2.2 if self.pixel_info.quality == "high" else 2.6
            else:
                self.line_width = 3.2
        self.show_points.set(False)
        self.show_polygon.set(False)
        self.show_fit_pixels.set(False)

    def export_bsplinecurve(self) -> None:
        if self.fit_results:
            export_fits = self.fit_results
            controls = export_fits[0].control_points
            degree = export_fits[0].degree
            knots = export_fits[0].knots
        elif self.fit_result:
            export_fits = [self.fit_result]
            controls = self.fit_result.control_points
            degree = self.fit_result.degree
            knots = self.fit_result.knots
        else:
            export_fits = []
            controls = next((stroke for stroke in self.curves if stroke), [])
            if not controls:
                messagebox.showwarning("Export", "Chua co duong cong de xuat.")
                return
            degree = clamp_degree(self.degree, len(controls))
            knots = generate_clamped_knots(len(controls), degree)

        path = filedialog.asksaveasfilename(
            title="Export bsplinecurve.dat",
            initialdir=str(OUTPUT_DIR),
            initialfile="bsplinecurve.dat",
            defaultextension=".dat",
            filetypes=[("DAT files", "*.dat"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            export_bsplinecurve_dat(path, controls, degree, knots)
            if len(export_fits) > 1:
                base_path = Path(path)
                for index, fit in enumerate(export_fits, start=1):
                    part_path = base_path.with_name(f"{base_path.stem}_curve_{index:02d}{base_path.suffix}")
                    export_bsplinecurve_dat(part_path, fit.control_points, fit.degree, fit.knots)
            report_path = Path(path).with_suffix(".readable.txt")
            export_readable_report(report_path, controls, degree, knots)
        except Exception as exc:
            messagebox.showerror("Export", f"Khong xuat duoc file: {exc}")
            return
        extra = f"\n\nDa xuat them {len(export_fits)} file curve rieng cung thu muc." if len(export_fits) > 1 else ""
        messagebox.showinfo("Export", f"Da xuat:\n{path}\n\nBan doc de kiem tra:\n{report_path}{extra}")

    def fit_view(self) -> None:
        points: list[Point2D] = []
        for stroke in self.curves:
            points.extend(stroke)
        points.extend(self.fit_points)
        if not points:
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        min_x = min(p.x for p in points)
        max_x = max(p.x for p in points)
        min_y = min(p.y for p in points)
        max_y = max(p.y for p in points)
        dx = max(1.0, max_x - min_x)
        dy = max(1.0, max_y - min_y)
        self.zoom = max(0.05, min(12.0, min(width / (dx * 1.25), height / (dy * 1.25))))
        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        self.pan_x = width / 2 - cx * self.zoom
        self.pan_y = height / 2 - cy * self.zoom
        self.redraw()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = BSplineApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
