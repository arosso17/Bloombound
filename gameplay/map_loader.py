from __future__ import annotations

import json
from pathlib import Path

from gameplay.map_types import (
    CollisionRect,
    DecorationDef,
    EggSpawnDef,
    EnemySpawnDef,
    FinalBloomDef,
    HazardZoneDef,
    MapDefinition,
    PatrolPointDef,
    RestorationZoneDef,
    ShrineDef,
    SpawnPoint,
    TraversalBarrierDef,
)


MAPS_DIR = Path(__file__).resolve().parent / "maps"


def load_map(map_id: str) -> MapDefinition:
    map_path = MAPS_DIR / f"{map_id}.json"
    payload = json.loads(map_path.read_text(encoding="utf-8"))

    player_spawns = [SpawnPoint(**spawn) for spawn in payload["player_spawns"]]
    collision_rects = [CollisionRect(**rect) for rect in payload["collision_rects"]]
    traversal_barriers = [TraversalBarrierDef(**barrier) for barrier in payload.get("traversal_barriers", [])]
    decorations = [DecorationDef(**decoration) for decoration in payload.get("decorations", [])]
    patrol_points = [PatrolPointDef(**point) for point in payload.get("patrol_points", [])]
    egg_spawns = [EggSpawnDef(**spawn) for spawn in payload["egg_spawns"]]
    restoration_zones = [RestorationZoneDef(**zone) for zone in payload.get("restoration_zones", [])]
    hazard_zones = [HazardZoneDef(**zone) for zone in payload.get("hazard_zones", [])]
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
        restoration_zones=restoration_zones,
        hazard_zones=hazard_zones,
        shrine=shrine,
        enemy_spawns=enemy_spawns,
        final_bloom=final_bloom,
    )
