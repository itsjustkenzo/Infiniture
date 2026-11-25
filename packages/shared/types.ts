// JSON Schemas beside this file are authoritative at service boundaries.
export type Point = { x: number; y: number };
export type Rect = Point & { width: number; height: number };
export type WallSide = 'north' | 'south' | 'east' | 'west';
export type RoomShape = 'rectangle' | 'square' | 'l_shape' | 'alcove' | 'orthogonal';
export type GeometryOptions = {
  shape: RoomShape | 'auto';
  variableSize: boolean;
  entrances: number;
  partition: boolean;
};
export type GenerationSeeds = {
  geometry: number;
  selection: number;
  placement: number;
  decoration: number;
};
export type RoomGeometry = {
  shape: RoomShape;
  floorStyle: 'wood_floor' | 'stone_floor';
  floor: Point[];
  walls: (Point & { side: WallSide })[];
  doors: (Point & { side: WallSide; id: string; approach: Point })[];
  partitions: Point[];
};
export type Asset = {
  id: string;
  name: string;
  category: string;
  sprite: string;
  spriteSize: { width: number; height: number };
  footprint: { width: number; height: number };
  anchor: Point;
  orientationSprites: Record<string, string>;
  renderLayer: string;
  solid: boolean;
  approved: boolean;
  placeholder: boolean;
  [key: string]: any;
};
export type Placement = {
  id: string;
  assetId: string;
  groupId: string;
  zoneId: string;
  x: number;
  y: number;
  orientation: string;
  parentId: string | null;
  socketId: string | null;
  visualLift: number;
};
export type Layout = {
  schemaVersion: '1.0';
  width: number;
  height: number;
  seed: number;
  playerSize: number;
  placements: Placement[];
  zones: Record<string, Rect>;
  entrance: Point;
  exit: Point;
  circulation: Point[];
  geometry?: RoomGeometry | null;
  zoneCells?: Record<string, Point[]> | null;
};
export type MapResult = {
  ok: true;
  layout: Layout;
  assets: Asset[];
  scene: any;
  reproduction: any;
  diagnostics: any;
  validation: {
    valid: boolean;
    failures: any[];
    collisions: (Rect & { objectId: string })[];
    walkable: Point[];
    reachable: Point[];
    interactions: (Point & { objectId: string; reachable: boolean })[];
    paths: { target: string; points: Point[] }[];
    npcs: (Point & { id: string; name: string; dialogue: string; interactionRadius: number })[];
  };
  layers: Record<string, string[]>;
  stages: any;
};
export const overlays = [
  'Grid',
  'Boundaries',
  'Floor cells',
  'Wall segments',
  'Entrances',
  'Zones',
  'Groups',
  'Group anchors',
  'Sprite anchors',
  'Collision',
  'Visual bounds',
  'Occupied cells',
  'Walkable cells',
  'Circulation',
  'Paths',
  'Interactions',
  'Relationships',
  'Depth',
  'Failures',
] as const;
