import json
from pathlib import Path
from .models import Asset

ROOT = Path(__file__).resolve().parents[2]

def catalog():
    return [Asset.model_validate(a) for a in json.loads((ROOT/'packages/shared/assets.json').read_text())]
