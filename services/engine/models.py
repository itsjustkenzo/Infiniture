from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = '1.0'
BEHAVIORS = ['against_wall', 'along_wall', 'attached_to_wall', 'inside_corner',
             'near_object', 'facing_object', 'surround_object', 'attached_to_surface',
             'under_object', 'above_object', 'adjacent_to_object', 'aligned_with_object',
             'parallel_to_object', 'symmetrical_to_object', 'clustered_with_objects',
             'centered_within_zone', 'separated_from_zone', 'minimum_distance',
             'maximum_distance', 'maintain_clearance', 'connected_to_walking_path', 'repeated_arrangement']
LAYERS = ['floor', 'floor_decoration', 'wall', 'wall_decoration', 'furniture',
          'surface_decoration', 'collision', 'navigation', 'interaction', 'npc',
          'player', 'foreground', 'lighting']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Point(Strict):
    x: float
    y: float

class Size(Strict):
    width: float = Field(gt=0, le=256)
    height: float = Field(gt=0, le=256)

class Rect(Point, Size):
    pass

class Socket(Point):
    id: str
    categories: list[str]
    visualLift: float = Field(default=0, ge=0, le=8)

class Asset(Strict):
    schemaVersion: Literal['1.0'] = '1.0'
    version: int = Field(default=1, ge=1)
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    name: str = Field(min_length=1, max_length=100)
    category: str
    tags: list[str]
    purpose: list[str]
    sprite: str
    styleId: str = 'hearth_pixel'
    pixelDensity: Literal[16] = 16
    spriteSize: Size
    footprint: Size
    collision: Rect
    visualBounds: Rect
    anchor: Point
    supportedOrientations: list[Literal['north', 'south', 'east', 'west']] = Field(min_length=1)
    orientationSprites: dict[str, str]
    placementBehaviors: list[str]
    requiresWall: bool = False
    requiresSurface: bool = False
    surfaceSockets: list[Socket] = []
    wallSockets: list[Socket] = []
    interactionPoints: list[Point] = []
    interactionClearance: float = Field(default=0, ge=0, le=3)
    preferredZones: list[str] = []
    compatibleCategories: list[str] = []
    renderLayer: str
    depthOffset: float = 0
    solid: bool
    approved: bool = False
    placeholder: bool = True

    @model_validator(mode='after')
    def valid(self):
        if any(b not in BEHAVIORS for b in self.placementBehaviors):
            raise ValueError('unsupported asset placement behavior')
        if self.renderLayer not in LAYERS:
            raise ValueError('unsupported render layer')
        c, f = self.collision, self.footprint
        if c.x < 0 or c.y < 0 or c.x+c.width > f.width or c.y+c.height > f.height:
            raise ValueError('collision must fit physical footprint')
        if self.anchor.x < 0 or self.anchor.x > self.spriteSize.width or self.anchor.y < 0 or self.anchor.y > self.spriteSize.height:
            raise ValueError('anchor outside sprite')
        if any(o not in self.orientationSprites for o in self.supportedOrientations):
            raise ValueError('missing orientation-specific sprite')
        if self.requiresSurface and (self.solid or self.renderLayer != 'surface_decoration'):
            raise ValueError('surface decorations must be non-solid and use surface layer')
        if any(s.x < 0 or s.y < 0 or s.x >= f.width or s.y >= f.height for s in self.surfaceSockets):
            raise ValueError('surface socket outside footprint')
        return self

class Relation(Strict):
    type: str
    target: str | None = None
    distance: float = Field(default=1, ge=0, le=32)
    axis: Literal['x', 'y'] = 'x'
    wall: Literal['north', 'south', 'east', 'west'] = 'north'
    socket: str | None = None
    mandatory: bool = True

    @model_validator(mode='after')
    def valid(self):
        if self.type not in BEHAVIORS:
            raise ValueError(f'unsupported relationship: {self.type}')
        unary = {'against_wall','along_wall','attached_to_wall','inside_corner','centered_within_zone','maintain_clearance','connected_to_walking_path'}
        if self.type not in unary and not self.target:
            raise ValueError(f'{self.type} requires target')
        return self

class ObjectSpec(Strict):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
    assetId: str
    required: bool = True
    orientation: Literal['north','south','east','west'] = 'south'
    relations: list[Relation] = []

class Group(Strict):
    id: str
    zoneId: str
    anchorId: str
    required: bool = True
    objects: list[ObjectSpec] = Field(min_length=1, max_length=24)
    @model_validator(mode='after')
    def valid(self):
        ids = [o.id for o in self.objects]
        if len(set(ids)) != len(ids) or self.anchorId not in ids:
            raise ValueError('invalid group anchor or duplicate object ID')
        for o in self.objects:
            for r in o.relations:
                if r.target and r.type != 'separated_from_zone' and (r.target not in ids or r.target == o.id):
                    raise ValueError('relationship target must reference another member of the same group')
        return self

class Zone(Strict):
    id: str
    purpose: str
    minimumArea: int = Field(default=16, ge=4, le=4096)
    preferredArea: int = Field(default=48, ge=4, le=4096)
    priority: int = Field(default=1, ge=0, le=100)
    preferredWall: Literal['north','south','east','west'] | None = None
    accessible: bool = True
    required: bool = True
    nearZones: list[str] = Field(default_factory=list, max_length=12)
    awayFromZones: list[str] = Field(default_factory=list, max_length=12)
    nearEntrance: bool = False
    @model_validator(mode='after')
    def valid(self):
        if self.preferredArea < self.minimumArea:
            raise ValueError('preferred area is below minimum area')
        return self

class NPC(Strict):
    id: str
    name: str
    groupId: str
    dialogue: str = Field(max_length=500)

class Scene(Strict):
    schemaVersion: Literal['1.0'] = '1.0'
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=4000)
    styleId: Literal['hearth_pixel'] = 'hearth_pixel'
    zones: list[Zone] = Field(min_length=1, max_length=12)
    groups: list[Group] = Field(min_length=1, max_length=30)
    npcs: list[NPC] = Field(default_factory=list, max_length=12)
    referenceTags: list[str] = []
    @model_validator(mode='after')
    def valid(self):
        zs, gs = [z.id for z in self.zones], [g.id for g in self.groups]
        ids = [o.id for g in self.groups for o in g.objects]
        if len(zs)!=len(set(zs)) or len(gs)!=len(set(gs)) or len(ids)!=len(set(ids)):
            raise ValueError('duplicate scene ID')
        if any(g.zoneId not in zs for g in self.groups) or any(n.groupId not in gs for n in self.npcs):
            raise ValueError('unresolved zone or NPC group reference')
        if any(r.target not in zs for g in self.groups for o in g.objects for r in o.relations if r.type=='separated_from_zone'):
            raise ValueError('unresolved zone relationship')
        return self

class Weights(Strict):
    organization: float = Field(default=.25, ge=0)
    relationships: float = Field(default=.25, ge=0)
    navigation: float = Field(default=.20, ge=0)
    composition: float = Field(default=.15, ge=0)
    reference: float = Field(default=.10, ge=0)
    decoration: float = Field(default=.05, ge=0)
    @model_validator(mode='after')
    def valid(self):
        if sum(self.model_dump().values()) <= 0: raise ValueError('at least one scoring weight must be positive')
        return self

Direction = Literal['north', 'south', 'east', 'west']
Shape = Literal['rectangle', 'square', 'l_shape', 'alcove', 'orthogonal']
Dimension = Annotated[int, Field(ge=12, le=64)]
Seed = Annotated[int, Field(ge=0, le=2147483647)]
SpecId = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_]{0,19}$')]

class GeometryOptions(Strict):
    shape: Shape | Literal['auto'] = 'auto'
    variableSize: bool = False
    entrances: int = Field(default=2, ge=1, le=4)
    partition: bool = False
    floor: Literal['wood_floor', 'stone_floor'] | None = None

class GeometryPreferences(Strict):
    shapes: list[Shape] = Field(default_factory=lambda: ['rectangle'], min_length=1, max_length=5)
    minWidth: Dimension = 12
    maxWidth: Dimension = 64
    minHeight: Dimension = 12
    maxHeight: Dimension = 64
    floor: Literal['wood_floor', 'stone_floor'] = 'wood_floor'

    @model_validator(mode='after')
    def validate_range(self):
        if self.minWidth > self.maxWidth or self.minHeight > self.maxHeight:
            raise ValueError('geometry minimum dimensions exceed maximum dimensions')
        return self

class GenerationSeeds(Strict):
    geometry: Seed = 1042
    selection: Seed = 1042
    placement: Seed = 1042
    decoration: Seed = 1042

class ComponentRequirement(Strict):
    id: SpecId
    category: str = Field(min_length=1, max_length=60)
    anyTags: list[str] = Field(default_factory=list, max_length=20)
    orientation: Direction = 'south'
    requiresInteraction: bool = False
    required: bool = True
    decoration: bool = False
    relations: list[Relation] = Field(default_factory=list, max_length=12)

class GroupRequirement(Strict):
    id: SpecId
    zoneId: SpecId
    minimum: int = Field(default=1, ge=0, le=5)
    preferred: int = Field(default=1, ge=1, le=5)
    anchor: ComponentRequirement
    members: list[ComponentRequirement] = Field(default_factory=list, max_length=12)
    caretaker: bool = False

    @model_validator(mode='after')
    def validate_components(self):
        if self.preferred < self.minimum:
            raise ValueError('preferred quantity is below minimum quantity')
        if self.anchor.decoration or not self.anchor.required:
            raise ValueError('group anchor must be required furniture')
        if self.caretaker and (self.minimum < 1 or not self.anchor.requiresInteraction):
            raise ValueError('caretaker needs a required group with an interactive anchor')
        components = [self.anchor, *self.members]
        roles = {component.id: component for component in components}
        if len(roles) != len(components):
            raise ValueError('duplicate component role')
        for component in components:
            for relation in component.relations:
                if not relation.target or relation.type == 'separated_from_zone':
                    continue
                target = roles.get(relation.target)
                if component is self.anchor or target is None or target is component:
                    raise ValueError('invalid component relationship target')
                if relation.mandatory and component.required and not target.required:
                    raise ValueError('required component depends on an optional role')
                if not component.decoration and target.decoration:
                    raise ValueError('furniture cannot depend on decoration selection')
        return self

class RoomSpec(Strict):
    schemaVersion: Literal['1.0'] = '1.0'
    title: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=200)
    conceptSeed: Seed = 0
    description: str = Field(default='', max_length=4000)
    geometry: GeometryPreferences = Field(default_factory=GeometryPreferences)
    zones: list[Zone] = Field(min_length=1, max_length=12)
    groups: list[GroupRequirement] = Field(min_length=1, max_length=20)
    density: float = Field(default=.5, ge=.1, le=1)
    decorationDensity: float = Field(default=.5, ge=0, le=1)

    @model_validator(mode='after')
    def validate_references(self):
        zones = {zone.id: zone for zone in self.zones}
        if len(zones) != len(self.zones) or len({group.id for group in self.groups}) != len(self.groups):
            raise ValueError('duplicate zone or group ID')
        if not 1 <= sum(group.minimum for group in self.groups) <= 30:
            raise ValueError('room needs between 1 and 30 required groups')
        for zone in self.zones:
            if any(target not in zones or target == zone.id for target in zone.nearZones + zone.awayFromZones):
                raise ValueError('unknown zone preference target')
        for group in self.groups:
            if group.zoneId not in zones or (group.minimum and not zones[group.zoneId].required):
                raise ValueError('required groups must belong to required zones')
            for component in [group.anchor, *group.members]:
                if any(relation.type == 'separated_from_zone' and relation.target not in zones for relation in component.relations):
                    raise ValueError('unknown separation target')
        if sum(group.caretaker for group in self.groups) > 12:
            raise ValueError('at most 12 caretaker positions are supported')
        return self

class GenerateRequest(Strict):
    schemaVersion: Literal['1.0'] = '1.0'
    width: int = Field(default=28, ge=12, le=64)
    height: int = Field(default=24, ge=12, le=64)
    seed: int = Field(default=1042, ge=0, le=2147483647)
    candidates: int = Field(default=4, ge=1, le=12)
    maxSearchNodes: int = Field(default=6000, ge=100, le=30000)
    timeoutMs: int = Field(default=15000, ge=100, le=60000)
    density: float = Field(default=.5, ge=.1, le=1)
    decorationDensity: float = Field(default=.5, ge=0, le=1)
    playerSize: float = Field(default=.55, ge=.25, le=1.5)
    weights: Weights = Field(default_factory=Weights)
    scene: Scene | None = None
    room: RoomSpec | None = None
    geometry: GeometryOptions | None = None
    seeds: GenerationSeeds | None = None
    retainObjects: list[str] | None = Field(default=None, min_length=1, max_length=720)
    assets: list[Asset] | None = Field(default=None, max_length=200)

    @model_validator(mode='after')
    def validate_plan(self):
        if (self.scene is None) == (self.room is None):
            raise ValueError('provide exactly one of scene or room')
        if self.retainObjects is not None and len(set(self.retainObjects)) != len(self.retainObjects):
            raise ValueError('retained object IDs must be unique')
        return self

class PlanRequest(Strict):
    description: str = Field(min_length=1, max_length=4000)
    density: float = Field(default=.5, ge=.1, le=1)
    decorationDensity: float = Field(default=.5, ge=0, le=1)
    conceptSeed: Seed = 0

class Cell(Strict):
    x: int = Field(ge=0, le=64)
    y: int = Field(ge=0, le=64)

class Wall(Cell):
    side: Direction

class Door(Wall):
    id: str
    approach: Point

class RoomGeometry(Strict):
    shape: Shape
    floorStyle: Literal['wood_floor', 'stone_floor']
    floor: list[Cell] = Field(min_length=1, max_length=4096)
    walls: list[Wall] = Field(max_length=4096)
    doors: list[Door] = Field(min_length=1, max_length=4)
    partitions: list[Cell] = Field(default_factory=list, max_length=64)

class Placement(Strict):
    id: str
    assetId: str
    groupId: str
    zoneId: str
    x: float
    y: float
    orientation: Literal['north','south','east','west']
    parentId: str | None = None
    socketId: str | None = None
    visualLift: float = 0

class Layout(Strict):
    schemaVersion: Literal['1.0'] = '1.0'
    width: int = Field(ge=12, le=64)
    height: int = Field(ge=12, le=64)
    seed: int
    playerSize: float = Field(ge=.25, le=1.5)
    zones: dict[str, Rect]
    placements: list[Placement]
    entrance: Point
    exit: Point
    circulation: list[Point]
    geometry: RoomGeometry | None = None
    zoneCells: dict[str, list[Cell]] | None = None

class ValidateRequest(Strict):
    request: GenerateRequest
    layout: Layout

class InspectAssetRequest(Strict):
    asset: Asset
    pngBase64: str = Field(max_length=12000000)
