from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

from gameplay.collision import circle_overlaps_rect
from gameplay.map_types import CollisionRect


GridCell = tuple[int, int]


@dataclass(frozen=True)
class NavGrid:
    world_width: float
    world_height: float
    cell_size: int
    cols: int
    rows: int
    blocked: frozenset[GridCell]

    @classmethod
    def build(
        cls,
        *,
        world_width: float,
        world_height: float,
        cell_size: int,
        collision_rects: list[CollisionRect],
        agent_radius: float,
    ) -> "NavGrid":
        cols = max(1, int((world_width + cell_size - 1) // cell_size))
        rows = max(1, int((world_height + cell_size - 1) // cell_size))
        blocked: set[GridCell] = set()

        for row in range(rows):
            for col in range(cols):
                center_x, center_y = cls._cell_center_static(col, row, cell_size, world_width, world_height)
                if any(circle_overlaps_rect(center_x, center_y, agent_radius, rect) for rect in collision_rects):
                    blocked.add((col, row))

        return cls(
            world_width=world_width,
            world_height=world_height,
            cell_size=cell_size,
            cols=cols,
            rows=rows,
            blocked=frozenset(blocked),
        )

    @staticmethod
    def _cell_center_static(col: int, row: int, cell_size: int, world_width: float, world_height: float) -> tuple[float, float]:
        center_x = min(world_width - cell_size / 2, col * cell_size + cell_size / 2)
        center_y = min(world_height - cell_size / 2, row * cell_size + cell_size / 2)
        return center_x, center_y

    def point_to_cell(self, x: float, y: float) -> GridCell:
        col = max(0, min(self.cols - 1, int(x // self.cell_size)))
        row = max(0, min(self.rows - 1, int(y // self.cell_size)))
        return col, row

    def cell_center(self, cell: GridCell) -> tuple[float, float]:
        return self._cell_center_static(cell[0], cell[1], self.cell_size, self.world_width, self.world_height)

    def in_bounds(self, cell: GridCell) -> bool:
        return 0 <= cell[0] < self.cols and 0 <= cell[1] < self.rows

    def is_walkable(self, cell: GridCell, extra_blocked: set[GridCell] | frozenset[GridCell] | None = None) -> bool:
        return self.in_bounds(cell) and cell not in self.blocked and (extra_blocked is None or cell not in extra_blocked)

    def nearest_walkable(
        self,
        start: GridCell,
        extra_blocked: set[GridCell] | frozenset[GridCell] | None = None,
    ) -> GridCell | None:
        if self.is_walkable(start, extra_blocked):
            return start

        queue: deque[GridCell] = deque([start])
        visited = {start}
        while queue:
            cell = queue.popleft()
            for neighbor in self.neighbors(cell):
                if neighbor in visited:
                    continue
                if not self.in_bounds(neighbor):
                    continue
                if self.is_walkable(neighbor, extra_blocked):
                    return neighbor
                visited.add(neighbor)
                queue.append(neighbor)
        return None

    def neighbors(self, cell: GridCell) -> list[GridCell]:
        col, row = cell
        return [
            (col + 1, row),
            (col - 1, row),
            (col, row + 1),
            (col, row - 1),
        ]


def find_path(
    nav_grid: NavGrid,
    start: GridCell,
    goal: GridCell,
    *,
    extra_blocked: set[GridCell] | frozenset[GridCell] | None = None,
) -> list[GridCell]:
    walkable_start = nav_grid.nearest_walkable(start, extra_blocked)
    walkable_goal = nav_grid.nearest_walkable(goal, extra_blocked)
    if walkable_start is None or walkable_goal is None:
        return []
    if walkable_start == walkable_goal:
        return [walkable_start]

    frontier: list[tuple[int, GridCell]] = []
    heapq.heappush(frontier, (0, walkable_start))
    came_from: dict[GridCell, GridCell | None] = {walkable_start: None}
    cost_so_far: dict[GridCell, int] = {walkable_start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == walkable_goal:
            break

        for neighbor in nav_grid.neighbors(current):
            if not nav_grid.is_walkable(neighbor, extra_blocked):
                continue
            new_cost = cost_so_far[current] + 1
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + manhattan(neighbor, walkable_goal)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

    if walkable_goal not in came_from:
        return []

    path: list[GridCell] = []
    current: GridCell | None = walkable_goal
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def manhattan(a: GridCell, b: GridCell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
