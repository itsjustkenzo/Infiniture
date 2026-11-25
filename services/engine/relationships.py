import math
from .geometry import footprint,center,distance,contains,EPS
from .architecture import Architecture

LOCAL_UNARY={'against_wall','along_wall','attached_to_wall','inside_corner','centered_within_zone','separated_from_zone','maintain_clearance','connected_to_walking_path'}

def check_relation(r,p,target,assets,anchor=None,zone=None,room=None,zones=None):
    a=assets[p.assetId]; box=footprint(p,a); c=center(p,a); k=r.type
    if k in ['maintain_clearance','connected_to_walking_path']:
        return True # Independently verified by navigation/clearance validator, not aesthetic inference.
    if k in ['against_wall','along_wall','attached_to_wall','inside_corner']:
        if room is None:return True
        if isinstance(room, Architecture):
            edges = {side: room.touches_wall(box, side) for side in ('north','south','west','east')}
        else:
            w,h=room; edges={'north':abs(p.y-2)<EPS,'south':abs(p.y+a.footprint.height-(h-1))<EPS,'west':abs(p.x-1)<EPS,'east':abs(p.x+a.footprint.width-(w-1))<EPS}
        if k=='inside_corner':return (edges['north'] or edges['south']) and (edges['east'] or edges['west'])
        return edges[r.wall]
    if k=='centered_within_zone':
        return zone is None or math.dist(c,(zone.x+zone.width/2,zone.y+zone.height/2))<=r.distance+.5
    if k=='separated_from_zone':
        if zones is None or r.target not in zones:return True
        z=zones[r.target];return distance(box,(z.x,z.y,z.width,z.height))>=r.distance-EPS
    if target is None:return False
    ta=assets[target.assetId];tb=footprint(target,ta);tc=center(target,ta);d=distance(box,tb)
    if k=='attached_to_surface':
        return p.parentId==target.id and any(s.id==p.socketId and (not r.socket or s.id==r.socket) and a.category in s.categories and abs(p.x-target.x-s.x)<EPS and abs(p.y-target.y-s.y)<EPS and abs(p.visualLift-s.visualLift)<EPS for s in ta.surfaceSockets) and contains(tb,box)
    if k=='under_object':return a.renderLayer=='floor_decoration' and contains(box,tb)
    if k=='above_object':return p.y+a.footprint.height<=target.y+EPS and abs(c[0]-tc[0])<.51 and d<=r.distance+EPS
    if k in ['near_object','clustered_with_objects','maximum_distance']:return d<=r.distance+EPS
    if k=='minimum_distance':return d>=r.distance-EPS
    if k=='adjacent_to_object':return abs(d-r.distance)<.51 and (abs(c[0]-tc[0])<.51 or abs(c[1]-tc[1])<.51)
    if k=='aligned_with_object':return abs(c[0]-tc[0])<.51 if r.axis=='x' else abs(c[1]-tc[1])<.51
    if k=='parallel_to_object':return p.orientation==target.orientation and d<=r.distance+EPS
    if k=='symmetrical_to_object':
        if anchor is None:return False
        ac=center(anchor,assets[anchor.assetId]);desired=(2*ac[0]-tc[0],tc[1]) if r.axis=='x' else (tc[0],2*ac[1]-tc[1])
        return math.dist(c,desired)<.51
    if k=='repeated_arrangement':return p.assetId==target.assetId and (abs(c[0]-tc[0])<.51 or abs(c[1]-tc[1])<.51) and abs(d-r.distance)<.51
    if k in ['facing_object','surround_object']:
        dx,dy=tc[0]-c[0],tc[1]-c[1]
        aligned=(abs(dx)<.51 or abs(dy)<.51)
        facing={'north':dy<0 and abs(dx)<.51,'south':dy>0 and abs(dx)<.51,'east':dx>0 and abs(dy)<.51,'west':dx<0 and abs(dy)<.51}[p.orientation]
        return aligned and d<=r.distance+EPS and (facing if k=='facing_object' else True)
    return False
