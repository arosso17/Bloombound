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
class SpiritPickupDef:
    pickup_id: str
    x: float
    y: float
    radius: int = 12


@dataclass(frozen=True)
class PatrolPointDef:
    point_id: str
    enemy_id: str
    x: float
    y: float


@dataclass(frozen=True)
class DecorationDef:
    decoration_id: str
    asset_id: str
    x: float
    y: float
    scale: float = 1.0
    restored_by_zone_id: str = ""


@dataclass(frozen=True)
class TraversalBarrierDef:
    barrier_id: str
    x: float
    y: float
    width: float
    height: float
    cleared_by_zone_id: str = ""
    spirit_passable: bool = False


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
    aggro_radius: float = 220.0
    alert_duration_ticks: int = 80


@dataclass(frozen=True)
class RestorationZoneDef:
    zone_id: str
    x: float
    y: float
    radius: float = 72.0
    interact_radius: float = 84.0
    required_egg_type: str = "restoration"
    restore_cost: int = 1


@dataclass(frozen=True)
class HazardZoneDef:
    zone_id: str
    x: float
    y: float
    radius: float = 84.0
    damage_per_second: float = 18.0
    slow_multiplier: float = 0.72
    cleared_by_zone_id: str = ""


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
    traversal_barriers: list[TraversalBarrierDef]
    decorations: list[DecorationDef]
    patrol_points: list[PatrolPointDef]
    egg_spawns: list[EggSpawnDef]
    spirit_pickups: list[SpiritPickupDef]
    restoration_zones: list[RestorationZoneDef]
    hazard_zones: list[HazardZoneDef]
    shrine: ShrineDef
    enemy_spawns: list[EnemySpawnDef]
    final_bloom: FinalBloomDef
