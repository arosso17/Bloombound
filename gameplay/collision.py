from __future__ import annotations

from gameplay.map_types import CollisionRect


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def circle_overlaps_rect(x: float, y: float, radius: float, rect: CollisionRect) -> bool:
    nearest_x = clamp(x, rect.x, rect.x + rect.width)
    nearest_y = clamp(y, rect.y, rect.y + rect.height)
    delta_x = x - nearest_x
    delta_y = y - nearest_y
    return (delta_x * delta_x) + (delta_y * delta_y) < (radius * radius)


def move_circle(
    *,
    x: float,
    y: float,
    radius: float,
    delta_x: float,
    delta_y: float,
    world_width: float,
    world_height: float,
    collision_rects: list[CollisionRect],
) -> tuple[float, float]:
    next_x = clamp(x + delta_x, radius, world_width - radius)
    if any(circle_overlaps_rect(next_x, y, radius, rect) for rect in collision_rects):
        next_x = x

    next_y = clamp(y + delta_y, radius, world_height - radius)
    if any(circle_overlaps_rect(next_x, next_y, radius, rect) for rect in collision_rects):
        next_y = y

    return next_x, next_y
