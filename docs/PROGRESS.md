# Development progress and verification

Implemented in the initially empty `Infiniture` workspace on 24 November 2026. This delivers the requested local foundation, playable room, and initial spatial engine. It is not a completed production RPG world-generation product.

## Progress

- [x] Phase 1: React/TypeScript/Vite, Express/TypeScript and FastAPI monorepo; shared JSON Schema; health checks; local configuration; test infrastructure; responsive workbench.
- [x] Phase 2: floors, front-facing north walls, thin side/south boundaries, entrance/exit, 32 original placeholder sprites, four-direction player animation and movement, physical collision, depth sorting, camera/zoom, NPC interaction.
- [x] Phase 3 foundation: validated metadata and graph references; supported spatial predicates; atomic furniture-group assembly; demand-weighted functional zones; reserved circulation; collision, wall/surface attachment, clearance, and player-sized reachability validation.
- [x] Phase 4 foundation: seeded candidate ordering, bounded backtracking, optional-member repair, measurable configurable ranking, rejected-candidate reporting, overlays, stage views and independently validated group dragging.
- [x] Map save/reload/export and saved-input reproduction endpoint; MongoDB adapter and explicit local JSON fallback.
- [x] Reference upload and custom PNG sprite import; metadata editing quarantines assets; explicit human approval plus decoded image/metadata checks.
- [x] Phase 5 adapter groundwork: OpenRouter discovery, model assignments, semantic/vision planning, local JSON-schema validation, retries, timeout, fallback configuration, cache and usage/cost records. Adapter behavior tested with mocked HTTP responses.
- [ ] Verify live OpenRouter text and image analysis against an actual configured account/key. No key was supplied; no paid requests were made.
- [ ] Complete separate asset-manager, live image generation and visual-review workflows. Their role slots exist, but the workflows are not implemented. Live image generation is explicitly disabled.
- [ ] Complete full live reference-to-generated-assets pipeline.
- [ ] Production-quality assets and artistic polish, multiroom architecture, production hosting/authentication and multiuser operation.

## Dynamic interior phase

- Local checkpoint `checkpoint/pre-dynamic-interiors` at `7cbe966` preserves the previous implementation.
- Geometry is generated before furniture using seeded room dimensions, five orthogonal shape families, optional partition, and up to four boundary door approaches. Floors, wall sprites, collision and navigation use the generated footprint.
- Category-based room specifications drive approved asset selection and group quantities. Adaptive zones use contiguous floor masks, clear routes, wall availability and zone preferences. The same group solver handles all eight requested concepts.
- Geometry, selection, placement and decoration each have a seed. The browser offers four regeneration scopes. Arrangement-only keeps the currently placed object IDs and requires them to fit as complete groups. Saved replay pins asset versions and configuration.
- The inspector exposes floor cells, wall segments, doors, zones, groups, selection and placement decisions, and candidate rejection reasons. The offline `RoomSpec` schema is ready for a future semantic planner.
- Verification includes 120 generated and separately validated dynamic cases across the eight concepts, five shapes and three size/density settings. Tests also cover wider players, invalid geometry, unapproved assets, preserved arrangement selections and exact saved replay. Eight Edge browser tests cover regeneration scopes, gameplay against a partition, save and reload, and visual baselines for an L-shaped, alcove and irregular room.

## Verified results

- Backend: **4 tests passed**. Shared contracts, malformed inputs, concurrent atomic local persistence, provider modality checks, cache behavior, invalid AI JSON rejection and usage logging.
- Python: **27 tests passed**. Includes **100 unique seeded layouts** across ten room concepts, three densities and varied room dimensions. Every accepted layout was independently revalidated and regenerated for exact layout equality. **100 accepted, 0 rejected** in this feasible test matrix; impossible-layout tests separately require rejection. No accepted test case had a physical overlap or a failed mandatory accessibility check.
- Latest measured maximum for the 100-case matrix: **131.75 ms** per generation in this environment. This is a local measurement, not a performance guarantee. See `seeded-test-results.json` for per-case data.
- Browser: six end-to-end scenarios cover generation, overlays, keyboard movement along a returned route, actual caretaker interaction, furniture collision, save/reload, library search, scene inspection, uploads, invalid API inputs, mobile overflow, and three deterministic image baselines. The final machine-readable outcome is in `browser-test-results.json`.
- Builds: backend TypeScript build and frontend TypeScript/production Vite build pass. Phaser remains a large vendor chunk (about 1.48 MB raw / 340 KB gzip); Vite reports a nonfatal chunk-size warning.
- Runtime: React at port 5174, Express at 3001, and Python at 8000 returned successful health/page responses. The local fallback was exercised when Node's DNS resolver refused the Atlas SRV lookup. A DNS override for the API process restored the Atlas connection. The API now reports MongoDB storage, and the map listing returned HTTP 200. Remote writes were not exercised during this check.
- Visual review: inspected desktop tavern, library, bedroom, office, inspector/play views, and mobile layout. Screenshots show coherent groups, wall alignment and crisp original placeholder art. The rooms remain sparse, and the floor pattern is visually busy. Geometry scores are **not** evidence of production artistic quality.

## Failures found and resolved

1. Initial asset generation omitted the shared-output directory; the generator now creates it.
2. Counter chairs obstructed mandatory interaction clearance. The mock semantic relationship allows a larger supported gap; clearance was not relaxed.
3. Initial TypeScript integration had an incorrect shared import path and overly narrow inferred persistence-ID type; fixed before successful builds.
4. React StrictMode could create two Phaser canvases before cleanup. Boot is deferred until the effect is committed.
5. Rapid responsive transitions triggered a WebGL framebuffer incomplete-attachment error. The 2D preview now uses Phaser's Canvas renderer with nonzero-size guarded manual resizing.
6. Very short E-key taps could be lost between render frames. NPC interaction now uses the keyboard event rather than per-frame polling.
7. A corner-rule fixture used a one-tile crate whose declared interaction clearance extended beyond a side wall. The solver correctly rejected it. The positive fixture now uses a two-tile chest with feasible clearance; no constraint was weakened.

## Current limits and precise semantics

- The offline planner is a clearly labeled semantic vocabulary fixture, not an LLM. Unknown descriptions use the hospitality fixture. Arbitrary concepts can be expressed through Scene Planner JSON; placement uses the same engine for every concept.
- Legacy maps have rectangular rooms and a fixed north/south door pair. New maps have connected orthogonal floors and can contain one partial partition. Doors are reachable thresholds. Inter-room travel and arbitrary partition networks are future work.
- The supported relationship types all have computational checks, but bounded assembly is not a complete general-purpose constraint solver. It may reject a feasible complex graph when its search budget/relative search window is exhausted. Most group relations must form an acyclic dependency graph; object relationships are scoped to their group, with a special cross-zone separation relation.
- Initial wall-dependent sprites attach to the north wall, matching their artwork. Other wall orientation art is not invented or rotated. Direction-specific chair/player sprites are provided.
- Interactions use declared clearance and the actual player collision size. NPCs are nonblocking entities placed on reachable floor; navigation does not treat NPC bodies as permanent obstacles.
- Object collision uses axis-aligned rectangles. Navigation uses a player-sized cell-center flood fill and swept segment checks. On dynamic maps it can connect to off-grid interaction points with a two-leg approach.
- Density affects semantic demand and optional furniture. It is not yet a calibrated guarantee of a requested occupied-floor percentage. The default mock scenes intentionally contain few groups.
- Targeted repair currently removes optional group members and then reruns placement. It does not yet implement arbitrary conflict-directed rearrangement or visual-AI-guided repairs.
- Candidate comparison shows all scores/rejections, but only the selected candidate's geometry is returned/rendered. Alternative candidate map previews are not implemented.
- Reference similarity measures recognized semantic tag coverage when tags exist. It does not claim pixel-level visual similarity. Its weight is excluded when reference tags are unavailable.
- Scoring uses measured zone-centering, satisfied relations, reachable walkable fraction, solid-object centroid, semantic tag coverage and decoration count/demand. All hard constraints are checked before scoring.
- Layer identifiers are independent. Architecture is rendered from room geometry; object layers contain placement IDs. Collision/navigation/interaction/entity layers are represented by their corresponding validated output arrays, not duplicate occupied-cell maps.
- Stage inspector supports architecture, zones and final map. Group structure, graph, paths and validation outputs are inspectable; there is no animation of every internal backtracking step.
- After a validated manual group move, the diagnostic scores still describe the original generated candidate. The UI explicitly states this.
- PNG integrity, dimensions, transparency and metadata are checked programmatically. Perspective, lighting, proportional consistency and artistic quality require visual approval. Uploaded JPEG references are checked by signature and size, not fully decoded at upload; live vision remains unverified.
- Asset metadata is pinned in saved reproduction inputs. Uploaded sprite URLs are immutable UUID paths, but bundled sprites are source files rather than a content-addressed asset store.
- Settings currently expose model assignments and scoring weights. Some engine budgets are API-only. Asset editing is JSON-based rather than a graphical polygon editor. Project CRUD groundwork is limited to create/list; there is no project-management UI.
- Local files retain up to 200 records per collection and are for one developer. There is no database migration system, authentication, remote deployment, production rate limiting or cloud file store.
- FastAPI's current Starlette TestClient emits a nonfatal deprecation warning about its httpx compatibility layer. Tests pass; dependencies are bounded in `requirements.txt`, and JavaScript exact versions are in `package-lock.json`.

## Next dependency-ordered work

1. Test MongoDB writes using a dedicated development database and rotate the shared credential.
2. Add an OpenRouter key and select a text/vision-capable model; validate actual reference-image reconstruction against the schema and hard-constraint validator.
3. Improve semantic fixture density and group variants, then broaden adversarial/large-scene tests before introducing more complex zoning or a solver.
4. Replace the reviewed placeholder library with original production artwork and versioned binary assets.
5. Implement missing-asset resolution, provider-capability-checked image generation, approval quarantine, and optional visual-review recommendations.
