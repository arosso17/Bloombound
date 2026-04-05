from __future__ import annotations

import json
import sys
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pygame as pg

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gameplay.visual_assets import load_visual_asset, render_visual_asset
MAPS_DIR = REPO_ROOT / "gameplay" / "maps"
VISUALS_DIR = REPO_ROOT / "assets" / "visuals"
MAP_PREVIEW_DIR = REPO_ROOT / "assets" / "map_previews"

DEFAULT_MAP = {
    "map_id": "new_map",
    "name": "New Map",
    "world": {"width": 1600, "height": 960},
    "player_spawns": [],
    "collision_rects": [],
    "traversal_barriers": [],
    "decorations": [],
    "patrol_points": [],
    "egg_spawns": [],
    "spirit_pickups": [],
    "restoration_zones": [],
    "hazard_zones": [],
    "shrine": {"shrine_id": "shrine_1", "x": 240.0, "y": 220.0, "interact_radius": 54, "revive_radius": 72},
    "enemy_spawns": [],
    "final_bloom": {"bloom_id": "heart_bloom", "x": 1200.0, "y": 780.0, "radius": 26, "interact_radius": 74},
}

GRID_SIZE = 16


def deep_copy_map_payload(payload: dict) -> dict:
    return json.loads(json.dumps(payload))


class MapEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Bloombound Map Editor")
        self.map_data = deep_copy_map_payload(DEFAULT_MAP)
        self.map_path: Path | None = None

        self.tool_var = tk.StringVar(value="select")
        self.snap_to_grid_var = tk.BooleanVar(value=True)
        self.map_id_var = tk.StringVar(value=self.map_data["map_id"])
        self.map_name_var = tk.StringVar(value=self.map_data["name"])
        self.world_width_var = tk.StringVar(value=str(self.map_data["world"]["width"]))
        self.world_height_var = tk.StringVar(value=str(self.map_data["world"]["height"]))
        self.decoration_asset_var = tk.StringVar(value="")
        self.decoration_asset_options: list[str] = []
        self.layer_visibility_vars: dict[str, tk.BooleanVar] = {
            "collision_rects": tk.BooleanVar(value=True),
            "traversal_barriers": tk.BooleanVar(value=True),
            "decorations": tk.BooleanVar(value=True),
            "player_spawns": tk.BooleanVar(value=True),
            "egg_spawns": tk.BooleanVar(value=True),
            "spirit_pickups": tk.BooleanVar(value=True),
            "restoration_zones": tk.BooleanVar(value=True),
            "hazard_zones": tk.BooleanVar(value=True),
            "enemy_spawns": tk.BooleanVar(value=True),
            "patrol_points": tk.BooleanVar(value=True),
            "shrine": tk.BooleanVar(value=True),
            "final_bloom": tk.BooleanVar(value=True),
        }

        self.property_vars: dict[str, tk.StringVar] = {
            "id": tk.StringVar(value=""),
            "x": tk.StringVar(value=""),
            "y": tk.StringVar(value=""),
            "width": tk.StringVar(value=""),
            "height": tk.StringVar(value=""),
            "radius": tk.StringVar(value=""),
            "scale": tk.StringVar(value=""),
            "interact_radius": tk.StringVar(value=""),
            "revive_radius": tk.StringVar(value=""),
            "speed": tk.StringVar(value=""),
            "damage_per_second": tk.StringVar(value=""),
            "leash_radius": tk.StringVar(value=""),
            "aggro_radius": tk.StringVar(value=""),
            "alert_duration_ticks": tk.StringVar(value=""),
            "asset_id": tk.StringVar(value=""),
            "restored_by_zone_id": tk.StringVar(value=""),
            "draw_above_entities": tk.StringVar(value=""),
            "enemy_id": tk.StringVar(value=""),
            "required_egg_type": tk.StringVar(value=""),
            "restore_cost": tk.StringVar(value=""),
            "cleared_by_zone_id": tk.StringVar(value=""),
            "slow_multiplier": tk.StringVar(value=""),
            "egg_type": tk.StringVar(value=""),
            "spirit_passable": tk.StringVar(value=""),
        }

        self.selected_ref: tuple[str, int | None] | None = None
        self.preview_scale = 0.55
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.drag_mode: str | None = None
        self.drag_handle: str | None = None
        self.drag_start_world: tuple[float, float] | None = None
        self.drag_start_object: dict | None = None
        self.pan_last_screen: tuple[float, float] | None = None

        self._build_layout()
        self._bind_shortcuts()
        self.refresh_map_files()
        self._refresh_all()

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar_wrap = ttk.Frame(self.root, padding=10)
        sidebar_wrap.grid(row=0, column=0, sticky="nsew")
        sidebar_wrap.rowconfigure(0, weight=1)
        sidebar_wrap.columnconfigure(0, weight=1)

        self.sidebar_canvas = tk.Canvas(sidebar_wrap, width=280, highlightthickness=0)
        self.sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scrollbar = ttk.Scrollbar(sidebar_wrap, orient="vertical", command=self.sidebar_canvas.yview)
        sidebar_scrollbar.grid(row=0, column=1, sticky="ns")
        self.sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)

        sidebar = ttk.Frame(self.sidebar_canvas, padding=2)
        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", self._on_sidebar_frame_configure)
        self.sidebar_canvas.bind("<Configure>", self._on_sidebar_canvas_configure)
        self.sidebar_canvas.bind("<Enter>", self._bind_sidebar_mousewheel)
        self.sidebar_canvas.bind("<Leave>", self._unbind_sidebar_mousewheel)

        canvas_wrap = ttk.Frame(self.root, padding=10)
        canvas_wrap.grid(row=0, column=1, sticky="nsew")
        canvas_wrap.columnconfigure(0, weight=1)
        canvas_wrap.rowconfigure(1, weight=1)

        inspector_wrap = ttk.Frame(self.root, padding=10)
        inspector_wrap.grid(row=0, column=2, sticky="nsew")
        inspector_wrap.rowconfigure(0, weight=1)
        inspector_wrap.columnconfigure(0, weight=1)

        self.inspector_canvas = tk.Canvas(inspector_wrap, width=280, highlightthickness=0)
        self.inspector_canvas.grid(row=0, column=0, sticky="nsew")
        inspector_scrollbar = ttk.Scrollbar(inspector_wrap, orient="vertical", command=self.inspector_canvas.yview)
        inspector_scrollbar.grid(row=0, column=1, sticky="ns")
        self.inspector_canvas.configure(yscrollcommand=inspector_scrollbar.set)

        inspector = ttk.Frame(self.inspector_canvas, padding=2)
        self.inspector_frame = inspector
        self.inspector_window = self.inspector_canvas.create_window((0, 0), window=inspector, anchor="nw")
        inspector.bind("<Configure>", self._on_inspector_frame_configure)
        self.inspector_canvas.bind("<Configure>", self._on_inspector_canvas_configure)
        self.inspector_canvas.bind("<Enter>", self._bind_inspector_mousewheel)
        self.inspector_canvas.bind("<Leave>", self._unbind_inspector_mousewheel)

        self._build_sidebar(sidebar)
        self._build_canvas(canvas_wrap)
        self._build_inspector(inspector)
        self._bind_sidebar_region(sidebar)
        self._bind_inspector_region(inspector)

    def _on_sidebar_frame_configure(self, _event: tk.Event) -> None:
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

    def _on_sidebar_canvas_configure(self, event: tk.Event) -> None:
        self.sidebar_canvas.itemconfigure(self.sidebar_window, width=event.width)

    def _bind_sidebar_mousewheel(self, _event: tk.Event) -> None:
        self.sidebar_canvas.bind_all("<MouseWheel>", self._on_sidebar_mousewheel)
        self.sidebar_canvas.bind_all("<Button-4>", self._on_sidebar_mousewheel_linux_up)
        self.sidebar_canvas.bind_all("<Button-5>", self._on_sidebar_mousewheel_linux_down)

    def _unbind_sidebar_mousewheel(self, _event: tk.Event) -> None:
        self.sidebar_canvas.unbind_all("<MouseWheel>")
        self.sidebar_canvas.unbind_all("<Button-4>")
        self.sidebar_canvas.unbind_all("<Button-5>")

    def _on_sidebar_mousewheel(self, event: tk.Event) -> None:
        direction = -1 if event.delta > 0 else 1
        self.sidebar_canvas.yview_scroll(direction, "units")

    def _on_sidebar_mousewheel_linux_up(self, _event: tk.Event) -> None:
        self.sidebar_canvas.yview_scroll(-1, "units")

    def _on_sidebar_mousewheel_linux_down(self, _event: tk.Event) -> None:
        self.sidebar_canvas.yview_scroll(1, "units")

    def _on_inspector_frame_configure(self, _event: tk.Event) -> None:
        self.inspector_canvas.configure(scrollregion=self.inspector_canvas.bbox("all"))

    def _on_inspector_canvas_configure(self, event: tk.Event) -> None:
        self.inspector_canvas.itemconfigure(self.inspector_window, width=event.width)

    def _bind_inspector_mousewheel(self, _event: tk.Event) -> None:
        self.inspector_canvas.bind_all("<MouseWheel>", self._on_inspector_mousewheel)
        self.inspector_canvas.bind_all("<Button-4>", self._on_inspector_mousewheel_linux_up)
        self.inspector_canvas.bind_all("<Button-5>", self._on_inspector_mousewheel_linux_down)

    def _unbind_inspector_mousewheel(self, _event: tk.Event) -> None:
        self.inspector_canvas.unbind_all("<MouseWheel>")
        self.inspector_canvas.unbind_all("<Button-4>")
        self.inspector_canvas.unbind_all("<Button-5>")

    def _on_inspector_mousewheel(self, event: tk.Event) -> None:
        direction = -1 if event.delta > 0 else 1
        self.inspector_canvas.yview_scroll(direction, "units")

    def _on_inspector_mousewheel_linux_up(self, _event: tk.Event) -> None:
        self.inspector_canvas.yview_scroll(-1, "units")

    def _on_inspector_mousewheel_linux_down(self, _event: tk.Event) -> None:
        self.inspector_canvas.yview_scroll(1, "units")

    def _bind_sidebar_region(self, widget: tk.Misc) -> None:
        widget.bind("<Enter>", self._bind_sidebar_mousewheel, add="+")
        widget.bind("<Leave>", self._unbind_sidebar_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_sidebar_region(child)

    def _bind_inspector_region(self, widget: tk.Misc) -> None:
        widget.bind("<Enter>", self._bind_inspector_mousewheel, add="+")
        widget.bind("<Leave>", self._unbind_inspector_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_inspector_region(child)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        file_row = ttk.Frame(parent)
        file_row.grid(row=0, column=0, sticky="ew")
        ttk.Button(file_row, text="New", command=self.new_map).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(file_row, text="Open", command=self.open_map_dialog).grid(row=0, column=1, padx=4)
        ttk.Button(file_row, text="Save", command=self.save_map).grid(row=0, column=2, padx=4)
        ttk.Button(file_row, text="Save As", command=self.save_map_as).grid(row=0, column=3, padx=(4, 0))
        ttk.Button(parent, text="Export Preview", command=self.export_map_preview).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        maps_header = ttk.Frame(parent)
        maps_header.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(maps_header, text="Maps In Folder").grid(row=0, column=0, sticky="w")
        ttk.Button(maps_header, text="Refresh", command=self.refresh_map_files).grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.map_files_listbox = tk.Listbox(parent, height=8, exportselection=False)
        self.map_files_listbox.grid(row=3, column=0, sticky="ew", pady=(4, 10))
        self.map_files_listbox.bind("<Double-Button-1>", lambda _event: self.open_selected_map_file())

        ttk.Button(parent, text="Open Selected", command=self.open_selected_map_file).grid(row=4, column=0, sticky="ew")

        ttk.Label(parent, text="Tools").grid(row=5, column=0, sticky="w", pady=(12, 4))
        tools_frame = ttk.Frame(parent)
        tools_frame.grid(row=6, column=0, sticky="ew")

        tool_specs = [
            ("select", "Select"),
            ("collision", "Add Collision"),
            ("traversal_barrier", "Add Barrier"),
            ("decoration", "Add Decoration"),
            ("patrol_point", "Add Patrol Point"),
            ("player_spawn", "Add Player Spawn"),
            ("egg_spawn", "Add Egg Spawn"),
            ("spirit_pickup", "Add Spirit Pickup"),
            ("restoration_zone", "Add Restoration"),
            ("hazard_zone", "Add Hazard"),
            ("enemy_spawn", "Add Enemy Spawn"),
            ("shrine", "Set Shrine"),
            ("final_bloom", "Set Final Bloom"),
        ]
        for index, (value, label) in enumerate(tool_specs):
            ttk.Radiobutton(tools_frame, text=label, variable=self.tool_var, value=value).grid(row=index, column=0, sticky="w", pady=2)

        ttk.Checkbutton(parent, text="Snap To Grid", variable=self.snap_to_grid_var).grid(row=7, column=0, sticky="w", pady=(10, 4))

        ttk.Label(parent, text="Decoration Asset").grid(row=8, column=0, sticky="w", pady=(12, 4))
        self.decoration_asset_combo = ttk.Combobox(
            parent,
            textvariable=self.decoration_asset_var,
            state="readonly",
            height=12,
        )
        self.decoration_asset_combo.grid(row=9, column=0, sticky="ew")

        ttk.Label(parent, text="Layers").grid(row=10, column=0, sticky="w", pady=(12, 4))
        layers_frame = ttk.Frame(parent)
        layers_frame.grid(row=11, column=0, sticky="ew")
        layer_specs = [
            ("collision_rects", "Collision"),
            ("traversal_barriers", "Barriers"),
            ("decorations", "Decorations"),
            ("player_spawns", "Player Spawns"),
            ("egg_spawns", "Eggs"),
            ("spirit_pickups", "Spirit Pickups"),
            ("restoration_zones", "Restores"),
            ("hazard_zones", "Hazards"),
            ("enemy_spawns", "Enemies"),
            ("patrol_points", "Patrols"),
            ("shrine", "Shrine"),
            ("final_bloom", "Final Bloom"),
        ]
        for index, (section, label) in enumerate(layer_specs):
            ttk.Checkbutton(
                layers_frame,
                text=label,
                variable=self.layer_visibility_vars[section],
                command=self._draw_canvas,
            ).grid(row=index, column=0, sticky="w", pady=1)

        ttk.Label(parent, text="Objects").grid(row=12, column=0, sticky="w", pady=(12, 4))
        self.object_listbox = tk.Listbox(parent, height=20, exportselection=False)
        self.object_listbox.grid(row=13, column=0, sticky="nsew")
        self.object_listbox.bind("<<ListboxSelect>>", lambda _event: self._load_selected_object_from_list())
        parent.rowconfigure(13, weight=1)

    def _build_canvas(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Map").grid(row=0, column=0, sticky="w")
        self.canvas = tk.Canvas(parent, width=980, height=760, background="#e9e2cf", highlightthickness=1, highlightbackground="#988f7e")
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.canvas.bind("<Button-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", lambda event: self.on_mousewheel_linux(event, zoom_in=True))
        self.canvas.bind("<Button-5>", lambda event: self.on_mousewheel_linux(event, zoom_in=False))
        self.canvas.bind("<Configure>", lambda _event: self._draw_canvas())

    def _build_inspector(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Map Properties").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="Map ID").grid(row=1, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(parent, textvariable=self.map_id_var, width=24).grid(row=2, column=0, sticky="ew")
        ttk.Label(parent, text="Name").grid(row=3, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(parent, textvariable=self.map_name_var, width=24).grid(row=4, column=0, sticky="ew")

        size_row = ttk.Frame(parent)
        size_row.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(size_row, text="W").grid(row=0, column=0)
        ttk.Entry(size_row, textvariable=self.world_width_var, width=8).grid(row=0, column=1, padx=(4, 12))
        ttk.Label(size_row, text="H").grid(row=0, column=2)
        ttk.Entry(size_row, textvariable=self.world_height_var, width=8).grid(row=0, column=3, padx=(4, 0))
        ttk.Button(parent, text="Apply Map Properties", command=self.apply_map_properties).grid(row=6, column=0, sticky="ew", pady=(8, 14))

        ttk.Label(parent, text="Selected Object").grid(row=7, column=0, sticky="w")

        field_specs = [
            ("id", "ID"),
            ("x", "X"),
            ("y", "Y"),
            ("width", "Width"),
            ("height", "Height"),
            ("radius", "Radius"),
            ("spirit_passable", "Spirit Passable"),
            ("scale", "Scale"),
            ("interact_radius", "Interact Radius"),
            ("revive_radius", "Revive Radius"),
            ("speed", "Speed"),
            ("damage_per_second", "Damage / Sec"),
            ("leash_radius", "Leash Radius"),
            ("aggro_radius", "Aggro Radius"),
            ("alert_duration_ticks", "Alert Ticks"),
            ("asset_id", "Asset ID"),
            ("restored_by_zone_id", "Restored By Zone"),
            ("draw_above_entities", "Draw Above Items"),
            ("enemy_id", "Enemy ID"),
            ("required_egg_type", "Needs Egg Type"),
            ("restore_cost", "Restore Cost"),
            ("cleared_by_zone_id", "Cleared By Zone"),
            ("slow_multiplier", "Slow Multiplier"),
            ("egg_type", "Egg Type"),
        ]
        base_row = 8
        for index, (field_key, label) in enumerate(field_specs):
            row_index = base_row + index * 2
            ttk.Label(parent, text=label).grid(row=row_index, column=0, sticky="w", pady=(3, 0))
            if field_key == "asset_id":
                self.asset_id_combo = ttk.Combobox(
                    parent,
                    textvariable=self.property_vars[field_key],
                    state="readonly",
                    height=12,
                )
                self.asset_id_combo.grid(row=row_index + 1, column=0, sticky="ew", pady=(0, 2))
                self.asset_id_combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_selected_decoration_asset())
            else:
                ttk.Entry(parent, textvariable=self.property_vars[field_key], width=24).grid(row=row_index + 1, column=0, sticky="ew", pady=(0, 2))

        action_row = base_row + len(field_specs) * 2
        ttk.Button(parent, text="Apply Object Changes", command=self.apply_selected_object_changes).grid(row=action_row, column=0, sticky="ew", pady=(10, 4))
        ttk.Button(parent, text="Delete Selected", command=self.delete_selected_object).grid(row=action_row + 1, column=0, sticky="ew")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Delete>", lambda _event: self.delete_selected_object())
        self.root.bind("<Control-s>", lambda _event: self.save_map())
        self.root.bind("<plus>", lambda _event: self._zoom_at_canvas_center(1.1))
        self.root.bind("<minus>", lambda _event: self._zoom_at_canvas_center(1 / 1.1))

    def new_map(self) -> None:
        self.map_data = deep_copy_map_payload(DEFAULT_MAP)
        self.map_path = None
        self.selected_ref = None
        self.camera_x = 0.0
        self.camera_y = 0.0
        self._refresh_all()

    def open_map_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Open map",
            initialdir=MAPS_DIR,
            filetypes=[("JSON Files", "*.json")],
        )
        if path:
            self._load_map_path(Path(path))

    def open_selected_map_file(self) -> None:
        selection = self.map_files_listbox.curselection()
        if not selection:
            return
        name = self.map_files_listbox.get(selection[0])
        self._load_map_path(MAPS_DIR / name)

    def save_map(self) -> None:
        self._sync_map_metadata()
        if self.map_path is None:
            self.save_map_as()
            return
        self.map_path.write_text(json.dumps(self.map_data, indent=2) + "\n", encoding="utf-8")
        self.refresh_map_files(select_name=self.map_path.name)
        messagebox.showinfo("Saved", f"Saved {self.map_path.name}")

    def save_map_as(self) -> None:
        self._sync_map_metadata()
        initial_name = f"{self.map_data['map_id']}.json"
        path = filedialog.asksaveasfilename(
            title="Save map as",
            initialdir=MAPS_DIR,
            initialfile=initial_name,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not path:
            return
        self.map_path = Path(path)
        self.save_map()

    def export_map_preview(self) -> None:
        try:
            self._sync_map_metadata()
        except ValueError as exc:
            messagebox.showerror("Invalid map", str(exc))
            return

        MAP_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        output_path = MAP_PREVIEW_DIR / f"{self.map_data['map_id']}.png"
        pg.init()

        world_width = int(self.map_data["world"]["width"])
        world_height = int(self.map_data["world"]["height"])
        max_width = 1600
        max_height = 1200
        scale = min(max_width / max(1, world_width), max_height / max(1, world_height))
        scale = max(0.2, min(1.0, scale))

        surface = pg.Surface((max(1, int(world_width * scale)), max(1, int(world_height * scale))), pg.SRCALPHA)
        self._render_map_preview(surface, scale)
        pg.image.save(surface, output_path)
        messagebox.showinfo("Exported", f"Exported {output_path.name} to {output_path.parent}")

    def refresh_map_files(self, select_name: str | None = None) -> None:
        self.map_files_listbox.delete(0, tk.END)
        map_files = sorted(MAPS_DIR.glob("*.json"))
        for path in map_files:
            self.map_files_listbox.insert(tk.END, path.name)

        target_name = select_name or (self.map_path.name if self.map_path else None)
        if target_name is None:
            return
        for index, path in enumerate(map_files):
            if path.name == target_name:
                self.map_files_listbox.selection_clear(0, tk.END)
                self.map_files_listbox.selection_set(index)
                self.map_files_listbox.activate(index)
                self.map_files_listbox.see(index)
                break

    def refresh_visual_asset_files(self) -> None:
        self.decoration_asset_options = [path.stem for path in sorted(VISUALS_DIR.glob("*.json"))]
        if not self.decoration_asset_options:
            self.decoration_asset_options = ["decoration_asset"]
        self.decoration_asset_combo["values"] = self.decoration_asset_options
        if hasattr(self, "asset_id_combo"):
            self.asset_id_combo["values"] = self.decoration_asset_options
        current_default = self.decoration_asset_var.get().strip()
        if current_default not in self.decoration_asset_options:
            self.decoration_asset_var.set(self.decoration_asset_options[0])
        current_object_asset = self.property_vars["asset_id"].get().strip()
        if current_object_asset and current_object_asset not in self.decoration_asset_options:
            self.property_vars["asset_id"].set(self.decoration_asset_options[0])

    def apply_map_properties(self) -> None:
        try:
            width = int(float(self.world_width_var.get()))
            height = int(float(self.world_height_var.get()))
        except ValueError as exc:
            messagebox.showerror("Invalid map size", str(exc))
            return
        self.map_data["map_id"] = self.map_id_var.get().strip() or "new_map"
        self.map_data["name"] = self.map_name_var.get().strip() or "New Map"
        self.map_data["world"]["width"] = max(GRID_SIZE, width)
        self.map_data["world"]["height"] = max(GRID_SIZE, height)
        self._draw_canvas()

    def apply_selected_object_changes(self) -> None:
        target = self._selected_object()
        if target is None:
            return
        section, _, obj = target
        try:
            obj["x"] = self._parse_float_var("x")
            obj["y"] = self._parse_float_var("y")
            if section == "collision_rects":
                obj["rect_id"] = self.property_vars["id"].get().strip() or obj["rect_id"]
                obj["width"] = max(1.0, self._parse_float_var("width"))
                obj["height"] = max(1.0, self._parse_float_var("height"))
                obj["restored_by_zone_id"] = self.property_vars["restored_by_zone_id"].get().strip()
            elif section == "traversal_barriers":
                obj["barrier_id"] = self.property_vars["id"].get().strip() or obj["barrier_id"]
                obj["width"] = max(1.0, self._parse_float_var("width"))
                obj["height"] = max(1.0, self._parse_float_var("height"))
                obj["cleared_by_zone_id"] = self.property_vars["cleared_by_zone_id"].get().strip()
                obj["spirit_passable"] = self._parse_bool_var("spirit_passable")
            elif section == "decorations":
                obj["decoration_id"] = self.property_vars["id"].get().strip() or obj["decoration_id"]
                obj["asset_id"] = self.property_vars["asset_id"].get().strip() or obj["asset_id"]
                self.decoration_asset_var.set(obj["asset_id"])
                obj["restored_by_zone_id"] = self.property_vars["restored_by_zone_id"].get().strip()
                obj["draw_above_entities"] = self._parse_bool_var("draw_above_entities")
                obj["scale"] = max(0.1, self._parse_float_var("scale"))
            elif section == "patrol_points":
                obj["point_id"] = self.property_vars["id"].get().strip() or obj["point_id"]
                obj["enemy_id"] = self.property_vars["enemy_id"].get().strip() or obj["enemy_id"]
            elif section == "egg_spawns":
                obj["spawn_id"] = self.property_vars["id"].get().strip() or obj["spawn_id"]
                obj["egg_type"] = self.property_vars["egg_type"].get().strip() or obj.get("egg_type", "revival")
                obj["radius"] = max(1.0, self._parse_float_var("radius"))
            elif section == "spirit_pickups":
                obj["pickup_id"] = self.property_vars["id"].get().strip() or obj["pickup_id"]
                obj["radius"] = max(1.0, self._parse_float_var("radius"))
            elif section == "restoration_zones":
                obj["zone_id"] = self.property_vars["id"].get().strip() or obj["zone_id"]
                obj["radius"] = max(8.0, self._parse_float_var("radius"))
                obj["interact_radius"] = max(8.0, self._parse_float_var("interact_radius"))
                obj["required_egg_type"] = self.property_vars["required_egg_type"].get().strip() or obj.get("required_egg_type", "restoration")
                obj["restore_cost"] = max(1, int(self._parse_float_var("restore_cost")))
            elif section == "hazard_zones":
                obj["zone_id"] = self.property_vars["id"].get().strip() or obj["zone_id"]
                obj["radius"] = max(8.0, self._parse_float_var("radius"))
                obj["damage_per_second"] = max(0.0, self._parse_float_var("damage_per_second"))
                obj["slow_multiplier"] = max(0.1, min(1.0, self._parse_float_var("slow_multiplier")))
                obj["cleared_by_zone_id"] = self.property_vars["cleared_by_zone_id"].get().strip()
            elif section == "enemy_spawns":
                obj["enemy_id"] = self.property_vars["id"].get().strip() or obj["enemy_id"]
                obj["radius"] = max(1.0, self._parse_float_var("radius"))
                obj["speed"] = max(1.0, self._parse_float_var("speed"))
                obj["damage_per_second"] = max(0.0, self._parse_float_var("damage_per_second"))
                obj["leash_radius"] = max(8.0, self._parse_float_var("leash_radius"))
                obj["aggro_radius"] = max(8.0, self._parse_float_var("aggro_radius"))
                obj["alert_duration_ticks"] = max(1, int(self._parse_float_var("alert_duration_ticks")))
            elif section == "shrine":
                obj["shrine_id"] = self.property_vars["id"].get().strip() or obj["shrine_id"]
                obj["interact_radius"] = max(1.0, self._parse_float_var("interact_radius"))
                obj["revive_radius"] = max(1.0, self._parse_float_var("revive_radius"))
            elif section == "final_bloom":
                obj["bloom_id"] = self.property_vars["id"].get().strip() or obj["bloom_id"]
                obj["radius"] = max(1.0, self._parse_float_var("radius"))
                obj["interact_radius"] = max(1.0, self._parse_float_var("interact_radius"))
        except ValueError as exc:
            messagebox.showerror("Invalid object value", str(exc))
            return
        self._refresh_object_list()
        self._load_selected_object_properties()
        self._draw_canvas()

    def delete_selected_object(self) -> None:
        target = self._selected_object()
        if target is None:
            return
        section, index, _ = target
        if section in {"shrine", "final_bloom"}:
            messagebox.showinfo("Protected Object", "Shrine and Final Bloom are required map objects and cannot be deleted.")
            return
        if index is None:
            return
        del self.map_data[section][index]
        self.selected_ref = None
        self._refresh_object_list()
        self._clear_property_fields()
        self._draw_canvas()

    def on_left_press(self, event: tk.Event) -> None:
        world_x, world_y = self._screen_to_world(event.x, event.y)
        world_x, world_y = self._snap(world_x, world_y)
        tool = self.tool_var.get()

        if tool != "select":
            self._create_object_with_tool(tool, world_x, world_y)
            return

        if self.selected_ref is not None:
            handle_name = self._handle_at_screen_point(self.selected_ref, event.x, event.y)
            if handle_name is not None:
                self.drag_mode = "resize"
                self.drag_handle = handle_name
                self.drag_start_world = (world_x, world_y)
                selected = self._selected_object()
                self.drag_start_object = deepcopy(selected[2]) if selected else None
                return

        object_ref = self._object_at_world_point(world_x, world_y)
        self._select_object_ref(object_ref)
        if object_ref is None:
            self.drag_mode = None
            self.drag_handle = None
            self.drag_start_world = None
            self.drag_start_object = None
            return

        self.drag_mode = "move"
        self.drag_handle = None
        self.drag_start_world = (world_x, world_y)
        selected = self._selected_object()
        self.drag_start_object = deepcopy(selected[2]) if selected else None

    def on_left_drag(self, event: tk.Event) -> None:
        if self.drag_mode not in {"move", "resize"} or self.selected_ref is None or self.drag_start_world is None or self.drag_start_object is None:
            return

        target = self._selected_object()
        if target is None:
            return
        section, _, obj = target
        world_x, world_y = self._screen_to_world(event.x, event.y)
        world_x, world_y = self._snap(world_x, world_y)
        start_x, start_y = self.drag_start_world

        if self.drag_mode == "move":
            delta_x = world_x - start_x
            delta_y = world_y - start_y
            obj["x"] = round(float(self.drag_start_object.get("x", 0.0)) + delta_x, 2)
            obj["y"] = round(float(self.drag_start_object.get("y", 0.0)) + delta_y, 2)
        else:
            self._resize_object(section, obj, self.drag_start_object, self.drag_handle, world_x, world_y)

        self._constrain_object_to_world(section, obj)
        self._load_selected_object_properties()
        self._draw_canvas()

    def on_left_release(self, _event: tk.Event) -> None:
        self.drag_mode = None
        self.drag_handle = None
        self.drag_start_world = None
        self.drag_start_object = None

    def on_right_press(self, event: tk.Event) -> None:
        self.pan_last_screen = (event.x, event.y)

    def on_right_drag(self, event: tk.Event) -> None:
        if self.pan_last_screen is None:
            return
        last_x, last_y = self.pan_last_screen
        delta_x = (event.x - last_x) / self.preview_scale
        delta_y = (event.y - last_y) / self.preview_scale
        self.camera_x -= delta_x
        self.camera_y -= delta_y
        self.pan_last_screen = (event.x, event.y)
        self._clamp_camera()
        self._draw_canvas()

    def on_right_release(self, _event: tk.Event) -> None:
        self.pan_last_screen = None

    def on_mousewheel(self, event: tk.Event) -> None:
        zoom_factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._zoom_at_screen_point(event.x, event.y, zoom_factor)

    def on_mousewheel_linux(self, event: tk.Event, *, zoom_in: bool) -> None:
        zoom_factor = 1.1 if zoom_in else 1 / 1.1
        self._zoom_at_screen_point(event.x, event.y, zoom_factor)

    def _zoom_at_canvas_center(self, zoom_factor: float) -> None:
        width = int(self.canvas.winfo_width() or 980)
        height = int(self.canvas.winfo_height() or 760)
        self._zoom_at_screen_point(width / 2, height / 2, zoom_factor)

    def _zoom_at_screen_point(self, screen_x: float, screen_y: float, zoom_factor: float) -> None:
        before_x, before_y = self._screen_to_world(screen_x, screen_y)
        self.preview_scale = max(0.1, min(3.0, self.preview_scale * zoom_factor))
        after_x, after_y = self._screen_to_world(screen_x, screen_y)
        self.camera_x += before_x - after_x
        self.camera_y += before_y - after_y
        self._clamp_camera()
        self._draw_canvas()

    def _refresh_all(self) -> None:
        self.map_id_var.set(self.map_data["map_id"])
        self.map_name_var.set(self.map_data["name"])
        self.world_width_var.set(str(self.map_data["world"]["width"]))
        self.world_height_var.set(str(self.map_data["world"]["height"]))
        self.refresh_visual_asset_files()
        self.refresh_map_files()
        self._refresh_object_list()
        self._load_selected_object_properties()
        self._draw_canvas()

    def _refresh_object_list(self) -> None:
        self.object_listbox.delete(0, tk.END)
        labels = self._object_labels()
        for _, label in labels:
            self.object_listbox.insert(tk.END, label)
        if self.selected_ref is None:
            return
        for index, (ref, _) in enumerate(labels):
            if ref == self.selected_ref:
                self.object_listbox.selection_clear(0, tk.END)
                self.object_listbox.selection_set(index)
                self.object_listbox.activate(index)
                self.object_listbox.see(index)
                break

    def _object_labels(self) -> list[tuple[tuple[str, int | None], str]]:
        labels: list[tuple[tuple[str, int | None], str]] = []
        for index, rect in enumerate(self.map_data["collision_rects"]):
            labels.append((("collision_rects", index), f"Collision: {rect['rect_id']}"))
        for index, barrier in enumerate(self.map_data["traversal_barriers"]):
            barrier_kind = "Spirit" if barrier.get("spirit_passable", False) else "Solid"
            labels.append((("traversal_barriers", index), f"Barrier: {barrier['barrier_id']} ({barrier_kind})"))
        for index, decoration in enumerate(self.map_data["decorations"]):
            layer_tag = " FG" if decoration.get("draw_above_entities", False) else ""
            labels.append((("decorations", index), f"Decoration: {decoration['decoration_id']} ({decoration['asset_id']}{layer_tag})"))
        for index, point in enumerate(self.map_data["patrol_points"]):
            labels.append((("patrol_points", index), f"Patrol: {point['point_id']} -> {point['enemy_id']}"))
        for index, _spawn in enumerate(self.map_data["player_spawns"]):
            labels.append((("player_spawns", index), f"Player Spawn {index + 1}"))
        for index, spawn in enumerate(self.map_data["egg_spawns"]):
            labels.append((("egg_spawns", index), f"Egg: {spawn['spawn_id']}"))
        for index, pickup in enumerate(self.map_data["spirit_pickups"]):
            labels.append((("spirit_pickups", index), f"Spirit Pickup: {pickup['pickup_id']}"))
        for index, zone in enumerate(self.map_data["restoration_zones"]):
            labels.append((("restoration_zones", index), f"Restore: {zone['zone_id']}"))
        for index, zone in enumerate(self.map_data["hazard_zones"]):
            labels.append((("hazard_zones", index), f"Hazard: {zone['zone_id']}"))
        labels.append((("shrine", None), f"Shrine: {self.map_data['shrine']['shrine_id']}"))
        for index, enemy in enumerate(self.map_data["enemy_spawns"]):
            labels.append((("enemy_spawns", index), f"Enemy: {enemy['enemy_id']}"))
        labels.append((("final_bloom", None), f"Final Bloom: {self.map_data['final_bloom']['bloom_id']}"))
        return labels

    def _load_selected_object_from_list(self) -> None:
        selection = self.object_listbox.curselection()
        if not selection:
            return
        ref, _ = self._object_labels()[selection[0]]
        self._select_object_ref(ref)

    def _select_object_ref(self, ref: tuple[str, int | None] | None) -> None:
        self.selected_ref = ref
        self._refresh_object_list()
        self._load_selected_object_properties()
        self._draw_canvas()

    def _selected_object(self) -> tuple[str, int | None, dict] | None:
        if self.selected_ref is None:
            return None
        section, index = self.selected_ref
        if index is None:
            return section, None, self.map_data[section]
        if index < 0 or index >= len(self.map_data[section]):
            return None
        return section, index, self.map_data[section][index]

    def _load_selected_object_properties(self) -> None:
        target = self._selected_object()
        if target is None:
            self._clear_property_fields()
            return
        section, _, obj = target
        self._set_property("x", obj.get("x", ""))
        self._set_property("y", obj.get("y", ""))
        self._set_property("width", obj.get("width", ""))
        self._set_property("height", obj.get("height", ""))
        self._set_property("radius", obj.get("radius", ""))
        self._set_property("spirit_passable", obj.get("spirit_passable", ""))
        self._set_property("scale", obj.get("scale", ""))
        self._set_property("interact_radius", obj.get("interact_radius", ""))
        self._set_property("revive_radius", obj.get("revive_radius", ""))
        self._set_property("speed", obj.get("speed", ""))
        self._set_property("damage_per_second", obj.get("damage_per_second", ""))
        self._set_property("leash_radius", obj.get("leash_radius", 260.0 if section == "enemy_spawns" else ""))
        self._set_property("aggro_radius", obj.get("aggro_radius", 220.0 if section == "enemy_spawns" else ""))
        self._set_property("alert_duration_ticks", obj.get("alert_duration_ticks", 80 if section == "enemy_spawns" else ""))
        self._set_property("asset_id", obj.get("asset_id", ""))
        self._set_property("restored_by_zone_id", obj.get("restored_by_zone_id", ""))
        self._set_property("draw_above_entities", obj.get("draw_above_entities", ""))
        self._set_property("enemy_id", obj.get("enemy_id", ""))
        self._set_property("required_egg_type", obj.get("required_egg_type", ""))
        self._set_property("restore_cost", obj.get("restore_cost", ""))
        self._set_property("cleared_by_zone_id", obj.get("cleared_by_zone_id", ""))
        self._set_property("slow_multiplier", obj.get("slow_multiplier", ""))
        self._set_property("egg_type", obj.get("egg_type", ""))

        if section == "collision_rects":
            self._set_property("id", obj.get("rect_id", ""))
        elif section == "traversal_barriers":
            self._set_property("id", obj.get("barrier_id", ""))
        elif section == "decorations":
            self._set_property("id", obj.get("decoration_id", ""))
            asset_id = obj.get("asset_id", "")
            if asset_id in self.decoration_asset_options:
                self.decoration_asset_var.set(asset_id)
        elif section == "patrol_points":
            self._set_property("id", obj.get("point_id", ""))
        elif section == "egg_spawns":
            self._set_property("id", obj.get("spawn_id", ""))
        elif section == "spirit_pickups":
            self._set_property("id", obj.get("pickup_id", ""))
        elif section in {"restoration_zones", "hazard_zones"}:
            self._set_property("id", obj.get("zone_id", ""))
        elif section == "enemy_spawns":
            self._set_property("id", obj.get("enemy_id", ""))
        elif section == "shrine":
            self._set_property("id", obj.get("shrine_id", ""))
        elif section == "final_bloom":
            self._set_property("id", obj.get("bloom_id", ""))
        else:
            self._set_property("id", "")

    def _clear_property_fields(self) -> None:
        for key in self.property_vars:
            self.property_vars[key].set("")

    def _set_property(self, key: str, value: object) -> None:
        self.property_vars[key].set("" if value == "" else str(value))

    def _sync_map_metadata(self) -> None:
        self.apply_map_properties()

    def _layer_visible(self, section: str) -> bool:
        variable = self.layer_visibility_vars.get(section)
        return True if variable is None else bool(variable.get())

    def _ensure_layer_visible(self, section: str) -> None:
        if section in self.layer_visibility_vars:
            self.layer_visibility_vars[section].set(True)

    def _parse_float_var(self, key: str) -> float:
        value = self.property_vars[key].get().strip()
        if value == "":
            raise ValueError(f"{key} is required.")
        return float(value)

    def _parse_bool_var(self, key: str) -> bool:
        value = self.property_vars[key].get().strip().lower()
        if value in {"", "0", "false", "no", "off"}:
            return False
        if value in {"1", "true", "yes", "on"}:
            return True
        raise ValueError(f"{key} must be true/false.")

    def _draw_canvas(self) -> None:
        self.canvas.delete("all")
        canvas_width = int(self.canvas.winfo_width() or 980)
        canvas_height = int(self.canvas.winfo_height() or 760)
        self._clamp_camera()

        self.canvas.create_rectangle(0, 0, canvas_width, canvas_height, fill="#e9e2cf", outline="")
        self._draw_grid(canvas_width, canvas_height)

        world_w = self.map_data["world"]["width"]
        world_h = self.map_data["world"]["height"]
        left, top = self._world_to_screen(0, 0)
        right, bottom = self._world_to_screen(world_w, world_h)
        self.canvas.create_rectangle(left, top, right, bottom, outline="#6f6759", width=2, fill="#f5efde")

        if self._layer_visible("collision_rects"):
            for index, rect in enumerate(self.map_data["collision_rects"]):
                self._draw_collision_rect(index, rect)
        if self._layer_visible("traversal_barriers"):
            for index, barrier in enumerate(self.map_data["traversal_barriers"]):
                self._draw_traversal_barrier(index, barrier)
        if self._layer_visible("decorations"):
            for index, decoration in enumerate(self.map_data["decorations"]):
                self._draw_decoration_marker(index, decoration)
        if self._layer_visible("hazard_zones"):
            for index, zone in enumerate(self.map_data["hazard_zones"]):
                self._draw_radius_marker(zone, "#b56161", "HZ")
        if self._layer_visible("restoration_zones"):
            for index, zone in enumerate(self.map_data["restoration_zones"]):
                self._draw_radius_marker(zone, "#73ab73", "RZ")
        if self._layer_visible("player_spawns"):
            for index, spawn in enumerate(self.map_data["player_spawns"]):
                self._draw_point_marker(spawn["x"], spawn["y"], "#4f89ff", "P")
        if self._layer_visible("patrol_points"):
            for index, point in enumerate(self.map_data["patrol_points"]):
                self._draw_point_marker(point["x"], point["y"], "#8b6bd3", "PT")
        if self._layer_visible("egg_spawns"):
            for index, spawn in enumerate(self.map_data["egg_spawns"]):
                egg_fill = "#88cfa9" if spawn.get("egg_type") == "restoration" else "#f28bb1"
                self._draw_point_marker(spawn["x"], spawn["y"], egg_fill, "E")
        if self._layer_visible("spirit_pickups"):
            for index, pickup in enumerate(self.map_data["spirit_pickups"]):
                self._draw_point_marker(pickup["x"], pickup["y"], "#b9d9ff", "SP")
        if self._layer_visible("shrine"):
            self._draw_radius_marker(self.map_data["shrine"], "#ffd56c", "S")
        if self._layer_visible("enemy_spawns"):
            for index, enemy in enumerate(self.map_data["enemy_spawns"]):
                self._draw_radius_marker(enemy, "#6b8a63", "B")
        if self._layer_visible("final_bloom"):
            self._draw_radius_marker(self.map_data["final_bloom"], "#ffb6c7", "H")

        if self.selected_ref is not None:
            self._draw_selection_overlay(self.selected_ref)

    def _render_map_preview(self, surface: pg.Surface, scale: float) -> None:
        background_color = (233, 226, 207)
        world_fill = (245, 239, 222)
        dead_hedge_fill = (122, 106, 86)
        dead_hedge_accent = (150, 131, 108)
        restored_hedge_fill = (111, 139, 96)
        restored_hedge_accent = (140, 171, 122)
        hazard_fill = (164, 88, 88, 40)
        hazard_outline = (132, 61, 61, 148)
        restore_fill = (122, 174, 122, 28)
        restore_outline = (81, 132, 84, 120)
        barrier_fill = (144, 171, 111)
        spirit_barrier_fill = (156, 193, 218)
        text_color = (48, 58, 64)

        surface.fill(background_color)
        pg.draw.rect(surface, world_fill, surface.get_rect())

        def world_to_screen(x: float, y: float) -> tuple[int, int]:
            return (int(x * scale), int(y * scale))

        def draw_radius_zone(obj: dict, fill: tuple[int, ...], outline: tuple[int, ...]) -> None:
            center = world_to_screen(float(obj["x"]), float(obj["y"]))
            radius = max(8, int(float(obj.get("radius", 12.0)) * scale))
            overlay = pg.Surface((radius * 2 + 6, radius * 2 + 6), pg.SRCALPHA)
            pg.draw.circle(overlay, fill, (radius + 3, radius + 3), radius)
            surface.blit(overlay, (center[0] - radius - 3, center[1] - radius - 3))
            pg.draw.circle(surface, outline, center, radius, width=2)

        for zone in self.map_data["hazard_zones"]:
            draw_radius_zone(zone, hazard_fill, hazard_outline)
        for zone in self.map_data["restoration_zones"]:
            draw_radius_zone(zone, restore_fill, restore_outline)

        for rect in self.map_data["collision_rects"]:
            restored = bool(rect.get("restored_by_zone_id"))
            fill = restored_hedge_fill if restored else dead_hedge_fill
            accent = restored_hedge_accent if restored else dead_hedge_accent
            rect_surface = pg.Rect(
                int(float(rect["x"]) * scale),
                int(float(rect["y"]) * scale),
                max(1, int(float(rect["width"]) * scale)),
                max(1, int(float(rect["height"]) * scale)),
            )
            pg.draw.rect(surface, fill, rect_surface, border_radius=max(2, min(12, int(12 * scale))))
            accent_rect = rect_surface.inflate(max(-2, int(-8 * scale)), max(-2, int(-8 * scale)))
            if accent_rect.width > 0 and accent_rect.height > 0:
                pg.draw.rect(surface, accent, accent_rect, border_radius=max(2, min(10, int(10 * scale))))

        for barrier in self.map_data["traversal_barriers"]:
            rect_surface = pg.Rect(
                int(float(barrier["x"]) * scale),
                int(float(barrier["y"]) * scale),
                max(1, int(float(barrier["width"]) * scale)),
                max(1, int(float(barrier["height"]) * scale)),
            )
            fill = spirit_barrier_fill if barrier.get("spirit_passable", False) else barrier_fill
            pg.draw.rect(surface, fill, rect_surface, border_radius=max(2, min(10, int(10 * scale))))
            pg.draw.rect(surface, (79, 111, 136) if barrier.get("spirit_passable", False) else (91, 106, 65), rect_surface, width=2, border_radius=max(2, min(10, int(10 * scale))))

        self._render_preview_decorations(surface, scale, foreground_only=False)

        shrine_asset = load_visual_asset("shrine")
        render_visual_asset(surface, shrine_asset, world_to_screen(self.map_data["shrine"]["x"], self.map_data["shrine"]["y"]), scale=scale)

        for egg in self.map_data["egg_spawns"]:
            egg_asset = "egg_restoration" if egg.get("egg_type") == "restoration" else "egg_revival"
            render_visual_asset(surface, load_visual_asset(egg_asset), world_to_screen(egg["x"], egg["y"]), scale=scale)

        for pickup in self.map_data["spirit_pickups"]:
            render_visual_asset(surface, load_visual_asset("spirit_seed"), world_to_screen(pickup["x"], pickup["y"]), scale=scale)

        for enemy in self.map_data["enemy_spawns"]:
            render_visual_asset(surface, load_visual_asset("bramble_nest"), world_to_screen(enemy["x"], enemy["y"]), scale=scale)

        bloom_asset = load_visual_asset("heart_bloom_dormant")
        render_visual_asset(surface, bloom_asset, world_to_screen(self.map_data["final_bloom"]["x"], self.map_data["final_bloom"]["y"]), scale=scale)

        self._render_preview_decorations(surface, scale, foreground_only=True)

        try:
            font = pg.font.SysFont(None, max(20, int(28 * scale)))
            title = font.render(self.map_data["name"], True, text_color)
            surface.blit(title, (16, 12))
        except Exception:
            pass

    def _render_preview_decorations(self, surface: pg.Surface, scale: float, *, foreground_only: bool) -> None:
        for decoration in self.map_data["decorations"]:
            if bool(decoration.get("draw_above_entities", False)) != foreground_only:
                continue
            asset_id = str(decoration.get("asset_id", "")).strip()
            if not asset_id:
                continue
            try:
                asset = load_visual_asset(asset_id)
            except FileNotFoundError:
                continue
            center = (int(float(decoration["x"]) * scale), int(float(decoration["y"]) * scale))
            render_visual_asset(
                surface,
                asset,
                center,
                scale=max(0.1, float(decoration.get("scale", 1.0)) * scale),
            )

    def _draw_grid(self, canvas_width: int, canvas_height: int) -> None:
        step = GRID_SIZE * self.preview_scale
        if step < 8:
            return
        start_x = -((self.camera_x * self.preview_scale) % step)
        start_y = -((self.camera_y * self.preview_scale) % step)
        color = "#ddd5c1"
        x = start_x
        while x <= canvas_width:
            self.canvas.create_line(x, 0, x, canvas_height, fill=color)
            x += step
        y = start_y
        while y <= canvas_height:
            self.canvas.create_line(0, y, canvas_width, y, fill=color)
            y += step

    def _draw_collision_rect(self, index: int, rect: dict) -> None:
        x1, y1 = self._world_to_screen(rect["x"], rect["y"])
        x2, y2 = self._world_to_screen(rect["x"] + rect["width"], rect["y"] + rect["height"])
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#7aa06c", outline="#4f6c45", width=2)
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=rect["rect_id"], fill="#23311f")

    def _draw_traversal_barrier(self, index: int, barrier: dict) -> None:
        x1, y1 = self._world_to_screen(barrier["x"], barrier["y"])
        x2, y2 = self._world_to_screen(barrier["x"] + barrier["width"], barrier["y"] + barrier["height"])
        fill = "#9cc1da" if barrier.get("spirit_passable", False) else "#90ab6f"
        outline = "#4f6f88" if barrier.get("spirit_passable", False) else "#5b6a41"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2, dash=(4, 2))
        label = barrier["barrier_id"]
        if barrier.get("cleared_by_zone_id"):
            label += f" -> {barrier['cleared_by_zone_id']}"
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label, fill="#23311f")

    def _draw_point_marker(self, world_x: float, world_y: float, fill: str, label: str) -> None:
        x, y = self._world_to_screen(world_x, world_y)
        radius = 8
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="#203040", width=2)
        self.canvas.create_text(x, y - 16, text=label, fill="#203040")

    def _draw_decoration_marker(self, index: int, decoration: dict) -> None:
        x, y = self._world_to_screen(decoration["x"], decoration["y"])
        size = max(12, int(14 * float(decoration.get("scale", 1.0))))
        fill = "#d89b5f" if not decoration.get("draw_above_entities", False) else "#d58965"
        outline = "#6d4320" if not decoration.get("draw_above_entities", False) else "#84422a"
        label = "D" if not decoration.get("draw_above_entities", False) else "FG"
        self.canvas.create_rectangle(x - size, y - size, x + size, y + size, fill=fill, outline=outline, width=2)
        self.canvas.create_text(x, y - size - 10, text=label, fill="#203040")
        self.canvas.create_text(x, y + size + 10, text=decoration.get("asset_id", ""), fill="#6d4320")

    def _draw_radius_marker(self, obj: dict, fill: str, label: str) -> None:
        x, y = self._world_to_screen(obj["x"], obj["y"])
        radius = max(8, int(float(obj.get("radius", 12)) * self.preview_scale))
        interact_radius = float(obj.get("interact_radius", obj.get("revive_radius", 0))) * self.preview_scale
        if interact_radius > 0:
            self.canvas.create_oval(x - interact_radius, y - interact_radius, x + interact_radius, y + interact_radius, outline=fill, dash=(4, 4))
        leash_radius = float(obj.get("leash_radius", 260.0 if label == "B" else 0)) * self.preview_scale
        if leash_radius > 0:
            self.canvas.create_oval(
                x - leash_radius,
                y - leash_radius,
                x + leash_radius,
                y + leash_radius,
                outline="#8f5f2d",
                dash=(2, 6),
            )
        aggro_radius = float(obj.get("aggro_radius", 0)) * self.preview_scale
        if aggro_radius > 0:
            self.canvas.create_oval(
                x - aggro_radius,
                y - aggro_radius,
                x + aggro_radius,
                y + aggro_radius,
                outline="#d28f44",
                dash=(4, 2),
            )
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="#203040", width=2)
        self.canvas.create_text(x, y - radius - 10, text=label, fill="#203040")

    def _draw_selection_overlay(self, ref: tuple[str, int | None]) -> None:
        target = self._selected_object()
        if target is None:
            return
        section, _, obj = target
        if not self._layer_visible(section):
            return

        if section in {"collision_rects", "traversal_barriers"}:
            bbox = self._collision_bbox(obj)
            self.canvas.create_rectangle(*bbox, outline="#246bff", width=2, dash=(6, 4))
            for handle_name, hx, hy in self._rect_handles(obj):
                self._draw_handle(handle_name, hx, hy)
            return

        bbox = self._point_bbox(obj["x"], obj["y"], max(float(obj.get("radius", 10)), 12))
        self.canvas.create_rectangle(*bbox, outline="#246bff", width=2, dash=(6, 4))
        if section in {"shrine", "enemy_spawns", "final_bloom", "egg_spawns", "spirit_pickups", "restoration_zones", "hazard_zones"}:
            for handle_name, hx, hy in self._radius_handles(obj):
                self._draw_handle(handle_name, hx, hy)

    def _draw_handle(self, _name: str, screen_x: float, screen_y: float) -> None:
        self.canvas.create_rectangle(screen_x - 5, screen_y - 5, screen_x + 5, screen_y + 5, fill="#ffffff", outline="#246bff", width=2)

    def _object_at_world_point(self, world_x: float, world_y: float) -> tuple[str, int | None] | None:
        objects = self._iter_hit_test_objects()
        for ref, obj in reversed(objects):
            section, _ = ref
            if section in {"collision_rects", "traversal_barriers"}:
                if obj["x"] <= world_x <= obj["x"] + obj["width"] and obj["y"] <= world_y <= obj["y"] + obj["height"]:
                    return ref
            else:
                radius = max(float(obj.get("radius", 12)), 12.0)
                delta_x = world_x - obj["x"]
                delta_y = world_y - obj["y"]
                if (delta_x * delta_x) + (delta_y * delta_y) <= radius * radius:
                    return ref
        return None

    def _iter_hit_test_objects(self) -> list[tuple[tuple[str, int | None], dict]]:
        objects: list[tuple[tuple[str, int | None], dict]] = []
        if self._layer_visible("collision_rects"):
            objects.extend((("collision_rects", index), rect) for index, rect in enumerate(self.map_data["collision_rects"]))
        if self._layer_visible("traversal_barriers"):
            objects.extend((("traversal_barriers", index), barrier) for index, barrier in enumerate(self.map_data["traversal_barriers"]))
        if self._layer_visible("decorations"):
            objects.extend((("decorations", index), decoration) for index, decoration in enumerate(self.map_data["decorations"]))
        if self._layer_visible("hazard_zones"):
            objects.extend((("hazard_zones", index), zone) for index, zone in enumerate(self.map_data["hazard_zones"]))
        if self._layer_visible("restoration_zones"):
            objects.extend((("restoration_zones", index), zone) for index, zone in enumerate(self.map_data["restoration_zones"]))
        if self._layer_visible("player_spawns"):
            objects.extend((("player_spawns", index), spawn) for index, spawn in enumerate(self.map_data["player_spawns"]))
        if self._layer_visible("patrol_points"):
            objects.extend((("patrol_points", index), point) for index, point in enumerate(self.map_data["patrol_points"]))
        if self._layer_visible("egg_spawns"):
            objects.extend((("egg_spawns", index), spawn) for index, spawn in enumerate(self.map_data["egg_spawns"]))
        if self._layer_visible("spirit_pickups"):
            objects.extend((("spirit_pickups", index), pickup) for index, pickup in enumerate(self.map_data["spirit_pickups"]))
        if self._layer_visible("shrine"):
            objects.append((("shrine", None), self.map_data["shrine"]))
        if self._layer_visible("enemy_spawns"):
            objects.extend((("enemy_spawns", index), enemy) for index, enemy in enumerate(self.map_data["enemy_spawns"]))
        if self._layer_visible("final_bloom"):
            objects.append((("final_bloom", None), self.map_data["final_bloom"]))
        return objects

    def _handle_at_screen_point(self, ref: tuple[str, int | None], screen_x: float, screen_y: float) -> str | None:
        target = self._selected_object()
        if target is None:
            return None
        section, _, obj = target
        if section in {"collision_rects", "traversal_barriers"}:
            handles = self._rect_handles(obj)
        elif section in {"shrine", "enemy_spawns", "final_bloom", "egg_spawns", "spirit_pickups", "restoration_zones", "hazard_zones"}:
            handles = self._radius_handles(obj)
        else:
            return None
        for name, hx, hy in handles:
            if abs(screen_x - hx) <= 8 and abs(screen_y - hy) <= 8:
                return name
        return None

    def _rect_handles(self, rect: dict) -> list[tuple[str, float, float]]:
        x1, y1 = self._world_to_screen(rect["x"], rect["y"])
        x2, y2 = self._world_to_screen(rect["x"] + rect["width"], rect["y"] + rect["height"])
        return [("nw", x1, y1), ("ne", x2, y1), ("sw", x1, y2), ("se", x2, y2)]

    def _radius_handles(self, obj: dict) -> list[tuple[str, float, float]]:
        radius = float(obj.get("radius", obj.get("interact_radius", 12)))
        screen_center = self._world_to_screen(obj["x"], obj["y"])
        screen_radius = radius * self.preview_scale
        return [
            ("n", screen_center[0], screen_center[1] - screen_radius),
            ("e", screen_center[0] + screen_radius, screen_center[1]),
            ("s", screen_center[0], screen_center[1] + screen_radius),
            ("w", screen_center[0] - screen_radius, screen_center[1]),
        ]

    def _resize_object(self, section: str, obj: dict, start_obj: dict, handle_name: str | None, world_x: float, world_y: float) -> None:
        if handle_name is None:
            return

        if section in {"collision_rects", "traversal_barriers"}:
            left = float(start_obj["x"])
            top = float(start_obj["y"])
            right = left + float(start_obj["width"])
            bottom = top + float(start_obj["height"])
            min_size = GRID_SIZE / 2
            if "w" in handle_name:
                left = min(world_x, right - min_size)
            if "e" in handle_name:
                right = max(world_x, left + min_size)
            if "n" in handle_name:
                top = min(world_y, bottom - min_size)
            if "s" in handle_name:
                bottom = max(world_y, top + min_size)
            obj["x"] = round(left, 2)
            obj["y"] = round(top, 2)
            obj["width"] = round(right - left, 2)
            obj["height"] = round(bottom - top, 2)
            return

        radius = ((world_x - float(start_obj["x"])) ** 2 + (world_y - float(start_obj["y"])) ** 2) ** 0.5
        if section == "egg_spawns":
            obj["radius"] = round(max(4.0, radius), 2)
        elif section == "spirit_pickups":
            obj["radius"] = round(max(4.0, radius), 2)
        elif section == "enemy_spawns":
            obj["radius"] = round(max(4.0, radius), 2)
        elif section == "hazard_zones":
            obj["radius"] = round(max(8.0, radius), 2)
        elif section == "restoration_zones":
            obj["radius"] = round(max(8.0, radius), 2)
            obj["interact_radius"] = round(max(radius + 10.0, float(start_obj.get("interact_radius", radius))), 2)
        elif section == "final_bloom":
            obj["radius"] = round(max(4.0, radius), 2)
            obj["interact_radius"] = round(max(radius + 12.0, float(start_obj.get("interact_radius", radius))), 2)
        elif section == "shrine":
            obj["interact_radius"] = round(max(8.0, radius), 2)

    def _constrain_object_to_world(self, section: str, obj: dict) -> None:
        world_w = float(self.map_data["world"]["width"])
        world_h = float(self.map_data["world"]["height"])
        obj["x"] = round(max(0.0, min(world_w, float(obj["x"]))), 2)
        obj["y"] = round(max(0.0, min(world_h, float(obj["y"]))), 2)
        if section in {"collision_rects", "traversal_barriers"}:
            obj["width"] = round(max(1.0, min(float(obj["width"]), world_w - float(obj["x"]))), 2)
            obj["height"] = round(max(1.0, min(float(obj["height"]), world_h - float(obj["y"]))), 2)

    def _create_object_with_tool(self, tool: str, world_x: float, world_y: float) -> None:
        if tool == "collision":
            self._ensure_layer_visible("collision_rects")
            new_obj = {
                "rect_id": self._next_id("collision_rects", "rect_id", "rect"),
                "x": world_x,
                "y": world_y,
                "width": GRID_SIZE * 6,
                "height": GRID_SIZE * 2,
                "restored_by_zone_id": "",
            }
            self.map_data["collision_rects"].append(new_obj)
            self._select_object_ref(("collision_rects", len(self.map_data["collision_rects"]) - 1))
            return
        if tool == "traversal_barrier":
            self._ensure_layer_visible("traversal_barriers")
            cleared_by_zone_id = self.map_data["restoration_zones"][0]["zone_id"] if self.map_data["restoration_zones"] else ""
            self.map_data["traversal_barriers"].append(
                {
                    "barrier_id": self._next_id("traversal_barriers", "barrier_id", "barrier"),
                    "x": world_x,
                    "y": world_y,
                    "width": GRID_SIZE * 5,
                    "height": GRID_SIZE * 2,
                    "cleared_by_zone_id": cleared_by_zone_id,
                    "spirit_passable": False,
                }
            )
            self._select_object_ref(("traversal_barriers", len(self.map_data["traversal_barriers"]) - 1))
            return
        if tool == "decoration":
            self._ensure_layer_visible("decorations")
            self.map_data["decorations"].append(
                {
                    "decoration_id": self._next_id("decorations", "decoration_id", "decoration"),
                    "asset_id": self._default_asset_id(),
                    "restored_by_zone_id": "",
                    "draw_above_entities": False,
                    "x": world_x,
                    "y": world_y,
                    "scale": 1.0,
                }
            )
            self._select_object_ref(("decorations", len(self.map_data["decorations"]) - 1))
            return
        if tool == "patrol_point":
            self._ensure_layer_visible("patrol_points")
            enemy_id = self.map_data["enemy_spawns"][0]["enemy_id"] if self.map_data["enemy_spawns"] else "enemy_1"
            self.map_data["patrol_points"].append(
                {
                    "point_id": self._next_id("patrol_points", "point_id", "patrol"),
                    "enemy_id": enemy_id,
                    "x": world_x,
                    "y": world_y,
                }
            )
            self._select_object_ref(("patrol_points", len(self.map_data["patrol_points"]) - 1))
            return
        if tool == "player_spawn":
            self._ensure_layer_visible("player_spawns")
            self.map_data["player_spawns"].append({"x": world_x, "y": world_y})
            self._select_object_ref(("player_spawns", len(self.map_data["player_spawns"]) - 1))
            return
        if tool == "egg_spawn":
            self._ensure_layer_visible("egg_spawns")
            self.map_data["egg_spawns"].append(
                {
                    "spawn_id": self._next_id("egg_spawns", "spawn_id", "egg"),
                    "x": world_x,
                    "y": world_y,
                    "egg_type": "revival",
                    "radius": 12,
                }
            )
            self._select_object_ref(("egg_spawns", len(self.map_data["egg_spawns"]) - 1))
            return
        if tool == "spirit_pickup":
            self._ensure_layer_visible("spirit_pickups")
            self.map_data["spirit_pickups"].append(
                {
                    "pickup_id": self._next_id("spirit_pickups", "pickup_id", "spirit_pickup"),
                    "x": world_x,
                    "y": world_y,
                    "radius": 12,
                }
            )
            self._select_object_ref(("spirit_pickups", len(self.map_data["spirit_pickups"]) - 1))
            return
        if tool == "restoration_zone":
            self._ensure_layer_visible("restoration_zones")
            self.map_data["restoration_zones"].append(
                {
                    "zone_id": self._next_id("restoration_zones", "zone_id", "restore"),
                    "x": world_x,
                    "y": world_y,
                    "radius": 72.0,
                    "interact_radius": 84.0,
                    "required_egg_type": "restoration",
                    "restore_cost": 1,
                }
            )
            self._select_object_ref(("restoration_zones", len(self.map_data["restoration_zones"]) - 1))
            return
        if tool == "hazard_zone":
            self._ensure_layer_visible("hazard_zones")
            cleared_by_zone_id = self.map_data["restoration_zones"][0]["zone_id"] if self.map_data["restoration_zones"] else ""
            self.map_data["hazard_zones"].append(
                {
                    "zone_id": self._next_id("hazard_zones", "zone_id", "hazard"),
                    "x": world_x,
                    "y": world_y,
                    "radius": 84.0,
                    "damage_per_second": 18.0,
                    "slow_multiplier": 0.72,
                    "cleared_by_zone_id": cleared_by_zone_id,
                }
            )
            self._select_object_ref(("hazard_zones", len(self.map_data["hazard_zones"]) - 1))
            return
        if tool == "enemy_spawn":
            self._ensure_layer_visible("enemy_spawns")
            self.map_data["enemy_spawns"].append(
                {
                    "enemy_id": self._next_id("enemy_spawns", "enemy_id", "enemy"),
                    "x": world_x,
                    "y": world_y,
                    "radius": 18,
                    "speed": 150.0,
                    "damage_per_second": 40.0,
                    "leash_radius": 260.0,
                    "aggro_radius": 220.0,
                    "alert_duration_ticks": 80,
                }
            )
            self._select_object_ref(("enemy_spawns", len(self.map_data["enemy_spawns"]) - 1))
            return
        if tool == "shrine":
            self._ensure_layer_visible("shrine")
            self.map_data["shrine"]["x"] = world_x
            self.map_data["shrine"]["y"] = world_y
            self._select_object_ref(("shrine", None))
            return
        if tool == "final_bloom":
            self._ensure_layer_visible("final_bloom")
            self.map_data["final_bloom"]["x"] = world_x
            self.map_data["final_bloom"]["y"] = world_y
            self._select_object_ref(("final_bloom", None))

    def _next_id(self, section: str, key: str, prefix: str) -> str:
        existing = {entry.get(key) for entry in self.map_data[section]}
        index = 1
        while f"{prefix}_{index}" in existing:
            index += 1
        return f"{prefix}_{index}"

    def _default_asset_id(self) -> str:
        selected_asset = self.decoration_asset_var.get().strip()
        if selected_asset:
            return selected_asset
        visual_paths = sorted(VISUALS_DIR.glob("*.json"))
        if not visual_paths:
            return "decoration_asset"
        return visual_paths[0].stem

    def _sync_selected_decoration_asset(self) -> None:
        target = self._selected_object()
        if target is None:
            return
        section, _, obj = target
        if section != "decorations":
            return
        selected_asset = self.property_vars["asset_id"].get().strip()
        if not selected_asset:
            return
        obj["asset_id"] = selected_asset
        self.decoration_asset_var.set(selected_asset)
        self._refresh_object_list()
        self._draw_canvas()

    def _world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
        return ((world_x - self.camera_x) * self.preview_scale, (world_y - self.camera_y) * self.preview_scale)

    def _screen_to_world(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        return (screen_x / self.preview_scale + self.camera_x, screen_y / self.preview_scale + self.camera_y)

    def _snap(self, world_x: float, world_y: float) -> tuple[float, float]:
        if not self.snap_to_grid_var.get():
            return world_x, world_y
        return (
            round(round(world_x / GRID_SIZE) * GRID_SIZE, 2),
            round(round(world_y / GRID_SIZE) * GRID_SIZE, 2),
        )

    def _clamp_camera(self) -> None:
        canvas_w = max(1.0, float(self.canvas.winfo_width() or 980))
        canvas_h = max(1.0, float(self.canvas.winfo_height() or 760))
        visible_w = canvas_w / self.preview_scale
        visible_h = canvas_h / self.preview_scale
        world_w = float(self.map_data["world"]["width"])
        world_h = float(self.map_data["world"]["height"])
        max_x = max(0.0, world_w - visible_w)
        max_y = max(0.0, world_h - visible_h)
        self.camera_x = max(0.0, min(max_x, self.camera_x))
        self.camera_y = max(0.0, min(max_y, self.camera_y))

    def _collision_bbox(self, rect: dict) -> tuple[float, float, float, float]:
        x1, y1 = self._world_to_screen(rect["x"], rect["y"])
        x2, y2 = self._world_to_screen(rect["x"] + rect["width"], rect["y"] + rect["height"])
        return (x1, y1, x2, y2)

    def _point_bbox(self, x: float, y: float, radius: float) -> tuple[float, float, float, float]:
        screen_x, screen_y = self._world_to_screen(x, y)
        screen_radius = max(10.0, radius * self.preview_scale)
        return (
            screen_x - screen_radius,
            screen_y - screen_radius,
            screen_x + screen_radius,
            screen_y + screen_radius,
        )

    def _load_map_path(self, path: Path) -> None:
        self.map_path = path
        self.map_data = json.loads(path.read_text(encoding="utf-8"))
        self.map_data.setdefault("traversal_barriers", [])
        self.map_data.setdefault("decorations", [])
        self.map_data.setdefault("patrol_points", [])
        self.map_data.setdefault("spirit_pickups", [])
        self.map_data.setdefault("restoration_zones", [])
        self.map_data.setdefault("hazard_zones", [])
        self.selected_ref = None
        self.drag_mode = None
        self.drag_handle = None
        self.drag_start_world = None
        self.drag_start_object = None
        self._refresh_all()


def main() -> None:
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.geometry("1500x900")
    MapEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
