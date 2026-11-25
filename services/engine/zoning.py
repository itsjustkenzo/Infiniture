"""Reserve room for whole groups, then expand zones over adjacent usable floor."""

import math

import numpy as np

from .geometry import neighbors
from .models import Rect


class ZoneCapacity(Exception):
    def __init__(self, zone, width, height):
        self.reason = {'code': 'zone_capacity', 'stage': 'zoning', 'zoneId': zone,
                       'minimumWidth': width, 'minimumHeight': height,
                       'message': 'No connected floor region can accommodate the required zone and its groups.'}
        super().__init__(self.reason['message'])


def bounds(cells):
    xs, ys = zip(*cells)
    return Rect(x=min(xs), y=min(ys), width=max(xs)-min(xs)+1, height=max(ys)-min(ys)+1)


def _empty_rectangles(available, width, height):
    grid = np.zeros((height, width), dtype=np.int32)
    for x, y in available:
        grid[y, x] = 1
    return np.pad(grid.cumsum(0).cumsum(1), ((1, 0), (1, 0)))


def _wall_needs(members, assets):
    needed = {}
    for group in members:
        for p in group['placements']:
            spec = next(obj for obj in group['group'].objects if obj.id == p.id)
            if not spec.required:
                continue
            asset = assets[p.assetId]
            sides = [rel.wall for rel in spec.relations if rel.mandatory and rel.type in
                     ('against_wall', 'along_wall', 'attached_to_wall')]
            if asset.requiresWall:
                sides.append('north')
            for side in sides:
                span = asset.footprint.width if side in ('north', 'south') else asset.footprint.height
                needed[side] = max(needed.get(side, 0), math.ceil(span))
    return needed


def _core(zone, members, assets, architecture, available, placed, zone_specs, rng):
    min_width = max((g['width'] for g in members), default=2)
    min_height = max((g['height'] for g in members), default=2)
    demand = max(zone.minimumArea, sum((g['width']+1)*(g['height']+1) for g in members))
    target = max(demand, min(zone.preferredArea, demand + 20))
    wall_needs = _wall_needs(members, assets)
    width, height = architecture.width, architecture.height
    prefix = _empty_rectangles(available, width, height)
    door = (architecture.entrance.x, architecture.entrance.y)
    floor_center = (width/2, height/2)
    related_centers = []
    for target_id, region in placed.items():
        related = zone_specs[target_id]
        near = target_id in zone.nearZones or zone.id in related.nearZones
        away = target_id in zone.awayFromZones or zone.id in related.awayFromZones
        weight = .16 * (near - away)
        if weight:
            r = bounds(region)
            related_centers.append(((r.x+r.width/2, r.y+r.height/2), weight))
    candidates = []
    dimensions = sorted(((w, h) for w in range(min_width, min(width-1, target//min_height + 3))
                         for h in range(min_height, min(height-2, target//min_width + 3)) if w*h >= demand),
                        key=lambda wh: (abs(wh[0]*wh[1]-target), abs(wh[0]-wh[1])))
    for w, h in dimensions:
        coverage = prefix[h:, w:] - prefix[:-h, w:] - prefix[h:, :-w] + prefix[:-h, :-w]
        ys, xs = np.nonzero(coverage == w*h)
        for x, y in zip(xs.tolist(), ys.tolist()):
            box = (x, y, w, h)
            edge_cells = {'north': [(i, y, 'north') for i in range(x, x+w)],
                          'south': [(i, y+h-1, 'south') for i in range(x, x+w)],
                          'west': [(x, j, 'west') for j in range(y, y+h)],
                          'east': [(x+w-1, j, 'east') for j in range(y, y+h)]}
            def wall_length(side):
                run = longest = 0
                for edge in edge_cells[side]:
                    run = run + 1 if edge in architecture.walls else 0
                    longest = max(longest, run)
                return longest
            if any(wall_length(side) < span for side, span in wall_needs.items()):
                continue
            center = (x + w/2, y + h/2)
            cost = abs(w*h-target)*.035 + abs(w-h)*.05
            if zone.preferredWall:
                cost -= min(4, wall_length(zone.preferredWall))*.65
            cost += math.dist(center, door if zone.nearEntrance else floor_center) * (.16 if zone.nearEntrance else .045)
            cost += sum(math.dist(center, point)*weight for point,weight in related_centers)
            # Prefer a wall or circulation edge so neighboring zone capacity remains contiguous.
            touched = sum((i, y-1) not in available or (i, y+h) not in available for i in range(x, x+w))
            touched += sum((x-1, j) not in available or (x+w, j) not in available for j in range(y, y+h))
            cost -= touched*.23
            candidates.append((cost + rng.random()*.85, box))
        if len(candidates) >= 180:
            break
    if not candidates:
        raise ZoneCapacity(zone.id, min_width, min_height)
    _, (x, y, w, h) = min(candidates)
    return {(i, j) for i in range(x, x+w) for j in range(y, y+h)}


def allocate_dynamic_zones(scene, assembled, assets, architecture, rng):
    available = set(architecture.floor - architecture.circulation)
    zones = {}
    specs = {zone.id: zone for zone in scene.zones}
    members = {zone.id: [g for g in assembled if g['group'].zoneId == zone.id and g['group'].required]
               for zone in scene.zones}
    ordered = sorted(scene.zones, key=lambda zone: (not zone.required,
                     not _wall_needs(members[zone.id], assets), -zone.priority, zone.id))
    for zone in ordered:
        try:
            core = _core(zone, members[zone.id], assets, architecture, available, zones, specs, rng)
        except ZoneCapacity:
            if zone.required:
                raise
            continue
        zones[zone.id] = core
        available.difference_update(core)
    # Grow contiguous masks outside the rectangular placement cores. Keep free floor between groups.
    for zone in ordered:
        region = zones.get(zone.id)
        if region is None:
            continue
        box = bounds(region)
        center = (box.x+box.width/2, box.y+box.height/2)
        limit = max(zone.preferredArea, len(region) + min(12, len(region)//4))
        frontier = {n for cell in region for n in neighbors(cell) if n in available}
        while frontier and len(region) < limit:
            cell = min(frontier, key=lambda p: (math.dist(p, center), p))
            frontier.remove(cell)
            region.add(cell)
            available.remove(cell)
            frontier.update(n for n in neighbors(cell) if n in available)
    return {zone: bounds(cells) for zone, cells in zones.items()}, zones
