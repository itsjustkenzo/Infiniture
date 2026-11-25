from fastapi import FastAPI
from .models import GenerateRequest,ValidateRequest,PlanRequest,Asset,BEHAVIORS,LAYERS,InspectAssetRequest
from PIL import Image
import base64,io
from .planner import plan, mock_room
from .solver import generate,validate
from .catalog import catalog

app=FastAPI(title='Infiniture spatial engine',version='0.1.0')

@app.get('/health')
def health():return {'status':'ok','service':'engine','schemaVersion':'1.0'}

@app.get('/assets')
def assets():return [a.model_dump() for a in catalog()]

@app.get('/capabilities')
def capabilities():return {'behaviors':BEHAVIORS,'layers':LAYERS,'perspective':'top-down front surfaces','tileSize':16}

@app.post('/plan')
def plan_scene(req:PlanRequest):
    return {'scene':plan(req).model_dump(),'room':mock_room(req).model_dump(),'mode':'mock',
            'notice':'Planned from the offline room vocabulary. You can edit category requirements in Scene planner.'}

@app.post('/generate')
def generate_layout(req:GenerateRequest):return generate(req)

@app.post('/validate')
def validate_layout(req:ValidateRequest):return validate(req.request,req.layout)

@app.post('/assets/validate')
def validate_asset(asset:Asset):return {'valid':True,'asset':asset.model_dump()}

@app.post('/assets/inspect')
def inspect_asset(req:InspectAssetRequest):
    try:
        raw=base64.b64decode(req.pngBase64,validate=True)
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='PNG':return {'valid':False,'failures':['Sprite must be a PNG']}
            if im.size!=(req.asset.spriteSize.width,req.asset.spriteSize.height):return {'valid':False,'failures':['Sprite dimensions do not match metadata']}
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            alpha=im.convert('RGBA').getchannel('A')
            transparency=alpha.getextrema()[0]<255
            if req.asset.renderLayer not in ['floor','wall'] and not transparency:return {'valid':False,'failures':['Non-architectural sprites must have a transparent background']}
            return {'valid':True,'dimensions':{'width':im.width,'height':im.height},'hasTransparency':transparency,'requiresVisualReview':['perspective','proportions','lighting','style','pixel density']}
    except Exception:
        return {'valid':False,'failures':['Invalid or corrupt PNG data']}
