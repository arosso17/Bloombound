from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame as pg


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "visuals"


@dataclass(frozen=True)
class VisualShape:
    kind: str
    x: float
    y: float
    color_key: str | None = None
    rotation_degrees: float = 0.0
    width: float = 0.0
    height: float = 0.0
    radius: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    fill: tuple[int, ...] | None = None
    outline: tuple[int, ...] | None = None
    outline_width: int = 0


@dataclass(frozen=True)
class VisualAsset:
    asset_id: str
    width: int
    height: int
    shapes: list[VisualShape]


def _parse_color(value: list[int] | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    return tuple(int(channel) for channel in value)


def _asset_path(asset_id: str) -> Path:
    return ASSETS_DIR / f"{asset_id}.json"


def visual_asset_from_payload(payload: dict) -> VisualAsset:
    shapes = [
        VisualShape(
            kind=shape["kind"],
            x=float(shape.get("x", 0.0)),
            y=float(shape.get("y", 0.0)),
            color_key=shape.get("color_key"),
            rotation_degrees=float(shape.get("rotation_degrees", 0.0)),
            width=float(shape.get("width", 0.0)),
            height=float(shape.get("height", 0.0)),
            radius=float(shape.get("radius", 0.0)),
            x2=float(shape.get("x2", 0.0)),
            y2=float(shape.get("y2", 0.0)),
            fill=_parse_color(shape.get("fill")),
            outline=_parse_color(shape.get("outline")),
            outline_width=int(shape.get("outline_width", 0)),
        )
        for shape in payload["shapes"]
    ]
    return VisualAsset(
        asset_id=payload["asset_id"],
        width=int(payload["canvas"]["width"]),
        height=int(payload["canvas"]["height"]),
        shapes=shapes,
    )


@lru_cache(maxsize=64)
def load_visual_asset(asset_id: str) -> VisualAsset:
    payload = json.loads(_asset_path(asset_id).read_text(encoding="utf-8"))
    return visual_asset_from_payload(payload)


def render_visual_asset_to_surface(
    asset: VisualAsset,
    *,
    scale: float = 1.0,
    padding: int = 0,
    background_color: tuple[int, ...] | None = None,
    color_overrides: dict[str, tuple[int, ...]] | None = None,
) -> pg.Surface:
    width = max(1, int(asset.width * scale))
    height = max(1, int(asset.height * scale))
    surface = pg.Surface((width + padding * 2, height + padding * 2), pg.SRCALPHA)
    if background_color is not None:
        surface.fill(background_color)
    for shape in asset.shapes:
        _draw_shape(surface, shape, scale, color_overrides=color_overrides, offset_x=padding, offset_y=padding)
    return surface


def render_visual_asset(
    target: pg.Surface,
    asset: VisualAsset,
    center: tuple[int, int],
    *,
    scale: float = 1.0,
    color_overrides: dict[str, tuple[int, ...]] | None = None,
) -> None:
    width = max(1, int(asset.width * scale))
    height = max(1, int(asset.height * scale))
    asset_surface = render_visual_asset_to_surface(asset, scale=scale, color_overrides=color_overrides)
    top_left = (int(center[0] - width / 2), int(center[1] - height / 2))
    target.blit(asset_surface, top_left)


def _draw_shape(
    surface: pg.Surface,
    shape: VisualShape,
    scale: float,
    *,
    color_overrides: dict[str, tuple[int, ...]] | None = None,
    offset_x: int = 0,
    offset_y: int = 0,
) -> None:
    fill_color = shape.fill
    if color_overrides is not None and shape.color_key is not None:
        fill_color = color_overrides.get(shape.color_key, fill_color)

    if shape.kind == "circle":
        center = (int(shape.x * scale) + offset_x, int(shape.y * scale) + offset_y)
        radius = max(1, int(shape.radius * scale))
        if fill_color is not None:
            pg.draw.circle(surface, fill_color, center, radius)
        if shape.outline is not None and shape.outline_width > 0:
            pg.draw.circle(surface, shape.outline, center, radius, width=max(1, int(shape.outline_width * scale)))
        return

    if shape.kind in {"rect", "ellipse"}:
        rect = pg.Rect(
            int(shape.x * scale) + offset_x,
            int(shape.y * scale) + offset_y,
            max(1, int(shape.width * scale)),
            max(1, int(shape.height * scale)),
        )
        outline_width = max(1, int(shape.outline_width * scale)) if shape.outline is not None and shape.outline_width > 0 else 0
        if abs(shape.rotation_degrees) < 0.01:
            if fill_color is not None:
                if shape.kind == "rect":
                    pg.draw.rect(surface, fill_color, rect, border_radius=min(16, rect.width // 4, rect.height // 4))
                else:
                    pg.draw.ellipse(surface, fill_color, rect)
            if shape.outline is not None and outline_width > 0:
                if shape.kind == "rect":
                    pg.draw.rect(
                        surface,
                        shape.outline,
                        rect,
                        width=outline_width,
                        border_radius=min(16, rect.width // 4, rect.height // 4),
                    )
                else:
                    pg.draw.ellipse(surface, shape.outline, rect, width=outline_width)
            return

        padding = max(4, outline_width + 4)
        temp_surface = pg.Surface((rect.width + padding * 2, rect.height + padding * 2), pg.SRCALPHA)
        local_rect = pg.Rect(padding, padding, rect.width, rect.height)
        if fill_color is not None:
            if shape.kind == "rect":
                pg.draw.rect(
                    temp_surface,
                    fill_color,
                    local_rect,
                    border_radius=min(16, local_rect.width // 4, local_rect.height // 4),
                )
            else:
                pg.draw.ellipse(temp_surface, fill_color, local_rect)
        if shape.outline is not None and outline_width > 0:
            if shape.kind == "rect":
                pg.draw.rect(
                    temp_surface,
                    shape.outline,
                    local_rect,
                    width=outline_width,
                    border_radius=min(16, local_rect.width // 4, local_rect.height // 4),
                )
            else:
                pg.draw.ellipse(temp_surface, shape.outline, local_rect, width=outline_width)
        rotated_surface = pg.transform.rotozoom(temp_surface, -shape.rotation_degrees, 1.0)
        rotated_rect = rotated_surface.get_rect(center=rect.center)
        surface.blit(rotated_surface, rotated_rect)
        return

    if shape.kind == "line" and shape.outline is not None:
        start = (float(shape.x * scale), float(shape.y * scale))
        end = (float(shape.x2 * scale), float(shape.y2 * scale))
        start = (start[0] + offset_x, start[1] + offset_y)
        end = (end[0] + offset_x, end[1] + offset_y)
        if abs(shape.rotation_degrees) >= 0.01:
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            start = _rotate_point(start[0], start[1], mid_x, mid_y, shape.rotation_degrees)
            end = _rotate_point(end[0], end[1], mid_x, mid_y, shape.rotation_degrees)
        pg.draw.line(surface, shape.outline, start, end, width=max(1, int(shape.outline_width * scale)))


def _rotate_point(x: float, y: float, center_x: float, center_y: float, rotation_degrees: float) -> tuple[float, float]:
    radians = math.radians(rotation_degrees)
    cos_theta = math.cos(radians)
    sin_theta = math.sin(radians)
    rel_x = x - center_x
    rel_y = y - center_y
    return (
        center_x + rel_x * cos_theta - rel_y * sin_theta,
        center_y + rel_x * sin_theta + rel_y * cos_theta,
    )
