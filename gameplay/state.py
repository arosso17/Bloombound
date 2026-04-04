import math

from gameplay.entities import EggState, PlayerInput, PlayerState, ShrineState


WORLD_WIDTH = 1200
WORLD_HEIGHT = 720
ALIVE_SPEED = 230.0
SPIRIT_SPEED = 280.0
PLAYER_SPAWN_POINTS = [
    (160.0, 160.0),
    (260.0, 160.0),
    (160.0, 260.0),
    (260.0, 260.0),
]
PLAYER_COLORS = [
    (242, 119, 119),
    (112, 193, 179),
    (255, 209, 102),
    (123, 158, 249),
    (199, 146, 234),
    (247, 143, 179),
]


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


class GameState:
    def __init__(self, expected_players: int = 2) -> None:
        self.tick = 0
        self.expected_players = max(1, expected_players)
        self.match_phase = "lobby"
        self.host_id = ""
        self.players: dict[str, PlayerState] = {}
        self.egg = EggState("egg-1", 600.0, 240.0)
        self.shrine = ShrineState("shrine-1", 860.0, 420.0)

    def add_player(self, player_id: str, name: str) -> PlayerState:
        spawn_x, spawn_y = PLAYER_SPAWN_POINTS[len(self.players) % len(PLAYER_SPAWN_POINTS)]
        color_index = len(self.players) % len(PLAYER_COLORS)
        player = PlayerState(player_id=player_id, name=name, x=spawn_x, y=spawn_y, color_index=color_index)
        self.players[player_id] = player
        if not self.host_id:
            self.host_id = player_id
        return player

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        if self.host_id == player_id:
            self.host_id = next(iter(self.players), "")

    def rename_player(self, player_id: str, name: str) -> None:
        player = self.players.get(player_id)
        if player and name:
            player.name = name[:24]

    def set_color(self, player_id: str, color_index: int) -> None:
        player = self.players.get(player_id)
        if not player:
            return
        player.color_index = color_index % len(PLAYER_COLORS)

    def start_match(self, requesting_player_id: str) -> bool:
        if requesting_player_id != self.host_id:
            return False
        if len(self.players) < self.expected_players:
            return False
        self.match_phase = "playing"
        self.tick = 0
        self.egg.collected = False
        for index, player in enumerate(self.players.values()):
            spawn_x, spawn_y = PLAYER_SPAWN_POINTS[index % len(PLAYER_SPAWN_POINTS)]
            player.x = spawn_x
            player.y = spawn_y
            player.state = "alive"
            player.health = player.max_health
            player.revival_eggs = 0
            player.input_state = PlayerInput()
            player.prev_input_state = PlayerInput()
        return True

    def can_start(self) -> bool:
        return len(self.players) >= self.expected_players

    def build_lobby_state(self) -> dict:
        players = []
        for player in self.players.values():
            players.append(
                {
                    "id": player.player_id,
                    "name": player.name,
                    "color_index": player.color_index,
                    "color": list(PLAYER_COLORS[player.color_index]),
                    "is_host": player.player_id == self.host_id,
                }
            )
        return {
            "type": "lobby_state",
            "match_phase": self.match_phase,
            "expected_players": self.expected_players,
            "connected_players": len(self.players),
            "host_id": self.host_id,
            "can_start": self.can_start(),
            "players": players,
        }

    def apply_input(self, player_id: str, payload: dict) -> None:
        player = self.players.get(player_id)
        if not player or self.match_phase != "playing":
            return
        player.input_state = PlayerInput(
            move_x=float(payload.get("move_x", 0.0)),
            move_y=float(payload.get("move_y", 0.0)),
            interact=bool(payload.get("interact", False)),
            debug_down=bool(payload.get("debug_down", False)),
            seq=int(payload.get("seq", 0)),
        )

    def update(self, dt: float) -> None:
        self.tick += 1
        for player in self.players.values():
            self._update_player(player, dt)
        for player in self.players.values():
            player.prev_input_state = PlayerInput(
                move_x=player.input_state.move_x,
                move_y=player.input_state.move_y,
                interact=player.input_state.interact,
                debug_down=player.input_state.debug_down,
                seq=player.input_state.seq,
            )

    def build_snapshot(self) -> dict:
        return {
            "type": "world_snapshot",
            "tick": self.tick,
            "match_phase": self.match_phase,
            "world": {"width": WORLD_WIDTH, "height": WORLD_HEIGHT},
            "players": [self._player_snapshot(player) for player in self.players.values()],
            "egg": self.egg.to_dict(),
            "shrine": self.shrine.to_dict(),
        }

    def _player_snapshot(self, player: PlayerState) -> dict:
        payload = player.to_dict()
        payload["color"] = list(PLAYER_COLORS[player.color_index])
        return payload

    def _update_player(self, player: PlayerState, dt: float) -> None:
        move_x = max(-1.0, min(1.0, player.input_state.move_x))
        move_y = max(-1.0, min(1.0, player.input_state.move_y))
        magnitude = math.hypot(move_x, move_y)
        if magnitude > 1.0:
            move_x /= magnitude
            move_y /= magnitude

        speed = SPIRIT_SPEED if player.state == "spirit" else ALIVE_SPEED
        player.x += move_x * speed * dt
        player.y += move_y * speed * dt

        player.x = max(player.radius, min(WORLD_WIDTH - player.radius, player.x))
        player.y = max(player.radius, min(WORLD_HEIGHT - player.radius, player.y))

        if self._pressed(player, "debug_down") and player.state == "alive":
            player.state = "spirit"
            player.health = 0

        if player.state == "alive" and not self.egg.collected:
            if distance(player.x, player.y, self.egg.x, self.egg.y) <= player.radius + self.egg.radius:
                self.egg.collected = True
                player.revival_eggs += 1

        if self._pressed(player, "interact"):
            self._try_revive(player)

    def _pressed(self, player: PlayerState, attr: str) -> bool:
        return getattr(player.input_state, attr) and not getattr(player.prev_input_state, attr)

    def _try_revive(self, player: PlayerState) -> None:
        if player.state != "alive" or player.revival_eggs <= 0:
            return
        if distance(player.x, player.y, self.shrine.x, self.shrine.y) > self.shrine.interact_radius:
            return

        spirit_targets = [
            spirit
            for spirit in self.players.values()
            if spirit.state == "spirit"
            and distance(spirit.x, spirit.y, self.shrine.x, self.shrine.y) <= self.shrine.revive_radius
        ]
        if not spirit_targets:
            return

        revived = min(
            spirit_targets,
            key=lambda spirit: distance(spirit.x, spirit.y, self.shrine.x, self.shrine.y),
        )
        player.revival_eggs -= 1
        revived.state = "alive"
        revived.health = revived.max_health // 2
        revived.x = self.shrine.x + 36.0
        revived.y = self.shrine.y
