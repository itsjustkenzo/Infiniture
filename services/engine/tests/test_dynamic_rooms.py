import pytest
from fastapi.testclient import TestClient

from services.engine.app import app
from services.engine.architecture import DIRECTIONS, component
from services.engine.catalog import catalog
from services.engine.geometry import box_cells, collision, footprint, overlap
from services.engine.models import GenerateRequest, GenerationSeeds, GeometryOptions, Layout, PlanRequest
from services.engine.planner import mock_room
from services.engine.solver import generate, validate

CONCEPTS = ('tavern', 'bedroom', 'library', 'office', 'kitchen', 'shop', 'warehouse', 'classroom')
SHAPES = ('rectangle', 'square', 'l_shape', 'alcove', 'orthogonal')


def request(concept='tavern', shape='l_shape', **overrides):
    options = dict(room=mock_room(PlanRequest(description=concept)), candidates=3,
                   geometry=GeometryOptions(shape=shape, entrances=3, partition=True))
    return GenerateRequest(**(options | overrides))


@pytest.fixture(scope='module')
def sample():
    req = request()
    result = generate(req)
    assert result['ok'], result['diagnostics']
    return req, result


def cells(points):
    return {(p['x'], p['y']) for p in points}


@pytest.mark.parametrize('concept', CONCEPTS)
def test_dynamic_room_matrix(concept):
    """120 layouts, independently checked against regenerated architecture and catalog metadata."""
    assets = {asset.id: asset for asset in catalog()}
    measured = []
    for i, shape in enumerate(SHAPES):
        for j, (width, height, density) in enumerate(((22, 20, .3), (30, 25, .65), (36, 30, 1.0))):
            seed = i*37 + j + 100
            req = request(concept, shape, width=width, height=height, density=density,
                          playerSize=1.25 if j == 2 else .55,
                          geometry=GeometryOptions(shape=shape, entrances=1+(i+j)%4,
                                                   partition=(i+j)%2==0, variableSize=j==1),
                          seeds=GenerationSeeds(geometry=seed, selection=seed+1, placement=seed+2, decoration=seed+3))
            result = generate(req)
            assert result['ok'], (concept, shape, width, height, result['diagnostics'])
            measured.append(result['diagnostics']['durationMs'])
            layout = Layout.model_validate(result['layout'])
            validation = validate(req, layout)
            assert validation['valid'], validation['failures']
            assert result['diagnostics']['requiredPlacementRate'] == 1
            assert all(p['reachable'] for p in validation['interactions'])
            assert validation['npcs']
            floor = cells(result['layout']['geometry']['floor'])
            assert component(min(floor), floor) == floor
            if shape == 'square':
                assert layout.width == layout.height
            assert len(layout.geometry.doors) == req.geometry.entrances
            for door in layout.geometry.doors:
                assert (int(door.approach.x), int(door.approach.y)) in cells(validation['reachable'])
            wall_edges = {(wall.x, wall.y, wall.side) for wall in layout.geometry.walls}
            wall_edges.update((door.x, door.y, door.side) for door in layout.geometry.doors)
            assert wall_edges == {(x, y, side) for x, y in floor for side, (dx, dy) in DIRECTIONS.items()
                                  if (x+dx, y+dy) not in floor}
            assert bool(layout.geometry.partitions) == req.geometry.partition
            assert not floor.intersection(cells(result['layout']['geometry']['partitions']))
            solids = []
            for placement in layout.placements:
                asset = assets[placement.assetId]
                assert set(box_cells(footprint(placement, asset))) <= floor
                assert set(box_cells(footprint(placement, asset))) <= cells(result['layout']['zoneCells'][placement.zoneId])
                if asset.solid:
                    box = collision(placement, asset)
                    assert not any(overlap(box, other) for other in solids)
                    solids.append(box)
    print(f'{concept}: {len(measured)} accepted; max generation time {max(measured):.2f} ms')


def test_sizes_and_shapes_actually_change_floor_and_doors(sample):
    req, original = sample
    resized = generate(req.model_copy(update={'width': 34, 'height': 29}))
    rectangular = generate(req.model_copy(update={'geometry': GeometryOptions(shape='rectangle')}))
    assert resized['ok'] and rectangular['ok']
    assert (resized['layout']['width'], resized['layout']['height']) == (34, 29)
    assert rectangular['layout']['width'] == original['layout']['width']
    assert cells(rectangular['layout']['geometry']['floor']) != cells(original['layout']['geometry']['floor'])
    assert resized['layout']['geometry']['doors'] != original['layout']['geometry']['doors']
    assert resized['layout']['zoneCells'] != original['layout']['zoneCells']


def test_seed_isolation_and_exact_reproduction(sample):
    req, original = sample
    repeat = generate(GenerateRequest.model_validate(original['reproduction']))
    assert repeat['ok'] and repeat['layout'] == original['layout'] and repeat['scene'] == original['scene']
    baseline = GenerationSeeds()
    for key in ('selection', 'placement', 'decoration', 'geometry'):
        altered = generate(req.model_copy(update={'seeds': baseline.model_copy(update={key: 1043})}))
        assert altered['ok'], altered['diagnostics']
        if key != 'geometry':
            assert altered['layout']['geometry'] == original['layout']['geometry']
        if key == 'geometry':
            assert altered['layout']['geometry'] != original['layout']['geometry']
        elif key == 'placement':
            assert altered['scene'] == original['scene']
            assert altered['layout']['placements'] != original['layout']['placements']
        elif key == 'selection':
            assert altered['diagnostics']['selection'] != original['diagnostics']['selection']
        elif key == 'decoration':
            def chosen_furniture(result):
                decorative = {'rug', 'surface_detail', 'wall_art'}
                return [(obj['id'], obj['assetId']) for g in result['scene']['groups'] for obj in g['objects']
                        if next(a for a in catalog() if a.id == obj['assetId']).category not in decorative]
            assert chosen_furniture(altered) == chosen_furniture(original)
            assert altered['scene'] != original['scene']


def test_arrangement_retains_placed_objects(sample):
    _, original = sample
    payload = original['reproduction'] | {'retainObjects': [p['id'] for p in original['layout']['placements']]}
    payload['seeds'] = payload['seeds'] | {'placement': 2050}
    arranged = generate(GenerateRequest.model_validate(payload))
    assert arranged['ok'], arranged['diagnostics']
    assert arranged['layout']['geometry'] == original['layout']['geometry']
    assert {(p['id'], p['assetId']) for p in arranged['layout']['placements']} == {
        (p['id'], p['assetId']) for p in original['layout']['placements']}


def test_density_and_space_control_quantities():
    compact = generate(request('classroom', 'rectangle', width=22, height=20, density=.3))
    spacious = generate(request('classroom', 'rectangle', width=40, height=34, density=1))
    assert compact['ok'] and spacious['ok']
    assert sum(row['selected'] for row in spacious['diagnostics']['selection']) > sum(
        row['selected'] for row in compact['diagnostics']['selection'])
    assert len(spacious['layout']['placements']) > len(compact['layout']['placements'])


def test_reject_tampered_partition_floor_and_door(sample):
    req, result = sample
    layout = Layout.model_validate(result['layout'])
    layout.geometry.walls.pop()
    assert 'geometry_mismatch' in {failure['code'] for failure in validate(req, layout)['failures']}
    layout = Layout.model_validate(result['layout'])
    partition = layout.geometry.partitions[0]
    layout.placements[0].x, layout.placements[0].y = partition.x, partition.y
    assert 'room_bounds' in {failure['code'] for failure in validate(req, layout)['failures']}
    layout = Layout.model_validate(result['layout'])
    layout.zoneCells[next(iter(layout.zones))].append(partition)
    assert 'invalid_zone_floor' in {failure['code'] for failure in validate(req, layout)['failures']}


def test_impossible_geometry_and_missing_approved_asset():
    small = request('warehouse', 'square')
    small.room.geometry.minWidth, small.room.geometry.maxHeight = 32, 20
    assert generate(small)['diagnostics']['failures'][0]['code'] == 'square_dimensions'
    req = request('bedroom', assets=[a.model_copy(update={'approved': False}) if a.id == 'bed' else a for a in catalog()])
    result = generate(req)
    assert not result['ok'] and result['diagnostics']['failures'][0]['code'] == 'no_approved_asset'


def test_offline_api_plan_to_geometry_to_saved_replay():
    client = TestClient(app)
    first = client.post('/plan', json={'description': 'warehouse', 'conceptSeed': 1}).json()['room']
    second = client.post('/plan', json={'description': 'warehouse', 'conceptSeed': 2}).json()['room']
    assert first['groups'] != second['groups'] and first['conceptSeed'] != second['conceptSeed']
    result = client.post('/generate', json={'room': first, 'geometry': {'shape': 'alcove'}}).json()
    assert result['ok'], result['diagnostics']
    checked = client.post('/validate', json={'request': result['reproduction'], 'layout': result['layout']})
    assert checked.status_code == 200 and checked.json()['valid']
    defaults = client.post('/generate', json={'room': second}).json()
    assert defaults['ok'] and defaults['reproduction']['geometry']['variableSize'] is False
    assert client.post('/generate', json=defaults['reproduction']).json()['layout'] == defaults['layout']
