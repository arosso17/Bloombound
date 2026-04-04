from __future__ import annotations

import json
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


@lru_cache(maxsize=64)
def load_visual_asset(asset_id: str) -> VisualAsset:
    payload = json.loads(_asset_path(asset_id).read_text(encoding="utf-8"))
    shapes = [
        VisualShape(
            kind=shape["kind"],
            x=float(shape.get("x", 0.0)),
            y=float(shape.get("y", 0.0)),
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


def render_visual_asset(
    target: pg.Surface,
    asset: VisualAsset,
    center: tuple[int, int],
    *,
    scale: float = 1.0,
) -> None:
    width = max(1, int(asset.width * scale))
    height = max(1, int(asset.height * scale))
    asset_surface = pg.Surface((width, height), pg.SRCALPHA)

    for shape in asset.shapes:
        _draw_shape(asset_surface, shape, scale)

    top_left = (int(center[0] - width / 2), int(center[1] - height / 2))
    target.blit(asset_surface, top_left)


def _draw_shape(surface: pg.Surface, shape: VisualShape, scale: float) -> None:
    if shape.kind == "circle":
        center = (int(shape.x * scale), int(shape.y * scale))
        radius = max(1, int(shape.radius * scale))
        if shape.fill is not None:
            pg.draw.circle(surface, shape.fill, center, radius)
        if shape.outline is not None and shape.outline_width > 0:
            pg.draw.circle(surface, shape.outline, center, radius, width=max(1, int(shape.outline_width * scale)))
        return

    if shape.kind in {"rect", "ellipse"}:
        rect = pg.Rect(
            int(shape.x * scale),
            int(shape.y * scale),
            max(1, int(shape.width * scale)),
            max(1, int(shape.height * scale)),
        )
        if shape.fill is not None:
            if shape.kind == "rect":
                pg.draw.rect(surface, shape.fill, rect, border_radius=min(16, rect.width // 4, rect.height // 4))
            else:
                pg.draw.ellipse(surface, shape.fill, rect)
        if shape.outline is not None and shape.outline_width > 0:
            outline_width = max(1, int(shape.outline_width * scale))
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

    if shape.kind == "line" and shape.outline is not None:
        start = (int(shape.x * scale), int(shape.y * scale))
        end = (int(shape.x2 * scale), int(shape.y2 * scale))
        pg.draw.line(surface, shape.outline, start, end, width=max(1, int(shape.outline_width * scale)))
