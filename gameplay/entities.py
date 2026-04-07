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
    spirit_seeds: int = 0
    radius: int = 16
    hazard_slow_multiplier: float = 1.0
    last_input_seq: int = 0
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
            "spirit_seeds": self.spirit_seeds,
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
class SpiritPickupState:
    pickup_id: str
    x: float
    y: float
    collected: bool = False
    carrier_player_id: str = ""
    radius: int = 12

    def to_dict(self) -> dict:
        return {
            "id": self.pickup_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "collected": self.collected,
            "radius": self.radius,
        }


@dataclass
class ShrineState:
    shrine_id: str
    x: float
    y: float
    interact_radius: int = 52
    revive_radius: int = 70
    stored_revival_eggs: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.shrine_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "interact_radius": self.interact_radius,
            "revive_radius": self.revive_radius,
            "stored_revival_eggs": self.stored_revival_eggs,
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
            "home_x": round(self.home_x, 2),
            "home_y": round(self.home_y, 2),
            "radius": self.radius,
            "state": self.state,
        }


@dataclass
class RestorationShrineState:
    shrine_id: str
    x: float
    y: float
    interact_radius: float = 84.0
    restore_radius: float = 72.0
    required_egg_type: str = "restoration"
    restore_cost: int = 1
    restored: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.shrine_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "interact_radius": round(self.interact_radius, 2),
            "restore_radius": round(self.restore_radius, 2),
            "required_egg_type": self.required_egg_type,
            "restore_cost": self.restore_cost,
            "restored": self.restored,
        }


@dataclass
class BramblePatchState:
    patch_id: str
    x: float
    y: float
    rotation_degrees: float = 0.0
    radius: float = 84.0
    damage_per_second: float = 18.0
    slow_multiplier: float = 0.72
    cleared_by_shrine_id: str = ""
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.patch_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "rotation_degrees": round(self.rotation_degrees, 2),
            "radius": round(self.radius, 2),
            "damage_per_second": round(self.damage_per_second, 2),
            "slow_multiplier": round(self.slow_multiplier, 2),
            "cleared_by_shrine_id": self.cleared_by_shrine_id,
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
    channel_duration_seconds: float = 3.0
    channel_player_id: str = ""
    channel_progress_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.bloom_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": self.radius,
            "interact_radius": self.interact_radius,
            "restored": self.restored,
            "channel_duration_seconds": round(self.channel_duration_seconds, 2),
            "channel_player_id": self.channel_player_id,
            "channel_progress_seconds": round(self.channel_progress_seconds, 2),
        }
