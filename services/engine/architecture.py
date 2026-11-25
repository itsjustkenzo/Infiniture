"""Build the floor, wall edges and door approaches before any furniture is selected."""

import math
import random
from dataclasses import dataclass

from .geometry import EPS, box_cells, contains_floor, navigation, neighbors, point_box
from .models import Cell, Door, GeometryOptions, GeometryPreferences, Point, RoomGeometry, Wall

DIRECTIONS = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}
CellKey = tuple[int, int]


class GeometryFailure(Exception):
    def __init__(self, code: str, message: str):
        self.reason = {'code': code, 'message': message, 'stage': 'geometry'}
        super().__init__(message)


@dataclass(frozen=True)
class Architecture:
    width: int
    height: int
    geometry: RoomGeometry
    floor: frozenset[CellKey]
    walls: frozenset[tuple[int, int, str]]
    circulation: frozenset[CellKey]

    @property
    def entrance(self):
        return self.geometry.doors[0].approach

    @property
    def exit(self):
        return self.geometry.doors[-1].approach

    def touches_wall(self, box, side):
        x, y, width, height = box
        if side in ('north', 'south'):
            edge = y if side == 'north' else y + height
            if abs(edge - round(edge)) > EPS:
                return False
            row = round(edge) - (side == 'south')
            return all((i, row, side) in self.walls for i in range(math.floor(x + EPS), math.ceil(x + width - EPS)))
        edge = x if side == 'west' else x + width
        if abs(edge - round(edge)) > EPS:
            return False
        column = round(edge) - (side == 'east')
        return all((column, j, side) in self.walls for j in range(math.floor(y + EPS), math.ceil(y + height - EPS)))


def component(start, floor):
    seen = {start}
    queue = [start]
    for cell in queue:
        for next_cell in neighbors(cell):
            if next_cell in floor and next_cell not in seen:
                seen.add(next_cell)
                queue.append(next_cell)
    return seen


def _dimensions(width, height, shape, options, preferences, rng):
    def dimension(preferred, lower, upper):
        if not options.variableSize:
            return max(lower, min(upper, preferred))
        center = max(lower, min(upper, preferred))
        choices = list(range(max(lower, center - 4), min(upper, center + 4) + 1))
        return rng.choice(choices)

    if shape == 'square':
        low = max(preferences.minWidth, preferences.minHeight)
        high = min(preferences.maxWidth, preferences.maxHeight)
        if low > high:
            raise GeometryFailure('square_dimensions', 'Room width and height limits have no common square size.')
        size = dimension(round((width + height) / 2), low, high)
        return size, size
    return (dimension(width, preferences.minWidth, preferences.maxWidth),
            dimension(height, preferences.minHeight, preferences.maxHeight))


def _outer_floor(width, height, shape, rng):
    w, h = width - 2, height - 3
    local = {(x, y) for x in range(w) for y in range(h)}
    if shape == 'l_shape':
        cw, ch = max(2, round(w * rng.uniform(.28, .43))), max(2, round(h * rng.uniform(.28, .43)))
        corner = rng.randrange(4)
        local.difference_update((x, y) for x in range(w) for y in range(h)
                                if (x < cw if corner & 1 else x >= w-cw)
                                and (y < ch if corner & 2 else y >= h-ch))
    elif shape == 'alcove':
        # A recessed rear bay, with a wide opening onto the rest of the room.
        depth = max(2, min(h // 3, rng.randrange(2, 6)))
        outset = rng.randint(1, max(1, w // 4))
        span = max(4, round(w * rng.uniform(.43, .65)))
        local.difference_update((x, y) for x in range(w) for y in range(depth)
                                if not outset <= x < outset + span)
    elif shape == 'orthogonal':
        # Two independent edge notches, leaving room for a clear central passage.
        for left in (True, False):
            depth = rng.randint(2, max(2, w // 4))
            start = rng.randint(1, max(1, h // 2))
            length = rng.randint(2, max(2, h // 3))
            local.difference_update((x, y) for x in range(w) for y in range(start, start + length)
                                    if (x < depth if left else x >= w-depth))
    return {(x + 1, y + 2) for x, y in local}


def _partition(floor, height, rng):
    rows = list(range(max(5, height // 3), min(height - 4, height * 2 // 3) + 1))
    rng.shuffle(rows)
    for row in rows:
        xs = sorted(x for x, y in floor if y == row)
        if len(xs) < 8:
            continue
        length = rng.randint(2, min(6, len(xs) // 3))
        chosen = xs[:length] if rng.random() < .5 else xs[-length:]
        wall = {(x, row) for x in chosen}
        if all((x, row-1) in floor and (x, row+1) in floor for x in chosen):
            rest = floor - wall
            if len(component(min(rest), rest)) == len(rest):
                return wall
    raise GeometryFailure('partition_capacity', 'The floor has no suitable location for a partition with a bypass.')


def _doors(floor, exterior_walls, width, height, count, size, rng):
    choices = {}
    for x, y, side in sorted(exterior_walls):
        dx, dy = DIRECTIONS[side]
        if (x-dy, y-dx, side) not in exterior_walls or (x+dy, y+dx, side) not in exterior_walls:
            continue
        px, py = x + .5, y + .5
        if size > 1:
            px, py = px-dx, py-dy
        if contains_floor(floor, point_box((px, py), size)):
            choices.setdefault(side, []).append((x, y, px, py))

    for _ in range(12):
        doors = []
        for side in ('south', 'north', 'east', 'west'):
            if not choices.get(side):
                continue
            axis, middle = (0, width/2) if side in ('south', 'north') else (1, height/2)
            best = sorted(choices[side], key=lambda c: abs(c[axis] + .5 - middle))
            x, y, px, py = rng.choice(best[:max(2, len(best)//2)])
            doors.append(Door(id=f'door_{len(doors)+1}', x=x, y=y, side=side, approach=Point(x=px, y=py)))
            if len(doors) == count:
                break
        if len(doors) != count:
            raise GeometryFailure('door_capacity', 'The boundary has too few usable door segments.')
        _, seen, parents = navigation(width, height, [], doors[0].approach, size, floor)
        targets = [(int(door.approach.x), int(door.approach.y)) for door in doors]
        if len(set(targets)) != count or not all(target in seen for target in targets):
            continue
        # A single-door room still gets an unobstructed approach toward its center.
        if count == 1:
            center = min(seen, key=lambda c: (math.dist(c, (width/2, height/2)), c))
            targets.append(center)
        route = set()
        for cell in targets:
            while cell is not None and cell not in route:
                route.add(cell)
                cell = parents[cell]
        reserved = {tile for x, y in route for tile in box_cells(point_box((x+.5, y+.5), size))}
        reserved.update((door.x, door.y) for door in doors)
        return doors, reserved
    raise GeometryFailure('door_connectivity', 'Door approaches cannot be connected at this player width.')


def build_architecture(width, height, player_size, options: GeometryOptions,
                       preferences: GeometryPreferences, seed: int):
    rng = random.Random(seed)
    shape = rng.choice(preferences.shapes) if options.shape == 'auto' else options.shape
    width, height = _dimensions(width, height, shape, options, preferences, rng)
    exterior = _outer_floor(width, height, shape, rng)
    partitions = _partition(exterior, height, rng) if options.partition else set()
    floor = exterior - partitions
    all_walls = {(x, y, side) for x, y in floor for side, (dx, dy) in DIRECTIONS.items()
                 if (x+dx, y+dy) not in floor}
    exterior_walls = {(x, y, side) for x, y, side in all_walls
                      if (x+DIRECTIONS[side][0], y+DIRECTIONS[side][1]) not in exterior}
    doors, reserved = _doors(floor, exterior_walls, width, height, options.entrances, player_size, rng)
    walls = all_walls - {(door.x, door.y, door.side) for door in doors}
    geometry = RoomGeometry(shape=shape, floorStyle=options.floor or preferences.floor,
                            floor=[Cell(x=x, y=y) for x, y in sorted(floor)], doors=doors,
                            walls=[Wall(x=x, y=y, side=side) for x, y, side in sorted(walls)],
                            partitions=[Cell(x=x, y=y) for x, y in sorted(partitions)])
    return Architecture(width, height, geometry, frozenset(floor), frozenset(walls), frozenset(reserved))
