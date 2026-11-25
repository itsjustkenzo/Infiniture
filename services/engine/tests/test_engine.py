import copy,json,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from services.engine.app import app
from services.engine.models import GenerateRequest,PlanRequest,Scene,Asset,Layout,Relation,Placement
from services.engine.catalog import catalog
from services.engine.planner import plan,CONCEPTS
from services.engine.solver import generate,validate,assemble,Failure
from services.engine.geometry import overlap,collision,point_box,navigation,reachable
from services.engine.relationships import check_relation

def request(concept='tavern',**kw):
    density=kw.get('density',.5)
    return GenerateRequest(scene=plan(PlanRequest(description=concept,density=density)),candidates=2,**kw)

@pytest.fixture(scope='module')
def room():
    req=request();result=generate(req);assert result['ok'];return req,result

def test_catalog():
    assets=catalog();assert len(assets)==32;assert all(a.placeholder and a.approved for a in assets)
    from PIL import Image
    root=Path(__file__).resolve().parents[3]
    for a in assets:
        for url in a.orientationSprites.values():
            im=Image.open(root/'apps/web/public'/url.lstrip('/'))
            assert im.size==(a.spriteSize.width,a.spriteSize.height)
            assert im.mode=='RGBA'

def test_100_seeded_layouts():
    rows=[]
    for ci,concept in enumerate(CONCEPTS):
        for seed in range(10):
            req=request(concept,width=[24,28,32,36][seed%4],height=[22,24,28][seed%3],seed=ci*1000+seed,density=[.3,.5,.85][seed%3])
            result=generate(req)
            row={'concept':concept,'seed':req.seed,'width':req.width,'height':req.height,'density':req.density,'accepted':result['ok'],'durationMs':result['diagnostics']['durationMs']}
            if result['ok']:
                report=validate(req,Layout.model_validate(result['layout']))
                assert report['valid'],report['failures']
                solids=report['collisions']
                for i,a in enumerate(solids):
                    assert not any(overlap((a['x'],a['y'],a['width'],a['height']),(b['x'],b['y'],b['width'],b['height'])) for b in solids[i+1:])
                assert result['diagnostics']['requiredPlacementRate']==1
                assert result['diagnostics']['mandatoryAccessibility']
                assert all(p['reachable'] for p in report['interactions'])
                again=generate(req)
                assert again['ok'] and again['layout']==result['layout']
                row.update(hardViolations=len(report['failures']),requiredPlacementRate=1,reachableInteractions=len(report['interactions']),reproducible=True)
            else:row['failures']=result['diagnostics']['failures']
            rows.append(row)
    accepted=sum(r['accepted'] for r in rows)
    report={'cases':len(rows),'accepted':accepted,'rejected':len(rows)-accepted,'validGenerationRate':accepted/len(rows),'maxDurationMs':max(r['durationMs'] for r in rows),'results':rows}
    path=Path(__file__).resolve().parents[3]/'docs/seeded-test-results.json';path.write_text(json.dumps(report,indent=2))
    assert accepted==100,[(r['concept'],r['seed'],r.get('failures')) for r in rows if not r['accepted']]

def test_reject_impossible():
    req=request(width=12,height=12)
    req.scene.zones[0].minimumArea=500;req.scene.zones[0].preferredArea=500
    result=generate(req);assert not result['ok'];assert 'layout' not in result
    assert result['diagnostics']['failures'][0]['code']=='zone_capacity'

def test_missing_asset_and_approval():
    req=request();req.scene.groups[0].objects[0].assetId='missing'
    assert generate(req)['diagnostics']['failures'][0]['code']=='missing_asset'
    req=request();req.assets=catalog();req.assets[10].approved=False
    assert generate(req)['diagnostics']['failures'][0]['code']=='unapproved_asset'

def test_invalid_metadata_and_orientation():
    a=catalog()[10].model_dump();a['collision']['width']=200
    with pytest.raises(ValidationError):Asset.model_validate(a)
    a=catalog()[10].model_dump();del a['anchor']
    with pytest.raises(ValidationError):Asset.model_validate(a)
    req=request();req.scene.groups[0].objects[0].orientation='east'
    assert generate(req)['diagnostics']['failures'][0]['code']=='unsupported_orientation'

def test_unsupported_relation_and_missing_reference():
    with pytest.raises(ValidationError):Relation(type='teleport_on_top')
    scene=plan(PlanRequest(description='office')).model_dump();scene['groups'][0]['objects'][1]['relations'][0]['target']='unknown'
    with pytest.raises(ValidationError):Scene.model_validate(scene)

def test_cyclic_dependencies():
    req=request();g=req.scene.groups[0];g.objects[0].relations=[Relation(type='near_object',target=g.objects[1].id)]
    result=generate(req);assert not result['ok'];assert result['diagnostics']['failures'][0]['code']=='anchor_dependency'

def test_tampering_blocked_door_overlap_and_required(room):
    req,result=room
    layout=Layout.model_validate(result['layout']);p=layout.placements[0];p.x=layout.entrance.x;p.y=layout.entrance.y-1
    report=validate(req,layout);assert not report['valid'];assert any(f['code']=='blocked_circulation' for f in report['failures'])
    layout=Layout.model_validate(result['layout']);solids=[p for p in layout.placements if p.assetId in ['counter','table']];solids[1].x=solids[0].x;solids[1].y=solids[0].y
    assert any(f['code']=='physical_overlap' for f in validate(req,layout)['failures'])
    layout=Layout.model_validate(result['layout']);layout.placements=[p for p in layout.placements if p.id!='group_0_anchor']
    assert any(f['code']=='missing_required_object' for f in validate(req,layout)['failures'])

def test_surface_support_and_rug(room):
    req,result=room;layout=Layout.model_validate(result['layout']);detail=next(p for p in layout.placements if p.assetId=='candle')
    assert detail.parentId and detail.socketId
    detail.x+=1
    assert any(f['code']=='relationship' for f in validate(req,layout)['failures'])
    assert any(p.assetId=='carpet' for p in layout.placements)

def test_player_size_blocks_narrow_corridor():
    from services.engine.models import Point
    solids=[(1,2,4.1,9),(5.9,2,5.1,9)]
    small,seen,_=navigation(12,12,solids,Point(x=5.5,y=9.5),.55)
    big,bseen,_=navigation(12,12,solids,Point(x=5.5,y=9.5),1)
    assert (5,3) in seen and not bseen

def test_measurements_no_reference_fabrication(room):
    req,result=room
    scores=result['diagnostics']['candidates'][0]['score']
    assert scores['components']['reference'] is None
    assert scores['components']['navigation']==100
    assert scores['components']['relationships']==100

def test_api_contracts():
    client=TestClient(app)
    assert client.get('/health').status_code==200
    assert client.post('/generate',json={'scene':{}}).status_code==422
    assert client.post('/plan',json={'description':'library'}).status_code==200
    req=request('bedroom');r=client.post('/generate',json=req.model_dump());assert r.status_code==200 and r.json()['ok']
    assert client.post('/validate',json={'request':req.model_dump(),'layout':r.json()['layout']}).json()['valid']

def test_behavior_predicates():
    assets={a.id:a for a in catalog()}
    def p(id,asset,x,y,orientation='south',**kw):return Placement(id=id,assetId=asset,groupId='g',zoneId='z',x=x,y=y,orientation=orientation,**kw)
    table=p('table','table',4,4);chair=p('chair','chair',5,7.5,'north');anchor=p('anchor','crate',5,5)
    cases=[('facing_object',chair,table,2,True),('facing_object',chair.model_copy(update={'orientation':'south'}),table,2,False),('near_object',chair,table,2,True),('maximum_distance',chair,table,.1,False),('minimum_distance',chair,table,1,True),('surround_object',chair,table,2,True),('aligned_with_object',chair,table,1,True),('above_object',p('p','chair',5,2),table,2,True),('parallel_to_object',p('p','chair',8,4),table,2,True),('adjacent_to_object',p('p','chair',8,4.5),table,1,True),('clustered_with_objects',chair,table,2,True),('under_object',p('p','carpet',3,3),table,1,True),('repeated_arrangement',p('p','crate',7,5),anchor,1,True),('symmetrical_to_object',p('p','crate',3,5),p('t','crate',7,5),1,True)]
    for kind,item,target,dist,expected in cases:
        assert check_relation(Relation(type=kind,target=target.id,distance=dist),item,target,assets,anchor)==expected,kind

def test_wall_and_clearance_violations(room):
    req,result=room
    req=request('library');result=generate(req);assert result['ok']
    layout=Layout.model_validate(result['layout']);shelf=next(p for p in layout.placements if p.assetId=='bookshelf');shelf.y+=1
    assert any(f['code']=='wall_attachment' for f in validate(req,layout)['failures'])

def test_config_tampering(room):
    req,result=room;layout=Layout.model_validate(result['layout']);layout.circulation=[]
    assert any(f['code']=='invalid_circulation' for f in validate(req,layout)['failures'])

def test_budget_and_optional_repair():
    req=request(width=14,height=12);result=generate(req)
    assert not result['ok']
    assert all('repairs' in c for c in result['diagnostics']['candidates'])

def test_generic_unfamiliar_scene():
    scene=Scene.model_validate({'title':'Astral archive','zones':[{'id':'z','purpose':'Star reading','minimumArea':20,'preferredArea':60}], 'groups':[{'id':'g','zoneId':'z','anchorId':'lens','objects':[{'id':'lens','assetId':'desk'},{'id':'observer','assetId':'chair','orientation':'north','relations':[{'type':'facing_object','target':'lens','distance':2}]},{'id':'instrument','assetId':'computer','relations':[{'type':'attached_to_surface','target':'lens','socket':'top0'}]}]}]})
    result=generate(GenerateRequest(scene=scene,candidates=1));assert result['ok']
    assert len(result['layout']['placements'])==3

@pytest.mark.parametrize('behavior',['against_wall','along_wall','attached_to_wall','inside_corner','centered_within_zone','maintain_clearance','connected_to_walking_path'])
def test_unary_behaviors_generate_valid_layout(behavior):
    # A one-tile crate's 1.05-tile interaction clearance cannot touch a side wall;
    # use a two-tile chest to test corner placement with feasible metadata.
    aid='painting' if behavior=='attached_to_wall' else 'chest' if behavior=='inside_corner' else 'crate'
    scene=Scene.model_validate({'title':'Generic unary rule','zones':[{'id':'z','purpose':'Testing','minimumArea':16,'preferredArea':40}], 'groups':[{'id':'g','zoneId':'z','anchorId':'a','objects':[{'id':'a','assetId':aid,'relations':[{'type':behavior,'distance':.5}]}]}]})
    req=GenerateRequest(scene=scene,candidates=1);result=generate(req)
    assert result['ok'],result['diagnostics']
    assert validate(req,Layout.model_validate(result['layout']))['valid']

def test_multiple_chairs_are_assembled_as_one_group():
    scene=Scene.model_validate({'title':'Dining council','zones':[{'id':'z','purpose':'Discussion'}],'groups':[{'id':'g','zoneId':'z','anchorId':'t','objects':[{'id':'t','assetId':'table'},{'id':'left','assetId':'chair','orientation':'east','relations':[{'type':'facing_object','target':'t','distance':1}]},{'id':'right','assetId':'chair','orientation':'west','relations':[{'type':'facing_object','target':'t','distance':1}]},{'id':'south','assetId':'chair','orientation':'north','relations':[{'type':'facing_object','target':'t','distance':2}]}]}]})
    result=generate(GenerateRequest(scene=scene,candidates=1));assert result['ok'];assert len(result['layout']['placements'])==4

def test_sprite_inspection_rejects_corruption_and_opaque_background():
    import base64,io
    from PIL import Image
    client=TestClient(app);asset=catalog()[10]
    raw=io.BytesIO();Image.new('RGBA',(int(asset.spriteSize.width),int(asset.spriteSize.height)),(100,100,100,255)).save(raw,format='PNG')
    body={'asset':asset.model_dump(),'pngBase64':base64.b64encode(raw.getvalue()).decode()}
    assert not client.post('/assets/inspect',json=body).json()['valid']
    body['pngBase64']='bad data'
    assert not client.post('/assets/inspect',json=body).json()['valid']

def test_invalid_target_asset_does_not_crash_validator(room):
    req,result=room;layout=Layout.model_validate(result['layout']);layout.placements[0].assetId='unknown'
    report=validate(req,layout);assert not report['valid'];assert report['failures'][0]['code']=='invalid_asset_reference'
