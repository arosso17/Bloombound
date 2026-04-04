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
    radius: int = 16
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
            "radius": self.radius,
        }


@dataclass
class EggState:
    egg_id: str
    x: float
    y: float
    collected: bool = False
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

    def to_dict(self) -> dict:
        return {
            "id": self.enemy_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": self.radius,
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
