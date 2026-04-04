from dataclasses import dataclass, field


@dataclass
class PlayerInput:
    move_x: float = 0.0
    move_y: float = 0.0
    interact: bool = False
    debug_down: bool = False
    seq: int = 0


@dataclass
class PlayerState:
    player_id: str
    name: str
    x: float
    y: float
    color_index: int
    state: str = "alive"
    health: int = 100
    max_health: int = 100
    revival_eggs: int = 0
    restoration_eggs: int = 0
    radius: int = 16
    hazard_slow_multiplier: float = 1.0
    input_state: PlayerInput = field(default_factory=PlayerInput)
    prev_input_state: PlayerInput = field(default_factory=PlayerInput)

    def to_dict(self) -> dict:
        return {
            "id": self.player_id,
            "name": self.name,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "color_index": self.color_index,
            "state": self.state,
            "health": self.health,
            "max_health": self.max_health,
            "revival_eggs": self.revival_eggs,
            "restoration_eggs": self.restoration_eggs,
            "radius": self.radius,
        }


@dataclass
class EggState:
    egg_id: str
    x: float
    y: float
    collected: bool = False
    carrier_player_id: str = ""
    egg_type: str = "revival"
    radius: int = 12

    def to_dict(self) -> dict:
        return {
            "id": self.egg_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "collected": self.collected,
            "egg_type": self.egg_type,
            "radius": self.radius,
        }


@dataclass
class ShrineState:
    shrine_id: str
    x: float
    y: float
    interact_radius: int = 52
    revive_radius: int = 70

    def to_dict(self) -> dict:
        return {
            "id": self.shrine_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "interact_radius": self.interact_radius,
            "revive_radius": self.revive_radius,
        }


@dataclass
class EnemyState:
    enemy_id: str
    x: float
    y: float
    home_x: float
    home_y: float
    radius: int = 18
    speed: float = 150.0
    damage_per_second: float = 40.0
    leash_radius: float = 260.0
    aggro_radius: float = 220.0
    alert_duration_ticks: int = 80
    state: str = "patrol"
    target_player_id: str = ""
    alert_ticks_remaining: int = 0
    patrol_index: int = 0
    last_known_x: float = 0.0
    last_known_y: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.enemy_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": self.radius,
            "state": self.state,
        }


@dataclass
class RestorationZoneState:
    zone_id: str
    x: float
    y: float
    radius: float = 72.0
    interact_radius: float = 84.0
    required_egg_type: str = "restoration"
    restore_cost: int = 1
    restored: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.zone_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": round(self.radius, 2),
            "interact_radius": round(self.interact_radius, 2),
            "required_egg_type": self.required_egg_type,
            "restore_cost": self.restore_cost,
            "restored": self.restored,
        }


@dataclass
class HazardZoneState:
    zone_id: str
    x: float
    y: float
    radius: float = 84.0
    damage_per_second: float = 18.0
    slow_multiplier: float = 0.72
    cleared_by_zone_id: str = ""
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.zone_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": round(self.radius, 2),
            "damage_per_second": round(self.damage_per_second, 2),
            "slow_multiplier": round(self.slow_multiplier, 2),
            "cleared_by_zone_id": self.cleared_by_zone_id,
            "active": self.active,
        }


@dataclass
class FinalBloomState:
    bloom_id: str
    x: float
    y: float
    radius: int = 24
    interact_radius: int = 68
    restored: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.bloom_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": self.radius,
            "interact_radius": self.interact_radius,
            "restored": self.restored,
        }
