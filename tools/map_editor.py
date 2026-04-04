from __future__ import annotations

import json
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


REPO_ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = REPO_ROOT / "gameplay" / "maps"
VISUALS_DIR = REPO_ROOT / "assets" / "visuals"

DEFAULT_MAP = {
    "map_id": "new_map",
    "name": "New Map",
    "world": {"width": 1600, "height": 960},
    "player_spawns": [],
    "collision_rects": [],
    "decorations": [],
    "egg_spawns": [],
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
            "asset_id": tk.StringVar(value=""),
            "egg_type": tk.StringVar(value=""),
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

        sidebar = ttk.Frame(self.root, padding=10)
        sidebar.grid(row=0, column=0, sticky="ns")

        canvas_wrap = ttk.Frame(self.root, padding=10)
        canvas_wrap.grid(row=0, column=1, sticky="nsew")
        canvas_wrap.columnconfigure(0, weight=1)
        canvas_wrap.rowconfigure(1, weight=1)

        inspector = ttk.Frame(self.root, padding=10)
        inspector.grid(row=0, column=2, sticky="ns")

        self._build_sidebar(sidebar)
        self._build_canvas(canvas_wrap)
        self._build_inspector(inspector)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        file_row = ttk.Frame(parent)
        file_row.grid(row=0, column=0, sticky="ew")
        ttk.Button(file_row, text="New", command=self.new_map).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(file_row, text="Open", command=self.open_map_dialog).grid(row=0, column=1, padx=4)
        ttk.Button(file_row, text="Save", command=self.save_map).grid(row=0, column=2, padx=4)
        ttk.Button(file_row, text="Save As", command=self.save_map_as).grid(row=0, column=3, padx=(4, 0))

        maps_header = ttk.Frame(parent)
        maps_header.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(maps_header, text="Maps In Folder").grid(row=0, column=0, sticky="w")
        ttk.Button(maps_header, text="Refresh", command=self.refresh_map_files).grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.map_files_listbox = tk.Listbox(parent, height=8, exportselection=False)
        self.map_files_listbox.grid(row=2, column=0, sticky="ew", pady=(4, 10))
        self.map_files_listbox.bind("<Double-Button-1>", lambda _event: self.open_selected_map_file())

        ttk.Button(parent, text="Open Selected", command=self.open_selected_map_file).grid(row=3, column=0, sticky="ew")

        ttk.Label(parent, text="Tools").grid(row=4, column=0, sticky="w", pady=(12, 4))
        tools_frame = ttk.Frame(parent)
        tools_frame.grid(row=5, column=0, sticky="ew")

        tool_specs = [
            ("select", "Select"),
            ("collision", "Add Collision"),
            ("decoration", "Add Decoration"),
            ("player_spawn", "Add Player Spawn"),
            ("egg_spawn", "Add Egg Spawn"),
            ("enemy_spawn", "Add Enemy Spawn"),
            ("shrine", "Set Shrine"),
            ("final_bloom", "Set Final Bloom"),
        ]
        for index, (value, label) in enumerate(tool_specs):
            ttk.Radiobutton(tools_frame, text=label, variable=self.tool_var, value=value).grid(row=index, column=0, sticky="w", pady=2)

        ttk.Checkbutton(parent, text="Snap To Grid", variable=self.snap_to_grid_var).grid(row=6, column=0, sticky="w", pady=(10, 4))

        ttk.Label(parent, text="Objects").grid(row=7, column=0, sticky="w", pady=(12, 4))
        self.object_listbox = tk.Listbox(parent, height=20, exportselection=False)
        self.object_listbox.grid(row=8, column=0, sticky="nsew")
        self.object_listbox.bind("<<ListboxSelect>>", lambda _event: self._load_selected_object_from_list())
        parent.rowconfigure(8, weight=1)

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
            ("scale", "Scale"),
            ("interact_radius", "Interact Radius"),
            ("revive_radius", "Revive Radius"),
            ("speed", "Speed"),
            ("damage_per_second", "Damage / Sec"),
            ("leash_radius", "Leash Radius"),
            ("asset_id", "Asset ID"),
            ("egg_type", "Egg Type"),
        ]
        base_row = 8
        for index, (field_key, label) in enumerate(field_specs):
            row_index = base_row + index * 2
            ttk.Label(parent, text=label).grid(row=row_index, column=0, sticky="w", pady=(3, 0))
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
            elif section == "decorations":
                obj["decoration_id"] = self.property_vars["id"].get().strip() or obj["decoration_id"]
                obj["asset_id"] = self.property_vars["asset_id"].get().strip() or obj["asset_id"]
                obj["scale"] = max(0.1, self._parse_float_var("scale"))
            elif section == "egg_spawns":
                obj["spawn_id"] = self.property_vars["id"].get().strip() or obj["spawn_id"]
                obj["egg_type"] = self.property_vars["egg_type"].get().strip() or obj.get("egg_type", "revival")
                obj["radius"] = max(1.0, self._parse_float_var("radius"))
            elif section == "enemy_spawns":
                obj["enemy_id"] = self.property_vars["id"].get().strip() or obj["enemy_id"]
                obj["radius"] = max(1.0, self._parse_float_var("radius"))
                obj["speed"] = max(1.0, self._parse_float_var("speed"))
                obj["damage_per_second"] = max(0.0, self._parse_float_var("damage_per_second"))
                obj["leash_radius"] = max(8.0, self._parse_float_var("leash_radius"))
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
        for index, decoration in enumerate(self.map_data["decorations"]):
            labels.append((("decorations", index), f"Decoration: {decoration['decoration_id']} ({decoration['asset_id']})"))
        for index, _spawn in enumerate(self.map_data["player_spawns"]):
            labels.append((("player_spawns", index), f"Player Spawn {index + 1}"))
        for index, spawn in enumerate(self.map_data["egg_spawns"]):
            labels.append((("egg_spawns", index), f"Egg: {spawn['spawn_id']}"))
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
        self._set_property("scale", obj.get("scale", ""))
        self._set_property("interact_radius", obj.get("interact_radius", ""))
        self._set_property("revive_radius", obj.get("revive_radius", ""))
        self._set_property("speed", obj.get("speed", ""))
        self._set_property("damage_per_second", obj.get("damage_per_second", ""))
        self._set_property("leash_radius", obj.get("leash_radius", 260.0 if section == "enemy_spawns" else ""))
        self._set_property("asset_id", obj.get("asset_id", ""))
        self._set_property("egg_type", obj.get("egg_type", ""))

        if section == "collision_rects":
            self._set_property("id", obj.get("rect_id", ""))
        elif section == "decorations":
            self._set_property("id", obj.get("decoration_id", ""))
        elif section == "egg_spawns":
            self._set_property("id", obj.get("spawn_id", ""))
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

    def _parse_float_var(self, key: str) -> float:
        value = self.property_vars[key].get().strip()
        if value == "":
            raise ValueError(f"{key} is required.")
        return float(value)

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

        for index, rect in enumerate(self.map_data["collision_rects"]):
            self._draw_collision_rect(index, rect)
        for index, decoration in enumerate(self.map_data["decorations"]):
            self._draw_decoration_marker(index, decoration)
        for index, spawn in enumerate(self.map_data["player_spawns"]):
            self._draw_point_marker(spawn["x"], spawn["y"], "#4f89ff", "P")
        for index, spawn in enumerate(self.map_data["egg_spawns"]):
            self._draw_point_marker(spawn["x"], spawn["y"], "#f28bb1", "E")
        self._draw_radius_marker(self.map_data["shrine"], "#ffd56c", "S")
        for index, enemy in enumerate(self.map_data["enemy_spawns"]):
            self._draw_radius_marker(enemy, "#6b8a63", "B")
        self._draw_radius_marker(self.map_data["final_bloom"], "#ffb6c7", "H")

        if self.selected_ref is not None:
            self._draw_selection_overlay(self.selected_ref)

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

    def _draw_point_marker(self, world_x: float, world_y: float, fill: str, label: str) -> None:
        x, y = self._world_to_screen(world_x, world_y)
        radius = 8
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="#203040", width=2)
        self.canvas.create_text(x, y - 16, text=label, fill="#203040")

    def _draw_decoration_marker(self, index: int, decoration: dict) -> None:
        x, y = self._world_to_screen(decoration["x"], decoration["y"])
        size = max(12, int(14 * float(decoration.get("scale", 1.0))))
        self.canvas.create_rectangle(x - size, y - size, x + size, y + size, fill="#d89b5f", outline="#6d4320", width=2)
        self.canvas.create_text(x, y - size - 10, text="D", fill="#203040")
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
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="#203040", width=2)
        self.canvas.create_text(x, y - radius - 10, text=label, fill="#203040")

    def _draw_selection_overlay(self, ref: tuple[str, int | None]) -> None:
        target = self._selected_object()
        if target is None:
            return
        section, _, obj = target

        if section == "collision_rects":
            bbox = self._collision_bbox(obj)
            self.canvas.create_rectangle(*bbox, outline="#246bff", width=2, dash=(6, 4))
            for handle_name, hx, hy in self._rect_handles(obj):
                self._draw_handle(handle_name, hx, hy)
            return

        bbox = self._point_bbox(obj["x"], obj["y"], max(float(obj.get("radius", 10)), 12))
        self.canvas.create_rectangle(*bbox, outline="#246bff", width=2, dash=(6, 4))
        if section in {"shrine", "enemy_spawns", "final_bloom", "egg_spawns"}:
            for handle_name, hx, hy in self._radius_handles(obj):
                self._draw_handle(handle_name, hx, hy)

    def _draw_handle(self, _name: str, screen_x: float, screen_y: float) -> None:
        self.canvas.create_rectangle(screen_x - 5, screen_y - 5, screen_x + 5, screen_y + 5, fill="#ffffff", outline="#246bff", width=2)

    def _object_at_world_point(self, world_x: float, world_y: float) -> tuple[str, int | None] | None:
        objects = self._iter_hit_test_objects()
        for ref, obj in reversed(objects):
            section, _ = ref
            if section == "collision_rects":
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
        objects.extend((("collision_rects", index), rect) for index, rect in enumerate(self.map_data["collision_rects"]))
        objects.extend((("decorations", index), decoration) for index, decoration in enumerate(self.map_data["decorations"]))
        objects.extend((("player_spawns", index), spawn) for index, spawn in enumerate(self.map_data["player_spawns"]))
        objects.extend((("egg_spawns", index), spawn) for index, spawn in enumerate(self.map_data["egg_spawns"]))
        objects.append((("shrine", None), self.map_data["shrine"]))
        objects.extend((("enemy_spawns", index), enemy) for index, enemy in enumerate(self.map_data["enemy_spawns"]))
        objects.append((("final_bloom", None), self.map_data["final_bloom"]))
        return objects

    def _handle_at_screen_point(self, ref: tuple[str, int | None], screen_x: float, screen_y: float) -> str | None:
        target = self._selected_object()
        if target is None:
            return None
        section, _, obj = target
        handles = self._rect_handles(obj) if section == "collision_rects" else self._radius_handles(obj)
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

        if section == "collision_rects":
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
        elif section == "enemy_spawns":
            obj["radius"] = round(max(4.0, radius), 2)
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
        if section == "collision_rects":
            obj["width"] = round(max(1.0, min(float(obj["width"]), world_w - float(obj["x"]))), 2)
            obj["height"] = round(max(1.0, min(float(obj["height"]), world_h - float(obj["y"]))), 2)

    def _create_object_with_tool(self, tool: str, world_x: float, world_y: float) -> None:
        if tool == "collision":
            new_obj = {
                "rect_id": self._next_id("collision_rects", "rect_id", "rect"),
                "x": world_x,
                "y": world_y,
                "width": GRID_SIZE * 6,
                "height": GRID_SIZE * 2,
            }
            self.map_data["collision_rects"].append(new_obj)
            self._select_object_ref(("collision_rects", len(self.map_data["collision_rects"]) - 1))
            return
        if tool == "decoration":
            self.map_data["decorations"].append(
                {
                    "decoration_id": self._next_id("decorations", "decoration_id", "decoration"),
                    "asset_id": self._default_asset_id(),
                    "x": world_x,
                    "y": world_y,
                    "scale": 1.0,
                }
            )
            self._select_object_ref(("decorations", len(self.map_data["decorations"]) - 1))
            return
        if tool == "player_spawn":
            self.map_data["player_spawns"].append({"x": world_x, "y": world_y})
            self._select_object_ref(("player_spawns", len(self.map_data["player_spawns"]) - 1))
            return
        if tool == "egg_spawn":
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
        if tool == "enemy_spawn":
            self.map_data["enemy_spawns"].append(
                {
                    "enemy_id": self._next_id("enemy_spawns", "enemy_id", "enemy"),
                    "x": world_x,
                    "y": world_y,
                    "radius": 18,
                    "speed": 150.0,
                    "damage_per_second": 40.0,
                    "leash_radius": 260.0,
                }
            )
            self._select_object_ref(("enemy_spawns", len(self.map_data["enemy_spawns"]) - 1))
            return
        if tool == "shrine":
            self.map_data["shrine"]["x"] = world_x
            self.map_data["shrine"]["y"] = world_y
            self._select_object_ref(("shrine", None))
            return
        if tool == "final_bloom":
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
        visual_paths = sorted(VISUALS_DIR.glob("*.json"))
        if not visual_paths:
            return "decoration_asset"
        return visual_paths[0].stem

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
        self.map_data.setdefault("decorations", [])
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
