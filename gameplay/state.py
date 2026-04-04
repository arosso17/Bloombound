from __future__ import annotations

import math

from gameplay.collision import move_circle
from gameplay.entities import EggState, EnemyState, FinalBloomState, PlayerInput, PlayerState, ShrineState
from gameplay.map_loader import load_map


ALIVE_SPEED = 230.0
SPIRIT_SPEED = 280.0
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
    def __init__(self, expected_players: int = 2, map_id: str = "heart_garden") -> None:
        self.map = load_map(map_id)
        self.tick = 0
        self.expected_players = max(1, expected_players)
        self.match_phase = "lobby"
        self.host_id = ""
        self.map_id = self.map.map_id
        self.players: dict[str, PlayerState] = {}
        self.eggs = self._build_eggs_from_map()
        shrine_def = self.map.shrine
        self.shrine = ShrineState(
            shrine_def.shrine_id,
            shrine_def.x,
            shrine_def.y,
            interact_radius=shrine_def.interact_radius,
            revive_radius=shrine_def.revive_radius,
        )
        enemy_def = self.map.enemy_spawns[0]
        self.enemy = EnemyState(
            enemy_def.enemy_id,
            enemy_def.x,
            enemy_def.y,
            radius=enemy_def.radius,
            speed=enemy_def.speed,
            damage_per_second=enemy_def.damage_per_second,
        )
        bloom_def = self.map.final_bloom
        self.final_bloom = FinalBloomState(
            bloom_def.bloom_id,
            bloom_def.x,
            bloom_def.y,
            radius=bloom_def.radius,
            interact_radius=bloom_def.interact_radius,
        )

    def add_player(self, player_id: str, name: str) -> PlayerState:
        spawn = self.map.player_spawns[len(self.players) % len(self.map.player_spawns)]
        color_index = len(self.players) % len(PLAYER_COLORS)
        player = PlayerState(player_id=player_id, name=name, x=spawn.x, y=spawn.y, color_index=color_index)
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
        self.final_bloom.restored = False
        self._reset_eggs()
        enemy_def = self.map.enemy_spawns[0]
        self.enemy.x = enemy_def.x
        self.enemy.y = enemy_def.y
        for index, player in enumerate(self.players.values()):
            spawn = self.map.player_spawns[index % len(self.map.player_spawns)]
            player.x = spawn.x
            player.y = spawn.y
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
            "map_id": self.map_id,
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
        self._update_enemy(dt)
        for player in self.players.values():
            player.prev_input_state = PlayerInput(
                move_x=player.input_state.move_x,
                move_y=player.input_state.move_y,
                interact=player.input_state.interact,
                debug_down=player.input_state.debug_down,
                seq=player.input_state.seq,
            )
        if self.final_bloom.restored:
            self.match_phase = "won"
        elif self.players and all(player.state == "spirit" for player in self.players.values()):
            self.match_phase = "lost"

    def build_snapshot(self) -> dict:
        return {
            "type": "world_snapshot",
            "tick": self.tick,
            "map_id": self.map_id,
            "match_phase": self.match_phase,
            "world": {"width": self.map.world_width, "height": self.map.world_height},
            "players": [self._player_snapshot(player) for player in self.players.values()],
            "eggs": [egg.to_dict() for egg in self.eggs],
            "shrine": self.shrine.to_dict(),
            "enemy": self.enemy.to_dict(),
            "final_bloom": self.final_bloom.to_dict(),
            "objective_text": self._objective_text(),
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
        player.x, player.y = move_circle(
            x=player.x,
            y=player.y,
            radius=player.radius,
            delta_x=move_x * speed * dt,
            delta_y=move_y * speed * dt,
            world_width=self.map.world_width,
            world_height=self.map.world_height,
            collision_rects=self.map.collision_rects,
        )

        if self._pressed(player, "debug_down") and player.state == "alive":
            self._set_player_spirit(player)

        if player.state == "alive":
            self._try_collect_eggs(player)

        if self._pressed(player, "interact"):
            if not self._try_revive(player):
                self._try_restore_final_bloom(player)

    def _pressed(self, player: PlayerState, attr: str) -> bool:
        return getattr(player.input_state, attr) and not getattr(player.prev_input_state, attr)

    def _try_revive(self, player: PlayerState) -> bool:
        if player.state != "alive" or player.revival_eggs <= 0:
            return False
        if distance(player.x, player.y, self.shrine.x, self.shrine.y) > self.shrine.interact_radius:
            return False

        spirit_targets = [
            spirit
            for spirit in self.players.values()
            if spirit.state == "spirit"
            and distance(spirit.x, spirit.y, self.shrine.x, self.shrine.y) <= self.shrine.revive_radius
        ]
        if not spirit_targets:
            return False

        revived = min(
            spirit_targets,
            key=lambda spirit: distance(spirit.x, spirit.y, self.shrine.x, self.shrine.y),
        )
        player.revival_eggs -= 1
        revived.state = "alive"
        revived.health = revived.max_health // 2
        revived.x = self.shrine.x + 36.0
        revived.y = self.shrine.y
        return True

    def _try_restore_final_bloom(self, player: PlayerState) -> bool:
        if player.state != "alive" or player.revival_eggs <= 0:
            return False
        if distance(player.x, player.y, self.final_bloom.x, self.final_bloom.y) > self.final_bloom.interact_radius:
            return False

        player.revival_eggs -= 1
        self.final_bloom.restored = True
        return True

    def _update_enemy(self, dt: float) -> None:
        alive_targets = [player for player in self.players.values() if player.state == "alive"]
        if not alive_targets:
            return

        target = min(
            alive_targets,
            key=lambda player: distance(player.x, player.y, self.enemy.x, self.enemy.y),
        )
        delta_x = target.x - self.enemy.x
        delta_y = target.y - self.enemy.y
        magnitude = math.hypot(delta_x, delta_y)
        if magnitude > 0.0:
            self.enemy.x, self.enemy.y = move_circle(
                x=self.enemy.x,
                y=self.enemy.y,
                radius=self.enemy.radius,
                delta_x=(delta_x / magnitude) * self.enemy.speed * dt,
                delta_y=(delta_y / magnitude) * self.enemy.speed * dt,
                world_width=self.map.world_width,
                world_height=self.map.world_height,
                collision_rects=self.map.collision_rects,
            )

        if distance(target.x, target.y, self.enemy.x, self.enemy.y) <= target.radius + self.enemy.radius:
            target.health = max(0, int(target.health - self.enemy.damage_per_second * dt))
            if target.health <= 0:
                self._set_player_spirit(target)

    def _set_player_spirit(self, player: PlayerState) -> None:
        if player.state == "spirit":
            return
        if player.revival_eggs > 0:
            self._drop_carried_eggs(player)
            player.revival_eggs = 0
        player.state = "spirit"
        player.health = 0

    def _build_eggs_from_map(self) -> list[EggState]:
        return [
            EggState(
                spawn.spawn_id,
                spawn.x,
                spawn.y,
                egg_type=spawn.egg_type,
                radius=spawn.radius,
            )
            for spawn in self.map.egg_spawns
        ]

    def _reset_eggs(self) -> None:
        self.eggs = self._build_eggs_from_map()

    def _try_collect_eggs(self, player: PlayerState) -> None:
        for egg in self.eggs:
            if egg.collected:
                continue
            if distance(player.x, player.y, egg.x, egg.y) <= player.radius + egg.radius:
                egg.collected = True
                player.revival_eggs += 1

    def _drop_carried_eggs(self, player: PlayerState) -> None:
        collectible_eggs = [egg for egg in self.eggs if egg.collected]
        for egg in collectible_eggs[: player.revival_eggs]:
            egg.collected = False
            egg.x = round(player.x, 2)
            egg.y = round(player.y, 2)

    def _objective_text(self) -> str:
        if self.match_phase == "won":
            return "The Heart Garden bloomed. Press Enter as host to play again."
        if self.match_phase == "lost":
            return "All caretakers became spirits. Press Enter as host to retry."
        if any(player.state == "spirit" for player in self.players.values()):
            return "Carry the revival egg to the shrine to revive a teammate."
        if any(player.revival_eggs > 0 for player in self.players.values()):
            return "Carry the revival egg to the Heart Bloom to complete the map."
        if any(not egg.collected for egg in self.eggs):
            return "Gather the map's revival eggs before the bramble catches you."
        return "Bring your collected eggs to the Heart Bloom to complete the map."
