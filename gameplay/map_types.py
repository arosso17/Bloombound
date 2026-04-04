from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CollisionRect:
    rect_id: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class SpawnPoint:
    x: float
    y: float


@dataclass(frozen=True)
class EggSpawnDef:
    spawn_id: str
    x: float
    y: float
    egg_type: str = "revival"
    radius: int = 12


@dataclass(frozen=True)
class ShrineDef:
    shrine_id: str
    x: float
    y: float
    interact_radius: int = 52
    revive_radius: int = 70


@dataclass(frozen=True)
class EnemySpawnDef:
    enemy_id: str
    x: float
    y: float
    radius: int = 18
    speed: float = 150.0
    damage_per_second: float = 40.0
    leash_radius: float = 260.0


@dataclass(frozen=True)
class FinalBloomDef:
    bloom_id: str
    x: float
    y: float
    radius: int = 24
    interact_radius: int = 68


@dataclass(frozen=True)
class MapDefinition:
    map_id: str
    name: str
    world_width: int
    world_height: int
    player_spawns: list[SpawnPoint]
    collision_rects: list[CollisionRect]
    egg_spawns: list[EggSpawnDef]
    shrine: ShrineDef
    enemy_spawns: list[EnemySpawnDef]
    final_bloom: FinalBloomDef
