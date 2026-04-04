from __future__ import annotations

import math

from gameplay.collision import circle_overlaps_rect, move_circle
from gameplay.entities import (
    EggState,
    EnemyState,
    FinalBloomState,
    HazardZoneState,
    PlayerInput,
    PlayerState,
    RestorationZoneState,
    ShrineState,
)
from gameplay.map_loader import load_map
from gameplay.map_types import CollisionRect, TraversalBarrierDef
from gameplay.navigation import NavGrid, find_path


ALIVE_SPEED = 230.0
SPIRIT_SPEED = 280.0
NAV_CELL_SIZE = 40
ENEMY_PATH_RECALC_TICKS = 8
ENEMY_WAYPOINT_REACHED_DISTANCE = 10.0
ENEMY_HOME_IDLE_DISTANCE = 8.0
ENEMY_PATROL_REACHED_DISTANCE = 12.0
DEFAULT_HAZARD_SLOW_MULTIPLIER = 1.0
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
    def __init__(self, expected_players: int = 2, map_id: str = "heart_garden_slice") -> None:
        self.map = load_map(map_id)
        self.tick = 0
        self.expected_players = max(1, expected_players)
        self.match_phase = "lobby"
        self.host_id = ""
        self.map_id = self.map.map_id
        self.players: dict[str, PlayerState] = {}
        self.nav_grid = NavGrid.build(
            world_width=self.map.world_width,
            world_height=self.map.world_height,
            cell_size=NAV_CELL_SIZE,
            collision_rects=self.map.collision_rects,
            agent_radius=18.0,
        )
        self.enemy_paths: dict[str, list[tuple[int, int]]] = {}
        self.enemy_path_targets: dict[str, tuple[int, int]] = {}
        self.enemy_patrol_routes = self._build_enemy_patrol_routes()
        self.eggs = self._build_eggs_from_map()
        self.restoration_zones = self._build_restoration_zones_from_map()
        self.hazard_zones = self._build_hazard_zones_from_map()
        shrine_def = self.map.shrine
        self.shrine = ShrineState(
            shrine_def.shrine_id,
            shrine_def.x,
            shrine_def.y,
            interact_radius=shrine_def.interact_radius,
            revive_radius=shrine_def.revive_radius,
        )
        self.enemies = self._build_enemies_from_map()
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
        self._reset_restoration_zones()
        self._reset_hazard_zones()
        self._reset_enemies()
        for index, player in enumerate(self.players.values()):
            spawn = self.map.player_spawns[index % len(self.map.player_spawns)]
            player.x = spawn.x
            player.y = spawn.y
            player.state = "alive"
            player.health = player.max_health
            player.revival_eggs = 0
            player.restoration_eggs = 0
            player.hazard_slow_multiplier = DEFAULT_HAZARD_SLOW_MULTIPLIER
            player.last_input_seq = 0
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
        seq = int(payload.get("seq", 0))
        if seq < player.last_input_seq:
            return
        player.last_input_seq = seq
        player.input_state = PlayerInput(
            move_x=float(payload.get("move_x", 0.0)),
            move_y=float(payload.get("move_y", 0.0)),
            interact=bool(payload.get("interact", False)),
            debug_down=bool(payload.get("debug_down", False)),
            seq=seq,
        )

    def update(self, dt: float) -> None:
        self.tick += 1
        self._sync_hazard_state()
        for player in self.players.values():
            self._update_player(player, dt)
        self._update_environment_effects(dt)
        self._update_enemies(dt)
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
            "restoration_zones": [zone.to_dict() for zone in self.restoration_zones],
            "hazard_zones": [zone.to_dict() for zone in self.hazard_zones],
            "shrine": self.shrine.to_dict(),
            "enemies": [enemy.to_dict() for enemy in self.enemies],
            "final_bloom": self.final_bloom.to_dict(),
            "objective_text": self._objective_text(),
        }

    def _player_snapshot(self, player: PlayerState) -> dict:
        payload = player.to_dict()
        payload["color"] = list(PLAYER_COLORS[player.color_index])
        payload["hazard_slow_multiplier"] = round(player.hazard_slow_multiplier, 2)
        return payload

    def _update_player(self, player: PlayerState, dt: float) -> None:
        move_x = max(-1.0, min(1.0, player.input_state.move_x))
        move_y = max(-1.0, min(1.0, player.input_state.move_y))
        magnitude = math.hypot(move_x, move_y)
        if magnitude > 1.0:
            move_x /= magnitude
            move_y /= magnitude

        player.hazard_slow_multiplier = self._hazard_slow_multiplier_at(player.x, player.y)
        speed = SPIRIT_SPEED if player.state == "spirit" else ALIVE_SPEED
        speed *= player.hazard_slow_multiplier
        player.x, player.y = move_circle(
            x=player.x,
            y=player.y,
            radius=player.radius,
            delta_x=move_x * speed * dt,
            delta_y=move_y * speed * dt,
            world_width=self.map.world_width,
            world_height=self.map.world_height,
            collision_rects=self._player_collision_rects(player),
        )

        if self._pressed(player, "debug_down") and player.state == "alive":
            self._set_player_spirit(player)

        if player.state == "alive":
            self._try_collect_eggs(player)

        if self._pressed(player, "interact"):
            if not self._try_revive(player):
                if not self._try_restore_zone(player):
                    self._try_restore_final_bloom(player)

    def _update_environment_effects(self, dt: float) -> None:
        for player in self.players.values():
            player.hazard_slow_multiplier = self._hazard_slow_multiplier_at(player.x, player.y)
            if player.state != "alive":
                continue

            hazard_damage = 0.0
            for hazard in self.hazard_zones:
                if not hazard.active:
                    continue
                if distance(player.x, player.y, hazard.x, hazard.y) <= player.radius + hazard.radius:
                    hazard_damage += hazard.damage_per_second * dt
            if hazard_damage > 0.0:
                player.health = max(0, int(player.health - hazard_damage))
                if player.health <= 0:
                    self._set_player_spirit(player)
                    continue

    def _update_enemies(self, dt: float) -> None:
        alive_targets = [player for player in self.players.values() if player.state == "alive"]
        if not self.enemies:
            return
        enemy_blocked_cells = self._restored_zone_blocked_cells()

        for enemy in self.enemies:
            goal_x, goal_y, target = self._enemy_goal(enemy, alive_targets)
            if (
                target is None
                and enemy.state == "return"
                and distance(enemy.x, enemy.y, enemy.home_x, enemy.home_y) <= ENEMY_HOME_IDLE_DISTANCE
            ):
                enemy.state = "patrol"
                self.enemy_paths[enemy.enemy_id] = []
                self.enemy_path_targets.pop(enemy.enemy_id, None)

            path = self._path_for_enemy(enemy, goal_x, goal_y, enemy_blocked_cells)
            waypoint_x, waypoint_y = self._enemy_waypoint(enemy, goal_x, goal_y, path)
            delta_x = waypoint_x - enemy.x
            delta_y = waypoint_y - enemy.y
            magnitude = math.hypot(delta_x, delta_y)
            if magnitude > 0.0:
                step_distance = min(enemy.speed * dt, magnitude)
                enemy.x, enemy.y = move_circle(
                    x=enemy.x,
                    y=enemy.y,
                    radius=enemy.radius,
                    delta_x=(delta_x / magnitude) * step_distance,
                    delta_y=(delta_y / magnitude) * step_distance,
                    world_width=self.map.world_width,
                    world_height=self.map.world_height,
                    collision_rects=self._enemy_collision_rects(),
                )
                enemy.x, enemy.y = self._keep_enemy_out_of_restored_zones(enemy.x, enemy.y, enemy.radius)

            if target is None:
                continue
            if distance(target.x, target.y, enemy.x, enemy.y) <= target.radius + enemy.radius:
                target.health = max(0, int(target.health - enemy.damage_per_second * dt))
                if target.health <= 0:
                    self._set_player_spirit(target)

    def _enemy_goal(
        self,
        enemy: EnemyState,
        alive_targets: list[PlayerState],
    ) -> tuple[float, float, PlayerState | None]:
        restored_zone = self._restored_zone_at(enemy.x, enemy.y, enemy.radius)
        if restored_zone is not None:
            enemy.state = "return"
            enemy.target_player_id = ""
            exit_x, exit_y = self._nearest_restored_zone_exit(restored_zone, enemy.x, enemy.y, enemy.radius)
            enemy.last_known_x = exit_x
            enemy.last_known_y = exit_y
            return exit_x, exit_y, None

        visible_targets = [
            player
            for player in alive_targets
            if distance(player.x, player.y, enemy.x, enemy.y) <= enemy.aggro_radius
            and distance(player.x, player.y, enemy.home_x, enemy.home_y) <= enemy.leash_radius
            and self._restored_zone_at(player.x, player.y, player.radius) is None
        ]
        if visible_targets:
            target = min(
                visible_targets,
                key=lambda player: distance(player.x, player.y, enemy.x, enemy.y),
            )
            enemy.state = "chase"
            enemy.target_player_id = target.player_id
            enemy.alert_ticks_remaining = enemy.alert_duration_ticks
            enemy.last_known_x = target.x
            enemy.last_known_y = target.y
            return target.x, target.y, target

        if enemy.alert_ticks_remaining > 0 and (enemy.state == "chase" or enemy.state == "alert"):
            enemy.state = "alert"
            enemy.alert_ticks_remaining -= 1
            return enemy.last_known_x, enemy.last_known_y, None

        enemy.target_player_id = ""
        patrol_route = self.enemy_patrol_routes.get(enemy.enemy_id, [])
        if patrol_route:
            goal_x, goal_y = patrol_route[enemy.patrol_index]
            if distance(enemy.x, enemy.y, goal_x, goal_y) <= ENEMY_PATROL_REACHED_DISTANCE:
                enemy.patrol_index = (enemy.patrol_index + 1) % len(patrol_route)
                goal_x, goal_y = patrol_route[enemy.patrol_index]
            enemy.state = "patrol"
            return goal_x, goal_y, None

        enemy.state = "return"
        return enemy.home_x, enemy.home_y, None

    def _path_for_enemy(
        self,
        enemy: EnemyState,
        goal_x: float,
        goal_y: float,
        extra_blocked: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        start_cell = self.nav_grid.point_to_cell(enemy.x, enemy.y)
        target_cell = self.nav_grid.point_to_cell(goal_x, goal_y)
        cached_target = self.enemy_path_targets.get(enemy.enemy_id)
        should_recompute = (
            enemy.enemy_id not in self.enemy_paths
            or cached_target != target_cell
            or self.tick % ENEMY_PATH_RECALC_TICKS == 0
        )
        if should_recompute:
            self.enemy_paths[enemy.enemy_id] = find_path(self.nav_grid, start_cell, target_cell, extra_blocked=extra_blocked)
            self.enemy_path_targets[enemy.enemy_id] = target_cell

        path = self.enemy_paths.get(enemy.enemy_id, [])
        if not path:
            return []

        if start_cell in path:
            path = path[path.index(start_cell) :]
        elif path[0] != start_cell:
            path = find_path(self.nav_grid, start_cell, target_cell, extra_blocked=extra_blocked)
            self.enemy_path_targets[enemy.enemy_id] = target_cell

        self.enemy_paths[enemy.enemy_id] = path
        return path

    def _enemy_waypoint(
        self,
        enemy: EnemyState,
        goal_x: float,
        goal_y: float,
        path: list[tuple[int, int]],
    ) -> tuple[float, float]:
        if not path:
            return goal_x, goal_y

        current_cell = self.nav_grid.point_to_cell(enemy.x, enemy.y)
        remaining_path = path
        if remaining_path[0] == current_cell:
            remaining_path = remaining_path[1:]

        while len(remaining_path) > 1:
            waypoint_x, waypoint_y = self.nav_grid.cell_center(remaining_path[0])
            if distance(enemy.x, enemy.y, waypoint_x, waypoint_y) > ENEMY_WAYPOINT_REACHED_DISTANCE:
                break
            remaining_path = remaining_path[1:]

        self.enemy_paths[enemy.enemy_id] = remaining_path
        if not remaining_path:
            return goal_x, goal_y

        waypoint_cell = remaining_path[0]
        waypoint_x, waypoint_y = self.nav_grid.cell_center(waypoint_cell)
        return waypoint_x, waypoint_y

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
        self._consume_carried_eggs(player, "revival", 1)
        revived.state = "alive"
        revived.health = revived.max_health // 2
        revived.x = self.shrine.x + 36.0
        revived.y = self.shrine.y
        return True

    def _try_restore_zone(self, player: PlayerState) -> bool:
        if player.state != "alive":
            return False
        for zone in self.restoration_zones:
            if zone.restored:
                continue
            if distance(player.x, player.y, zone.x, zone.y) > zone.interact_radius:
                continue
            if not self._has_eggs(player, zone.required_egg_type, zone.restore_cost):
                continue
            self._consume_carried_eggs(player, zone.required_egg_type, zone.restore_cost)
            zone.restored = True
            self._sync_hazard_state()
            self.enemy_paths = {}
            self.enemy_path_targets = {}
            return True
        return False

    def _try_restore_final_bloom(self, player: PlayerState) -> bool:
        bloom_egg_type = self._final_bloom_egg_type()
        if player.state != "alive" or not self._has_eggs(player, bloom_egg_type, 1):
            return False
        if distance(player.x, player.y, self.final_bloom.x, self.final_bloom.y) > self.final_bloom.interact_radius:
            return False
        if any(not zone.restored for zone in self.restoration_zones):
            return False

        self._consume_carried_eggs(player, bloom_egg_type, 1)
        self.final_bloom.restored = True
        return True

    def _set_player_spirit(self, player: PlayerState) -> None:
        if player.state == "spirit":
            return
        self._drop_carried_eggs(player)
        player.revival_eggs = 0
        player.restoration_eggs = 0
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

    def _build_restoration_zones_from_map(self) -> list[RestorationZoneState]:
        return [
            RestorationZoneState(
                zone_id=zone.zone_id,
                x=zone.x,
                y=zone.y,
                radius=zone.radius,
                interact_radius=zone.interact_radius,
                required_egg_type=zone.required_egg_type,
                restore_cost=zone.restore_cost,
            )
            for zone in self.map.restoration_zones
        ]

    def _build_hazard_zones_from_map(self) -> list[HazardZoneState]:
        return [
            HazardZoneState(
                zone_id=zone.zone_id,
                x=zone.x,
                y=zone.y,
                radius=zone.radius,
                damage_per_second=zone.damage_per_second,
                slow_multiplier=zone.slow_multiplier,
                cleared_by_zone_id=zone.cleared_by_zone_id,
            )
            for zone in self.map.hazard_zones
        ]

    def _build_enemy_patrol_routes(self) -> dict[str, list[tuple[float, float]]]:
        routes: dict[str, list[tuple[float, float]]] = {enemy.enemy_id: [] for enemy in self.map.enemy_spawns}
        for point in self.map.patrol_points:
            routes.setdefault(point.enemy_id, []).append((point.x, point.y))
        return routes

    def _build_enemies_from_map(self) -> list[EnemyState]:
        return [
            EnemyState(
                spawn.enemy_id,
                spawn.x,
                spawn.y,
                home_x=spawn.x,
                home_y=spawn.y,
                radius=spawn.radius,
                speed=spawn.speed,
                damage_per_second=spawn.damage_per_second,
                leash_radius=spawn.leash_radius,
                aggro_radius=spawn.aggro_radius,
                alert_duration_ticks=spawn.alert_duration_ticks,
                last_known_x=spawn.x,
                last_known_y=spawn.y,
            )
            for spawn in self.map.enemy_spawns
        ]

    def _reset_eggs(self) -> None:
        self.eggs = self._build_eggs_from_map()

    def _reset_restoration_zones(self) -> None:
        self.restoration_zones = self._build_restoration_zones_from_map()

    def _reset_hazard_zones(self) -> None:
        self.hazard_zones = self._build_hazard_zones_from_map()
        self._sync_hazard_state()

    def _reset_enemies(self) -> None:
        self.enemies = self._build_enemies_from_map()
        self.enemy_paths = {}
        self.enemy_path_targets = {}

    def _sync_hazard_state(self) -> None:
        restored_lookup = {zone.zone_id: zone.restored for zone in self.restoration_zones}
        for hazard in self.hazard_zones:
            if hazard.cleared_by_zone_id:
                hazard.active = not restored_lookup.get(hazard.cleared_by_zone_id, False)
            else:
                hazard.active = True

    def _try_collect_eggs(self, player: PlayerState) -> None:
        for egg in self.eggs:
            if egg.collected:
                continue
            if distance(player.x, player.y, egg.x, egg.y) <= player.radius + egg.radius:
                egg.collected = True
                egg.carrier_player_id = player.player_id
                if egg.egg_type == "restoration":
                    player.restoration_eggs += 1
                else:
                    player.revival_eggs += 1

    def _drop_carried_eggs(self, player: PlayerState) -> None:
        carried_eggs = [egg for egg in self.eggs if egg.collected and egg.carrier_player_id == player.player_id]
        for egg in carried_eggs:
            egg.collected = False
            egg.carrier_player_id = ""
            egg.x = round(player.x, 2)
            egg.y = round(player.y, 2)

    def _consume_carried_eggs(self, player: PlayerState, egg_type: str, amount: int) -> None:
        remaining = amount
        for egg in self.eggs:
            if remaining <= 0:
                break
            if not egg.collected or egg.carrier_player_id != player.player_id or egg.egg_type != egg_type:
                continue
            egg.carrier_player_id = ""
            remaining -= 1

        if egg_type == "restoration":
            player.restoration_eggs = max(0, player.restoration_eggs - amount)
        else:
            player.revival_eggs = max(0, player.revival_eggs - amount)

    def _has_eggs(self, player: PlayerState, egg_type: str, amount: int) -> bool:
        if egg_type == "restoration":
            return player.restoration_eggs >= amount
        return player.revival_eggs >= amount

    def _hazard_slow_multiplier_at(self, x: float, y: float) -> float:
        multiplier = DEFAULT_HAZARD_SLOW_MULTIPLIER
        for hazard in self.hazard_zones:
            if not hazard.active:
                continue
            if distance(x, y, hazard.x, hazard.y) <= hazard.radius:
                multiplier = min(multiplier, hazard.slow_multiplier)
        return multiplier

    def _barrier_is_active(self, barrier: TraversalBarrierDef) -> bool:
        if not barrier.cleared_by_zone_id:
            return True
        for zone in self.restoration_zones:
            if zone.zone_id == barrier.cleared_by_zone_id:
                return not zone.restored
        return True

    @staticmethod
    def _barrier_collision_rects(barriers: list[TraversalBarrierDef]) -> list[CollisionRect]:
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

    def _active_barriers(self) -> list[TraversalBarrierDef]:
        return [barrier for barrier in self.map.traversal_barriers if self._barrier_is_active(barrier)]

    def _player_collision_rects(self, player: PlayerState) -> list[CollisionRect]:
        active_barriers = self._active_barriers()
        if player.state == "spirit":
            active_barriers = [barrier for barrier in active_barriers if not barrier.spirit_passable]
        return self.map.collision_rects + self._barrier_collision_rects(active_barriers)

    def _enemy_collision_rects(self) -> list[CollisionRect]:
        return self.map.collision_rects + self._barrier_collision_rects(self._active_barriers())

    def _restored_zone_at(self, x: float, y: float, radius: float = 0.0) -> RestorationZoneState | None:
        for zone in self.restoration_zones:
            if not zone.restored:
                continue
            if distance(x, y, zone.x, zone.y) <= zone.radius + radius:
                return zone
        return None

    def _nearest_restored_zone_exit(
        self,
        zone: RestorationZoneState,
        x: float,
        y: float,
        radius: float,
    ) -> tuple[float, float]:
        delta_x = x - zone.x
        delta_y = y - zone.y
        magnitude = math.hypot(delta_x, delta_y)
        if magnitude < 0.001:
            delta_x = 1.0
            delta_y = 0.0
            magnitude = 1.0
        clearance = zone.radius + radius + 10.0
        exit_x = zone.x + (delta_x / magnitude) * clearance
        exit_y = zone.y + (delta_y / magnitude) * clearance
        return (
            max(radius, min(self.map.world_width - radius, exit_x)),
            max(radius, min(self.map.world_height - radius, exit_y)),
        )

    def _keep_enemy_out_of_restored_zones(self, x: float, y: float, radius: float) -> tuple[float, float]:
        zone = self._restored_zone_at(x, y, radius)
        if zone is None:
            return x, y
        return self._nearest_restored_zone_exit(zone, x, y, radius)

    def _restored_zone_blocked_cells(self) -> set[tuple[int, int]]:
        blocked: set[tuple[int, int]] = set()
        for zone in self.restoration_zones:
            if not zone.restored:
                continue
            min_col = max(0, int((zone.x - zone.radius) // self.nav_grid.cell_size) - 1)
            max_col = min(self.nav_grid.cols - 1, int((zone.x + zone.radius) // self.nav_grid.cell_size) + 1)
            min_row = max(0, int((zone.y - zone.radius) // self.nav_grid.cell_size) - 1)
            max_row = min(self.nav_grid.rows - 1, int((zone.y + zone.radius) // self.nav_grid.cell_size) + 1)
            for col in range(min_col, max_col + 1):
                for row in range(min_row, max_row + 1):
                    center_x, center_y = self.nav_grid.cell_center((col, row))
                    if distance(center_x, center_y, zone.x, zone.y) <= zone.radius:
                        blocked.add((col, row))
        for barrier_rect in self._barrier_collision_rects(self._active_barriers()):
            min_col = max(0, int(barrier_rect.x // self.nav_grid.cell_size) - 1)
            max_col = min(self.nav_grid.cols - 1, int((barrier_rect.x + barrier_rect.width) // self.nav_grid.cell_size) + 1)
            min_row = max(0, int(barrier_rect.y // self.nav_grid.cell_size) - 1)
            max_row = min(self.nav_grid.rows - 1, int((barrier_rect.y + barrier_rect.height) // self.nav_grid.cell_size) + 1)
            for col in range(min_col, max_col + 1):
                for row in range(min_row, max_row + 1):
                    center_x, center_y = self.nav_grid.cell_center((col, row))
                    if circle_overlaps_rect(center_x, center_y, 18.0, barrier_rect):
                        blocked.add((col, row))
        return blocked

    def _objective_text(self) -> str:
        if self.match_phase == "won":
            return "The Heart Garden bloomed. Press Enter as host to play again."
        if self.match_phase == "lost":
            return "All caretakers became spirits. Press Enter as host to retry."
        if any(player.state == "spirit" for player in self.players.values()):
            return "Use a revival egg at the shrine to bring back a teammate."
        unrestored_count = sum(1 for zone in self.restoration_zones if not zone.restored)
        if unrestored_count > 0:
            return f"Restore the garden circles with restoration eggs. Zones left: {unrestored_count}."
        if any(not egg.collected for egg in self.eggs):
            return f"Gather the remaining eggs and bring a {self._final_bloom_egg_type()} egg to the Heart Bloom."
        return f"All zones are restored. Bring a {self._final_bloom_egg_type()} egg to the Heart Bloom."

    def _final_bloom_egg_type(self) -> str:
        if self.restoration_zones or any(egg.egg_type == "restoration" for egg in self.eggs):
            return "restoration"
        return "revival"
