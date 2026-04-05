from __future__ import annotations

import json
import math
import sys
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import pygame as pg

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gameplay.visual_assets import load_visual_asset, render_visual_asset_to_surface, visual_asset_from_payload

ASSET_DIR = REPO_ROOT / "assets" / "visuals"
PREVIEW_DIR = REPO_ROOT / "assets" / "visual_previews"
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
        self.nudge_step = 1.0

        self.asset_id_var = tk.StringVar(value=self.asset["asset_id"])
        self.canvas_width_var = tk.StringVar(value=str(self.asset["canvas"]["width"]))
        self.canvas_height_var = tk.StringVar(value=str(self.asset["canvas"]["height"]))

        self.shape_fields: dict[str, tk.StringVar] = {
            "x": tk.StringVar(value="0"),
            "y": tk.StringVar(value="0"),
            "rotation_degrees": tk.StringVar(value="0"),
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
        self._bind_shortcuts()

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

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-d>", lambda event: self._handle_duplicate_shortcut(event))
        self.root.bind_all("<Left>", lambda event: self._handle_nudge_shortcut(event, -self._nudge_amount(event), 0.0))
        self.root.bind_all("<Right>", lambda event: self._handle_nudge_shortcut(event, self._nudge_amount(event), 0.0))
        self.root.bind_all("<Up>", lambda event: self._handle_nudge_shortcut(event, 0.0, -self._nudge_amount(event)))
        self.root.bind_all("<Down>", lambda event: self._handle_nudge_shortcut(event, 0.0, self._nudge_amount(event)))

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

        export_row = ttk.Frame(parent)
        export_row.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(export_row, text="Export PNG", command=self.export_asset_png).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ttk.Button(export_row, text="Export Sheet", command=self.export_preview_sheet).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        assets_header = ttk.Frame(parent)
        assets_header.grid(row=5, column=0, sticky="ew")
        ttk.Label(assets_header, text="Assets In Folder").grid(row=0, column=0, sticky="w")
        ttk.Button(assets_header, text="Refresh", command=self.refresh_asset_files).grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.asset_files_listbox = tk.Listbox(parent, height=8, exportselection=False)
        self.asset_files_listbox.grid(row=6, column=0, sticky="nsew", pady=(4, 10))
        self.asset_files_listbox.bind("<Double-Button-1>", lambda _: self.open_selected_asset_file())

        asset_file_buttons = ttk.Frame(parent)
        asset_file_buttons.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(asset_file_buttons, text="Open Selected", command=self.open_selected_asset_file).grid(row=0, column=0, sticky="ew")

        ttk.Label(parent, text="Shapes").grid(row=8, column=0, sticky="w")
        self.shape_listbox = tk.Listbox(parent, height=18, exportselection=False)
        self.shape_listbox.grid(row=9, column=0, sticky="nsew")
        self.shape_listbox.bind("<<ListboxSelect>>", lambda _: self._load_selected_shape())
        parent.rowconfigure(9, weight=1)

        shape_buttons = ttk.Frame(parent)
        shape_buttons.grid(row=10, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(shape_buttons, text="Add Circle", command=lambda: self.add_shape("circle")).grid(row=0, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Add Rect", command=lambda: self.add_shape("rect")).grid(row=1, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Add Ellipse", command=lambda: self.add_shape("ellipse")).grid(row=2, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Add Line", command=lambda: self.add_shape("line")).grid(row=3, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Delete", command=self.delete_shape).grid(row=4, column=0, pady=(8, 2), sticky="ew")
        ttk.Button(shape_buttons, text="Duplicate", command=self.duplicate_shape).grid(row=5, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Move Up", command=lambda: self.move_shape(-1)).grid(row=6, column=0, pady=2, sticky="ew")
        ttk.Button(shape_buttons, text="Move Down", command=lambda: self.move_shape(1)).grid(row=7, column=0, pady=2, sticky="ew")

    def _build_editor(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Shape Properties").grid(row=0, column=0, sticky="w", pady=(0, 8))

        field_names = [
            ("x", "X"),
            ("y", "Y"),
            ("rotation_degrees", "Rotation"),
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
                color_buttons = ttk.Frame(parent)
                color_buttons.grid(row=row_index, column=2, sticky="ew", pady=3)
                ttk.Button(color_buttons, text="Pick", command=lambda key=field_key: self.pick_color(key)).grid(row=0, column=0, padx=(0, 4))
                ttk.Button(color_buttons, text="None", command=lambda key=field_key: self.clear_color(key)).grid(row=0, column=1)

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
        self._load_asset_from_path(Path(path))

    def save_asset(self) -> None:
        self._sync_asset_metadata()
        if self.asset_path is None:
            self.save_asset_as()
            return
        self.asset_path.write_text(json.dumps(self.asset, indent=2) + "\n", encoding="utf-8")
        load_visual_asset.cache_clear()
        self.refresh_asset_files(select_name=self.asset_path.name)
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

    def export_asset_png(self) -> None:
        try:
            self._sync_asset_metadata()
        except ValueError as exc:
            messagebox.showerror("Invalid asset", str(exc))
            return
        output_path = PREVIEW_DIR / f"{self.asset['asset_id']}.png"
        self._ensure_preview_dir()
        self._save_asset_surface(visual_asset_from_payload(self.asset), output_path)
        messagebox.showinfo("Exported", f"Exported {output_path.name} to {output_path.parent}")

    def export_preview_sheet(self) -> None:
        self._ensure_preview_dir()
        pg.init()
        try:
            self._sync_asset_metadata()
        except ValueError as exc:
            messagebox.showerror("Invalid asset", str(exc))
            return

        asset_paths = sorted(ASSET_DIR.glob("*.json"))
        current_asset = visual_asset_from_payload(self.asset)
        current_name = self.asset_path.name if self.asset_path is not None else f"{self.asset['asset_id']}.json"
        assets: list = []
        used_current_asset = False

        for path in asset_paths:
            if path.name == current_name:
                assets.append(current_asset)
                used_current_asset = True
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            assets.append(visual_asset_from_payload(payload))

        if not assets and not self.asset["shapes"]:
            messagebox.showinfo("No Assets", "No visual assets were found to export.")
            return

        if not used_current_asset:
            assets.append(current_asset)

        cols = 3
        cell_w = 188
        cell_h = 172
        margin = 18
        rows = math.ceil(len(assets) / cols)
        sheet = pg.Surface((cols * cell_w + margin * 2, rows * cell_h + margin * 2))
        sheet.fill((237, 231, 216))
        font = pg.font.SysFont(None, 22)
        small_font = pg.font.SysFont(None, 18)

        for index, asset in enumerate(assets):
            col = index % cols
            row = index // cols
            cell_left = margin + col * cell_w
            cell_top = margin + row * cell_h
            card_rect = pg.Rect(cell_left, cell_top, cell_w - 12, cell_h - 12)
            pg.draw.rect(sheet, (248, 244, 234), card_rect, border_radius=16)
            pg.draw.rect(sheet, (170, 160, 145), card_rect, width=2, border_radius=16)

            preview_scale = min(1.0, 104 / max(asset.width, asset.height))
            preview = render_visual_asset_to_surface(asset, scale=preview_scale, padding=10)
            preview_rect = preview.get_rect(center=(card_rect.centerx, card_rect.top + 66))
            sheet.blit(preview, preview_rect)

            name_surf = font.render(asset.asset_id, True, (48, 58, 64))
            size_surf = small_font.render(f"{asset.width} x {asset.height}", True, (86, 94, 98))
            sheet.blit(name_surf, (card_rect.left + 12, card_rect.bottom - 48))
            sheet.blit(size_surf, (card_rect.left + 12, card_rect.bottom - 24))

        output_path = PREVIEW_DIR / "preview_sheet.png"
        pg.image.save(sheet, output_path)
        load_visual_asset.cache_clear()
        messagebox.showinfo("Exported", f"Exported preview_sheet.png to {output_path.parent}")

    def refresh_asset_files(self, select_name: str | None = None) -> None:
        self.asset_files_listbox.delete(0, tk.END)
        asset_files = sorted(ASSET_DIR.glob("*.json"))
        for asset_file in asset_files:
            self.asset_files_listbox.insert(tk.END, asset_file.name)

        target_name = select_name
        if target_name is None and self.asset_path is not None:
            target_name = self.asset_path.name

        if target_name is None:
            return

        for index, asset_file in enumerate(asset_files):
            if asset_file.name == target_name:
                self.asset_files_listbox.selection_clear(0, tk.END)
                self.asset_files_listbox.selection_set(index)
                self.asset_files_listbox.activate(index)
                self.asset_files_listbox.see(index)
                break

    def open_selected_asset_file(self) -> None:
        selection = self.asset_files_listbox.curselection()
        if not selection:
            return
        asset_name = self.asset_files_listbox.get(selection[0])
        self._load_asset_from_path(ASSET_DIR / asset_name)

    def add_shape(self, kind: str) -> None:
        shape = {
            "kind": kind,
            "x": 12,
            "y": 12,
            "rotation_degrees": 0,
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

    def duplicate_shape(self) -> None:
        index = self.selected_shape_index()
        if index is None:
            return
        new_shape = deepcopy(self.asset["shapes"][index])
        new_shape["x"] = round(float(new_shape.get("x", 0)) + 8.0, 2)
        new_shape["y"] = round(float(new_shape.get("y", 0)) + 8.0, 2)
        if new_shape["kind"] == "line":
            new_shape["x2"] = round(float(new_shape.get("x2", 0)) + 8.0, 2)
            new_shape["y2"] = round(float(new_shape.get("y2", 0)) + 8.0, 2)
        insert_index = index + 1
        self.asset["shapes"].insert(insert_index, new_shape)
        self._refresh_shape_list()
        self._select_shape(insert_index)

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
            shape["rotation_degrees"] = float(self.shape_fields["rotation_degrees"].get())
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

    def clear_color(self, field_key: str) -> None:
        self.shape_fields[field_key].set("")

    def _load_selected_shape(self) -> None:
        index = self.selected_shape_index()
        if index is None or index >= len(self.asset["shapes"]):
            self._draw_preview()
            return
        shape = self.asset["shapes"][index]
        self.shape_fields["x"].set(str(shape.get("x", 0)))
        self.shape_fields["y"].set(str(shape.get("y", 0)))
        self.shape_fields["rotation_degrees"].set(str(shape.get("rotation_degrees", 0)))
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
        self.refresh_asset_files()
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
            selected_shape = self.asset["shapes"][selected_index]
            bbox = self._shape_screen_bbox(selected_shape, offset_x, offset_y, scale)
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
            rotate_handle = self._shape_rotate_handle(selected_shape, offset_x, offset_y, scale)
            if rotate_handle is not None:
                handle_name, handle_x, handle_y = rotate_handle
                center_x, center_y = self._shape_screen_center(selected_shape, offset_x, offset_y, scale)
                self.preview_canvas.create_line(center_x, center_y, handle_x, handle_y, fill="#2f6fed", dash=(3, 3))
                self.preview_canvas.create_oval(
                    handle_x - 6,
                    handle_y - 6,
                    handle_x + 6,
                    handle_y + 6,
                    fill="#f0f6ff",
                    outline="#2f6fed",
                    width=2,
                    tags=("handle", f"handle-{handle_name}"),
                )
            for handle_name, handle_x, handle_y in self._shape_resize_handles(selected_shape, offset_x, offset_y, scale):
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
            points = self._shape_screen_points(shape, offset_x, offset_y, scale)
            if not points:
                return
            flat_points = [coordinate for point in points for coordinate in point]
            self.preview_canvas.create_polygon(
                *flat_points,
                fill=fill,
                outline=outline,
                width=outline_width if outline else 0,
                smooth=(shape["kind"] == "ellipse"),
                splinesteps=24,
                tags=tags,
            )
            return

        if shape["kind"] == "line":
            x1 = float(shape.get("x", 0))
            y1 = float(shape.get("y", 0))
            x2 = float(shape.get("x2", 0))
            y2 = float(shape.get("y2", 0))
            rotation = float(shape.get("rotation_degrees", 0.0))
            if abs(rotation) >= 0.01:
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                x1, y1 = self._rotate_point(x1, y1, center_x, center_y, rotation)
                x2, y2 = self._rotate_point(x2, y2, center_x, center_y, rotation)
            self.preview_canvas.create_line(
                offset_x + x1 * scale,
                offset_y + y1 * scale,
                offset_x + x2 * scale,
                offset_y + y2 * scale,
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
                self.drag_mode = "rotate" if handle_name == "rotate" else "resize"
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
        if self.drag_mode == "rotate":
            self._rotate_shape_to_pointer(shape, world_x, world_y)
        elif self.drag_mode == "resize":
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

    def nudge_selected_shape(self, delta_x: float, delta_y: float) -> None:
        index = self.selected_shape_index()
        if index is None or index >= len(self.asset["shapes"]):
            return
        shape = self.asset["shapes"][index]
        shape["x"] = round(float(shape.get("x", 0)) + delta_x, 2)
        shape["y"] = round(float(shape.get("y", 0)) + delta_y, 2)
        if shape["kind"] == "line":
            shape["x2"] = round(float(shape.get("x2", 0)) + delta_x, 2)
            shape["y2"] = round(float(shape.get("y2", 0)) + delta_y, 2)
        self._load_selected_shape()

    def _handle_duplicate_shortcut(self, event: tk.Event) -> str | None:
        if self._focused_widget_is_text_input():
            return None
        self.duplicate_shape()
        return "break"

    def _handle_nudge_shortcut(self, event: tk.Event, delta_x: float, delta_y: float) -> str | None:
        if self._focused_widget_is_text_input():
            return None
        self.nudge_selected_shape(delta_x, delta_y)
        return "break"

    def _focused_widget_is_text_input(self) -> bool:
        focused = self.root.focus_get()
        return isinstance(focused, (tk.Entry, tk.Text))

    def _nudge_amount(self, event: tk.Event) -> float:
        shift_mask = 0x0001
        return 10.0 if (event.state & shift_mask) else self.nudge_step

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
        rotate_handle = self._shape_rotate_handle(
            self.asset["shapes"][shape_index],
            self.preview_offset_x,
            self.preview_offset_y,
            self.preview_scale,
        )
        if rotate_handle is not None:
            handle_name, handle_x, handle_y = rotate_handle
            if abs(screen_x - handle_x) <= 8 and abs(screen_y - handle_y) <= 8:
                return handle_name
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
            points = self._shape_screen_points(shape, offset_x, offset_y, scale)
            if len(points) == 4:
                x, y = points[0]
                x2, y2 = points[1]
                x3, y3 = points[2]
                x4, y4 = points[3]
                return [
                    ("nw", x, y),
                    ("ne", x2, y2),
                    ("se", x3, y3),
                    ("sw", x4, y4),
                ]
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
            x1 = float(shape.get("x", 0))
            y1 = float(shape.get("y", 0))
            x2 = float(shape.get("x2", 0))
            y2 = float(shape.get("y2", 0))
            rotation = float(shape.get("rotation_degrees", 0.0))
            if abs(rotation) >= 0.01:
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                x1, y1 = self._rotate_point(x1, y1, center_x, center_y, rotation)
                x2, y2 = self._rotate_point(x2, y2, center_x, center_y, rotation)
            x1 = offset_x + x1 * scale
            y1 = offset_y + y1 * scale
            x2 = offset_x + x2 * scale
            y2 = offset_y + y2 * scale
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
            world_x, world_y = self._inverse_rotate_point_for_shape(shape, world_x, world_y)
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
            if handle_name not in {"start", "end"}:
                return
            rotation = float(shape.get("rotation_degrees", 0.0))
            if abs(rotation) >= 0.01:
                center_x = (float(shape.get("x", 0)) + float(shape.get("x2", 0))) / 2
                center_y = (float(shape.get("y", 0)) + float(shape.get("y2", 0))) / 2
                world_x, world_y = self._rotate_point(world_x, world_y, center_x, center_y, -rotation)
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
            rotated_x, rotated_y = self._inverse_rotate_point_for_shape(shape, world_x, world_y)
            x = float(shape.get("x", 0))
            y = float(shape.get("y", 0))
            width = float(shape.get("width", 0))
            height = float(shape.get("height", 0))
            return x <= rotated_x <= x + width and y <= rotated_y <= y + height

        if kind == "ellipse":
            width = float(shape.get("width", 0))
            height = float(shape.get("height", 0))
            if width <= 0 or height <= 0:
                return False
            center_x = float(shape.get("x", 0)) + width / 2
            center_y = float(shape.get("y", 0)) + height / 2
            rotated_x, rotated_y = self._inverse_rotate_point_for_shape(shape, world_x, world_y)
            norm_x = (rotated_x - center_x) / (width / 2)
            norm_y = (rotated_y - center_y) / (height / 2)
            return (norm_x * norm_x) + (norm_y * norm_y) <= 1.0

        if kind == "line":
            x1 = float(shape.get("x", 0))
            y1 = float(shape.get("y", 0))
            x2 = float(shape.get("x2", 0))
            y2 = float(shape.get("y2", 0))
            rotation = float(shape.get("rotation_degrees", 0.0))
            if abs(rotation) >= 0.01:
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                x1, y1 = self._rotate_point(x1, y1, center_x, center_y, rotation)
                x2, y2 = self._rotate_point(x2, y2, center_x, center_y, rotation)
            return self._point_near_line(
                world_x,
                world_y,
                x1,
                y1,
                x2,
                y2,
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
            points = self._shape_screen_points(shape, offset_x, offset_y, scale)
            if not points:
                return None
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            return (min(xs), min(ys), max(xs), max(ys))

        if kind == "line":
            x1 = float(shape.get("x", 0))
            y1 = float(shape.get("y", 0))
            x2 = float(shape.get("x2", 0))
            y2 = float(shape.get("y2", 0))
            rotation = float(shape.get("rotation_degrees", 0.0))
            if abs(rotation) >= 0.01:
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                x1, y1 = self._rotate_point(x1, y1, center_x, center_y, rotation)
                x2, y2 = self._rotate_point(x2, y2, center_x, center_y, rotation)
            x1 = offset_x + x1 * scale
            y1 = offset_y + y1 * scale
            x2 = offset_x + x2 * scale
            y2 = offset_y + y2 * scale
            padding = max(6.0, float(shape.get("outline_width", 0)) * scale)
            return (
                min(x1, x2) - padding,
                min(y1, y2) - padding,
                max(x1, x2) + padding,
                max(y1, y2) + padding,
            )

        return None

    def _shape_screen_points(
        self,
        shape: dict,
        offset_x: float,
        offset_y: float,
        scale: float,
    ) -> list[tuple[float, float]]:
        kind = shape["kind"]
        x = float(shape.get("x", 0))
        y = float(shape.get("y", 0))
        width = float(shape.get("width", 0))
        height = float(shape.get("height", 0))
        center_x = x + width / 2
        center_y = y + height / 2
        rotation = float(shape.get("rotation_degrees", 0.0))

        if kind == "rect":
            corners = [
                (x, y),
                (x + width, y),
                (x + width, y + height),
                (x, y + height),
            ]
            return [
                (
                    offset_x + rotated_x * scale,
                    offset_y + rotated_y * scale,
                )
                for rotated_x, rotated_y in (
                    self._rotate_point(px, py, center_x, center_y, rotation)
                    for px, py in corners
                )
            ]

        if kind == "ellipse":
            points: list[tuple[float, float]] = []
            radius_x = width / 2
            radius_y = height / 2
            if radius_x <= 0 or radius_y <= 0:
                return points
            for step in range(24):
                theta = (math.tau * step) / 24
                point_x = center_x + math.cos(theta) * radius_x
                point_y = center_y + math.sin(theta) * radius_y
                rotated_x, rotated_y = self._rotate_point(point_x, point_y, center_x, center_y, rotation)
                points.append((offset_x + rotated_x * scale, offset_y + rotated_y * scale))
            return points

        return []

    def _inverse_rotate_point_for_shape(self, shape: dict, world_x: float, world_y: float) -> tuple[float, float]:
        width = float(shape.get("width", 0))
        height = float(shape.get("height", 0))
        center_x = float(shape.get("x", 0)) + width / 2
        center_y = float(shape.get("y", 0)) + height / 2
        rotation = float(shape.get("rotation_degrees", 0.0))
        return self._rotate_point(world_x, world_y, center_x, center_y, -rotation)

    def _rotate_shape_to_pointer(self, shape: dict, world_x: float, world_y: float) -> None:
        center_x, center_y = self._shape_center(shape)
        angle = math.degrees(math.atan2(world_y - center_y, world_x - center_x)) + 90.0
        shape["rotation_degrees"] = round(angle, 2)

    def _shape_center(self, shape: dict) -> tuple[float, float]:
        kind = shape["kind"]
        if kind == "circle":
            return float(shape.get("x", 0)), float(shape.get("y", 0))
        if kind in {"rect", "ellipse"}:
            return (
                float(shape.get("x", 0)) + float(shape.get("width", 0)) / 2,
                float(shape.get("y", 0)) + float(shape.get("height", 0)) / 2,
            )
        if kind == "line":
            return (
                (float(shape.get("x", 0)) + float(shape.get("x2", 0))) / 2,
                (float(shape.get("y", 0)) + float(shape.get("y2", 0))) / 2,
            )
        return float(shape.get("x", 0)), float(shape.get("y", 0))

    def _shape_screen_center(self, shape: dict, offset_x: float, offset_y: float, scale: float) -> tuple[float, float]:
        center_x, center_y = self._shape_center(shape)
        return offset_x + center_x * scale, offset_y + center_y * scale

    def _shape_rotate_handle(
        self,
        shape: dict,
        offset_x: float,
        offset_y: float,
        scale: float,
    ) -> tuple[str, float, float] | None:
        if shape["kind"] == "circle":
            return None
        center_x, center_y = self._shape_center(shape)
        if shape["kind"] in {"rect", "ellipse"}:
            local_x = center_x
            local_y = float(shape.get("y", 0)) - 18.0
        else:
            local_x = center_x
            local_y = center_y - 18.0
        rotated_x, rotated_y = self._rotate_point(
            local_x,
            local_y,
            center_x,
            center_y,
            float(shape.get("rotation_degrees", 0.0)),
        )
        return ("rotate", offset_x + rotated_x * scale, offset_y + rotated_y * scale)

    @staticmethod
    def _rotate_point(x: float, y: float, center_x: float, center_y: float, rotation_degrees: float) -> tuple[float, float]:
        radians = math.radians(rotation_degrees)
        cos_theta = math.cos(radians)
        sin_theta = math.sin(radians)
        rel_x = x - center_x
        rel_y = y - center_y
        return (
            center_x + rel_x * cos_theta - rel_y * sin_theta,
            center_y + rel_x * sin_theta + rel_y * cos_theta,
        )

    def _load_asset_from_path(self, path: Path) -> None:
        self.asset_path = path
        self.asset = json.loads(self.asset_path.read_text(encoding="utf-8"))
        self.drag_shape_index = None
        self.drag_last_world = None
        self.drag_mode = None
        self.drag_handle = None
        self._refresh_all()

    def _ensure_preview_dir(self) -> None:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    def _save_asset_surface(self, asset, output_path: Path) -> None:
        pg.init()
        preview = render_visual_asset_to_surface(asset, scale=1.0, padding=12)
        background = pg.Surface(preview.get_size())
        background.fill((248, 244, 234))
        background.blit(preview, (0, 0))
        pg.image.save(background, output_path)


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.geometry("1200x760")
    app = VisualAssetEditor(root)
    root.bind("<Control-s>", lambda _event: app.save_asset())
    root.mainloop()


if __name__ == "__main__":
    main()
