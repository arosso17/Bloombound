from __future__ import annotations

import json
from pathlib import Path

from gameplay.map_types import (
    CollisionRect,
    DecorationDef,
    EggSpawnDef,
    EnemySpawnDef,
    FinalBloomDef,
    MapDefinition,
    ShrineDef,
    SpawnPoint,
)


MAPS_DIR = Path(__file__).resolve().parent / "maps"


def load_map(map_id: str) -> MapDefinition:
    map_path = MAPS_DIR / f"{map_id}.json"
    payload = json.loads(map_path.read_text(encoding="utf-8"))

    player_spawns = [SpawnPoint(**spawn) for spawn in payload["player_spawns"]]
    collision_rects = [CollisionRect(**rect) for rect in payload["collision_rects"]]
    decorations = [DecorationDef(**decoration) for decoration in payload.get("decorations", [])]
    egg_spawns = [EggSpawnDef(**spawn) for spawn in payload["egg_spawns"]]
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
        decorations=decorations,
        egg_spawns=egg_spawns,
        shrine=shrine,
        enemy_spawns=enemy_spawns,
        final_bloom=final_bloom,
    )
