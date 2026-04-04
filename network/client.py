from __future__ import annotations

import queue
import socket
import threading
from dataclasses import dataclass

import pygame as pg

from gameplay.map_loader import load_map
from gameplay.map_types import MapDefinition
from gameplay.state import PLAYER_COLORS
from gameplay.visual_assets import load_visual_asset, render_visual_asset
from network.shared import read_messages_forever, safe_close, send_message


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
CAMERA_ZOOM = 1.0
BACKGROUND_COLOR = (232, 228, 214)
PLAYFIELD_COLOR = (205, 214, 188)
SHRINE_COLOR = (255, 216, 138)
TEXT_COLOR = (48, 58, 64)
SPIRIT_COLOR = (188, 234, 255)
SELF_RING_COLOR = (40, 40, 40)
HEALTH_BG_COLOR = (233, 222, 212)
HEALTH_FILL_COLOR = (120, 191, 104)
LOSS_COLOR = (125, 76, 76)
WIN_COLOR = (89, 143, 84)
HEDGE_COLOR = (111, 139, 96)
HEDGE_ACCENT_COLOR = (140, 171, 122)
REVIVAL_EGG_COLOR = (244, 173, 208)
RESTORATION_EGG_COLOR = (143, 214, 181)
HAZARD_FILL_COLOR = (164, 88, 88, 72)
HAZARD_OUTLINE_COLOR = (132, 61, 61)
RESTORATION_FILL_COLOR = (122, 174, 122, 58)
RESTORATION_OUTLINE_COLOR = (81, 132, 84)
RESTORATION_RESTORED_FILL = (160, 216, 156, 92)
RESTORATION_RESTORED_OUTLINE = (58, 117, 65)
ENEMY_PATROL_RING = (86, 118, 78)
ENEMY_ALERT_RING = (224, 162, 81)
ENEMY_CHASE_RING = (198, 83, 83)
ENEMY_RETURN_RING = (120, 105, 84)


@dataclass
class ClientSnapshot:
    tick: int = 0
    world_width: int = 1200
    world_height: int = 720
    match_phase: str = "lobby"
    players: list[dict] | None = None
    eggs: list[dict] | None = None
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
        self.name = name
        self.sock: socket.socket | None = None
        self.send_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.incoming: queue.Queue[dict] = queue.Queue()

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        threading.Thread(target=self._reader_loop, daemon=True).start()
        self.send({"type": "join", "name": self.name})

    def close(self) -> None:
        self.stop_event.set()
        safe_close(self.sock)

    def send(self, message: dict) -> None:
        if self.sock is None:
            return
        with self.send_lock:
            send_message(self.sock, message)

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


class EasterClientApp:
    def __init__(self, host: str, port: int, name: str) -> None:
        self.network = NetworkClient(host, port, name)
        self.player_id = ""
        self.name_input = name[:24]
        self.selected_color_index = 0
        self.profile_initialized = False
        self.snapshot = ClientSnapshot(players=[], eggs=[], restoration_zones=[], hazard_zones=[], shrine=None, enemies=[])
        self.connected = False
        self.connection_closed = False
        self.input_seq = 0
        self.lobby_players: list[dict] = []
        self.expected_players = 1
        self.host_id = ""
        self.can_start = False
        self.current_map: MapDefinition | None = None
        self.visual_assets = {
            "shrine": load_visual_asset("shrine"),
            "egg": load_visual_asset("egg"),
            "bramble_enemy": load_visual_asset("bramble_enemy"),
            "heart_bloom_dormant": load_visual_asset("heart_bloom_dormant"),
            "heart_bloom_restored": load_visual_asset("heart_bloom_restored"),
            "player": load_visual_asset("player"),
        }

    def run(self) -> None:
        pg.init()
        screen = pg.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
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
            clock.tick(60)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.KEYDOWN:
                    self._handle_keydown(event)

            self._handle_network_messages()
            if self.snapshot.match_phase == "playing":
                keys = pg.key.get_pressed()
                self._send_input(keys)
            self._draw(screen, font, small_font)
            pg.display.flip()

            if self.connection_closed:
                running = False

        self.network.close()
        pg.quit()

    def _handle_network_messages(self) -> None:
        for message in self.network.poll_messages():
            message_type = message.get("type")
            if message_type == "welcome":
                self.player_id = str(message["player_id"])
                self._load_map(str(message.get("map_id", "heart_garden")))
                self.snapshot.match_phase = str(message.get("match_phase", "lobby"))
                self.snapshot.world_width = int(message["world"]["width"])
                self.snapshot.world_height = int(message["world"]["height"])
                self.connected = True
                self.connection_closed = False
                self._send_profile_update()
            elif message_type == "lobby_state":
                self._load_map(str(message.get("map_id", "heart_garden")))
                self.snapshot.match_phase = str(message.get("match_phase", "lobby"))
                self.expected_players = int(message.get("expected_players", 1))
                self.host_id = str(message.get("host_id", ""))
                self.can_start = bool(message.get("can_start", False))
                self.lobby_players = list(message.get("players", []))
                self._sync_local_profile_from_lobby()
            elif message_type == "world_snapshot":
                self._load_map(str(message.get("map_id", "heart_garden")))
                self.snapshot.tick = int(message.get("tick", 0))
                self.snapshot.match_phase = str(message.get("match_phase", "playing"))
                self.snapshot.players = list(message.get("players", []))
                self.snapshot.eggs = list(message.get("eggs", []))
                self.snapshot.restoration_zones = list(message.get("restoration_zones", []))
                self.snapshot.hazard_zones = list(message.get("hazard_zones", []))
                self.snapshot.shrine = message.get("shrine")
                self.snapshot.enemies = list(message.get("enemies", []))
                self.snapshot.final_bloom = message.get("final_bloom")
                self.snapshot.objective_text = str(message.get("objective_text", ""))
            elif message_type == "disconnected":
                self.connected = False
                self.connection_closed = True

    def _handle_keydown(self, event: pg.event.Event) -> None:
        if not self.connected:
            return
        if self.snapshot.match_phase in {"won", "lost"}:
            if event.key == pg.K_RETURN and self.is_host and self.can_start:
                self.network.send({"type": "start_game"})
            return
        if self.snapshot.match_phase != "lobby":
            return
        if event.key == pg.K_BACKSPACE:
            self.name_input = self.name_input[:-1]
            self._send_profile_update()
            return
        if event.key == pg.K_LEFT:
            self.selected_color_index = (self.selected_color_index - 1) % len(PLAYER_COLORS)
            self._send_profile_update()
            return
        if event.key == pg.K_RIGHT:
            self.selected_color_index = (self.selected_color_index + 1) % len(PLAYER_COLORS)
            self._send_profile_update()
            return
        if event.key == pg.K_RETURN:
            if self.is_host and self.can_start:
                self.network.send({"type": "start_game"})
            return
        if event.unicode and event.unicode.isprintable() and len(self.name_input) < 24:
            self.name_input += event.unicode
            self._send_profile_update()

    def _send_input(self, keys: pg.key.ScancodeWrapper) -> None:
        if not self.connected:
            return
        move_x = float(keys[pg.K_d]) - float(keys[pg.K_a])
        move_y = float(keys[pg.K_s]) - float(keys[pg.K_w])
        self.input_seq += 1
        self.network.send(
            {
                "type": "player_input",
                "seq": self.input_seq,
                "move_x": move_x,
                "move_y": move_y,
                "interact": bool(keys[pg.K_e]),
                "debug_down": bool(keys[pg.K_k]),
            }
        )

    def _draw(self, screen: pg.Surface, font: pg.font.Font, small_font: pg.font.Font) -> None:
        if self.snapshot.match_phase == "lobby":
            self._draw_lobby(screen, font, small_font)
            return

        screen.fill(BACKGROUND_COLOR)
        playfield_rect = pg.Rect(32, 96, WINDOW_WIDTH - 64, WINDOW_HEIGHT - 132)
        pg.draw.rect(screen, PLAYFIELD_COLOR, playfield_rect, border_radius=18)
        camera_rect = self._camera_rect(playfield_rect)
        self._draw_map_geometry(screen, playfield_rect, camera_rect)
        self._draw_hazard_zones(screen, playfield_rect, camera_rect)
        self._draw_restoration_zones(screen, playfield_rect, camera_rect, small_font)
        self._draw_map_decorations(screen, playfield_rect, camera_rect)

        if self.snapshot.shrine:
            shrine_x, shrine_y = self._screen_point(
                self.snapshot.shrine["x"],
                self.snapshot.shrine["y"],
                playfield_rect,
                camera_rect,
            )
            render_visual_asset(screen, self.visual_assets["shrine"], (shrine_x, shrine_y))

        if self.snapshot.final_bloom:
            bloom_x, bloom_y = self._screen_point(
                self.snapshot.final_bloom["x"],
                self.snapshot.final_bloom["y"],
                playfield_rect,
                camera_rect,
            )
            bloom_asset = "heart_bloom_restored" if self.snapshot.final_bloom.get("restored") else "heart_bloom_dormant"
            render_visual_asset(screen, self.visual_assets[bloom_asset], (bloom_x, bloom_y))

        for egg in self.snapshot.eggs or []:
            if egg.get("collected", False):
                continue
            egg_x, egg_y = self._screen_point(
                egg["x"],
                egg["y"],
                playfield_rect,
                camera_rect,
            )
            egg_color = RESTORATION_EGG_COLOR if egg.get("egg_type") == "restoration" else REVIVAL_EGG_COLOR
            pg.draw.circle(screen, egg_color, (egg_x, egg_y), 14, width=3)
            render_visual_asset(screen, self.visual_assets["egg"], (egg_x, egg_y))

        for enemy in self.snapshot.enemies or []:
            enemy_x, enemy_y = self._screen_point(
                enemy["x"],
                enemy["y"],
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
            px, py = self._screen_point(player["x"], player["y"], playfield_rect, camera_rect)
            color = tuple(player["color"])
            radius = int(player["radius"] * CAMERA_ZOOM)
            ring_radius = radius + 5
            if player["state"] == "spirit":
                pg.draw.circle(screen, SPIRIT_COLOR, (px, py), radius + 2)
                pg.draw.circle(screen, color, (px, py), radius, width=2)
            else:
                player_scale = max(0.45, (player["radius"] * 2.25) / self.visual_assets["player"].width)
                render_visual_asset(
                    screen,
                    self.visual_assets["player"],
                    (px, py),
                    scale=player_scale,
                    color_overrides={"player_head": color},
                )
                ring_radius = max(ring_radius, int((self.visual_assets["player"].width * player_scale) / 2) + 2)
            if player["id"] == self.player_id:
                pg.draw.circle(screen, SELF_RING_COLOR, (px, py), ring_radius, width=2)
            name_surf = small_font.render(
                f"{player['name']} (R{player['revival_eggs']} S{player.get('restoration_eggs', 0)})",
                True,
                TEXT_COLOR,
            )
            screen.blit(name_surf, (px - name_surf.get_width() // 2, py - radius - 24))
            if player["state"] == "alive":
                bar_width = 42
                bar_height = 6
                health_ratio = max(0.0, min(1.0, player["health"] / max(1, player["max_health"])))
                bar_rect = pg.Rect(px - bar_width // 2, py + radius + 10, bar_width, bar_height)
                pg.draw.rect(screen, HEALTH_BG_COLOR, bar_rect, border_radius=4)
                pg.draw.rect(
                    screen,
                    HEALTH_FILL_COLOR,
                    pg.Rect(bar_rect.left, bar_rect.top, int(bar_width * health_ratio), bar_height),
                    border_radius=4,
                )
                if float(player.get("hazard_slow_multiplier", 1.0)) < 1.0:
                    pg.draw.circle(screen, HAZARD_OUTLINE_COLOR, (px, py), ring_radius + 6, width=2)

        title = font.render("Bloombound Networking Prototype", True, TEXT_COLOR)
        if self.connected:
            status_text = self.snapshot.objective_text or "Move: WASD | Interact: E at shrine | Debug spirit: K"
        else:
            status_text = f"Connecting to {self.network.host}:{self.network.port}..."
        status = small_font.render(status_text, True, TEXT_COLOR)
        tick_text = small_font.render(f"Snapshot tick: {self.snapshot.tick}", True, TEXT_COLOR)
        screen.blit(title, (32, 28))
        screen.blit(status, (32, 58))
        screen.blit(tick_text, (WINDOW_WIDTH - 180, 28))
        if self.snapshot.match_phase in {"won", "lost"}:
            self._draw_match_overlay(screen, font, small_font, playfield_rect)

    def _draw_lobby(self, screen: pg.Surface, font: pg.font.Font, small_font: pg.font.Font) -> None:
        screen.fill(BACKGROUND_COLOR)
        panel = pg.Rect(64, 72, WINDOW_WIDTH - 128, WINDOW_HEIGHT - 144)
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
                return player
        return None

    def _draw_map_geometry(self, screen: pg.Surface, playfield_rect: pg.Rect, camera_rect: pg.Rect) -> None:
        if self.current_map is None:
            return

        for rect in self.current_map.collision_rects:
            screen_rect = self._screen_rect(rect.x, rect.y, rect.width, rect.height, playfield_rect, camera_rect)
            if screen_rect is None:
                continue
            pg.draw.rect(screen, HEDGE_COLOR, screen_rect, border_radius=12)
            accent_rect = screen_rect.inflate(-8, -8)
            if accent_rect.width > 0 and accent_rect.height > 0:
                pg.draw.rect(screen, HEDGE_ACCENT_COLOR, accent_rect, border_radius=10)

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
            try:
                asset = load_visual_asset(decoration.asset_id)
            except FileNotFoundError:
                dx, dy = self._screen_point(decoration.x, decoration.y, playfield_rect, camera_rect)
                pg.draw.rect(screen, (216, 155, 95), pg.Rect(dx - 10, dy - 10, 20, 20), border_radius=4)
                pg.draw.rect(screen, (109, 67, 32), pg.Rect(dx - 10, dy - 10, 20, 20), width=2, border_radius=4)
                continue
            dx, dy = self._screen_point(decoration.x, decoration.y, playfield_rect, camera_rect)
            render_visual_asset(screen, asset, (dx, dy), scale=max(0.1, decoration.scale))

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


def run_client(host: str, port: int, name: str) -> None:
    EasterClientApp(host, port, name).run()
