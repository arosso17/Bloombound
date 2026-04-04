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

    def selected_shape_index(self) -> int | None:
        selection = self.shape_listbox.curselection()
        if not selection:
            return None
        return int(selection[0])

    def new_asset(self) -> None:
        self.asset = json.loads(json.dumps(DEFAULT_ASSET))
        self.asset_path = None
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

        for shape in self.asset["shapes"]:
            self._draw_preview_shape(shape, offset_x, offset_y, scale)

    def _draw_preview_shape(self, shape: dict, offset_x: float, offset_y: float, scale: float) -> None:
        fill = rgb_to_hex(shape.get("fill"))
        outline = rgb_to_hex(shape.get("outline"))
        outline_width = max(1, int(shape.get("outline_width", 0) * scale)) if shape.get("outline_width", 0) else 1

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
            )


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.geometry("1200x760")
    app = VisualAssetEditor(root)
    root.bind("<Control-s>", lambda _event: app.save_asset())
    root.mainloop()


if __name__ == "__main__":
    main()
