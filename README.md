# Infiniture

A local React/Phaser interior-generation workbench backed by Express and a deterministic Python spatial engine. The fixed library and offline semantic planner work without AI credentials or MongoDB. This is a tested prototype foundation, with original placeholder art; the complete live AI asset-generation pipeline is not finished.

## Start on Windows

Prerequisites: Node.js 20+ (22 recommended), Python 3.10+, and npm. Microsoft Edge is used by the optional browser tests.

```powershell
cd C:\Users\USER\Infiniture
npm.cmd install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services/engine/requirements.txt
Copy-Item apps/api/.env.example apps/api/.env   # only if .env does not already exist
npm.cmd run dev
```

Open **http://127.0.0.1:5174**. The API uses port 3001; Python uses port 8000. Port 5174 is intentional because another application occupied 5173 during implementation. The frontend fails explicitly if 5174 is occupied.

The ignored `apps/api/.env` contains the MongoDB connection supplied for this task. The local API connects to Atlas with `STORAGE_MODE=mongo`. If Node reports `querySrv ECONNREFUSED`, `MONGODB_DNS_SERVERS` can specify a comma-separated list of working DNS resolver addresses for the API process. Restart the API after changing environment variables and check `/api/health` for `storage: mongodb`. Set `STORAGE_MODE=local` for deliberate offline use. Maps saved during local fallback stay in `runtime/data` and are available in local mode. Rotate the supplied database password because it was shared in chat.

`npm run dev` launches all three services. To run them separately:

```powershell
python -m uvicorn services.engine.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir services/engine
npm.cmd run dev -w apps/api
npm.cmd run dev -w apps/web
```

## Use

1. Describe a tavern, bedroom, library, kitchen, office, shop, warehouse, classroom, hospital, blacksmith workshop, laboratory or spaceship. The offline vocabulary uses a tavern fixture for unrecognized concepts. Edit the room specification to define another concept.
2. Choose a room shape, preferred dimensions, entrance count and optional partition. With **Vary dimensions by seed** enabled, the geometry seed varies dimensions within the room specification's limits. Enter separate seeds for geometry, furniture selection, placement and decoration. Select **Generate interior**.
3. Use **Regenerate** to rearrange the items already placed, reselect furniture inside the same architecture, rebuild architecture and layout, or request another offline concept variant for the same description. Inspect floor cells, walls, entrances, zones, paths and candidate diagnostics in Layout inspector. Scene planner accepts `RoomSpec` JSON and existing concrete scene graphs.
4. Select **Play**, click the map, and use WASD/arrows. Press E near the caretaker. Zoom controls and editor overview are available.
5. In Editor, drag a furniture member to move its entire group. Changes must pass the independent validator; invalid moves are rejected. Original generation scores are not recalculated after manual editing.
6. Save the result, reload it from Dashboard, or export JSON. Saved results include the seed, semantic graph, configuration and versioned metadata snapshot.

Uploads are stored in `runtime/uploads`. The dynamic generator uses offline specifications and the approved asset catalog. Reference images are stored for future planning. `packages/shared/room.schema.json` is the input contract for a future OpenRouter semantic planner.

## Commands

```powershell
npm.cmd run build                 # backend typecheck/build + frontend typecheck/production build
npm.cmd test                      # backend contracts/provider/storage + Python engine suite
npx.cmd playwright test           # running app required; Edge gameplay/API/visual regression tests
npm.cmd run assets                # rebuild 32 original placeholder PNGs and metadata catalog
npm.cmd run schema                # export Pydantic contracts to shared JSON Schema
```

The browser suite creates test maps/history/uploads in the current development storage. Use `STORAGE_MODE=local` for test runs if you do not want test records in MongoDB. Golden screenshots are in `tests/browser/studio.spec.ts-snapshots`; update them deliberately with `npx playwright test --update-snapshots` only after reviewing changes. Golden images were captured on Windows/Edge and can differ on another platform.

Production build output: `apps/api/dist` and `apps/web/dist`. This repository does not configure public hosting, authentication, reverse proxies or a production process manager. All development services bind loopback.

## Source and evidence

- [Architecture and implementation decisions](docs/ARCHITECTURE.md)
- [API contracts and routes](docs/API.md)
- [Progress, limitations and verification](docs/PROGRESS.md)
- [100-seed measured results](docs/seeded-test-results.json)
- [Browser test report](docs/browser-test-results.json)
- [Reviewed screenshots](docs/screenshots)

The engine builds a connected orthogonal floor, marks wall edges, reserves routes between doors and selects functional furniture groups from the approved catalog. Zones grow over the available floor. The existing solver assembles related furniture and uses bounded candidate search and player-sized navigation to validate layouts. Older saves still use their original rectangular geometry. Dynamic rooms are single connected interiors with 1–4 door approaches and at most one partial partition. Doors mark reachable thresholds within the room.
