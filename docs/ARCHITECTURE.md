# Infiniture architecture and implementation plan

The supplied workspace is empty. There is no earlier placement system, existing animation, or reusable source to audit. The new brief supersedes the refactor request and authorizes a standalone implementation.

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
