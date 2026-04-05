from __future__ import annotations

import queue
import socket
import threading
import time
from copy import deepcopy
from dataclasses import dataclass

import pygame as pg

from gameplay.collision import move_circle
from gameplay.map_loader import load_map
from gameplay.map_types import CollisionRect, DecorationDef, MapDefinition, TraversalBarrierDef
from gameplay.state import ALIVE_SPEED, PLAYER_COLORS, SPIRIT_SPEED
from gameplay.visual_assets import load_visual_asset, render_visual_asset
from network.diagnostics import ClientDiagnostics
from network.shared import decode_message, encode_message, read_messages_forever, safe_close, send_message


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 640
CAMERA_ZOOM = 1.0
BACKGROUND_COLOR = (232, 228, 214)
PLAYFIELD_COLOR = (205, 214, 188)
HUD_PANEL_COLOR = (243, 238, 226)
HUD_PANEL_ACCENT = (224, 216, 201)
SHRINE_COLOR = (255, 216, 138)
TEXT_COLOR = (48, 58, 64)
SPIRIT_COLOR = (188, 234, 255)
SELF_RING_COLOR = (40, 40, 40)
HEALTH_BG_COLOR = (233, 222, 212)
HEALTH_FILL_COLOR = (120, 191, 104)
LOSS_COLOR = (125, 76, 76)
WIN_COLOR = (89, 143, 84)
DEAD_HEDGE_COLOR = (122, 106, 86)
DEAD_HEDGE_ACCENT_COLOR = (150, 131, 108)
RESTORED_HEDGE_COLOR = (111, 139, 96)
RESTORED_HEDGE_ACCENT_COLOR = (140, 171, 122)
REVIVAL_EGG_COLOR = (244, 173, 208)
RESTORATION_EGG_COLOR = (143, 214, 181)
HAZARD_FILL_COLOR = (164, 88, 88, 40)
HAZARD_OUTLINE_COLOR = (132, 61, 61, 148)
RESTORATION_FILL_COLOR = (122, 174, 122, 28)
RESTORATION_OUTLINE_COLOR = (81, 132, 84, 120)
RESTORATION_RESTORED_FILL = (160, 216, 156, 44)
RESTORATION_RESTORED_OUTLINE = (58, 117, 65, 138)
SPIRIT_PICKUP_FILL = (187, 221, 255)
SPIRIT_PICKUP_OUTLINE = (88, 127, 173)
NEST_CORRUPT_FILL = (118, 72, 72)
NEST_CORRUPT_OUTLINE = (78, 41, 41)
NEST_CLEANSED_FILL = (128, 178, 118)
NEST_CLEANSED_OUTLINE = (69, 115, 64)
ENEMY_PATROL_RING = (86, 118, 78)
ENEMY_ALERT_RING = (224, 162, 81)
ENEMY_CHASE_RING = (198, 83, 83)
ENEMY_RETURN_RING = (120, 105, 84)
REMOTE_POSITION_LERP = 0.28
LOCAL_CORRECTION_LERP = 0.35
LOCAL_SNAP_DISTANCE = 96.0
INPUT_SEND_INTERVAL = 1.0 / 20.0


@dataclass
class ClientSnapshot:
    tick: int = 0
    world_width: int = 1200
    world_height: int = 720
    match_phase: str = "lobby"
    players: list[dict] | None = None
    eggs: list[dict] | None = None
    spirit_pickups: list[dict] | None = None
    restoration_zones: list[dict] | None = None
    hazard_zones: list[dict] | None = None
    shrine: dict | None = None
    enemies: list[dict] | None = None
    final_bloom: dict | None = None
    objective_text: str = ""


class NetworkClient:
    def __init__(self, host: str, port: int, name: str) -> None:
        self.host = host
        self.port = port
        self.udp_port = port + 1
        self.name = name
        self.sock: socket.socket | None = None
        self.udp_sock: socket.socket | None = None
        self.send_lock = threading.Lock()
        self.udp_send_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.incoming: queue.Queue[dict] = queue.Queue()

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.connect((self.host, self.port))
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("", 0))
        self.udp_sock.settimeout(0.5)
        threading.Thread(target=self._reader_loop, daemon=True).start()
        threading.Thread(target=self._udp_reader_loop, daemon=True).start()
        self.send({"type": "join", "name": self.name})

    def close(self) -> None:
        self.stop_event.set()
        safe_close(self.sock)
        safe_close(self.udp_sock)

    def send(self, message: dict) -> None:
        if self.sock is None:
            return
        with self.send_lock:
            send_message(self.sock, message)

    def send_udp(self, message: dict) -> bool:
        if self.udp_sock is None:
            return False
        try:
            with self.udp_send_lock:
                self.udp_sock.sendto(encode_message(message), (self.host, self.udp_port))
            return True
        except OSError:
            return False

    def poll_messages(self) -> list[dict]:
        messages = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return messages

    def _reader_loop(self) -> None:
        assert self.sock is not None
        read_messages_forever(
            self.sock,
            should_stop=self.stop_event.is_set,
            on_message=self.incoming.put,
            on_disconnect=lambda: self.incoming.put({"type": "disconnected"}),
        )

    def _udp_reader_loop(self) -> None:
        assert self.udp_sock is not None
        try:
            while not self.stop_event.is_set():
                try:
                    data, _ = self.udp_sock.recvfrom(65536)
                except socket.timeout:
                    continue
                message = decode_message(data)
                if message is None:
                    continue
                self.incoming.put(message)
        except OSError:
            pass


class EasterClientApp:
    def __init__(self, host: str, port: int, name: str, net_debug: bool = False) -> None:
        self.network = NetworkClient(host, port, name)
        self.player_id = ""
        self.name_input = name[:24]
        self.selected_color_index = 0
        self.profile_initialized = False
        self.snapshot = ClientSnapshot(
            players=[],
            eggs=[],
            spirit_pickups=[],
            restoration_zones=[],
            hazard_zones=[],
            shrine=None,
            enemies=[],
        )
        self.connected = False
        self.connection_closed = False
        self.input_seq = 0
        self.lobby_players: list[dict] = []
        self.expected_players = 1
        self.host_id = ""
        self.can_start = False
        self.current_map: MapDefinition | None = None
        self.current_move_x = 0.0
        self.current_move_y = 0.0
        self.render_positions: dict[tuple[str, str], tuple[float, float]] = {}
        self.local_predicted_player: dict | None = None
        self.diagnostics = ClientDiagnostics(enabled=net_debug)
        self.next_ping_at = 0.0
        self.ping_nonce = 0
        self.next_input_send_at = 0.0
        self.last_sent_input_state = (0.0, 0.0, False, False)
        self.udp_ready = False
        self.udp_nonce = 0
        self.next_udp_hello_at = 0.0
        self.show_full_hud = False
        self.fullscreen = False
        self.windowed_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.visual_assets = {
            "shrine": load_visual_asset("shrine"),
            "egg_revival": load_visual_asset("egg_revival"),
            "egg_restoration": load_visual_asset("egg_restoration"),
            "bramble_enemy": load_visual_asset("bramble_enemy"),
            "bramble_nest": load_visual_asset("bramble_nest"),
            "heart_bloom_dormant": load_visual_asset("heart_bloom_dormant"),
            "heart_bloom_restored": load_visual_asset("heart_bloom_restored"),
            "player": load_visual_asset("player"),
            "spirit_seed": load_visual_asset("spirit_seed"),
        }

    def _apply_display_mode(self) -> pg.Surface:
        if self.fullscreen:
            return pg.display.set_mode((0, 0), pg.FULLSCREEN)
        width = max(MIN_WINDOW_WIDTH, int(self.windowed_size[0]))
        height = max(MIN_WINDOW_HEIGHT, int(self.windowed_size[1]))
        self.windowed_size = (width, height)
        return pg.display.set_mode(self.windowed_size, pg.RESIZABLE)

    def _toggle_fullscreen(self) -> pg.Surface:
        if self.fullscreen:
            self.fullscreen = False
        else:
            current_surface = pg.display.get_surface()
            if current_surface is not None:
                current_size = current_surface.get_size()
                self.windowed_size = (
                    max(MIN_WINDOW_WIDTH, current_size[0]),
                    max(MIN_WINDOW_HEIGHT, current_size[1]),
                )
            self.fullscreen = True
        return self._apply_display_mode()

    def run(self) -> None:
        pg.init()
        screen = self._apply_display_mode()
        pg.display.set_caption("Bloombound Prototype Client")
        clock = pg.time.Clock()
        font = pg.font.SysFont(None, 24)
        small_font = pg.font.SysFont(None, 20)

        try:
            self.network.connect()
        except OSError as exc:
            print(f"Could not connect to {self.network.host}:{self.network.port}: {exc}")
            pg.quit()
            return

        running = True
        while running:
            dt = clock.tick(60) / 1000.0
            self.diagnostics.record_frame(dt)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.VIDEORESIZE and not self.fullscreen:
                    resized_width = max(MIN_WINDOW_WIDTH, int(event.w))
                    resized_height = max(MIN_WINDOW_HEIGHT, int(event.h))
                    self.windowed_size = (resized_width, resized_height)
                    screen = self._apply_display_mode()
                elif event.type == pg.KEYDOWN:
                    screen = self._handle_keydown(event, screen)
            self._handle_network_messages()
            if self.snapshot.match_phase == "playing":
                keys = pg.key.get_pressed()
                self._send_input(keys)
                self._advance_local_prediction(dt)
                self._advance_remote_smoothing()
            else:
                self.current_move_x = 0.0
                self.current_move_y = 0.0
            self._maybe_send_udp_hello()
            self._maybe_send_ping()
            self._draw(screen, font, small_font)
            pg.display.flip()
            self.diagnostics.maybe_emit()

            if self.connection_closed:
                running = False

        self.network.close()
        pg.quit()

    def _handle_network_messages(self) -> None:
        for message in self.network.poll_messages():
            message_type = message.get("type")
            self.diagnostics.record_message(str(message_type or "unknown"))
            if message_type == "welcome":
                self.player_id = str(message["player_id"])
                self._load_map(str(message.get("map_id", "new_map")))
                self.snapshot.match_phase = str(message.get("match_phase", "lobby"))
                self.snapshot.world_width = int(message["world"]["width"])
                self.snapshot.world_height = int(message["world"]["height"])
                self.network.udp_port = int(message.get("udp_port", self.network.udp_port))
                self.connected = True
                self.connection_closed = False
                self.udp_ready = False
                self.next_udp_hello_at = 0.0
                self.render_positions.clear()
                self.local_predicted_player = None
                self._send_profile_update()
            elif message_type == "lobby_state":
                self._load_map(str(message.get("map_id", "new_map")))
                self.snapshot.match_phase = str(message.get("match_phase", "lobby"))
                self.expected_players = int(message.get("expected_players", 1))
                self.host_id = str(message.get("host_id", ""))
                self.can_start = bool(message.get("can_start", False))
                self.lobby_players = list(message.get("players", []))
                self.render_positions.clear()
                self.local_predicted_player = None
                self._sync_local_profile_from_lobby()
            elif message_type == "world_snapshot":
                snapshot_tick = int(message.get("tick", 0))
                if snapshot_tick < self.snapshot.tick:
                    continue
                self._load_map(str(message.get("map_id", "new_map")))
                self.snapshot.tick = snapshot_tick
                self.snapshot.match_phase = str(message.get("match_phase", "playing"))
                self.snapshot.players = list(message.get("players", []))
                self.snapshot.eggs = list(message.get("eggs", []))
                self.snapshot.spirit_pickups = list(message.get("spirit_pickups", []))
                self.snapshot.restoration_zones = list(message.get("restoration_zones", []))
                self.snapshot.hazard_zones = list(message.get("hazard_zones", []))
                self.snapshot.shrine = message.get("shrine")
                self.snapshot.enemies = list(message.get("enemies", []))
                self.snapshot.final_bloom = message.get("final_bloom")
                self.snapshot.objective_text = str(message.get("objective_text", ""))
                transport_seconds = None
                if "server_sent_at" in message:
                    try:
                        server_sent_at = float(message["server_sent_at"])
                        transport_seconds = max(0.0, time.time() - server_sent_at)
                    except (TypeError, ValueError):
                        transport_seconds = None
                self.diagnostics.record_world_snapshot(self.snapshot.tick, transport_seconds)
                self._reconcile_render_state()
            elif message_type == "udp_welcome":
                if str(message.get("player_id", "")) == self.player_id:
                    self.udp_ready = True
            elif message_type == "pong":
                self._handle_pong(message)
            elif message_type == "disconnected":
                self.connected = False
                self.connection_closed = True
                self.udp_ready = False

    def _handle_keydown(self, event: pg.event.Event, screen: pg.Surface) -> pg.Surface:
        if not self.connected:
            if event.key == pg.K_F11:
                return self._toggle_fullscreen()
            return screen
        if event.key == pg.K_F11:
            return self._toggle_fullscreen()
        if event.key == pg.K_TAB and self.snapshot.match_phase != "lobby":
            self.show_full_hud = not self.show_full_hud
            return screen
        if self.snapshot.match_phase in {"won", "lost"}:
            if event.key == pg.K_RETURN and self.is_host:
                self.network.send({"type": "start_game"})
            return screen
        if self.snapshot.match_phase != "lobby":
            return screen
        if event.key == pg.K_BACKSPACE:
            self.name_input = self.name_input[:-1]
            self._send_profile_update()
            return screen
        if event.key == pg.K_LEFT:
            self.selected_color_index = (self.selected_color_index - 1) % len(PLAYER_COLORS)
            self._send_profile_update()
            return screen
        if event.key == pg.K_RIGHT:
            self.selected_color_index = (self.selected_color_index + 1) % len(PLAYER_COLORS)
            self._send_profile_update()
            return screen
        if event.key == pg.K_RETURN:
            if self.is_host and self.can_start:
                self.network.send({"type": "start_game"})
            return screen
        if event.unicode and event.unicode.isprintable() and len(self.name_input) < 24:
            self.name_input += event.unicode
            self._send_profile_update()
        return screen

    def _send_input(self, keys: pg.key.ScancodeWrapper) -> None:
        if not self.connected:
            return
        move_x = float(keys[pg.K_d] or keys[pg.K_RIGHT]) - float(keys[pg.K_a] or keys[pg.K_LEFT])
        move_y = float(keys[pg.K_s] or keys[pg.K_DOWN]) - float(keys[pg.K_w] or keys[pg.K_UP])
        self.current_move_x = move_x
        self.current_move_y = move_y
        interact = bool(keys[pg.K_e] or keys[pg.K_SPACE])
        debug_down = bool(keys[pg.K_k])
        current_state = (move_x, move_y, interact, debug_down)
        now = time.perf_counter()
        moving = move_x != 0.0 or move_y != 0.0
        state_changed = current_state != self.last_sent_input_state
        should_send = state_changed or (
            now >= self.next_input_send_at and (moving or interact or debug_down)
        )
        if not should_send:
            return
        self.input_seq += 1
        self.diagnostics.record_input_sent()
        payload = {
            "type": "player_input",
            "seq": self.input_seq,
            "move_x": move_x,
            "move_y": move_y,
            "interact": interact,
            "debug_down": debug_down,
        }
        if self.udp_ready:
            sent = self.network.send_udp(payload)
            if not sent:
                self.network.send(payload)
        else:
            self.network.send(payload)
        self.last_sent_input_state = current_state
        self.next_input_send_at = now + INPUT_SEND_INTERVAL

    def _reconcile_render_state(self) -> None:
        active_keys: set[tuple[str, str]] = set()

        for enemy in self.snapshot.enemies or []:
            key = ("enemy", str(enemy["id"]))
            current_position = self.render_positions.get(key)
            if current_position is not None:
                self.diagnostics.record_enemy_error(
                    ((current_position[0] - float(enemy["x"])) ** 2 + (current_position[1] - float(enemy["y"])) ** 2)
                    ** 0.5
                )
            self.render_positions.setdefault(key, (float(enemy["x"]), float(enemy["y"])))
            active_keys.add(key)

        for player in self.snapshot.players or []:
            player_id = str(player["id"])
            if player_id == self.player_id:
                self._reconcile_local_prediction(player)
                continue
            key = ("player", player_id)
            current_position = self.render_positions.get(key)
            if current_position is not None:
                self.diagnostics.record_remote_player_error(
                    ((current_position[0] - float(player["x"])) ** 2 + (current_position[1] - float(player["y"])) ** 2)
                    ** 0.5
                )
            self.render_positions.setdefault(key, (float(player["x"]), float(player["y"])))
            active_keys.add(key)

        self.render_positions = {
            key: position
            for key, position in self.render_positions.items()
            if key in active_keys
        }

    def _reconcile_local_prediction(self, player: dict) -> None:
        server_x = float(player["x"])
        server_y = float(player["y"])
        if self.local_predicted_player is None:
            self.local_predicted_player = deepcopy(player)
            self.local_predicted_player["x"] = server_x
            self.local_predicted_player["y"] = server_y
            return

        predicted_x = float(self.local_predicted_player.get("x", server_x))
        predicted_y = float(self.local_predicted_player.get("y", server_y))
        self.diagnostics.record_local_error(((predicted_x - server_x) ** 2 + (predicted_y - server_y) ** 2) ** 0.5)
        if ((predicted_x - server_x) ** 2 + (predicted_y - server_y) ** 2) ** 0.5 > LOCAL_SNAP_DISTANCE:
            predicted_x = server_x
            predicted_y = server_y
        else:
            predicted_x += (server_x - predicted_x) * LOCAL_CORRECTION_LERP
            predicted_y += (server_y - predicted_y) * LOCAL_CORRECTION_LERP

        self.local_predicted_player = deepcopy(player)
        self.local_predicted_player["x"] = predicted_x
        self.local_predicted_player["y"] = predicted_y

    def _advance_local_prediction(self, dt: float) -> None:
        if self.local_predicted_player is None or self.current_map is None:
            return

        move_x = max(-1.0, min(1.0, self.current_move_x))
        move_y = max(-1.0, min(1.0, self.current_move_y))
        magnitude = (move_x * move_x + move_y * move_y) ** 0.5
        if magnitude > 1.0:
            move_x /= magnitude
            move_y /= magnitude

        speed = SPIRIT_SPEED if self.local_predicted_player.get("state") == "spirit" else ALIVE_SPEED
        speed *= float(self.local_predicted_player.get("hazard_slow_multiplier", 1.0))
        next_x, next_y = move_circle(
            x=float(self.local_predicted_player["x"]),
            y=float(self.local_predicted_player["y"]),
            radius=float(self.local_predicted_player["radius"]),
            delta_x=move_x * speed * dt,
            delta_y=move_y * speed * dt,
            world_width=self.snapshot.world_width,
            world_height=self.snapshot.world_height,
            collision_rects=self._local_collision_rects(),
        )
        self.local_predicted_player["x"] = next_x
        self.local_predicted_player["y"] = next_y

    def _advance_remote_smoothing(self) -> None:
        for enemy in self.snapshot.enemies or []:
            key = ("enemy", str(enemy["id"]))
            current_x, current_y = self.render_positions.get(key, (float(enemy["x"]), float(enemy["y"])))
            self.render_positions[key] = (
                current_x + (float(enemy["x"]) - current_x) * REMOTE_POSITION_LERP,
                current_y + (float(enemy["y"]) - current_y) * REMOTE_POSITION_LERP,
            )

        for player in self.snapshot.players or []:
            player_id = str(player["id"])
            if player_id == self.player_id:
                continue
            key = ("player", player_id)
            current_x, current_y = self.render_positions.get(key, (float(player["x"]), float(player["y"])))
            self.render_positions[key] = (
                current_x + (float(player["x"]) - current_x) * REMOTE_POSITION_LERP,
                current_y + (float(player["y"]) - current_y) * REMOTE_POSITION_LERP,
            )

    def _display_player(self, player: dict) -> dict:
        if str(player["id"]) == self.player_id and self.local_predicted_player is not None:
            return self.local_predicted_player

        key = ("player", str(player["id"]))
        smoothed_x, smoothed_y = self.render_positions.get(key, (float(player["x"]), float(player["y"])))
        payload = dict(player)
        payload["x"] = smoothed_x
        payload["y"] = smoothed_y
        return payload

    def _display_position(self, kind: str, entity_id: str, x: float, y: float) -> tuple[float, float]:
        return self.render_positions.get((kind, entity_id), (x, y))

    def _draw(self, screen: pg.Surface, font: pg.font.Font, small_font: pg.font.Font) -> None:
        if self.snapshot.match_phase == "lobby":
            self._draw_lobby(screen, font, small_font)
            return

        screen_rect = screen.get_rect()
        screen.fill(BACKGROUND_COLOR)
        playfield_rect = pg.Rect(32, 96, max(320, screen_rect.width - 64), max(220, screen_rect.height - 132))
        pg.draw.rect(screen, PLAYFIELD_COLOR, playfield_rect, border_radius=18)
        camera_rect = self._camera_rect(playfield_rect)
        screen.set_clip(playfield_rect)
        self._draw_hazard_zones(screen, playfield_rect, camera_rect)
        self._draw_restoration_zones(screen, playfield_rect, camera_rect, small_font)
        self._draw_map_geometry(screen, playfield_rect, camera_rect)
        self._draw_map_decorations(screen, playfield_rect, camera_rect)
        self._draw_enemy_spawners(screen, playfield_rect, camera_rect)

        if self.snapshot.shrine:
            shrine_x, shrine_y = self._screen_point(
                self.snapshot.shrine["x"],
                self.snapshot.shrine["y"],
                playfield_rect,
                camera_rect,
            )
            if self._world_point_visible(self.snapshot.shrine["x"], self.snapshot.shrine["y"], playfield_rect, camera_rect, margin=64):
                render_visual_asset(screen, self.visual_assets["shrine"], (shrine_x, shrine_y))

        if self.snapshot.final_bloom:
            bloom_x, bloom_y = self._screen_point(
                self.snapshot.final_bloom["x"],
                self.snapshot.final_bloom["y"],
                playfield_rect,
                camera_rect,
            )
            bloom_asset = "heart_bloom_restored" if self.snapshot.final_bloom.get("restored") else "heart_bloom_dormant"
            if self._world_point_visible(self.snapshot.final_bloom["x"], self.snapshot.final_bloom["y"], playfield_rect, camera_rect, margin=64):
                render_visual_asset(screen, self.visual_assets[bloom_asset], (bloom_x, bloom_y))

        for egg in self.snapshot.eggs or []:
            if egg.get("collected", False):
                continue
            if not self._world_point_visible(egg["x"], egg["y"], playfield_rect, camera_rect, margin=48):
                continue
            egg_x, egg_y = self._screen_point(
                egg["x"],
                egg["y"],
                playfield_rect,
                camera_rect,
            )
            egg_type = str(egg.get("egg_type", "revival"))
            egg_asset = "egg_restoration" if egg_type == "restoration" else "egg_revival"
            render_visual_asset(screen, self.visual_assets[egg_asset], (egg_x, egg_y))

        for pickup in self.snapshot.spirit_pickups or []:
            if pickup.get("collected", False):
                continue
            if not self._world_point_visible(pickup["x"], pickup["y"], playfield_rect, camera_rect, margin=48):
                continue
            pickup_x, pickup_y = self._screen_point(
                pickup["x"],
                pickup["y"],
                playfield_rect,
                camera_rect,
            )
            render_visual_asset(screen, self.visual_assets["spirit_seed"], (pickup_x, pickup_y))

        for enemy in self.snapshot.enemies or []:
            display_x, display_y = self._display_position("enemy", str(enemy["id"]), float(enemy["x"]), float(enemy["y"]))
            if not self._world_point_visible(display_x, display_y, playfield_rect, camera_rect, margin=60):
                continue
            enemy_x, enemy_y = self._screen_point(
                display_x,
                display_y,
                playfield_rect,
                camera_rect,
            )
            ring_color = {
                "patrol": ENEMY_PATROL_RING,
                "alert": ENEMY_ALERT_RING,
                "chase": ENEMY_CHASE_RING,
                "return": ENEMY_RETURN_RING,
            }.get(str(enemy.get("state", "patrol")), ENEMY_PATROL_RING)
            pg.draw.circle(screen, ring_color, (enemy_x, enemy_y), int(enemy["radius"]) + 10, width=3)
            render_visual_asset(screen, self.visual_assets["bramble_enemy"], (enemy_x, enemy_y))

        for player in self.snapshot.players or []:
            display_player = self._display_player(player)
            if not self._world_point_visible(display_player["x"], display_player["y"], playfield_rect, camera_rect, margin=72):
                continue
            px, py = self._screen_point(display_player["x"], display_player["y"], playfield_rect, camera_rect)
            color = tuple(display_player["color"])
            radius = int(display_player["radius"] * CAMERA_ZOOM)
            ring_radius = radius + 5
            if display_player["state"] == "spirit":
                pg.draw.circle(screen, SPIRIT_COLOR, (px, py), radius + 2)
                pg.draw.circle(screen, color, (px, py), radius, width=2)
            else:
                player_scale = max(0.9, (display_player["radius"] * 4.4) / self.visual_assets["player"].width)
                render_visual_asset(
                    screen,
                    self.visual_assets["player"],
                    (px, py),
                    scale=player_scale,
                    color_overrides={"player_head": color},
                )
                ring_radius = max(ring_radius, int((self.visual_assets["player"].width * player_scale) / 2) + 2)
            if display_player["id"] == self.player_id:
                pg.draw.circle(screen, SELF_RING_COLOR, (px, py), ring_radius, width=2)
            name_surf = small_font.render(display_player["name"], True, TEXT_COLOR)
            name_y = py - ring_radius - name_surf.get_height() - 6
            screen.blit(name_surf, (px - name_surf.get_width() // 2, name_y))
            if display_player["state"] == "alive":
                bar_width = 42
                bar_height = 6
                health_ratio = max(0.0, min(1.0, display_player["health"] / max(1, display_player["max_health"])))
                bar_rect = pg.Rect(px - bar_width // 2, py + ring_radius + 8, bar_width, bar_height)
                pg.draw.rect(screen, HEALTH_BG_COLOR, bar_rect, border_radius=4)
                pg.draw.rect(
                    screen,
                    HEALTH_FILL_COLOR,
                    pg.Rect(bar_rect.left, bar_rect.top, int(bar_width * health_ratio), bar_height),
                    border_radius=4,
                )
                if float(display_player.get("hazard_slow_multiplier", 1.0)) < 1.0:
                    pg.draw.circle(screen, HAZARD_OUTLINE_COLOR, (px, py), ring_radius + 6, width=2)
        screen.set_clip(None)

        title = font.render("Bloombound Networking Prototype", True, TEXT_COLOR)
        if self.connected:
            status_text = self.snapshot.objective_text or "Move: WASD | Interact: E at shrine | Debug spirit: K"
        else:
            status_text = f"Connecting to {self.network.host}:{self.network.port}..."
        status = small_font.render(status_text, True, TEXT_COLOR)
        tick_text = small_font.render(f"Tick {self.snapshot.tick}", True, TEXT_COLOR)
        screen.blit(title, (32, 28))
        screen.blit(status, (32, 58))
        screen.blit(tick_text, (screen_rect.right - tick_text.get_width() - 32, 28))
        self._draw_compact_hud(screen, font, small_font)
        if self.show_full_hud:
            self._draw_details_overlay(screen, font, small_font, playfield_rect)
        if self.snapshot.match_phase in {"won", "lost"}:
            self._draw_match_overlay(screen, font, small_font, playfield_rect)

    def _draw_lobby(self, screen: pg.Surface, font: pg.font.Font, small_font: pg.font.Font) -> None:
        screen_rect = screen.get_rect()
        screen.fill(BACKGROUND_COLOR)
        panel = pg.Rect(64, 72, max(420, screen_rect.width - 128), max(360, screen_rect.height - 144))
        pg.draw.rect(screen, PLAYFIELD_COLOR, panel, border_radius=24)

        title = font.render("Bloombound Lobby", True, TEXT_COLOR)
        screen.blit(title, (panel.left + 24, panel.top + 20))

        status_text = f"Players: {len(self.lobby_players)}/{self.expected_players}"
        if self.is_host and self.can_start:
            status_text += "  |  Press Enter to start"
        elif self.is_host:
            status_text += "  |  Waiting for expected players"
        else:
            status_text += "  |  Waiting for host to start"
        status = small_font.render(status_text, True, TEXT_COLOR)
        screen.blit(status, (panel.left + 24, panel.top + 54))

        name_label = small_font.render("Name", True, TEXT_COLOR)
        name_value = small_font.render(self.name_input or "_", True, TEXT_COLOR)
        screen.blit(name_label, (panel.left + 24, panel.top + 108))
        pg.draw.rect(screen, (247, 243, 233), pg.Rect(panel.left + 24, panel.top + 136, 280, 42), border_radius=10)
        screen.blit(name_value, (panel.left + 36, panel.top + 148))

        color_label = small_font.render("Color (Left/Right)", True, TEXT_COLOR)
        screen.blit(color_label, (panel.left + 24, panel.top + 204))
        color_rect = pg.Rect(panel.left + 24, panel.top + 234, 90, 50)
        pg.draw.rect(screen, PLAYER_COLORS[self.selected_color_index], color_rect, border_radius=12)
        pg.draw.rect(screen, SELF_RING_COLOR, color_rect, width=2, border_radius=12)

        help_text = small_font.render("Type to edit name. Backspace deletes.", True, TEXT_COLOR)
        screen.blit(help_text, (panel.left + 24, panel.top + 302))

        roster_title = small_font.render("Joined Players", True, TEXT_COLOR)
        screen.blit(roster_title, (panel.left + 380, panel.top + 108))

        for index, player in enumerate(self.lobby_players):
            row_top = panel.top + 144 + index * 52
            row_rect = pg.Rect(panel.left + 380, row_top, 420, 42)
            pg.draw.rect(screen, (247, 243, 233), row_rect, border_radius=12)
            pg.draw.circle(screen, tuple(player["color"]), (row_rect.left + 26, row_rect.centery), 12)
            label = player["name"]
            if player["is_host"]:
                label += " (Host)"
            name_surf = small_font.render(label, True, TEXT_COLOR)
            screen.blit(name_surf, (row_rect.left + 48, row_rect.top + 11))

    def _send_profile_update(self) -> None:
        if not self.connected:
            return
        self.network.send(
            {
                "type": "set_profile",
                "name": self.name_input or self.network.name,
                "color_index": self.selected_color_index,
            }
        )

    def _sync_local_profile_from_lobby(self) -> None:
        for player in self.lobby_players:
            if player["id"] != self.player_id:
                continue
            if not self.profile_initialized:
                self.selected_color_index = int(player["color_index"])
                self.profile_initialized = True
            if not self.name_input:
                self.name_input = str(player["name"])
            break

    @property
    def is_host(self) -> bool:
        return self.player_id != "" and self.player_id == self.host_id

    @staticmethod
    def _screen_point(
        world_x: float,
        world_y: float,
        playfield_rect: pg.Rect,
        camera_rect: pg.Rect,
    ) -> tuple[int, int]:
        return (
            int(playfield_rect.left + (world_x - camera_rect.left) * CAMERA_ZOOM),
            int(playfield_rect.top + (world_y - camera_rect.top) * CAMERA_ZOOM),
        )

    def _camera_rect(self, playfield_rect: pg.Rect) -> pg.Rect:
        visible_width = playfield_rect.width / CAMERA_ZOOM
        visible_height = playfield_rect.height / CAMERA_ZOOM
        local_player = self._local_player()

        if local_player is None:
            camera_left = max(0.0, (self.snapshot.world_width - visible_width) / 2)
            camera_top = max(0.0, (self.snapshot.world_height - visible_height) / 2)
        else:
            camera_left = local_player["x"] - visible_width / 2
            camera_top = local_player["y"] - visible_height / 2

        max_left = max(0.0, self.snapshot.world_width - visible_width)
        max_top = max(0.0, self.snapshot.world_height - visible_height)
        camera_left = max(0.0, min(max_left, camera_left))
        camera_top = max(0.0, min(max_top, camera_top))

        return pg.Rect(
            int(camera_left),
            int(camera_top),
            int(visible_width),
            int(visible_height),
        )

    def _local_player(self) -> dict | None:
        for player in self.snapshot.players or []:
            if player["id"] == self.player_id:
                return self._display_player(player)
        return None

    def _draw_map_geometry(self, screen: pg.Surface, playfield_rect: pg.Rect, camera_rect: pg.Rect) -> None:
        if self.current_map is None:
            return

        for rect in self.current_map.collision_rects:
            screen_rect = self._screen_rect(rect.x, rect.y, rect.width, rect.height, playfield_rect, camera_rect)
            if screen_rect is None:
                continue
            restored = self._zone_is_restored(rect.restored_by_zone_id)
            fill_color = RESTORED_HEDGE_COLOR if restored else DEAD_HEDGE_COLOR
            accent_color = RESTORED_HEDGE_ACCENT_COLOR if restored else DEAD_HEDGE_ACCENT_COLOR
            pg.draw.rect(screen, fill_color, screen_rect, border_radius=12)
            accent_rect = screen_rect.inflate(-8, -8)
            if accent_rect.width > 0 and accent_rect.height > 0:
                pg.draw.rect(screen, accent_color, accent_rect, border_radius=10)

        for barrier in self._active_barriers():
            screen_rect = self._screen_rect(barrier.x, barrier.y, barrier.width, barrier.height, playfield_rect, camera_rect)
            if screen_rect is None:
                continue
            fill_color = (120, 150, 102) if not barrier.spirit_passable else (130, 166, 189)
            accent_color = (156, 185, 136) if not barrier.spirit_passable else (173, 205, 223)
            pg.draw.rect(screen, fill_color, screen_rect, border_radius=10)
            accent_rect = screen_rect.inflate(-8, -8)
            if accent_rect.width > 0 and accent_rect.height > 0:
                pg.draw.rect(screen, accent_color, accent_rect, border_radius=8)
            if barrier.spirit_passable and screen_rect.width > 14 and screen_rect.height > 14:
                pg.draw.rect(screen, (230, 244, 255), screen_rect, width=2, border_radius=10)

    def _draw_hazard_zones(self, screen: pg.Surface, playfield_rect: pg.Rect, camera_rect: pg.Rect) -> None:
        for zone in self.snapshot.hazard_zones or []:
            if not zone.get("active", True):
                continue
            self._draw_radius_overlay(
                screen,
                zone["x"],
                zone["y"],
                float(zone["radius"]),
                playfield_rect,
                camera_rect,
                fill_color=HAZARD_FILL_COLOR,
                outline_color=HAZARD_OUTLINE_COLOR,
            )

    def _draw_restoration_zones(
        self,
        screen: pg.Surface,
        playfield_rect: pg.Rect,
        camera_rect: pg.Rect,
        label_font: pg.font.Font,
    ) -> None:
        for zone in self.snapshot.restoration_zones or []:
            restored = bool(zone.get("restored", False))
            fill_color = RESTORATION_RESTORED_FILL if restored else RESTORATION_FILL_COLOR
            outline_color = RESTORATION_RESTORED_OUTLINE if restored else RESTORATION_OUTLINE_COLOR
            self._draw_radius_overlay(
                screen,
                zone["x"],
                zone["y"],
                float(zone["radius"]),
                playfield_rect,
                camera_rect,
                fill_color=fill_color,
                outline_color=outline_color,
            )
            screen_x, screen_y = self._screen_point(zone["x"], zone["y"], playfield_rect, camera_rect)
            label = "Restored" if restored else "Restore"
            label_surf = label_font.render(label, True, outline_color)
            screen.blit(label_surf, (screen_x - label_surf.get_width() // 2, screen_y - 10))

    def _draw_map_decorations(self, screen: pg.Surface, playfield_rect: pg.Rect, camera_rect: pg.Rect) -> None:
        if self.current_map is None:
            return

        for decoration in self.current_map.decorations:
            if not self._world_point_visible(decoration.x, decoration.y, playfield_rect, camera_rect, margin=96):
                continue
            asset_id = self._decoration_asset_id(decoration)
            try:
                asset = load_visual_asset(asset_id)
            except FileNotFoundError:
                dx, dy = self._screen_point(decoration.x, decoration.y, playfield_rect, camera_rect)
                pg.draw.rect(screen, (216, 155, 95), pg.Rect(dx - 10, dy - 10, 20, 20), border_radius=4)
                pg.draw.rect(screen, (109, 67, 32), pg.Rect(dx - 10, dy - 10, 20, 20), width=2, border_radius=4)
                continue
            dx, dy = self._screen_point(decoration.x, decoration.y, playfield_rect, camera_rect)
            render_visual_asset(screen, asset, (dx, dy), scale=max(0.1, decoration.scale))

    def _draw_enemy_spawners(self, screen: pg.Surface, playfield_rect: pg.Rect, camera_rect: pg.Rect) -> None:
        if self.current_map is None:
            return
        active_enemy_ids = {str(enemy.get("id", "")) for enemy in self.snapshot.enemies or []}
        for spawn in self.current_map.enemy_spawns:
            if not self._world_point_visible(spawn.x, spawn.y, playfield_rect, camera_rect, margin=80):
                continue
            sx, sy = self._screen_point(spawn.x, spawn.y, playfield_rect, camera_rect)
            is_active = spawn.enemy_id in active_enemy_ids
            outline_color = NEST_CORRUPT_OUTLINE if is_active else NEST_CLEANSED_OUTLINE
            color_overrides = (
                {
                    "nest_core": (128, 82, 85),
                    "nest_glow": (178, 109, 116),
                }
                if is_active
                else {
                    "nest_core": (114, 168, 104),
                    "nest_glow": (193, 224, 173),
                }
            )
            render_visual_asset(
                screen,
                self.visual_assets["bramble_nest"],
                (sx, sy),
                color_overrides=color_overrides,
            )
            pg.draw.circle(screen, outline_color, (sx, sy), 28, width=2)

    def _decoration_asset_id(self, decoration: DecorationDef) -> str:
        asset_id = decoration.asset_id
        restored_zone = self._restored_zone_for_decoration(decoration)
        if restored_zone is None:
            return asset_id

        if asset_id.startswith("dead_"):
            candidate_id = "restored_" + asset_id[len("dead_") :]
        elif asset_id.startswith("deaf_"):
            candidate_id = "restored_" + asset_id[len("deaf_") :]
        else:
            return asset_id

        try:
            load_visual_asset(candidate_id)
            return candidate_id
        except FileNotFoundError:
            return asset_id

    def _restored_zone_for_decoration(self, decoration: DecorationDef) -> dict | None:
        if not decoration.restored_by_zone_id:
            return None
        for zone in self.snapshot.restoration_zones or []:
            if str(zone.get("id", "")) != decoration.restored_by_zone_id:
                continue
            if bool(zone.get("restored", False)):
                return zone
        return None

    def _zone_is_restored(self, zone_id: str) -> bool:
        if not zone_id:
            return False
        for zone in self.snapshot.restoration_zones or []:
            if str(zone.get("id", "")) != zone_id:
                continue
            return bool(zone.get("restored", False))
        return False

    def _draw_compact_hud(
        self,
        screen: pg.Surface,
        font: pg.font.Font,
        small_font: pg.font.Font,
    ) -> None:
        local_player = self._local_player()
        revival_eggs = int(local_player.get("revival_eggs", 0)) if local_player is not None else 0
        restoration_eggs = int(local_player.get("restoration_eggs", 0)) if local_player is not None else 0
        spirit_seeds = int(local_player.get("spirit_seeds", 0)) if local_player is not None else 0

        screen_rect = screen.get_rect()
        hud_rect = pg.Rect(screen_rect.right - 194, 16, 162, 58)
        pg.draw.rect(screen, HUD_PANEL_COLOR, hud_rect, border_radius=16)
        pg.draw.rect(screen, HUD_PANEL_ACCENT, hud_rect, width=2, border_radius=16)
        render_visual_asset(
            screen,
            self.visual_assets["heart_bloom_dormant"],
            (hud_rect.left + 26, hud_rect.centery),
            scale=0.34,
        )
        title = small_font.render("Bloombound", True, TEXT_COLOR)
        values = small_font.render(f"R {revival_eggs}   T {restoration_eggs}   P {spirit_seeds}", True, TEXT_COLOR)
        screen.blit(title, (hud_rect.left + 48, hud_rect.top + 12))
        screen.blit(values, (hud_rect.left + 48, hud_rect.top + 32))

    def _draw_details_overlay(
        self,
        screen: pg.Surface,
        font: pg.font.Font,
        small_font: pg.font.Font,
        playfield_rect: pg.Rect,
    ) -> None:
        local_player = self._local_player()
        players = self.snapshot.players or []
        restoration_zones = self.snapshot.restoration_zones or []
        restored_count = sum(1 for zone in restoration_zones if zone.get("restored", False))
        local_name = local_player["name"] if local_player is not None else "Caretaker"
        local_state = str(local_player.get("state", "alive")).title() if local_player is not None else "Unknown"
        health = int(local_player.get("health", 0)) if local_player is not None else 0
        max_health = int(local_player.get("max_health", 0)) if local_player is not None else 0
        revival_eggs = int(local_player.get("revival_eggs", 0)) if local_player is not None else 0
        restoration_eggs = int(local_player.get("restoration_eggs", 0)) if local_player is not None else 0
        spirit_seeds = int(local_player.get("spirit_seeds", 0)) if local_player is not None else 0

        overlay = pg.Surface(screen.get_size(), pg.SRCALPHA)
        overlay.fill((24, 28, 24, 110))
        screen.blit(overlay, (0, 0))

        panel = pg.Rect(playfield_rect.left + 58, playfield_rect.top + 40, playfield_rect.width - 116, playfield_rect.height - 80)
        pg.draw.rect(screen, HUD_PANEL_COLOR, panel, border_radius=24)
        pg.draw.rect(screen, HUD_PANEL_ACCENT, panel, width=2, border_radius=24)

        title = font.render("Caretaker Details", True, TEXT_COLOR)
        subtitle = small_font.render("Tab toggles this panel", True, TEXT_COLOR)
        screen.blit(title, (panel.left + 24, panel.top + 20))
        screen.blit(subtitle, (panel.left + 24, panel.top + 48))

        info_left = panel.left + 24
        info_top = panel.top + 92
        name_text = small_font.render(f"{local_name}  |  State: {local_state}", True, TEXT_COLOR)
        screen.blit(name_text, (info_left, info_top))

        if max_health > 0:
            bar_rect = pg.Rect(info_left, info_top + 28, 220, 12)
            health_ratio = max(0.0, min(1.0, health / max_health))
            pg.draw.rect(screen, HEALTH_BG_COLOR, bar_rect, border_radius=6)
            pg.draw.rect(
                screen,
                HEALTH_FILL_COLOR,
                pg.Rect(bar_rect.left, bar_rect.top, int(bar_rect.width * health_ratio), bar_rect.height),
                border_radius=6,
            )
            health_text = small_font.render(f"Health {health}/{max_health}", True, TEXT_COLOR)
            screen.blit(health_text, (info_left, info_top + 46))

        inventory_top = info_top + 90
        inv_title = small_font.render("Inventory", True, TEXT_COLOR)
        screen.blit(inv_title, (info_left, inventory_top))
        self._draw_inventory_row(screen, small_font, info_left, inventory_top + 26, "Revival Eggs", revival_eggs, REVIVAL_EGG_COLOR)
        self._draw_inventory_row(screen, small_font, info_left, inventory_top + 54, "Restore Eggs", restoration_eggs, RESTORATION_EGG_COLOR)
        self._draw_inventory_row(screen, small_font, info_left, inventory_top + 82, "Spirit Seeds", spirit_seeds, SPIRIT_PICKUP_FILL)

        progress_left = panel.centerx + 12
        progress_top = info_top
        progress_title = small_font.render("Garden Progress", True, TEXT_COLOR)
        screen.blit(progress_title, (progress_left, progress_top))
        progress_lines = [
            f"Restored zones: {restored_count}/{len(restoration_zones)}",
            f"Live enemies: {len(self.snapshot.enemies or [])}",
            f"Loose eggs: {sum(1 for egg in (self.snapshot.eggs or []) if not egg.get('collected', False))}",
            f"Spirit seeds left: {sum(1 for pickup in (self.snapshot.spirit_pickups or []) if not pickup.get('collected', False))}",
        ]
        for index, line in enumerate(progress_lines):
            line_surf = small_font.render(line, True, TEXT_COLOR)
            screen.blit(line_surf, (progress_left, progress_top + 28 + index * 24))

        team_top = progress_top + 138
        team_title = small_font.render("Team", True, TEXT_COLOR)
        screen.blit(team_title, (progress_left, team_top))
        for index, player in enumerate(players[:4]):
            row_top = team_top + 24 + index * 24
            color = tuple(player["color"])
            pg.draw.circle(screen, color, (progress_left + 8, row_top + 8), 7)
            label = (
                f"{player['name']}  "
                f"R{int(player.get('revival_eggs', 0))} "
                f"T{int(player.get('restoration_eggs', 0))} "
                f"P{int(player.get('spirit_seeds', 0))}  "
                f"{str(player['state']).title()}"
            )
            row_surf = small_font.render(label, True, TEXT_COLOR)
            screen.blit(row_surf, (progress_left + 22, row_top))

        objective_top = inventory_top + 144
        objective_title = small_font.render("Objective", True, TEXT_COLOR)
        screen.blit(objective_title, (info_left, objective_top))
        wrapped_objective = self._wrap_text(
            self.snapshot.objective_text or "Move with WASD or arrows. Interact with E or Space.",
            small_font,
            panel.width - 48,
        )
        for index, line in enumerate(wrapped_objective[:5]):
            line_surf = small_font.render(line, True, TEXT_COLOR)
            screen.blit(line_surf, (info_left, objective_top + 28 + index * 22))

        controls_top = panel.bottom - 96
        controls_title = small_font.render("Controls", True, TEXT_COLOR)
        screen.blit(controls_title, (info_left, controls_top))
        control_lines = [
            "Move: WASD or Arrows",
            "Interact: E or Space",
            "Debug Spirit: K",
        ]
        for index, line in enumerate(control_lines):
            line_surf = small_font.render(line, True, TEXT_COLOR)
            screen.blit(line_surf, (info_left, controls_top + 24 + index * 20))

    def _draw_inventory_row(
        self,
        screen: pg.Surface,
        small_font: pg.font.Font,
        left: int,
        top: int,
        label: str,
        value: int,
        swatch_color: tuple[int, ...],
        *,
        short: bool = False,
    ) -> None:
        swatch_rect = pg.Rect(left, top + 2, 16, 16)
        pg.draw.rect(screen, swatch_color[:3], swatch_rect, border_radius=5)
        pg.draw.rect(screen, TEXT_COLOR, swatch_rect, width=1, border_radius=5)
        rendered_label = label
        if short:
            rendered_label = {
                "Revival Eggs": "Revive",
                "Restore Eggs": "Restore",
                "Spirit Seeds": "Seeds",
            }.get(label, label)
        line = small_font.render(f"{rendered_label}: {value}", True, TEXT_COLOR)
        screen.blit(line, (left + 24, top))

    @staticmethod
    def _wrap_text(text: str, font: pg.font.Font, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _active_barriers(self) -> list[TraversalBarrierDef]:
        if self.current_map is None:
            return []
        restored_lookup = {
            str(zone.get("id", "")): bool(zone.get("restored", False))
            for zone in self.snapshot.restoration_zones or []
        }
        active: list[TraversalBarrierDef] = []
        for barrier in self.current_map.traversal_barriers:
            if barrier.cleared_by_zone_id and restored_lookup.get(barrier.cleared_by_zone_id, False):
                continue
            active.append(barrier)
        return active

    @staticmethod
    def _barrier_rects(barriers: list[TraversalBarrierDef]) -> list[CollisionRect]:
        return [
            CollisionRect(
                rect_id=barrier.barrier_id,
                x=barrier.x,
                y=barrier.y,
                width=barrier.width,
                height=barrier.height,
            )
            for barrier in barriers
        ]

    def _local_collision_rects(self) -> list[CollisionRect]:
        if self.current_map is None or self.local_predicted_player is None:
            return []
        active_barriers = self._active_barriers()
        if self.local_predicted_player.get("state") == "spirit":
            active_barriers = [barrier for barrier in active_barriers if not barrier.spirit_passable]
        return self.current_map.collision_rects + self._barrier_rects(active_barriers)

    def _screen_rect(
        self,
        world_x: float,
        world_y: float,
        width: float,
        height: float,
        playfield_rect: pg.Rect,
        camera_rect: pg.Rect,
    ) -> pg.Rect | None:
        left = int(playfield_rect.left + (world_x - camera_rect.left) * CAMERA_ZOOM)
        top = int(playfield_rect.top + (world_y - camera_rect.top) * CAMERA_ZOOM)
        rect = pg.Rect(left, top, int(width * CAMERA_ZOOM), int(height * CAMERA_ZOOM))
        clipped = rect.clip(playfield_rect)
        if clipped.width <= 0 or clipped.height <= 0:
            return None
        return clipped

    def _draw_radius_overlay(
        self,
        screen: pg.Surface,
        world_x: float,
        world_y: float,
        radius: float,
        playfield_rect: pg.Rect,
        camera_rect: pg.Rect,
        *,
        fill_color: tuple[int, ...],
        outline_color: tuple[int, ...],
    ) -> None:
        screen_x, screen_y = self._screen_point(world_x, world_y, playfield_rect, camera_rect)
        screen_radius = max(8, int(radius * CAMERA_ZOOM))
        overlay_rect = pg.Rect(screen_x - screen_radius, screen_y - screen_radius, screen_radius * 2, screen_radius * 2)
        if overlay_rect.right < playfield_rect.left or overlay_rect.left > playfield_rect.right:
            return
        if overlay_rect.bottom < playfield_rect.top or overlay_rect.top > playfield_rect.bottom:
            return
        overlay_surface = pg.Surface((screen_radius * 2 + 4, screen_radius * 2 + 4), pg.SRCALPHA)
        pg.draw.circle(overlay_surface, fill_color, (screen_radius + 2, screen_radius + 2), screen_radius)
        screen.blit(overlay_surface, (screen_x - screen_radius - 2, screen_y - screen_radius - 2))
        pg.draw.circle(screen, outline_color, (screen_x, screen_y), screen_radius, width=2)

    def _world_point_visible(
        self,
        world_x: float,
        world_y: float,
        playfield_rect: pg.Rect,
        camera_rect: pg.Rect,
        *,
        margin: int = 0,
    ) -> bool:
        screen_x, screen_y = self._screen_point(world_x, world_y, playfield_rect, camera_rect)
        return (
            playfield_rect.left - margin <= screen_x <= playfield_rect.right + margin
            and playfield_rect.top - margin <= screen_y <= playfield_rect.bottom + margin
        )

    def _load_map(self, map_id: str) -> None:
        if self.current_map is not None and self.current_map.map_id == map_id:
            return
        self.current_map = load_map(map_id)

    def _draw_match_overlay(
        self,
        screen: pg.Surface,
        font: pg.font.Font,
        small_font: pg.font.Font,
        playfield_rect: pg.Rect,
    ) -> None:
        overlay = pg.Surface((playfield_rect.width, playfield_rect.height), pg.SRCALPHA)
        overlay.fill((24, 30, 24, 124))
        screen.blit(overlay, playfield_rect.topleft)

        if self.snapshot.match_phase == "won":
            title_text = "Heart Garden Restored"
            title_color = WIN_COLOR
        else:
            title_text = "The Bramble Took Over"
            title_color = LOSS_COLOR

        title = font.render(title_text, True, title_color)
        prompt = small_font.render(self.snapshot.objective_text, True, (246, 244, 238))
        controls = small_font.render("Host can press Enter to restart.", True, (246, 244, 238))

        center_x = playfield_rect.centerx
        center_y = playfield_rect.centery
        screen.blit(title, (center_x - title.get_width() // 2, center_y - 32))
        screen.blit(prompt, (center_x - prompt.get_width() // 2, center_y + 2))
        screen.blit(controls, (center_x - controls.get_width() // 2, center_y + 28))

    def _maybe_send_ping(self) -> None:
        if not self.diagnostics.enabled or not self.connected:
            return
        now = time.perf_counter()
        if now < self.next_ping_at:
            return
        self.next_ping_at = now + 1.0
        self.ping_nonce += 1
        self.network.send(
            {
                "type": "ping",
                "nonce": self.ping_nonce,
                "client_sent_at": now,
            }
        )

    def _handle_pong(self, message: dict) -> None:
        try:
            client_sent_at = float(message.get("client_sent_at", 0.0))
        except (TypeError, ValueError):
            return
        if client_sent_at <= 0.0:
            return
        now = time.perf_counter()
        server_turnaround = None
        try:
            received_at = float(message.get("server_received_at", 0.0))
            replied_at = float(message.get("server_replied_at", 0.0))
        except (TypeError, ValueError):
            received_at = 0.0
            replied_at = 0.0
        if replied_at >= received_at > 0.0:
            server_turnaround = replied_at - received_at
        self.diagnostics.record_rtt(now - client_sent_at, server_turnaround)

    def _maybe_send_udp_hello(self) -> None:
        if not self.connected or self.player_id == "" or self.udp_ready:
            return
        now = time.perf_counter()
        if now < self.next_udp_hello_at:
            return
        self.udp_nonce += 1
        self.network.send_udp(
            {
                "type": "udp_hello",
                "player_id": self.player_id,
                "nonce": self.udp_nonce,
            }
        )
        self.next_udp_hello_at = now + 1.0


def run_client(host: str, port: int, name: str, net_debug: bool = False) -> None:
    EasterClientApp(host, port, name, net_debug=net_debug).run()
