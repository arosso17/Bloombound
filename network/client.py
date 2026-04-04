from __future__ import annotations

import queue
import socket
import threading
from dataclasses import dataclass

import pygame as pg

from gameplay.state import PLAYER_COLORS
from network.shared import read_messages_forever, safe_close, send_message


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
CAMERA_ZOOM = 1.0
BACKGROUND_COLOR = (232, 228, 214)
PLAYFIELD_COLOR = (205, 214, 188)
SHRINE_COLOR = (255, 216, 138)
EGG_COLOR = (244, 160, 177)
TEXT_COLOR = (48, 58, 64)
SPIRIT_COLOR = (188, 234, 255)
SELF_RING_COLOR = (40, 40, 40)
ENEMY_COLOR = (77, 104, 72)
ENEMY_CORE_COLOR = (154, 195, 140)
HEALTH_BG_COLOR = (233, 222, 212)
HEALTH_FILL_COLOR = (120, 191, 104)
LOSS_COLOR = (125, 76, 76)
WIN_COLOR = (89, 143, 84)


@dataclass
class ClientSnapshot:
    tick: int = 0
    world_width: int = 1200
    world_height: int = 720
    match_phase: str = "lobby"
    players: list[dict] | None = None
    egg: dict | None = None
    shrine: dict | None = None
    enemy: dict | None = None
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
        self.snapshot = ClientSnapshot(players=[], egg=None, shrine=None)
        self.connected = False
        self.connection_closed = False
        self.input_seq = 0
        self.lobby_players: list[dict] = []
        self.expected_players = 1
        self.host_id = ""
        self.can_start = False

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
                self.snapshot.match_phase = str(message.get("match_phase", "lobby"))
                self.snapshot.world_width = int(message["world"]["width"])
                self.snapshot.world_height = int(message["world"]["height"])
                self.connected = True
                self.connection_closed = False
                self._send_profile_update()
            elif message_type == "lobby_state":
                self.snapshot.match_phase = str(message.get("match_phase", "lobby"))
                self.expected_players = int(message.get("expected_players", 1))
                self.host_id = str(message.get("host_id", ""))
                self.can_start = bool(message.get("can_start", False))
                self.lobby_players = list(message.get("players", []))
                self._sync_local_profile_from_lobby()
            elif message_type == "world_snapshot":
                self.snapshot.tick = int(message.get("tick", 0))
                self.snapshot.match_phase = str(message.get("match_phase", "playing"))
                self.snapshot.players = list(message.get("players", []))
                self.snapshot.egg = message.get("egg")
                self.snapshot.shrine = message.get("shrine")
                self.snapshot.enemy = message.get("enemy")
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

        if self.snapshot.shrine:
            shrine_x, shrine_y = self._screen_point(
                self.snapshot.shrine["x"],
                self.snapshot.shrine["y"],
                playfield_rect,
                camera_rect,
            )
            pg.draw.circle(screen, SHRINE_COLOR, (shrine_x, shrine_y), 26)
            pg.draw.circle(screen, (255, 247, 215), (shrine_x, shrine_y), 42, width=3)

        if self.snapshot.egg and not self.snapshot.egg.get("collected", False):
            egg_x, egg_y = self._screen_point(
                self.snapshot.egg["x"],
                self.snapshot.egg["y"],
                playfield_rect,
                camera_rect,
            )
            pg.draw.ellipse(screen, EGG_COLOR, pg.Rect(egg_x - 10, egg_y - 14, 20, 28))

        if self.snapshot.enemy:
            enemy_x, enemy_y = self._screen_point(
                self.snapshot.enemy["x"],
                self.snapshot.enemy["y"],
                playfield_rect,
                camera_rect,
            )
            enemy_radius = int(self.snapshot.enemy["radius"] * CAMERA_ZOOM)
            pg.draw.circle(screen, ENEMY_COLOR, (enemy_x, enemy_y), enemy_radius + 3)
            pg.draw.circle(screen, ENEMY_CORE_COLOR, (enemy_x, enemy_y), max(4, enemy_radius - 4))

        for player in self.snapshot.players or []:
            px, py = self._screen_point(player["x"], player["y"], playfield_rect, camera_rect)
            color = tuple(player["color"])
            radius = int(player["radius"] * CAMERA_ZOOM)
            if player["state"] == "spirit":
                pg.draw.circle(screen, SPIRIT_COLOR, (px, py), radius + 2)
                pg.draw.circle(screen, color, (px, py), radius, width=2)
            else:
                pg.draw.circle(screen, color, (px, py), radius)
            if player["id"] == self.player_id:
                pg.draw.circle(screen, SELF_RING_COLOR, (px, py), radius + 5, width=2)
            name_surf = small_font.render(
                f"{player['name']} ({player['revival_eggs']})",
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
