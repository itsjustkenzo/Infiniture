from collections import deque
import math

EPS=1e-7

def overlap(a,b):
    return a[0]<b[0]+b[2]-EPS and a[0]+a[2]>b[0]+EPS and a[1]<b[1]+b[3]-EPS and a[1]+a[3]>b[1]+EPS

def contains(a,b):
    return b[0]>=a[0]-EPS and b[1]>=a[1]-EPS and b[0]+b[2]<=a[0]+a[2]+EPS and b[1]+b[3]<=a[1]+a[3]+EPS

def collision(p,a):
    return (p.x+a.collision.x,p.y+a.collision.y,a.collision.width,a.collision.height)

def footprint(p,a): return (p.x,p.y,a.footprint.width,a.footprint.height)
def center(p,a): return (p.x+a.footprint.width/2,p.y+a.footprint.height/2)
def point_box(p,size): return (p[0]-size/2,p[1]-size/2,size,size)
def distance(a,b):
    return math.hypot(max(a[0]-b[0]-b[2], b[0]-a[0]-a[2],0),max(a[1]-b[1]-b[3],b[1]-a[1]-a[3],0))

def segment_clear(a,b,solids,size,bounds):
    # Axis-aligned segment swept rectangle. Diagonals conservatively test bounding sweep.
    swept=(min(a[0],b[0])-size/2,min(a[1],b[1])-size/2,abs(a[0]-b[0])+size,abs(a[1]-b[1])+size)
    return contains(bounds,swept) and not any(overlap(swept,r) for r in solids)

def navigation(width,height,solids,entrance,size):
    bounds=(1,2,width-2,height-3)
    walk=set()
    for y in range(2,height-1):
        for x in range(1,width-1):
            b=point_box((x+.5,y+.5),size)
            if contains(bounds,b) and not any(overlap(b,r) for r in solids): walk.add((x,y))
    start=(int(entrance.x),int(entrance.y))
    seen={start} if start in walk else set(); parents={start:None} if seen else {}; queue=deque(seen)
    while queue:
        x,y=queue.popleft()
        for q in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
            if q in walk and q not in seen and segment_clear((x+.5,y+.5),(q[0]+.5,q[1]+.5),solids,size,bounds):
                seen.add(q);parents[q]=(x,y);queue.append(q)
    return walk,seen,parents

def reachable(point,seen,solids,size,bounds):
    x,y=point
    for gx in range(math.floor(x)-1,math.floor(x)+2):
        for gy in range(math.floor(y)-1,math.floor(y)+2):
            if (gx,gy) in seen and segment_clear((gx+.5,gy+.5),point,solids,size,bounds): return (gx,gy)
    return None

def path_to(cell,parents):
    path=[]
    while cell is not None:
        path.append({'x':cell[0]+.5,'y':cell[1]+.5});cell=parents.get(cell)
    return list(reversed(path))
