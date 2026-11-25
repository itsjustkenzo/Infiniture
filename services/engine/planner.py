"""Offline semantic fixture planner. Recipes choose purposes/assets, never coordinates."""
from .models import Scene, PlanRequest

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
