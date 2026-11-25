import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from services.engine.models import GenerateRequest, Scene, Asset, ValidateRequest, PlanRequest
for name,model in [('generate',GenerateRequest),('scene',Scene),('asset',Asset),('validate',ValidateRequest),('plan',PlanRequest)]:
    (root/f'packages/shared/{name}.schema.json').write_text(json.dumps(model.model_json_schema(),indent=2)+'\n')
print('Exported shared JSON Schema contracts from Pydantic.')
