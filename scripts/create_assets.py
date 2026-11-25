"""Original, intentionally simple placeholder pixel sprites; no external artwork."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'apps/web/public/assets'
OUT.mkdir(parents=True, exist_ok=True)
(ROOT/'packages/shared').mkdir(parents=True, exist_ok=True)
INK='#302b39'; WOOD='#946443'; LIGHT='#c59663'; DARK='#61442f'; GREEN='#678c65'
specs=[
 ('wood_floor','Wood floor','architecture',1,1,'floor',False),('stone_floor','Stone floor','architecture',1,1,'floor',False),
 ('north_wall','North wall','architecture',1,1,'wall',False),('side_wall','Side wall','architecture',1,1,'wall',False),('door','Door','architecture',2,1,'wall',False),('window','Window','wall_art',2,1,'wall_decoration',False),
 ('round_table','Round table','table',3,2,'furniture',True),('table','Oak table','table',3,2,'furniture',True),('chair','Chair','seating',1,1,'furniture',True),('stool','Stool','seating',1,1,'furniture',True),
 ('counter','Counter','counter',4,1,'furniture',True),('bookshelf','Bookshelf','storage',3,1,'furniture',True),('cabinet','Cabinet','storage',2,1,'furniture',True),('bed','Bed','bed',2,3,'furniture',True),('desk','Desk','table',3,1,'furniture',True),('bench','Bench','seating',3,1,'furniture',True),
 ('barrel','Barrel','storage',1,1,'furniture',True),('crate','Crate','storage',1,1,'furniture',True),('chest','Chest','storage',2,1,'furniture',True),('shelf','Storage shelf','storage',3,1,'furniture',True),
 ('carpet','Woven rug','rug',5,4,'floor_decoration',False),('candle','Candle','surface_detail',.5,.5,'surface_decoration',False),('plate','Plate','surface_detail',.5,.5,'surface_decoration',False),('mug','Mug','surface_detail',.5,.5,'surface_decoration',False),
 ('plant','Fern','plant',1,1,'furniture',True),('painting','Painting','wall_art',2,1,'wall_decoration',False),('wall_lamp','Wall lantern','wall_art',1,1,'wall_decoration',False),('lamp','Standing lamp','light',1,1,'furniture',True),
 ('computer','Computer','surface_detail',1,.5,'surface_decoration',False),('anvil','Anvil','equipment',2,1,'furniture',True),('player','Explorer','character',1,1,'player',False),('npc','Caretaker','character',1,1,'npc',False)]
assets=[]
for aid,name,cat,fw,fh,layer,solid in specs:
    sw=int(fw*16); lift=0 if layer in ['floor','floor_decoration'] else (24 if aid in ['bookshelf','shelf','cabinet'] else 8)
    sh=int(fh*16)+lift
    if cat=='character': sw,sh=16,24
    if cat=='surface_detail': sw,sh=max(8,sw),16
    im=Image.new('RGBA',(sw,sh)); d=ImageDraw.Draw(im)
    def rect(box,fill,outline=INK): d.rectangle(box,fill=fill,outline=outline)
    if layer=='floor':
        rect((0,0,sw-1,sh-1),'#99764e' if aid=='wood_floor' else '#737780','#715437' if aid=='wood_floor' else '#545761')
        d.line((0,7,15,7),fill='#b08c61'); d.line((7,0,7,7),fill='#715437')
    elif aid=='north_wall':
        rect((0,0,15,sh-1),'#b1a18a'); rect((0,0,15,3),DARK); rect((0,sh-5,15,sh-1),DARK); d.line((0,12,15,12),fill='#97856f')
    elif aid=='side_wall': rect((6,0,10,sh-1),DARK)
    elif aid=='door':
        rect((0,0,sw-1,sh-1),DARK); rect((4,3,sw-5,sh-1),'#322e38'); d.line((5,sh-3,sw-6,sh-3),fill=LIGHT)
    elif aid=='carpet':
        rect((0,0,sw-1,sh-1),'#824a55'); rect((3,3,sw-4,sh-4),'#c48c6a'); rect((5,5,sw-6,sh-6),'#754853')
        for x in range(10,sw-8,12): d.polygon([(x,sh//2-5),(x+4,sh//2),(x,sh//2+5),(x-4,sh//2)], fill='#c48c6a')
    elif cat=='character':
        d.ellipse((3,20,13,23),fill='#302b3970'); rect((5,17,7,22),'#3f414e'); rect((10,17,12,22),'#3f414e'); rect((3,10,13,18),'#77a8a1' if aid=='player' else '#b77c5e'); rect((4,2,12,10),'#deb48b'); rect((3,1,13,4),'#61442f'); d.point((10,7), fill=INK)
    elif cat=='surface_detail':
        if aid=='computer':
            rect((1,1,sw-2,10),'#515d66'); rect((3,3,sw-4,8),'#80b6aa'); rect((sw//2-1,11,sw//2+1,14),'#515d66')
        elif aid=='candle':
            d.ellipse((0,11,7,15),fill=LIGHT); rect((3,5,5,12),'#e7d9ad'); d.point((4,2),fill='#ffe1a1'); d.point((4,3),fill='#e9a75c')
        elif aid=='plate': d.ellipse((0,9,7,14),fill='#ddd9c5',outline='#9aa3a1')
        else: rect((1,8,5,13),'#b3bdb5'); d.arc((4,8,7,12),270,90,fill='#ddd9c5')
    elif cat=='wall_art':
        rect((0,0,sw-1,sh-3),DARK); rect((3,3,sw-4,sh-6),'#729c9b' if aid=='window' else '#6b8067'); d.line((sw//2,3,sw//2,sh-6),fill=LIGHT)
    elif aid in ['bookshelf','shelf','cabinet']:
        rect((0,0,sw-1,sh-1),DARK); rect((3,3,sw-4,sh-4),WOOD)
        for yy in [8,23]:
            for xx in range(5,sw-5,6): rect((xx,yy,xx+3,yy+8),['#9f635a','#7b9292','#c4aa70'][(xx//6)%3])
            d.line((2,yy+10,sw-3,yy+10),fill=LIGHT,width=2)
    elif aid=='bed':
        rect((0,0,sw-1,sh-1),DARK); rect((3,5,sw-4,sh-6),'#567b89'); rect((4,6,sw-5,16),'#ded2b5'); rect((3,20,sw-4,sh-8),'#759d9b'); d.line((5,22,sw-6,22),fill='#a4beb0')
    elif aid=='plant':
        rect((4,sh-9,12,sh-2),WOOD); d.line((8,5,8,sh-8),fill=GREEN,width=2)
        for xx,yy in [(1,3),(7,0),(9,6),(0,10)]: d.ellipse((xx,yy,xx+6,yy+7),fill=GREEN,outline='#48654c')
    elif aid in ['barrel','crate','chest']:
        rect((1,4,sw-2,sh-2),WOOD); rect((2,3,sw-3,7),LIGHT); d.line((2,sh-7,sw-3,sh-7),fill='#555762',width=2)
        if aid=='crate': d.line((2,6,sw-3,sh-3),fill=LIGHT,width=2)
    elif aid in ['chair','stool']:
        rect((3,12,5,sh-1),DARK); rect((11,12,13,sh-1),DARK); rect((1,9,14,17),WOOD); d.line((2,10,13,10),fill=LIGHT)
        if aid=='chair': rect((1,1,14,7),WOOD); d.line((2,2,13,2),fill=LIGHT)
    elif aid=='lamp':
        rect((7,6,9,sh-3),LIGHT); d.ellipse((2,sh-6,14,sh-1),fill=DARK); d.polygon([(4,0),(12,0),(15,8),(1,8)],fill='#d2bd83',outline=INK)
    else:
        rect((3,sh-10,6,sh-1),DARK); rect((sw-7,sh-10,sw-4,sh-1),DARK)
        color='#727c85' if aid=='anvil' else WOOD
        if aid=='round_table': d.ellipse((0,0,sw-1,sh-8),fill=color,outline=INK)
        else: rect((0,0,sw-1,sh-8),color)
        d.line((4,3,sw-5,3),fill=LIGHT); d.line((3,sh-10,sw-4,sh-10),fill=DARK)
    im.save(OUT/f'{aid}.png')
    orientations=['south']
    if aid in ['chair','stool','player','npc']: orientations=['south','north','east','west']
    paths={o:f'/assets/{aid}.png' for o in orientations}
    if aid=='chair':
        for o in ['north','east','west']:
            ci=Image.new('RGBA',(sw,sh)); cd=ImageDraw.Draw(ci)
            cd.rectangle((3,12,5,23),fill=DARK); cd.rectangle((11,12,13,23),fill=DARK); cd.rectangle((1,9,14,17),fill=WOOD,outline=INK)
            box={'north':(1,13,14,19),'east':(1,3,5,15),'west':(10,3,14,15)}[o]
            cd.rectangle(box,fill=LIGHT,outline=INK); ci.save(OUT/f'{aid}_{o}.png'); paths[o]=f'/assets/{aid}_{o}.png'
    if cat=='character':
        sheet=Image.new('RGBA',(16*3,24*4))
        for row,o in enumerate(['south','west','east','north']):
            for frame in range(3):
                fr=im.copy(); fd=ImageDraw.Draw(fr)
                fd.rectangle((4,5,12,9),fill='#deb48b')
                if o=='north': fd.rectangle((4,2,12,9),fill=DARK)
                else: fd.point((5 if o=='west' else 11,7),fill=INK)
                if frame: fd.rectangle((5 if frame==1 else 10,21,7 if frame==1 else 12,23),fill='#3f414e')
                sheet.paste(fr,(frame*16,row*24))
        sheet.save(OUT/f'{aid}_walk.png')
    sockets=[]
    if cat in ['table','counter']:
        sockets=[{'id':f'top{i}','x':x,'y':.25,'categories':['surface_detail'],'visualLift':.5} for i,x in enumerate([.5,fw-1])]
    wall=aid in ['bookshelf','cabinet','shelf'] or cat=='wall_art'
    interaction=[{'x':fw/2,'y':fh+.8}] if solid and cat not in ['plant','light','seating'] else []
    assets.append(dict(schemaVersion='1.0',version=1,id=aid,name=name,category=cat,tags=[cat,aid],purpose=[cat],sprite=f'/assets/{aid}.png',styleId='hearth_pixel',pixelDensity=16,spriteSize={'width':sw,'height':sh},footprint={'width':fw,'height':fh},collision={'x':0,'y':0,'width':fw,'height':fh},visualBounds={'x':0,'y':0,'width':sw,'height':sh},anchor={'x':sw/2,'y':sh},supportedOrientations=orientations,orientationSprites=paths,placementBehaviors=['against_wall'] if wall else (['attached_to_surface'] if cat=='surface_detail' else ['under_object'] if cat=='rug' else ['near_object','centered_within_zone']),requiresWall=wall,requiresSurface=cat=='surface_detail',surfaceSockets=sockets,wallSockets=[],interactionPoints=interaction,interactionClearance=.25 if interaction else 0,preferredZones=[cat],compatibleCategories=[cat],renderLayer=layer,depthOffset=0,solid=solid,approved=True,placeholder=True))
(ROOT/'packages/shared/assets.json').write_text(json.dumps(assets,indent=2)+'\n')
print(f'Created {len(assets)} original placeholder assets with validated metadata inputs.')
