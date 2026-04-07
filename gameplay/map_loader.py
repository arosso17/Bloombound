from __future__ import annotations

import json
from pathlib import Path

from gameplay.map_types import (
    BramblePatchDef,
    CollisionRect,
    DecorationDef,
    EggSpawnDef,
    EnemySpawnDef,
    FinalBloomDef,
    MapDefinition,
    PatrolPointDef,
    RestorationShrineDef,
    ShrineDef,
    SpawnPoint,
    SpiritPickupDef,
    TraversalBarrierDef,
)


MAPS_DIR = Path(__file__).resolve().parent / "maps"


def _restoration_shrines_from_payload(payload: dict) -> list[RestorationShrineDef]:
    shrine_payloads = payload.get("restoration_shrines")
    if shrine_payloads is not None:
        return [RestorationShrineDef(**shrine) for shrine in shrine_payloads]

    legacy_zone_payloads = payload.get("restoration_zones", [])
    return [
        RestorationShrineDef(
            shrine_id=zone["zone_id"],
            x=float(zone["x"]),
            y=float(zone["y"]),
            interact_radius=float(zone.get("interact_radius", 84.0)),
            restore_radius=float(zone.get("radius", 72.0)),
            required_egg_type=str(zone.get("required_egg_type", "restoration")),
            restore_cost=int(zone.get("restore_cost", 1)),
        )
        for zone in legacy_zone_payloads
    ]


def _bramble_patches_from_payload(payload: dict) -> list[BramblePatchDef]:
    patch_payloads = payload.get("bramble_patches")
    if patch_payloads is not None:
        return [BramblePatchDef(**patch) for patch in patch_payloads]

    legacy_hazard_payloads = payload.get("hazard_zones", [])
    return [
        BramblePatchDef(
            patch_id=zone["zone_id"],
            x=float(zone["x"]),
            y=float(zone["y"]),
            radius=float(zone.get("radius", 84.0)),
            damage_per_second=float(zone.get("damage_per_second", 18.0)),
            slow_multiplier=float(zone.get("slow_multiplier", 0.72)),
            cleared_by_shrine_id=str(zone.get("cleared_by_zone_id", "")),
        )
        for zone in legacy_hazard_payloads
    ]


def load_map(map_id: str) -> MapDefinition:
    map_path = MAPS_DIR / f"{map_id}.json"
    payload = json.loads(map_path.read_text(encoding="utf-8"))

    player_spawns = [SpawnPoint(**spawn) for spawn in payload["player_spawns"]]
    collision_rects = [CollisionRect(**rect) for rect in payload["collision_rects"]]
    traversal_barriers = [TraversalBarrierDef(**barrier) for barrier in payload.get("traversal_barriers", [])]
    decorations = [DecorationDef(**decoration) for decoration in payload.get("decorations", [])]
    patrol_points = [PatrolPointDef(**point) for point in payload.get("patrol_points", [])]
    egg_spawns = [EggSpawnDef(**spawn) for spawn in payload["egg_spawns"]]
    spirit_pickups = [SpiritPickupDef(**pickup) for pickup in payload.get("spirit_pickups", [])]
    restoration_shrines = _restoration_shrines_from_payload(payload)
    bramble_patches = _bramble_patches_from_payload(payload)
    enemy_spawns = [EnemySpawnDef(**spawn) for spawn in payload["enemy_spawns"]]
    shrine = ShrineDef(**payload["shrine"])
    final_bloom = FinalBloomDef(**payload["final_bloom"])

    return MapDefinition(
        map_id=payload["map_id"],
        name=payload["name"],
        world_width=int(payload["world"]["width"]),
        world_height=int(payload["world"]["height"]),
        player_spawns=player_spawns,
        collision_rects=collision_rects,
        traversal_barriers=traversal_barriers,
        decorations=decorations,
        patrol_points=patrol_points,
        egg_spawns=egg_spawns,
        spirit_pickups=spirit_pickups,
        restoration_shrines=restoration_shrines,
        bramble_patches=bramble_patches,
        shrine=shrine,
        enemy_spawns=enemy_spawns,
        final_bloom=final_bloom,
    )
