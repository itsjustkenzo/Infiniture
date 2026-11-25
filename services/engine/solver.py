import math,random,time
from collections import Counter
from .models import Cell, GenerationSeeds, GeometryOptions, GeometryPreferences, Placement, Layout, Point, Rect, LAYERS
from .catalog import catalog
from .geometry import approach_path, contains_floor, overlap,contains,collision,footprint,point_box,navigation,reachable,path_to,center
from .relationships import check_relation
from .architecture import GeometryFailure, build_architecture, component
from .selection import SelectionFailure, select_scene
from .zoning import ZoneCapacity, allocate_dynamic_zones, bounds as zone_bounds

class Failure(Exception):
    def __init__(self,code,message,**details):
        self.reason={'code':code,'message':message,**details};super().__init__(message)

def asset_map(req):
    supplied=req.assets if req.assets is not None else catalog()
    assets={a.id:a for a in supplied}
    if len(assets)!=len(supplied):raise Failure('duplicate_asset','Duplicate asset IDs')
    for g in req.scene.groups:
        for o in g.objects:
            a=assets.get(o.assetId)
            if a is None:raise Failure('missing_asset',f'Unknown asset {o.assetId}',objectId=o.id)
            if not a.approved:raise Failure('unapproved_asset',f'Asset {a.id} has not been approved')
            if a.styleId!=req.scene.styleId:raise Failure('incompatible_style',f'Asset {a.id} uses a different visual style')
            if a.category in ['architecture','character']:raise Failure('invalid_furniture_asset',f'{a.id} belongs to the architectural/entity pipeline')
            if o.orientation not in a.supportedOrientations:raise Failure('unsupported_orientation',f'{a.id} cannot face {o.orientation}')
            if a.requiresSurface and not any(r.type=='attached_to_surface' and r.mandatory for r in o.relations):raise Failure('unsupported_surface_attachment',f'{o.id} requires a mandatory surface relationship')
    return assets

def prepare(req):
    """Resolve geometry and categories once. Legacy scene requests keep their original layout rules."""
    if req.room is None and req.geometry is None and req.seeds is None and req.retainObjects is None:
        return req, None, [], None
    seeds = req.seeds or GenerationSeeds(geometry=req.seed, selection=req.seed, placement=req.seed, decoration=req.seed)
    geometry_options = req.geometry or GeometryOptions()
    architecture = build_architecture(req.width, req.height, req.playerSize, geometry_options,
                                      req.room.geometry if req.room else GeometryPreferences(), seeds.geometry)
    supplied = req.assets if req.assets is not None else catalog()
    if len({asset.id for asset in supplied}) != len(supplied):
        raise Failure('duplicate_asset', 'Duplicate asset IDs')
    if req.room:
        density = req.density if 'density' in req.model_fields_set else req.room.density
        decoration = req.decorationDensity if 'decorationDensity' in req.model_fields_set else req.room.decorationDensity
        scene, decisions = select_scene(req.room, architecture, supplied, seeds, density, decoration)
    else:
        scene, decisions = req.scene, []
        density, decoration = req.density, req.decorationDensity
    if req.retainObjects is not None:
        keep=set(req.retainObjects)
        if not keep<={obj.id for group in scene.groups for obj in group.objects}:
            raise SelectionFailure('retained_selection_changed','Previously placed objects are no longer in the selection.')
        groups=[]
        for group in scene.groups:
            objects=[obj for obj in group.objects if obj.id in keep]
            if not objects and not group.required:
                continue
            if group.anchorId not in keep or any(obj.required and obj.id not in keep for obj in group.objects):
                raise SelectionFailure('retained_group_incomplete','An arrangement must keep the complete required group.',groupId=group.id)
            for obj in objects:
                if any(rel.mandatory and rel.target and rel.type!='separated_from_zone' and rel.target not in keep for rel in obj.relations):
                    raise SelectionFailure('retained_group_incomplete','An arrangement must keep required attachments.',groupId=group.id)
            groups.append(group.model_copy(update={'required':True,'objects':[obj.model_copy(update={
                'required':True,'relations':[rel for rel in obj.relations if not rel.target or rel.target in keep or rel.type=='separated_from_zone']}) for obj in objects]}))
        required_zone_ids={group.zoneId for group in groups}
        scene=scene.model_copy(update={'groups':groups,'zones':[z.model_copy(update={'required':True})
                                                              if z.id in required_zone_ids else z for z in scene.zones]})
    resolved = req.model_copy(update={'scene': scene, 'assets': supplied, 'seed': seeds.placement,
                                      'width': architecture.width, 'height': architecture.height,
                                      'geometry': geometry_options,
                                      'density': density, 'decorationDensity': decoration})
    return resolved, architecture, decisions, seeds

def interactions(placements,assets,player):
    points=[]
    for placement in placements:
        asset=assets[placement.assetId]
        x,y,w,h=collision(placement,asset)
        for socket in asset.interactionPoints:
            px,py=placement.x+socket.x,placement.y+socket.y
            if asset.solid:
                # A larger player approaches the same side, far enough for the full clearance box.
                gap,dx,dy=max(((x-px,-1,0),(px-x-w,1,0),(y-py,0,-1),(py-y-h,0,1)))
                if gap>=0:
                    extra=max(0,player/2+asset.interactionClearance-gap)
                    px,py=px+dx*extra,py+dy*extra
            points.append((placement.id,(px,py),asset.interactionClearance))
    return points

def internal_valid(placements,assets,player):
    solids=[collision(p,assets[p.assetId]) for p in placements if assets[p.assetId].solid]
    for i,a in enumerate(solids):
        if any(overlap(a,b) for b in solids[i+1:]):return False
    for _,pt,clearance in interactions(placements,assets,player):
        if any(overlap(point_box(pt,player+clearance*2),b) for b in solids):return False
    sockets=[(p.parentId,p.socketId) for p in placements if p.parentId]
    return len(sockets)==len(set(sockets))

def assemble(group,assets,seed,player,allow_optional=True,deadline=None):
    rng=random.Random(seed); specs={o.id:o for o in group.objects}; anchor=specs[group.anchorId]
    if any(r.target and r.type!='separated_from_zone' for r in anchor.relations):raise Failure('anchor_dependency','Group anchor cannot depend on another object',groupId=group.id)
    order=[anchor];remaining=[o for o in group.objects if o.id!=anchor.id]
    while remaining:
        ready=[o for o in remaining if all(not r.target or r.type=='separated_from_zone' or r.target in [v.id for v in order] for r in o.relations)]
        if not ready:raise Failure('cyclic_relationship','Cyclic group dependencies',groupId=group.id)
        order.extend(ready);remaining=[o for o in remaining if o not in ready]
    def make(o,x,y,**kw):return Placement(id=o.id,assetId=o.assetId,groupId=group.id,zoneId=group.zoneId,x=x,y=y,orientation=o.orientation,**kw)
    placed=[make(anchor,0,0)];nodes=0
    def visit(i):
        nonlocal nodes
        if deadline is not None and time.perf_counter()>deadline:raise Failure('time_budget','Group assembly exceeded generation time budget')
        if i==len(order):return list(placed)
        o=order[i];a=assets[o.assetId];index={p.id:p for p in placed}
        if not allow_optional and not o.required:return visit(i+1)
        special=next((r for r in o.relations if r.type in ['attached_to_surface','under_object']),None)
        choices=[]
        if special:
            target=index.get(special.target)
            if target:
                ta=assets[target.assetId]
                if special.type=='attached_to_surface':
                    choices=[make(o,target.x+s.x,target.y+s.y,parentId=target.id,socketId=s.id,visualLift=s.visualLift) for s in ta.surfaceSockets if a.category in s.categories and (not special.socket or special.socket==s.id)]
                else:choices=[make(o,target.x+(ta.footprint.width-a.footprint.width)/2,target.y+(ta.footprint.height-a.footprint.height)/2)]
        else:
            target=next((index[r.target] for r in o.relations if r.target in index),placed[0]);ta=assets[target.assetId]
            # Bounded relative search; evaluate relationships before expensive group validity.
            offsets=[(x/2,y/2) for x in range(-12,17) for y in range(-12,17)]
            rng.shuffle(offsets)
            offsets.sort(key=lambda v:math.hypot(v[0]+a.footprint.width/2-ta.footprint.width/2,v[1]+a.footprint.height/2-ta.footprint.height/2))
            choices=[make(o,target.x+x,target.y+y) for x,y in offsets]
        for p in choices:
            if deadline is not None and time.perf_counter()>deadline:raise Failure('time_budget','Group assembly exceeded generation time budget')
            if nodes>=5000:break
            if not all(check_relation(r,p,index.get(r.target),assets,placed[0]) for r in o.relations if r.mandatory):continue
            nodes+=1
            if not internal_valid(placed+[p],assets,player):continue
            placed.append(p);result=visit(i+1)
            if result is not None:return result
            placed.pop()
        if not o.required:return visit(i+1)
        return None
    result=visit(1)
    if result is None:raise Failure('group_unsatisfiable','Cannot assemble required group relationships',groupId=group.id)
    # Include interaction clearances in combined group bounds, not just solid cells.
    boxes=[footprint(p,assets[p.assetId]) for p in result]
    boxes += [point_box(pt,player+c*2) for _,pt,c in interactions(result,assets,player)]
    x0=min(b[0] for b in boxes);y0=min(b[1] for b in boxes)
    x1=max(b[0]+b[2] for b in boxes);y1=max(b[1]+b[3] for b in boxes)
    return {'group':group,'placements':[p.model_copy(update={'x':p.x-x0,'y':p.y-y0}) for p in result],'width':math.ceil(x1-x0),'height':math.ceil(y1-y0),'anchorOffset':(x0,y0)}

def allocate_zones(req,assembled,variant):
    # A central three-tile spine is reserved before variable-sized, demand-weighted strips.
    mid=req.width//2; sides=[{'x':1,'width':mid-2,'y':2},{'x':mid+2,'width':req.width-mid-3,'y':2}]
    zones={}; ordered=sorted(req.scene.zones,key=lambda z:(z.preferredWall!='north',-z.priority,-z.minimumArea,z.id))
    if variant%2:sides.reverse()
    for z in ordered:
        members=[g for g in assembled if g['group'].zoneId==z.id and g['group'].required]
        need_w=max([g['width'] for g in members]+[2]);need_h=max([g['height'] for g in members]+[2])
        demand=max(z.minimumArea,sum((g['width']+1)*(g['height']+1) for g in members))
        options=[]
        for si,s in enumerate(sides):
            hh=max(need_h,math.ceil(demand/max(1,s['width'])))
            if need_w>s['width'] or s['y']+hh>req.height-1:continue
            # Mandatory wall assets force north edge; all wall constraints are rechecked later.
            if z.preferredWall=='north' and s['y']!=2:continue
            options.append((s['y'],si,hh))
        if not options:raise Failure('zone_capacity','Not enough connected room area for functional zone',zoneId=z.id,minimumWidth=need_w,minimumHeight=need_h)
        _,si,hh=min(options);s=sides[si]
        remaining=sum(1 for zz in ordered[ordered.index(z)+1:] if zz.id not in zones)
        preferred=math.ceil(z.preferredArea/s['width'])
        extra=max(0,(req.height-1-s['y']-hh)//(remaining+1))
        hh+=min(max(0,preferred-hh),extra)
        zones[z.id]=Rect(x=s['x'],y=s['y'],width=s['width'],height=hh)
        s['y']+=hh+1
    # Distribute remaining depth by functional area demand instead of abandoning the
    # southern half of the room. North-attached zones retain their wall edge.
    for side in sides:
        ids=sorted([zid for zid,z in zones.items() if z.x==side['x']],key=lambda zid:zones[zid].y)
        if not ids:continue
        free=int(req.height-1-(zones[ids[-1]].y+zones[ids[-1]].height))
        demands={z.id:z.preferredArea for z in req.scene.zones if z.id in ids}
        total=sum(demands.values());cursor=2;remaining=free
        for n,zid in enumerate(ids):
            extra=remaining if n==len(ids)-1 else int(free*demands[zid]/total)
            remaining-=extra;z=zones[zid];zones[zid]=Rect(x=z.x,y=cursor,width=z.width,height=z.height+extra)
            cursor+=z.height+extra+1
    return zones

def wall_ok(p,a,architecture):
    if not a.requiresWall:return True
    # Fixed library wall sprites are north-facing; no arbitrary rotation.
    if architecture is not None:
        return architecture.touches_wall(footprint(p,a),'north')
    return abs(p.y-2)<1e-7

def candidate(req,assets,index,deadline,allow_optional=True,architecture=None):
    rng=random.Random(req.seed+index*1009)
    assembled=[]
    failure_counts=Counter()
    for i,g in enumerate(req.scene.groups):
        try:
            assembled.append(assemble(g,assets,req.seed+index*1009+i,req.playerSize,allow_optional,deadline))
        except Failure as error:
            if g.required or error.reason['code'] != 'group_unsatisfiable':raise
            failure_counts['optional_group_assembly']+=1
    room=architecture or (req.width,req.height)
    if architecture:
        zones,zone_masks=allocate_dynamic_zones(req.scene,assembled,assets,architecture,rng)
        circulation=[Point(x=x+.5,y=y+.5) for x,y in sorted(architecture.circulation)]
        entrance,exit=architecture.entrance,architecture.exit
    else:
        zones=allocate_zones(req,assembled,index)
        zone_masks=None
        mid=req.width//2; circulation=[Point(x=x+.5,y=y+.5) for y in range(2,req.height-1) for x in range(mid-1,mid+2)]
        entrance=Point(x=mid+.5,y=req.height-1.5);exit=Point(x=mid+.5,y=2.5)
    reserved=[(p.x-.5,p.y-.5,1,1) for p in circulation]
    assembled.sort(key=lambda g:(not g['group'].required,not any(assets[p.assetId].requiresWall for p in g['placements']),-g['width']*g['height'],g['group'].id))
    all_choices={}
    for ag in assembled:
        if ag['group'].zoneId not in zones:
            all_choices[ag['group'].id]=[]
            continue
        z=zones[ag['group'].zoneId];options=[]
        for y in range(int(z.y),int(z.y+z.height-ag['height'])+1):
            if time.perf_counter()>deadline:raise Failure('time_budget','Candidate enumeration exceeded generation time budget')
            for x in range(int(z.x),int(z.x+z.width-ag['width'])+1):
                ps=[p.model_copy(update={'x':p.x+x,'y':p.y+y}) for p in ag['placements']]
                by_id={p.id:p for p in ps}; anchor=by_id[ag['group'].anchorId]
                if zone_masks is not None and not all(contains_floor(zone_masks[ag['group'].zoneId],footprint(p,assets[p.assetId])) for p in ps):
                    failure_counts['outside_zone_floor']+=1;continue
                if not all(wall_ok(p,assets[p.assetId],architecture) for p in ps):
                    failure_counts['wall_attachment']+=1;continue
                if not all(check_relation(r,by_id[o.id],by_id.get(r.target),assets,anchor,z,room,zones) for o in ag['group'].objects if o.id in by_id for r in o.relations if r.mandatory):
                    failure_counts['relationship']+=1;continue
                if not architecture and any(overlap(collision(p,assets[p.assetId]),r) for p in ps if assets[p.assetId].solid for r in reserved):continue
                if architecture and not all(contains_floor(architecture.floor,point_box(pt,req.playerSize+2*c)) for _,pt,c in interactions(ps,assets,req.playerSize)):
                    failure_counts['clearance']+=1;continue
                options.append(ps)
        rng.shuffle(options)
        # Boundary alignment and zone centering are geometry-based placement preferences.
        options.sort(key=lambda ps: min(abs(ps[0].x-z.x),abs(ps[0].x+assets[ps[0].assetId].footprint.width-z.x-z.width))*.3+abs(center(ps[0],assets[ps[0].assetId])[1]-(z.y+z.height/2))*.1)
        all_choices[ag['group'].id]=options
    nodes=0;placed=[];last_failure=None
    serialized_zones={zid:[Cell(x=x,y=y) for x,y in sorted(cells)] for zid,cells in zone_masks.items()} if zone_masks is not None else None
    # Find a playable required layout first. Optional groups must not consume the
    # search budget before the engine has a valid furniture arrangement to return.
    search=assembled if architecture is None else [ag for ag in assembled if ag['group'].required]
    def visit(i):
        nonlocal nodes,last_failure
        if time.perf_counter()>deadline:raise Failure('time_budget','Generation time budget exhausted')
        if i==len(search):
            layout=Layout(width=req.width,height=req.height,seed=req.seed,playerSize=req.playerSize,zones=zones,placements=list(placed),entrance=entrance,exit=exit,circulation=circulation,geometry=architecture.geometry if architecture else None,zoneCells=serialized_zones)
            report=validate_layout(req,layout,assets,architecture)
            if report['valid']:return layout,report
            for f in report['failures']:failure_counts[f['code']]+=1
            last_failure=report['failures'];return None
        ag=search[i]
        for ps in all_choices[ag['group'].id]:
            nodes+=1
            if nodes>req.maxSearchNodes:return None
            if not internal_valid(placed+ps,assets,req.playerSize):failure_counts['overlap_or_clearance']+=1;continue
            placed.extend(ps);result=visit(i+1)
            if result:return result
            del placed[-len(ps):]
        if not ag['group'].required:return visit(i+1)
        return None
    result=visit(0)
    if result is None:raise Failure('placement_unsatisfiable','No valid arrangement within the search budget',searchNodes=nodes,rejectedConstraints=dict(failure_counts),lastFailures=last_failure)
    if architecture:
        layout,report=result
        for ag in assembled:
            if ag['group'].required:continue
            for ps in all_choices[ag['group'].id][:24]:
                if nodes>=req.maxSearchNodes or time.perf_counter()>deadline:break
                nodes+=1
                if not internal_valid(layout.placements+ps,assets,req.playerSize):
                    failure_counts['overlap_or_clearance']+=1;continue
                expanded=layout.model_copy(update={'placements':layout.placements+ps})
                checked=validate_layout(req,expanded,assets,architecture)
                if checked['valid']:
                    layout,report=expanded,checked
                    break
                failure_counts.update(f['code'] for f in checked['failures'])
        result=layout,report
    return *result,nodes,dict(failure_counts)

def validate(req,layout):
    try:
        effective,architecture,_,_=prepare(req)
        return validate_layout(effective,layout,asset_map(effective),architecture)
    except (Failure,GeometryFailure,SelectionFailure) as e:
        return {'valid':False,'failures':[e.reason]}


def validate_layout(req,layout,assets,architecture):
    failures=[]
    def fail(code,message,**details): failures.append({'code':code,'message':message,**details})
    bounds=(1,2,req.width-2,req.height-3)
    if (layout.width,layout.height,layout.playerSize,layout.seed)!=(req.width,req.height,req.playerSize,req.seed):fail('configuration_mismatch','Layout geometry does not match generation request')
    floor=architecture.floor if architecture else None
    room=architecture or (req.width,req.height)
    if layout.geometry!=(architecture.geometry if architecture else None):
        fail('geometry_mismatch','Floor, partitions, walls and doors must match generated architecture')
    specs={o.id:(o,g) for g in req.scene.groups for o in g.objects}; placed={p.id:p for p in layout.placements}
    if len(placed)!=len(layout.placements):fail('duplicate_placement','Duplicate placement ID')
    # Reject bad references before relationship evaluators dereference target assets.
    invalid=[p.id for p in layout.placements if p.id not in specs or p.assetId not in assets]
    if invalid:return {'valid':False,'failures':[{'code':'invalid_asset_reference','message':'Unknown placement or asset','objectIds':invalid}]}
    expected_zones={z.id for z in req.scene.zones}
    required_zones={z.id for z in req.scene.zones if z.required or not architecture}
    if not required_zones<=set(layout.zones)<=expected_zones:fail('invalid_zones','Zone IDs must match the scene')
    zone_masks={}
    if architecture:
        used=set()
        if set(layout.zoneCells or {})!=set(layout.zones):fail('invalid_zone_floor','All zones need a floor mask')
        for zid, cells in (layout.zoneCells or {}).items():
            mask={(c.x,c.y) for c in cells}
            zone_masks[zid]=mask
            if not mask or len(mask)!=len(cells) or mask-used != mask or not mask<=floor-architecture.circulation:
                fail('invalid_zone_floor','Zone contains invalid, overlapping or reserved cells',zoneId=zid)
                continue
            used.update(mask)
            if len(component(min(mask),mask))!=len(mask) or layout.zones.get(zid)!=zone_bounds(mask):
                fail('invalid_zone_floor','Zone floor must be contiguous and match its bounds',zoneId=zid)
    zone_values=list(layout.zones.items())
    for zid,z in zone_values:
        zr=(z.x,z.y,z.width,z.height)
        if not contains(bounds,zr):fail('zone_bounds','Zone outside playable bounds',zoneId=zid)
        spec=next((s for s in req.scene.zones if s.id==zid),None)
        area=len(zone_masks.get(zid,())) if architecture else z.width*z.height
        if spec and area<spec.minimumArea:fail('zone_area','Zone below minimum area',zoneId=zid)
    for i,(zid,z) in enumerate(zone_values):
        if not architecture and any(overlap((z.x,z.y,z.width,z.height),(o.x,o.y,o.width,o.height)) for _,o in zone_values[i+1:]):fail('zone_overlap','Functional areas overlap',zoneId=zid)
    expected_mid=req.width//2
    if architecture:
        if layout.entrance!=architecture.entrance or layout.exit!=architecture.exit:fail('invalid_door','Entrances must match the architecture')
        reserved={(x+.5,y+.5) for x,y in architecture.circulation}
    else:
        if (layout.entrance.x,layout.entrance.y)!=(expected_mid+.5,req.height-1.5) or (layout.exit.x,layout.exit.y)!=(expected_mid+.5,2.5):fail('invalid_door','Entrances must match the architecture')
        reserved={(x+.5,y+.5) for y in range(2,req.height-1) for x in range(expected_mid-1,expected_mid+2)}
    if {(p.x,p.y) for p in layout.circulation}!=reserved:fail('invalid_circulation','Reserved circulation data has been modified')
    safe=[]
    for p in layout.placements:
        if p.id not in specs or p.assetId not in assets:fail('invalid_asset_reference','Unknown placement',objectId=p.id);continue
        o,g=specs[p.id];a=assets[p.assetId]
        if p.assetId!=o.assetId or p.groupId!=g.id or p.zoneId!=g.zoneId:fail('scene_mismatch','Placement differs from semantic graph',objectId=p.id)
        if p.orientation!=o.orientation or p.orientation not in a.supportedOrientations:fail('unsupported_orientation','Unsupported or incorrect sprite orientation',objectId=p.id)
        if not a.approved:fail('unapproved_asset','Unapproved asset',objectId=p.id)
        if not contains(bounds,footprint(p,a)) or (architecture and not contains_floor(floor,footprint(p,a))):fail('room_bounds','Object outside playable floor',objectId=p.id)
        z=layout.zones.get(p.zoneId)
        if not z or not contains((z.x,z.y,z.width,z.height),footprint(p,a)) or (architecture and not contains_floor(zone_masks.get(p.zoneId,set()),footprint(p,a))):fail('zone_bounds','Object outside assigned zone',objectId=p.id)
        if not wall_ok(p,a,architecture):fail('wall_attachment','Asset requires a continuous north wall',objectId=p.id)
        if a.requiresSurface and (not p.parentId or not any(r.type=='attached_to_surface' for r in o.relations)):fail('surface_attachment','Missing support relationship',objectId=p.id)
        if p.parentId and not any(r.type=='attached_to_surface' and r.target==p.parentId for r in o.relations):fail('surface_attachment','Unexpected attachment parent',objectId=p.id)
        if not p.parentId and (p.socketId is not None or p.visualLift!=0):fail('invalid_visual_lift','Unsupported visual attachment offset',objectId=p.id)
        for r in o.relations:
            if r.mandatory and not check_relation(r,p,placed.get(r.target),assets,placed.get(g.anchorId),z,room,layout.zones):fail('relationship','Mandatory relationship violated',objectId=p.id,relationship=r.type)
        safe.append(p)
    for g in req.scene.groups:
        present=any(o.id in placed for o in g.objects)
        if g.required or present:
            for o in g.objects:
                if o.required and o.id not in placed:fail('missing_required_object','Required group member is absent',objectId=o.id,groupId=g.id)
    solids=[(p.id,collision(p,assets[p.assetId])) for p in safe if assets[p.assetId].solid]
    for i,(pid,box) in enumerate(solids):
        for qid,other in solids[i+1:]:
            if overlap(box,other):fail('physical_overlap','Solid footprints overlap',objectId=pid,otherId=qid)
        if any(overlap(box,(x-.5,y-.5,1,1)) for x,y in reserved):fail('blocked_circulation','Furniture blocks a reserved route',objectId=pid)
    sockets=[(p.parentId,p.socketId) for p in safe if p.parentId]
    if len(sockets)!=len(set(sockets)):fail('socket_occupied','A surface socket has multiple attachments')
    rects=[r for _,r in solids]
    walk,seen,parents=navigation(req.width,req.height,rects,layout.entrance,req.playerSize,floor)
    interaction_data=[];paths=[]
    for pid,pt,clearance in interactions(safe,assets,req.playerSize):
        approach=approach_path(pt,seen,rects,req.playerSize,bounds,floor)
        clearance_box=point_box(pt,req.playerSize+clearance*2)
        valid_clearance=contains(bounds,clearance_box) and (floor is None or contains_floor(floor,clearance_box)) and not any(overlap(clearance_box,r) for r in rects)
        if approach is None:fail('inaccessible_interaction','Interactive object cannot be reached',objectId=pid)
        if not valid_clearance:fail('clearance','Required interaction clearance is blocked',objectId=pid)
        interaction_data.append({'objectId':pid,'x':pt[0],'y':pt[1],'reachable':approach is not None,'clearance':clearance})
        if approach:
            cell,steps=approach
            paths.append({'target':pid,'points':path_to(cell,parents)+[{'x':x,'y':y} for x,y in steps]})
    doors=[(door.id,door.approach) for door in architecture.geometry.doors] if architecture else [('entrance',layout.entrance),('exit',layout.exit)]
    for label,pt in doors:
        cell=reachable((pt.x,pt.y),seen,rects,req.playerSize,bounds,floor)
        if cell is None:fail('blocked_door',f'{label} cannot be reached')
        elif architecture:paths.append({'target':label,'points':path_to(cell,parents)+[{'x':pt.x,'y':pt.y}]})
    for z in req.scene.zones:
        zr=layout.zones.get(z.id)
        accessible=bool(seen & zone_masks.get(z.id,set())) if architecture else zr and any(zr.x<=x+.5<zr.x+zr.width and zr.y<=y+.5<zr.y+zr.height for x,y in seen)
        if z.accessible and zr and not accessible:fail('inaccessible_zone','Functional zone cannot be reached',zoneId=z.id)
    # Unary clearance/path behaviors also apply to objects without declared interaction sockets.
    for p in safe:
        o,g=specs[p.id];a=assets[p.assetId]
        for r in o.relations:
            if not r.mandatory or r.type not in ['maintain_clearance','connected_to_walking_path']:continue
            box=footprint(p,a);points=[(box[0]+box[2]/2,box[1]+box[3]+.5),(box[0]-.5,box[1]+box[3]/2),(box[0]+box[2]+.5,box[1]+box[3]/2),(box[0]+box[2]/2,box[1]-.5)]
            if r.type=='connected_to_walking_path' and not any(reachable(pt,seen,rects,req.playerSize,bounds,floor) is not None for pt in points):fail('path_connection','No accessible approach',objectId=p.id)
            if r.type=='maintain_clearance':
                expanded=(box[0]-r.distance,box[1]-r.distance,box[2]+2*r.distance,box[3]+2*r.distance)
                if not contains(bounds,expanded) or (floor is not None and not contains_floor(floor,expanded)) or any(qid!=p.id and overlap(expanded,b) for qid,b in solids):fail('clearance','Object clearance radius violated',objectId=p.id)
    npc_data=[];used=set()
    door_approaches={(door.approach.x,door.approach.y) for door in architecture.geometry.doors} if architecture else set()
    for n in req.scene.npcs:
        group_points=[pt for pt in interaction_data if specs[pt['objectId']][1].id==n.groupId and pt['reachable']]
        choices=[]
        for pt in group_points:
            for x,y in sorted(seen,key=lambda c:math.dist((c[0]+.5,c[1]+.5),(pt['x'],pt['y']))):
                q=(x+.5,y+.5)
                if math.dist(q,(pt['x'],pt['y']))>2.5:break
                if q not in used and q not in (door_approaches if architecture else reserved):choices.append(q)
            if choices:break
            if architecture:
                # NPCs are nonblocking. An off-grid interaction point cleared by the
                # navigation validator also works as a position if no cell center fits.
                q=(pt['x'],pt['y'])
                if q not in used and all(math.dist(q,door)>1 for door in door_approaches):
                    choices.append(q);break
        if not choices:fail('inaccessible_npc','No valid NPC interaction position',npcId=n.id)
        else:
            q=choices[0];used.add(q);npc_data.append({'id':n.id,'name':n.name,'dialogue':n.dialogue,'x':q[0],'y':q[1],'interactionRadius':1.5})
    return {'valid':not failures,'failures':failures,'walkable':[{'x':x,'y':y} for x,y in sorted(walk)],'reachable':[{'x':x,'y':y} for x,y in sorted(seen)],'interactions':interaction_data,'paths':paths,'npcs':npc_data,'collisions':[{'objectId':pid,'x':b[0],'y':b[1],'width':b[2],'height':b[3]} for pid,b in solids]}

def score(req,layout,report,assets,architecture=None):
    ps=layout.placements;by_id={p.id:p for p in ps}
    centers=[center(p,assets[p.assetId]) for p in ps if assets[p.assetId].solid]
    organization=sum(1-min(1,math.dist(center(p,assets[p.assetId]),(layout.zones[p.zoneId].x+layout.zones[p.zoneId].width/2,layout.zones[p.zoneId].y+layout.zones[p.zoneId].height/2))/max(layout.zones[p.zoneId].width,layout.zones[p.zoneId].height)) for p in ps)/max(1,len(ps))
    relations=[(o,r,g) for g in req.scene.groups for o in g.objects if o.id in by_id for r in o.relations]
    room=architecture or (req.width,req.height)
    relationship=sum(check_relation(r,by_id[o.id],by_id.get(r.target),assets,by_id.get(g.anchorId),layout.zones[g.zoneId],room,layout.zones) for o,r,g in relations)/max(1,len(relations)) if relations else 1
    navigation_score=len(report['reachable'])/max(1,len(report['walkable']))
    centroid=(sum(c[0] for c in centers)/len(centers),sum(c[1] for c in centers)/len(centers)) if centers else (req.width/2,req.height/2)
    composition=max(0,1-math.dist(centroid,(req.width/2,req.height/2))/math.hypot(req.width/2,req.height/2))
    tags={t for p in ps for t in assets[p.assetId].tags}
    reference=len(tags.intersection(req.scene.referenceTags))/len(set(req.scene.referenceTags)) if req.scene.referenceTags else None
    details=sum(assets[p.assetId].renderLayer in ['surface_decoration','floor_decoration','wall_decoration'] for p in ps)
    target=max(1,len(centers)*req.decorationDensity)
    decoration=max(0,1-abs(details-target)/max(target,details,1))
    metrics=dict(organization=organization,relationships=relationship,navigation=navigation_score,composition=composition,reference=reference,decoration=decoration)
    weights=req.weights.model_dump();denom=sum(weights[k] for k,v in metrics.items() if v is not None)
    total=sum(v*weights[k] for k,v in metrics.items() if v is not None)/denom if denom else 0
    return {'total':round(total*100,3),'components':{k:round(v*100,3) if v is not None else None for k,v in metrics.items()},'referenceMethod':'semantic tag coverage' if reference is not None else 'not available; weight excluded'}

def generate(req):
    original=req
    started=time.perf_counter();deadline=started+req.timeoutMs/1000;attempts=[];valid=[]
    try:
        req,architecture,selection,seeds=prepare(req)
        assets=asset_map(req)
    except (Failure,GeometryFailure,SelectionFailure) as e:
        return {'ok':False,'diagnostics':{'seed':req.seed,'durationMs':round((time.perf_counter()-started)*1000,2),'attempted':0,'valid':0,'failures':[e.reason],'candidates':[]}}
    for i in range(req.candidates):
        if time.perf_counter()>deadline:break
        repairs=[]
        # A difficult geometry variant should leave time for a fresh zone allocation.
        attempt_deadline=deadline if architecture is None else min(deadline,time.perf_counter()+max(.2,(deadline-time.perf_counter())/(req.candidates-i)))
        try:
            try:layout,report,nodes,rejections=candidate(req,assets,i,attempt_deadline,architecture=architecture)
            except (Failure,ZoneCapacity) as initial:
                if initial.reason['code']=='time_budget':raise
                repairs.append({'action':'remove_optional_group_members','initialFailure':initial.reason})
                layout,report,nodes,rejections=candidate(req,assets,i,attempt_deadline,allow_optional=False,architecture=architecture)
            scores=score(req,layout,report,assets,architecture)
            entry={'index':i,'valid':True,'score':scores,'searchNodes':nodes,'repairs':repairs,'rejectedPlacements':rejections}
            valid.append((scores['total'],i,layout,report));attempts.append(entry)
        except (Failure,ZoneCapacity) as e:attempts.append({'index':i,'valid':False,'failures':[e.reason],'repairs':repairs})
    diagnostics={'seed':req.seed,'durationMs':round((time.perf_counter()-started)*1000,2),'attempted':len(attempts),'valid':len(valid),'rejected':len(attempts)-len(valid),'candidates':attempts,'failures':[],'budgetExceeded':time.perf_counter()>deadline}
    if architecture:
        diagnostics.update(seeds=seeds.model_dump(), geometry={'shape':architecture.geometry.shape,'width':req.width,'height':req.height,'floorCells':len(architecture.floor),'walls':len(architecture.walls),'doors':len(architecture.geometry.doors),'partitionCells':len(architecture.geometry.partitions)}, selection=selection)
    if not valid:
        diagnostics['failures']=[f for a in attempts for f in a.get('failures',[])] or [{'code':'time_budget','message':'Time budget exhausted before candidate search'}]
        return {'ok':False,'diagnostics':diagnostics}
    _,idx,layout,report=max(valid,key=lambda v:(v[0],-v[1]));diagnostics['selectedCandidate']=idx
    required=[o.id for g in req.scene.groups if g.required for o in g.objects if o.required];optional=[o.id for g in req.scene.groups for o in g.objects if not o.required or not g.required];ids={p.id for p in layout.placements}
    placed_groups={p.groupId for p in layout.placements}
    for choice in selection:
        choice['placed']=sum(group['groupId'] in placed_groups for group in choice['instances'])
    diagnostics.update(requiredPlacementRate=sum(i in ids for i in required)/max(1,len(required)),optionalPlacementRate=sum(i in ids for i in optional)/len(optional) if optional else 1,mandatoryAccessibility=all(p['reachable'] for p in report['interactions']))
    layers={layer:[] for layer in LAYERS}
    for p in layout.placements:layers[assets[p.assetId].renderLayer].append(p.id)
    used={p.assetId for p in layout.placements}|{'player','npc','wood_floor','stone_floor','north_wall','side_wall','door'}
    result={'ok':True,'layout':layout.model_dump(),'validation':report,'diagnostics':diagnostics,'layers':layers,'assets':[a.model_dump() for a in assets.values() if a.id in used],'scene':req.scene.model_dump(),'reproduction':original.model_dump()}
    # Asset snapshots pin metadata versions even if the catalog changes later.
    result['reproduction']['assets']=[a.model_dump() for a in assets.values()]
    if architecture:
        result['reproduction'].update(seeds=seeds.model_dump(),geometry=req.geometry.model_dump(),
                                      density=req.density,decorationDensity=req.decorationDensity)
    result['stages']={'architecture':{'entrance':layout.entrance.model_dump(),'exit':layout.exit.model_dump()},'zones':{k:v.model_dump() for k,v in layout.zones.items()},'groups':[{'id':g.id,'anchorId':g.anchorId,'members':[o.id for o in g.objects]} for g in req.scene.groups],'validation':{'valid':report['valid'],'failures':report['failures']}}
    return result
