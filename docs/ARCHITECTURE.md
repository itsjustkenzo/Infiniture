# Infiniture architecture and implementation plan

Infiniture started as a standalone prototype. The dynamic interior phase extends the existing grouped placement engine and keeps its concrete scene and saved-map contracts compatible.

## Boundaries

- `apps/web`: React/TypeScript/Vite developer workbench. Phaser renders the authoritative engine output and uses the same physical rectangles and player dimensions for movement.
- `apps/api`: Express/TypeScript gateway. Owns secrets, uploads, persisted projects/assets/maps, and optional OpenRouter calls. Local JSON storage is an explicit development fallback; MongoDB is configurable.
- `services/engine`: FastAPI/Pydantic contracts, semantic planning mock, approved asset catalog, deterministic group assembly, zoning, bounded search, collision/navigation validation, and measured ranking.
- `packages/shared`: exported JSON Schema contracts, frontend types, versioned asset catalog.
- `scripts`: original placeholder pixel art generation, local launcher, integration verification.

AI produces a semantic graph, never authoritative coordinates. A single engine assembles generic group relationships before searching zone positions. Required groups are atomic. Invalid graphs and unsatisfiable layouts return structured failures. The final validator is also exposed independently; generation success requires this validator to pass.

## Dependency order and verification

1. Foundation: workspace, shared contracts, health checks, responsive shell. Verify dependency installation and TypeScript builds.
2. Playable room: original fixed sprite library, architecture, player movement, collision, depth and NPC interaction. Verify service startup and browser play.
3. Spatial engine: typed metadata, validated graph, group relationships, zones, reserved paths, candidate search and player-sized navigation. Unit-test geometry, attachments, unsupported metadata and deliberately impossible inputs.
4. Optimization/inspection: bounded backtracking, independently scored candidates, diagnostics and overlays. Run at least 100 seeds across ten semantic concepts, check determinism and all accepted maps independently.
5. Optional AI/persistence: schema-validated OpenRouter planner/vision and MongoDB through backend secrets. Default mock mode requires neither external service. Test fallback/error handling without spending API credits.
6. Asset management: metadata editing/import/review quarantine. Live image generation remains gated until a compatible provider and visual review are available.

## Decisions

- Local development is the requested deliverable; no hosting deployment. Python and MongoDB are independent services, not a static-site backend.
- Logical coordinates use 16 px per tile. World rectangles are represented in tile units. Sprite dimensions and ground anchors are independent of collision bounds.
- Default player is 0.55 × 0.55 tiles. Navigation tests a player-sized box at cell centers and validates segments between centers.
- Seeded candidate ordering is stable; search-node and candidate budgets ensure reproducibility. A wall-clock deadline may return a timeout, never a partially validated room.
- Only approved, schema-valid assets can enter placement. The initial art is original programmatically drawn **placeholder** art, not production art.
- Credentials are ignored backend environment files. No credentials are sent in API responses or frontend builds.

Progress, tests and explicit remaining work will be recorded in `docs/PROGRESS.md` after implementation.

## Dynamic rooms

1. `architecture.py` resolves dimensions and shape from the room preferences, UI overrides and geometry seed. The floor mask defines wall edges, doors, and empty circulation cells before asset selection.
2. `selection.py` resolves semantic categories against approved assets. It chooses group quantities within the room's floor capacity and uses separate deterministic streams for furniture and decorative roles. It outputs the existing `Scene` with selected asset IDs and relationship references.
3. `zoning.py` allocates connected floor masks around the assembled group's fit and wall requirements, door proximity and soft relationships between zones. Required zones are allocated first. Reserved circulation and partitions are excluded.
4. `solver.py` reuses group assembly, relationship checks, bounded placement search and ranking. Dynamic candidates validate required groups before adding compatible optional groups. Complete validation compares the architecture to the seeded request, checks physical footprints against floor and zone masks, and verifies all doors and mandatory interaction points. Phaser's movement uses the same floor mask and collision bounds.
5. A saved dynamic map retains its room specification or scene, effective geometry configuration, seeds and metadata snapshot. Requests with only a concrete scene and the legacy seed still use the earlier rectangular path.

The structured `RoomSpec` schema is provider neutral. A future OpenRouter adapter can produce it after schema and semantic validation. The current generator only uses the offline planner. Geometry supports orthogonal outlines, a partial partition with a bypass, and up to four boundary entrances. Doors do not connect separate maps. Complex demands can fail with a capacity or search-budget diagnostic. Timing limits can reduce which validated candidates are considered.
