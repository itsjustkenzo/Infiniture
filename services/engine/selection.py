"""Translate category requirements into the existing concrete scene graph."""

import math
import random

from .models import Group, NPC, ObjectSpec, Scene


class SelectionFailure(Exception):
    def __init__(self, code, message, **details):
        self.reason = {'code': code, 'message': message, 'stage': 'selection', **details}
        super().__init__(message)


def _compatible(component, asset, selected):
    attachments = [relation for relation in component.relations if relation.type == 'attached_to_surface']
    if asset.requiresSurface and not any(relation.mandatory for relation in attachments):
        return False
    for relation in component.relations:
        if not relation.target or relation.type == 'separated_from_zone':
            continue
        target = selected.get(relation.target)
        if target is None:
            if relation.mandatory:
                return False
            continue
        if relation.type == 'attached_to_surface' and not any(
            asset.category in socket.categories and (not relation.socket or relation.socket == socket.id)
            and socket.x + asset.footprint.width <= target.footprint.width
            and socket.y + asset.footprint.height <= target.footprint.height
            for socket in target.surfaceSockets
        ):
            return False
        if relation.type == 'under_object' and (
            asset.renderLayer != 'floor_decoration' or asset.footprint.width < target.footprint.width
            or asset.footprint.height < target.footprint.height
        ):
            return False
    return True


def _component_order(group):
    ordered = [group.anchor]
    pending = list(group.members)
    while pending:
        resolved = {role.id for role in ordered}
        ready = [role for role in pending if all(
            not rel.target or rel.target in resolved or rel.type == 'separated_from_zone' for rel in role.relations
        )]
        if not ready:
            raise SelectionFailure('cyclic_components', 'Group component roles contain a cycle.', groupId=group.id)
        # Complete the furniture graph before considering optional decoration.
        role = min(ready, key=lambda item: (item.decoration, not item.required))
        ordered.append(role)
        pending.remove(role)
    return ordered


def _select_group(requirement, ordered, pools, instance, required, seeds, decoration_density):
    group_id = f'{requirement.id}_{instance+1}'
    selected = {}
    budget = 800

    def pick(index):
        nonlocal budget
        if index == len(ordered):
            return True
        role = ordered[index]
        randomizer = random.Random(f'{seeds.decoration if role.decoration else seeds.selection}:{group_id}:{role.id}')
        if role.decoration and not role.required and randomizer.random() >= decoration_density:
            return pick(index + 1)
        candidates = list(pools[role.id])
        randomizer.shuffle(candidates)
        for asset in candidates:
            budget -= 1
            if budget < 0:
                return False
            if _compatible(role, asset, selected):
                selected[role.id] = asset
                if pick(index + 1):
                    return True
                del selected[role.id]
        return not role.required and pick(index + 1)

    if not pick(0):
        return None
    objects = []
    for role in ordered:
        if role.id not in selected:
            continue
        relations = [relation.model_copy(update={'target': f'{group_id}_{relation.target}'})
                     if relation.target and relation.type != 'separated_from_zone' else relation
                     for relation in role.relations
                     if not relation.target or relation.type == 'separated_from_zone' or relation.target in selected]
        objects.append(ObjectSpec(id=f'{group_id}_{role.id}', assetId=selected[role.id].id,
                                  required=role.required, orientation=role.orientation, relations=relations))
    return Group(id=group_id, zoneId=requirement.zoneId, anchorId=objects[0].id, required=required, objects=objects)


def select_scene(room, architecture, assets, seeds, density, decoration_density):
    usable_area = len(architecture.floor - architecture.circulation)
    items = sorted((asset for asset in assets if asset.approved and asset.styleId == 'hearth_pixel'
                    and asset.category not in ('architecture', 'character')), key=lambda asset: asset.id)
    areas = {zone.id: zone.preferredArea for zone in room.zones}
    available = {zone.id: usable_area * zone.preferredArea / sum(areas.values()) for zone in room.zones}
    estimates = {}
    data = []
    for requirement in room.groups:
        ordered = _component_order(requirement)
        pools = {role.id: [asset for asset in items if asset.category == role.category
                          and role.orientation in asset.supportedOrientations
                          and (not role.requiresInteraction or asset.interactionPoints)
                          and (not role.anyTags or set(role.anyTags).intersection(asset.tags))]
                 for role in ordered}
        for role in ordered:
            if requirement.minimum and role.required and not pools[role.id]:
                raise SelectionFailure('no_approved_asset', f'No approved asset matches {role.category}.',
                                       groupId=requirement.id, role=role.id, tags=role.anyTags)
        estimate = 5 + 2 * sum(min((a.footprint.width * a.footprint.height for a in pools[role.id]), default=0)
                             for role in ordered if role.required and not role.decoration)
        estimates[requirement.id] = estimate
        available[requirement.zoneId] -= estimate * requirement.minimum
        data.append((requirement, ordered, pools))

    groups, npcs, decisions = [], [], []
    remaining_slots = 30 - sum(requirement.minimum for requirement in room.groups)
    for requirement, ordered, pools in data:
        estimate = estimates[requirement.id]
        # Area is a cap; the room spec and density still determine desired functional groups.
        desired = requirement.minimum + math.floor((requirement.preferred-requirement.minimum) * density + .35)
        capacity = max(0, math.floor(available[requirement.zoneId] / (estimate * 1.7)))
        optional = min(desired-requirement.minimum, capacity, remaining_slots)
        remaining_slots -= optional
        available[requirement.zoneId] -= estimate * 1.7 * optional
        count = requirement.minimum + optional
        instances = []
        for index in range(count):
            required = index < requirement.minimum
            group = _select_group(requirement, ordered, pools, index, required, seeds, decoration_density)
            if group is None:
                if required:
                    raise SelectionFailure('incompatible_group_assets', 'Approved assets cannot satisfy group relationships.', groupId=requirement.id)
                continue
            groups.append(group)
            instances.append({'groupId': group.id, 'required': required, 'assetIds': [obj.assetId for obj in group.objects]})
            if requirement.caretaker and index == 0:
                npcs.append(NPC(id=f'caretaker_{group.id}', name='Caretaker', groupId=group.id,
                                dialogue='Welcome in. Every room has a story waiting to unfold.'))
        decisions.append({'requirementId': requirement.id, 'category': requirement.anchor.category,
                          'zoneId': requirement.zoneId, 'minimum': requirement.minimum,
                          'preferred': requirement.preferred, 'requested': count,
                          'selected': len(instances), 'instances': instances})
    return Scene(title=room.title, description=room.description, zones=room.zones, groups=groups, npcs=npcs), decisions
