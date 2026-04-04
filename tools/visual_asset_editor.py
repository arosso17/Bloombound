from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk


REPO_ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = REPO_ROOT / "assets" / "visuals"
DEFAULT_ASSET = {
    "asset_id": "untitled_asset",
    "canvas": {"width": 96, "height": 96},
    "shapes": [],
}


def clamp_color_text(text: str) -> str:
    return text.strip()


def rgb_to_hex(rgb: list[int] | tuple[int, ...] | None) -> str:
    if not rgb:
        return ""
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])


def hex_to_rgb(value: str) -> list[int] | None:
    value = value.strip()
    if not value:
        return None
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise ValueError("Expected a 6-digit hex color.")
    return [int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)]


class VisualAssetEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Bloombound Visual Asset Editor")
        self.asset = json.loads(json.dumps(DEFAULT_ASSET))
        self.asset_path: Path | None = None
        self.preview_scale = 1.0
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        self.drag_shape_index: int | None = None
        self.drag_last_world: tuple[float, float] | None = None
        self.drag_mode: str | None = None
        self.drag_handle: str | None = None

        self.asset_id_var = tk.StringVar(value=self.asset["asset_id"])
        self.canvas_width_var = tk.StringVar(value=str(self.asset["canvas"]["width"]))
        self.canvas_height_var = tk.StringVar(value=str(self.asset["canvas"]["height"]))

        self.shape_fields: dict[str, tk.StringVar] = {
            "x": tk.StringVar(value="0"),
            "y": tk.StringVar(value="0"),
            "width": tk.StringVar(value="24"),
            "height": tk.StringVar(value="24"),
            "radius": tk.StringVar(value="12"),
            "x2": tk.StringVar(value="24"),
            "y2": tk.StringVar(value="24"),
            "fill": tk.StringVar(value=""),
            "outline": tk.StringVar(value=""),
            "outline_width": tk.StringVar(value="2"),
        }

        self._build_layout()
        self._refresh_all()

    def _build_layout(self) -> None:
        self.root.columnconfigure(2, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.root, padding=10)
        sidebar.grid(row=0, column=0, sticky="ns")

        editor = ttk.Frame(self.root, padding=10)
        editor.grid(row=0, column=1, sticky="ns")

        preview = ttk.Frame(self.root, padding=10)
        preview.grid(row=0, column=2, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)

        self._build_sidebar(sidebar)
        self._build_editor(editor)
        self._build_preview(preview)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Asset").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.asset_id_var, width=24).grid(row=1, column=0, sticky="ew", pady=(0, 8))

        size_row = ttk.Frame(parent)
        size_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(size_row, text="W").grid(row=0, column=0)
        ttk.Entry(size_row, textvariable=self.canvas_width_var, width=6).grid(row=0, column=1, padx=(4, 10))
        ttk.Label(size_row, text="H").grid(row=0, column=2)
        ttk.Entry(size_row, textvariable=self.canvas_height_var, width=6).grid(row=0, column=3, padx=(4, 0))

        button_row = ttk.Frame(parent)
        button_row.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(button_row, text="New", command=self.new_asset).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(button_row, text="Open", command=self.open_asset).grid(row=0, column=1, padx=4)
        ttk.Button(button_row, text="Save", command=self.save_asset).grid(row=0, column=2, padx=4)
        ttk.Button(button_row, text="Save As", command=self.save_asset_as).grid(row=0, column=3, padx=(4, 0))

        ttk.Label(parent, text="Shapes").grid(row=4, column=0, sticky="w")
        self.shape_listbox = tk.Listbox(parent, height=18, exportselection=False)
        self.shape_listbox.grid(row=5, column=0, sticky="nsew")
        self.shape_listbox.bind("<<ListboxSelect>>", lambda _: self._load_selected_shape())
        parent.rowconfigure(5, weight=1)

        shape_buttons = ttk.Frame(parent)
        shape_buttons.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(shape_buttons, text="Add Circle", command=lambda: self.add_shape("circle")).grid(row=0, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Add Rect", command=lambda: self.add_shape("rect")).grid(row=1, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Add Ellipse", command=lambda: self.add_shape("ellipse")).grid(row=2, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Add Line", command=lambda: self.add_shape("line")).grid(row=3, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Delete", command=self.delete_shape).grid(row=4, column=0, pady=(8, 2), sticky="ew")
        ttk.Button(shape_buttons, text="Move Up", command=lambda: self.move_shape(-1)).grid(row=5, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Move Down", command=lambda: self.move_shape(1)).grid(row=6, column=0, pady=2, sticky="ew")

    def _build_editor(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Shape Properties").grid(row=0, column=0, sticky="w", pady=(0, 8))

        field_names = [
            ("x", "X"),
            ("y", "Y"),
            ("width", "Width"),
            ("height", "Height"),
            ("radius", "Radius"),
            ("x2", "X2"),
            ("y2", "Y2"),
            ("outline_width", "Outline W"),
            ("fill", "Fill"),
            ("outline", "Outline"),
        ]

        for row_index, (field_key, label) in enumerate(field_names, start=1):
            ttk.Label(parent, text=label).grid(row=row_index, column=0, sticky="w", pady=3)
            ttk.Entry(parent, textvariable=self.shape_fields[field_key], width=16).grid(row=row_index, column=1, sticky="ew", padx=(8, 6), pady=3)
            if field_key in {"fill", "outline"}:
                ttk.Button(parent, text="Pick", command=lambda key=field_key: self.pick_color(key)).grid(row=row_index, column=2, sticky="ew", pady=3)

        ttk.Button(parent, text="Apply Shape Changes", command=self.apply_shape_changes).grid(
            row=len(field_names) + 1,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(10, 0),
        )

    def _build_preview(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Preview").grid(row=0, column=0, sticky="w")
        self.preview_canvas = tk.Canvas(parent, width=640, height=640, background="#ede7d8", highlightthickness=1, highlightbackground="#a9a18f")
        self.preview_canvas.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.preview_canvas.bind("<Button-1>", self.on_preview_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_preview_release)
        self.preview_canvas.bind("<Configure>", lambda _event: self._draw_preview())

    def selected_shape_index(self) -> int | None:
        selection = self.shape_listbox.curselection()
        if not selection:
            return None
        return int(selection[0])

    def new_asset(self) -> None:
        self.asset = json.loads(json.dumps(DEFAULT_ASSET))
        self.asset_path = None
        self.drag_shape_index = None
        self.drag_last_world = None
        self.drag_mode = None
        self.drag_handle = None
        self._refresh_all()

    def open_asset(self) -> None:
        path = filedialog.askopenfilename(
            title="Open visual asset",
            initialdir=ASSET_DIR,
            filetypes=[("JSON Files", "*.json")],
        )
        if not path:
            return
        self.asset_path = Path(path)
        self.asset = json.loads(self.asset_path.read_text(encoding="utf-8"))
        self.drag_shape_index = None
        self.drag_last_world = None
        self.drag_mode = None
        self.drag_handle = None
        self._refresh_all()

    def save_asset(self) -> None:
        self._sync_asset_metadata()
        if self.asset_path is None:
            self.save_asset_as()
            return
        self.asset_path.write_text(json.dumps(self.asset, indent=2) + "\n", encoding="utf-8")
        messagebox.showinfo("Saved", f"Saved {self.asset_path.name}")

    def save_asset_as(self) -> None:
        self._sync_asset_metadata()
        initial_name = f"{self.asset['asset_id']}.json"
        path = filedialog.asksaveasfilename(
            title="Save visual asset",
            initialdir=ASSET_DIR,
            initialfile=initial_name,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not path:
            return
        self.asset_path = Path(path)
        self.save_asset()

    def add_shape(self, kind: str) -> None:
        shape = {
            "kind": kind,
            "x": 12,
            "y": 12,
            "width": 24,
            "height": 24,
            "radius": 12,
            "x2": 36,
            "y2": 36,
            "fill": [255, 255, 255] if kind != "line" else None,
            "outline": [48, 58, 64],
            "outline_width": 2,
        }
        self.asset["shapes"].append(shape)
        self._refresh_shape_list()
        new_index = len(self.asset["shapes"]) - 1
        self.shape_listbox.selection_clear(0, tk.END)
        self.shape_listbox.selection_set(new_index)
        self._load_selected_shape()
        self._draw_preview()

    def delete_shape(self) -> None:
        index = self.selected_shape_index()
        if index is None:
            return
        del self.asset["shapes"][index]
        self.drag_shape_index = None
        self.drag_last_world = None
        self.drag_mode = None
        self.drag_handle = None
        self._refresh_shape_list()
        self._draw_preview()

    def move_shape(self, direction: int) -> None:
        index = self.selected_shape_index()
        if index is None:
            return
        target = index + direction
        if target < 0 or target >= len(self.asset["shapes"]):
            return
        self.asset["shapes"][index], self.asset["shapes"][target] = self.asset["shapes"][target], self.asset["shapes"][index]
        self._refresh_shape_list()
        self.shape_listbox.selection_set(target)
        self._load_selected_shape()
        self._draw_preview()

    def apply_shape_changes(self) -> None:
        index = self.selected_shape_index()
        if index is None:
            return
        shape = self.asset["shapes"][index]
        try:
            shape["x"] = float(self.shape_fields["x"].get())
            shape["y"] = float(self.shape_fields["y"].get())
            shape["width"] = float(self.shape_fields["width"].get())
            shape["height"] = float(self.shape_fields["height"].get())
            shape["radius"] = float(self.shape_fields["radius"].get())
            shape["x2"] = float(self.shape_fields["x2"].get())
            shape["y2"] = float(self.shape_fields["y2"].get())
            shape["outline_width"] = int(float(self.shape_fields["outline_width"].get()))
            shape["fill"] = hex_to_rgb(clamp_color_text(self.shape_fields["fill"].get()))
            shape["outline"] = hex_to_rgb(clamp_color_text(self.shape_fields["outline"].get()))
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return

        self._refresh_shape_list()
        self.shape_listbox.selection_set(index)
        self._draw_preview()

    def pick_color(self, field_key: str) -> None:
        current = self.shape_fields[field_key].get().strip() or None
        chosen = colorchooser.askcolor(color=current, title=f"Choose {field_key} color")
        if not chosen[1]:
            return
        self.shape_fields[field_key].set(chosen[1])

    def _load_selected_shape(self) -> None:
        index = self.selected_shape_index()
        if index is None or index >= len(self.asset["shapes"]):
            self._draw_preview()
            return
        shape = self.asset["shapes"][index]
        self.shape_fields["x"].set(str(shape.get("x", 0)))
        self.shape_fields["y"].set(str(shape.get("y", 0)))
        self.shape_fields["width"].set(str(shape.get("width", 0)))
        self.shape_fields["height"].set(str(shape.get("height", 0)))
        self.shape_fields["radius"].set(str(shape.get("radius", 0)))
        self.shape_fields["x2"].set(str(shape.get("x2", 0)))
        self.shape_fields["y2"].set(str(shape.get("y2", 0)))
        self.shape_fields["outline_width"].set(str(shape.get("outline_width", 0)))
        self.shape_fields["fill"].set(rgb_to_hex(shape.get("fill")))
        self.shape_fields["outline"].set(rgb_to_hex(shape.get("outline")))
        self._draw_preview()

    def _refresh_all(self) -> None:
        self.asset_id_var.set(self.asset["asset_id"])
        self.canvas_width_var.set(str(self.asset["canvas"]["width"]))
        self.canvas_height_var.set(str(self.asset["canvas"]["height"]))
        self._refresh_shape_list()
        self._draw_preview()

    def _refresh_shape_list(self) -> None:
        self.shape_listbox.delete(0, tk.END)
        for index, shape in enumerate(self.asset["shapes"]):
            self.shape_listbox.insert(tk.END, f"{index:02d}  {shape['kind']}")

    def _sync_asset_metadata(self) -> None:
        try:
            width = int(float(self.canvas_width_var.get()))
            height = int(float(self.canvas_height_var.get()))
        except ValueError as exc:
            raise ValueError("Canvas width and height must be numbers.") from exc
        self.asset["asset_id"] = self.asset_id_var.get().strip() or "untitled_asset"
        self.asset["canvas"]["width"] = max(1, width)
        self.asset["canvas"]["height"] = max(1, height)

    def _draw_preview(self) -> None:
        self.preview_canvas.delete("all")
        try:
            self._sync_asset_metadata()
        except ValueError:
            return

        canvas_w = int(self.asset["canvas"]["width"])
        canvas_h = int(self.asset["canvas"]["height"])
        preview_w = int(self.preview_canvas.winfo_width() or 640)
        preview_h = int(self.preview_canvas.winfo_height() or 640)
        scale = min((preview_w - 40) / max(1, canvas_w), (preview_h - 40) / max(1, canvas_h))
        scale = max(1.0, scale)
        offset_x = (preview_w - canvas_w * scale) / 2
        offset_y = (preview_h - canvas_h * scale) / 2

        self.preview_canvas.create_rectangle(
            offset_x,
            offset_y,
            offset_x + canvas_w * scale,
            offset_y + canvas_h * scale,
            outline="#8a846f",
            fill="#f8f4ea",
        )

        self.preview_scale = scale
        self.preview_offset_x = offset_x
        self.preview_offset_y = offset_y

        for index, shape in enumerate(self.asset["shapes"]):
            self._draw_preview_shape(shape, offset_x, offset_y, scale, index)

        selected_index = self.selected_shape_index()
        if selected_index is not None and selected_index < len(self.asset["shapes"]):
            bbox = self._shape_screen_bbox(self.asset["shapes"][selected_index], offset_x, offset_y, scale)
            if bbox is not None:
                self.preview_canvas.create_rectangle(
                    bbox[0] - 4,
                    bbox[1] - 4,
                    bbox[2] + 4,
                    bbox[3] + 4,
                    outline="#2f6fed",
                    width=2,
                    dash=(6, 4),
                )
            for handle_name, handle_x, handle_y in self._shape_resize_handles(
                self.asset["shapes"][selected_index],
                offset_x,
                offset_y,
                scale,
            ):
                self.preview_canvas.create_rectangle(
                    handle_x - 5,
                    handle_y - 5,
                    handle_x + 5,
                    handle_y + 5,
                    fill="#ffffff",
                    outline="#2f6fed",
                    width=2,
                    tags=("handle", f"handle-{handle_name}"),
                )

    def _draw_preview_shape(self, shape: dict, offset_x: float, offset_y: float, scale: float, index: int) -> None:
        fill = rgb_to_hex(shape.get("fill"))
        outline = rgb_to_hex(shape.get("outline"))
        outline_width = max(1, int(shape.get("outline_width", 0) * scale)) if shape.get("outline_width", 0) else 1
        tags = ("shape", f"shape-{index}")

        if shape["kind"] == "circle":
            radius = float(shape.get("radius", 0)) * scale
            x = offset_x + float(shape.get("x", 0)) * scale
            y = offset_y + float(shape.get("y", 0)) * scale
            self.preview_canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=fill,
                outline=outline,
                width=outline_width if outline else 0,
                tags=tags,
            )
            return

        if shape["kind"] in {"rect", "ellipse"}:
            x = offset_x + float(shape.get("x", 0)) * scale
            y = offset_y + float(shape.get("y", 0)) * scale
            w = float(shape.get("width", 0)) * scale
            h = float(shape.get("height", 0)) * scale
            if shape["kind"] == "rect":
                self.preview_canvas.create_rectangle(
                    x,
                    y,
                    x + w,
                    y + h,
                    fill=fill,
                    outline=outline,
                    width=outline_width if outline else 0,
                    tags=tags,
                )
            else:
                self.preview_canvas.create_oval(
                    x,
                    y,
                    x + w,
                    y + h,
                    fill=fill,
                    outline=outline,
                    width=outline_width if outline else 0,
                    tags=tags,
                )
            return

        if shape["kind"] == "line":
            self.preview_canvas.create_line(
                offset_x + float(shape.get("x", 0)) * scale,
                offset_y + float(shape.get("y", 0)) * scale,
                offset_x + float(shape.get("x2", 0)) * scale,
                offset_y + float(shape.get("y2", 0)) * scale,
                fill=outline or "#000000",
                width=outline_width,
                tags=tags,
            )

    def on_preview_press(self, event: tk.Event) -> None:
        world_point = self._preview_to_world(event.x, event.y)
        selected_index = self.selected_shape_index()
        if selected_index is not None:
            handle_name = self._handle_at_screen_point(selected_index, event.x, event.y)
            if handle_name is not None:
                self.drag_shape_index = selected_index
                self.drag_last_world = world_point
                self.drag_mode = "resize"
                self.drag_handle = handle_name
                return

        shape_index = self._shape_at_world_point(*world_point)
        self._select_shape(shape_index)
        if shape_index is None:
            self.drag_shape_index = None
            self.drag_last_world = None
            self.drag_mode = None
            self.drag_handle = None
            return
        self.drag_shape_index = shape_index
        self.drag_last_world = world_point
        self.drag_mode = "move"
        self.drag_handle = None

    def on_preview_drag(self, event: tk.Event) -> None:
        if self.drag_shape_index is None or self.drag_last_world is None:
            return
        if self.drag_shape_index >= len(self.asset["shapes"]):
            return

        world_x, world_y = self._preview_to_world(event.x, event.y)

        shape = self.asset["shapes"][self.drag_shape_index]
        if self.drag_mode == "resize":
            self._resize_shape(shape, self.drag_handle, world_x, world_y)
        else:
            last_x, last_y = self.drag_last_world
            delta_x = world_x - last_x
            delta_y = world_y - last_y
            if delta_x == 0 and delta_y == 0:
                return

            shape["x"] = round(float(shape.get("x", 0)) + delta_x, 2)
            shape["y"] = round(float(shape.get("y", 0)) + delta_y, 2)
            if shape["kind"] == "line":
                shape["x2"] = round(float(shape.get("x2", 0)) + delta_x, 2)
                shape["y2"] = round(float(shape.get("y2", 0)) + delta_y, 2)

        self.drag_last_world = (world_x, world_y)
        self._load_selected_shape()

    def on_preview_release(self, _event: tk.Event) -> None:
        self.drag_shape_index = None
        self.drag_last_world = None
        self.drag_mode = None
        self.drag_handle = None

    def _select_shape(self, index: int | None) -> None:
        self.shape_listbox.selection_clear(0, tk.END)
        if index is None:
            self._draw_preview()
            return
        self.shape_listbox.selection_set(index)
        self.shape_listbox.activate(index)
        self._load_selected_shape()

    def _preview_to_world(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        world_x = (canvas_x - self.preview_offset_x) / max(self.preview_scale, 1e-6)
        world_y = (canvas_y - self.preview_offset_y) / max(self.preview_scale, 1e-6)
        return world_x, world_y

    def _shape_at_world_point(self, world_x: float, world_y: float) -> int | None:
        for index in range(len(self.asset["shapes"]) - 1, -1, -1):
            if self._shape_contains_point(self.asset["shapes"][index], world_x, world_y):
                return index
        return None

    def _handle_at_screen_point(self, shape_index: int, screen_x: float, screen_y: float) -> str | None:
        if shape_index >= len(self.asset["shapes"]):
            return None
        for handle_name, handle_x, handle_y in self._shape_resize_handles(
            self.asset["shapes"][shape_index],
            self.preview_offset_x,
            self.preview_offset_y,
            self.preview_scale,
        ):
            if abs(screen_x - handle_x) <= 7 and abs(screen_y - handle_y) <= 7:
                return handle_name
        return None

    def _shape_resize_handles(
        self,
        shape: dict,
        offset_x: float,
        offset_y: float,
        scale: float,
    ) -> list[tuple[str, float, float]]:
        kind = shape["kind"]
        if kind == "circle":
            x = offset_x + float(shape.get("x", 0)) * scale
            y = offset_y + float(shape.get("y", 0)) * scale
            radius = float(shape.get("radius", 0)) * scale
            return [
                ("n", x, y - radius),
                ("e", x + radius, y),
                ("s", x, y + radius),
                ("w", x - radius, y),
            ]

        if kind in {"rect", "ellipse"}:
            x = offset_x + float(shape.get("x", 0)) * scale
            y = offset_y + float(shape.get("y", 0)) * scale
            width = float(shape.get("width", 0)) * scale
            height = float(shape.get("height", 0)) * scale
            return [
                ("nw", x, y),
                ("ne", x + width, y),
                ("sw", x, y + height),
                ("se", x + width, y + height),
            ]

        if kind == "line":
            x1 = offset_x + float(shape.get("x", 0)) * scale
            y1 = offset_y + float(shape.get("y", 0)) * scale
            x2 = offset_x + float(shape.get("x2", 0)) * scale
            y2 = offset_y + float(shape.get("y2", 0)) * scale
            return [("start", x1, y1), ("end", x2, y2)]

        return []

    def _resize_shape(self, shape: dict, handle_name: str | None, world_x: float, world_y: float) -> None:
        if handle_name is None:
            return
        kind = shape["kind"]
        min_size = 4.0

        if kind == "circle":
            center_x = float(shape.get("x", 0))
            center_y = float(shape.get("y", 0))
            radius = ((world_x - center_x) ** 2 + (world_y - center_y) ** 2) ** 0.5
            shape["radius"] = round(max(min_size, radius), 2)
            return

        if kind in {"rect", "ellipse"}:
            left = float(shape.get("x", 0))
            top = float(shape.get("y", 0))
            right = left + float(shape.get("width", 0))
            bottom = top + float(shape.get("height", 0))

            if "w" in handle_name:
                left = min(world_x, right - min_size)
            if "e" in handle_name:
                right = max(world_x, left + min_size)
            if "n" in handle_name:
                top = min(world_y, bottom - min_size)
            if "s" in handle_name:
                bottom = max(world_y, top + min_size)

            shape["x"] = round(left, 2)
            shape["y"] = round(top, 2)
            shape["width"] = round(max(min_size, right - left), 2)
            shape["height"] = round(max(min_size, bottom - top), 2)
            return

        if kind == "line":
            if handle_name == "start":
                shape["x"] = round(world_x, 2)
                shape["y"] = round(world_y, 2)
            elif handle_name == "end":
                shape["x2"] = round(world_x, 2)
                shape["y2"] = round(world_y, 2)

    def _shape_contains_point(self, shape: dict, world_x: float, world_y: float) -> bool:
        kind = shape["kind"]
        if kind == "circle":
            radius = float(shape.get("radius", 0))
            delta_x = world_x - float(shape.get("x", 0))
            delta_y = world_y - float(shape.get("y", 0))
            return (delta_x * delta_x) + (delta_y * delta_y) <= radius * radius

        if kind == "rect":
            x = float(shape.get("x", 0))
            y = float(shape.get("y", 0))
            width = float(shape.get("width", 0))
            height = float(shape.get("height", 0))
            return x <= world_x <= x + width and y <= world_y <= y + height

        if kind == "ellipse":
            width = float(shape.get("width", 0))
            height = float(shape.get("height", 0))
            if width <= 0 or height <= 0:
                return False
            center_x = float(shape.get("x", 0)) + width / 2
            center_y = float(shape.get("y", 0)) + height / 2
            norm_x = (world_x - center_x) / (width / 2)
            norm_y = (world_y - center_y) / (height / 2)
            return (norm_x * norm_x) + (norm_y * norm_y) <= 1.0

        if kind == "line":
            return self._point_near_line(
                world_x,
                world_y,
                float(shape.get("x", 0)),
                float(shape.get("y", 0)),
                float(shape.get("x2", 0)),
                float(shape.get("y2", 0)),
                tolerance=max(4.0, float(shape.get("outline_width", 0)) + 2.0),
            )

        return False

    def _point_near_line(
        self,
        point_x: float,
        point_y: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        tolerance: float,
    ) -> bool:
        delta_x = x2 - x1
        delta_y = y2 - y1
        length_squared = (delta_x * delta_x) + (delta_y * delta_y)
        if length_squared == 0:
            return ((point_x - x1) ** 2 + (point_y - y1) ** 2) <= tolerance * tolerance

        projection = ((point_x - x1) * delta_x + (point_y - y1) * delta_y) / length_squared
        projection = max(0.0, min(1.0, projection))
        nearest_x = x1 + projection * delta_x
        nearest_y = y1 + projection * delta_y
        return ((point_x - nearest_x) ** 2 + (point_y - nearest_y) ** 2) <= tolerance * tolerance

    def _shape_screen_bbox(
        self,
        shape: dict,
        offset_x: float,
        offset_y: float,
        scale: float,
    ) -> tuple[float, float, float, float] | None:
        kind = shape["kind"]
        if kind == "circle":
            radius = float(shape.get("radius", 0)) * scale
            x = offset_x + float(shape.get("x", 0)) * scale
            y = offset_y + float(shape.get("y", 0)) * scale
            return (x - radius, y - radius, x + radius, y + radius)

        if kind in {"rect", "ellipse"}:
            x = offset_x + float(shape.get("x", 0)) * scale
            y = offset_y + float(shape.get("y", 0)) * scale
            w = float(shape.get("width", 0)) * scale
            h = float(shape.get("height", 0)) * scale
            return (x, y, x + w, y + h)

        if kind == "line":
            x1 = offset_x + float(shape.get("x", 0)) * scale
            y1 = offset_y + float(shape.get("y", 0)) * scale
            x2 = offset_x + float(shape.get("x2", 0)) * scale
            y2 = offset_y + float(shape.get("y2", 0)) * scale
            padding = max(6.0, float(shape.get("outline_width", 0)) * scale)
            return (
                min(x1, x2) - padding,
                min(y1, y2) - padding,
                max(x1, x2) + padding,
                max(y1, y2) + padding,
            )

        return None


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.geometry("1200x760")
    app = VisualAssetEditor(root)
    root.bind("<Control-s>", lambda _event: app.save_asset())
    root.mainloop()


if __name__ == "__main__":
    main()
