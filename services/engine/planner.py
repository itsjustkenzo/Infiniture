"""Offline semantic fixture planner. Recipes choose purposes/assets, never coordinates."""
from .models import Scene, PlanRequest, RoomSpec

# These are semantic vocabulary mappings, not room layouts or placement algorithms.
CONCEPTS={
 'tavern': [('Hospitality','counter'),('Dining','table'),('Supplies','barrel')],
 'bedroom': [('Rest','bed'),('Study','desk'),('Storage','cabinet')],
 'library': [('Book storage','bookshelf'),('Reading','table'),('Reception','desk')],
 'kitchen': [('Preparation','counter'),('Dining','table'),('Pantry','shelf')],
 'office': [('Work','desk'),('Meetings','table'),('Records','cabinet')],
 'shop': [('Service','counter'),('Display','shelf'),('Stock','crate')],
 'hospital': [('Reception','desk'),('Treatment','bed'),('Medical storage','cabinet')],
 'blacksmith': [('Metalwork','anvil'),('Workbench','desk'),('Materials','crate')],
 'laboratory': [('Research','desk'),('Experiment','counter'),('Equipment','shelf')],
 'spaceship': [('Control','desk'),('Crew','table'),('Equipment','cabinet')],
}

ROOM_CONCEPTS = {
    **CONCEPTS,
    'warehouse': [('Receiving','counter'),('Bulk storage','crate'),('Inventory','shelf')],
    'classroom': [('Instruction','desk'),('Student work','table'),('Teaching supplies','cabinet')],
}

# Fixture vocabulary. Each role supplies category and compatible semantic tags.
ROLE_ASSETS = {
    'table': ('table', ['table', 'round_table']), 'desk': ('table', ['desk']),
    'counter': ('counter', []), 'bed': ('bed', []), 'anvil': ('equipment', []),
    'bookshelf': ('storage', ['bookshelf', 'shelf']), 'shelf': ('storage', ['shelf', 'cabinet']),
    'cabinet': ('storage', ['cabinet', 'shelf']),
    'barrel': ('storage', ['barrel', 'crate', 'chest']),
    'crate': ('storage', ['crate', 'barrel', 'chest']),
}


def mock_room(req: PlanRequest):
    """The offline planner produces category requirements, never sprite positions or IDs."""
    concept = next((name for name in ROOM_CONCEPTS if name in req.description.lower()), 'tavern')
    variant = req.conceptSeed % 3
    zones, groups = [], []
    for index, (purpose, role) in enumerate(ROOM_CONCEPTS[concept]):
        zone = f'area_{index+1}'
        category, tags = ROLE_ASSETS[role]
        zones.append(dict(id=zone, purpose=purpose, minimumArea=16,
                          preferredArea=68 if role in ('table', 'bed') else 44,
                          priority=3-index, preferredWall='north' if role in ('bookshelf', 'cabinet', 'shelf') else None,
                          nearEntrance=index == 0, nearZones=['area_1'] if index == 1 else []))
        members = []
        if role in ('table', 'desk', 'counter'):
            members.append(dict(id='seat', category='seating', anyTags=['chair', 'stool'], orientation='north',
                                relations=[dict(type='facing_object', target='primary', distance=2)]))
            tags_for_detail = ['computer'] if role == 'desk' else ['candle', 'plate', 'mug']
            members.append(dict(id='detail', category='surface_detail', anyTags=tags_for_detail, required=False,
                                decoration=True, relations=[dict(type='attached_to_surface', target='primary')]))
            if role == 'table' and variant != 1:
                members.append(dict(id='rug', category='rug', required=False, decoration=True,
                                    relations=[dict(type='under_object', target='primary')]))
        if role == 'bed':
            members.append(dict(id='bedside', category='storage', anyTags=['chest', 'crate'],
                                relations=[dict(type='near_object', target='primary', distance=2)]))
        preferred = 1 if index == 0 or role == 'bed' else (3 if variant == 1 or concept in ('warehouse', 'classroom') else 2)
        groups.append(dict(id=f'set_{index+1}', zoneId=zone, minimum=1, preferred=preferred, caretaker=index == 0,
                           anchor=dict(id='primary', category=category, anyTags=tags, requiresInteraction=True),
                           members=members))
    if variant == 2:
        zones.append(dict(id='quiet', purpose='Quiet corner', minimumArea=10, preferredArea=20,
                          priority=0, required=False, awayFromZones=['area_1']))
        groups.append(dict(id='quiet_set', zoneId='quiet', minimum=0, preferred=1,
                           anchor=dict(id='primary', category='seating', anyTags=['bench'])))
    floor = 'stone_floor' if concept in ('warehouse', 'blacksmith', 'laboratory') or variant == 1 else 'wood_floor'
    return RoomSpec(title=f'{concept.title()} interior', purpose=concept, description=req.description, conceptSeed=req.conceptSeed,
                    geometry={'shapes': ['rectangle', 'square', 'l_shape', 'alcove', 'orthogonal'], 'floor': floor},
                    zones=zones, groups=groups, density=req.density, decorationDensity=req.decorationDensity)

def plan(req: PlanRequest):
    text=req.description.lower()
    concept=next((k for k in CONCEPTS if k in text),'tavern')
    zones=[];groups=[]
    for i,(purpose,asset) in enumerate(CONCEPTS[concept]):
        zid=f'zone_{i}'; gid=f'group_{i}'; anchor=f'{gid}_anchor'
        zones.append(dict(id=zid,purpose=purpose,minimumArea=20,preferredArea=60 if asset in ['table','bed'] else 36,priority=3-i,preferredWall='north' if asset in ['bookshelf','cabinet','shelf'] else None))
        objects=[dict(id=anchor,assetId=asset)]
        if asset in ['table','desk','counter']:
            objects.append(dict(id=f'{gid}_chair',assetId='chair',orientation='north',relations=[dict(type='facing_object',target=anchor,distance=2)]))
            if req.decorationDensity>0:
                objects.append(dict(id=f'{gid}_detail',assetId='computer' if asset=='desk' else 'candle',required=False,relations=[dict(type='attached_to_surface',target=anchor,socket='top0')]))
            if req.decorationDensity>.35 and asset=='table':
                objects.append(dict(id=f'{gid}_rug',assetId='carpet',required=False,relations=[dict(type='under_object',target=anchor)]))
        if asset=='bed':
            objects.append(dict(id=f'{gid}_chest',assetId='chest',relations=[dict(type='near_object',target=anchor,distance=2)]))
        groups.append(dict(id=gid,zoneId=zid,anchorId=anchor,objects=objects))
    if req.density>.65:
        # Additional demand, same generic solver.
        gid='group_extra'; anchor=gid+'_anchor'
        groups.append(dict(id=gid,zoneId='zone_1',anchorId=anchor,required=False,objects=[dict(id=anchor,assetId='table'),dict(id=gid+'_chair',assetId='chair',orientation='north',relations=[dict(type='facing_object',target=anchor,distance=2)])]))
    return Scene.model_validate(dict(title=concept.title()+' interior',description=req.description,zones=zones,groups=groups,npcs=[dict(id='caretaker',name='Caretaker',groupId='group_0',dialogue='Welcome in. Every room has a story waiting to unfold.')]))
