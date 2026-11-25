# Local API

Express: `http://127.0.0.1:3001/api`. Python OpenAPI and interactive contracts: `http://127.0.0.1:8000/docs`. Vite proxies `/api` and `/uploads`. All servers bind loopback. This prototype has no remote authentication layer and is intended for a single local developer.

## Core pipeline

| Method and route    | Input / result                                                                                                                                                                                                                                                                                                                   |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET `/health`       | Engine connectivity, storage mode and credential-presence boolean; no secret values.                                                                                                                                                                                                                                             |
| POST `/plan`        | `{description, density?, decorationDensity?, conceptSeed?, mode?: "mock", referenceId?}`. The offline response includes `room` for dynamic generation and `scene` for older clients. Uploaded references are stored.                                                                                                             |
| POST `/generate`    | Send exactly one of `room` or `scene`, plus optional `width`, `height`, `geometry`, `seeds`, densities and search settings. The backend uses its approved asset registry. Successful results include `layout`, `validation`, `diagnostics`, `scene` and `reproduction`. Unsatisfiable requests return `ok:false` with no layout. |
| POST `/validate`    | `{request: GenerateRequest, layout: Layout}`. Independent full validation, collision rectangles, player-sized walkability, paths, interactions and NPC positions.                                                                                                                                                                |
| GET `/capabilities` | Supported relationship names, layers and tile size.                                                                                                                                                                                                                                                                              |
| GET `/history`      | Recent generation diagnostics, including failed generations.                                                                                                                                                                                                                                                                     |

`packages/shared/room.schema.json` describes the offline planner output. A room specifies dimension ranges, shape preferences, required and optional zones, and category-based group requirements. Group quantities have minimum and preferred counts. Roles within a group can express interaction requirements and relationships to other roles. `packages/shared/scene.schema.json` describes the existing resolved scene with concrete asset IDs. In both contracts `separated_from_zone` references a zone. The engine rejects unsupported relationships, cycles and invalid references.

Dynamic generation uses `geometry: {shape, variableSize, entrances, partition}` and `seeds: {geometry, selection, placement, decoration}`. Shapes include `auto`, `rectangle`, `square`, `l_shape`, `alcove` and `orthogonal`. Choose 1–4 entrances. With `variableSize` enabled, the width and height inputs are preferred sizes. Generation changes the size within the specification's limits. If seeds are omitted, `seed` initializes all four streams. A concrete scene request without any dynamic options keeps the legacy rectangular pipeline.

An arrangement-only request keeps the same specification, geometry options, and asset catalog. Advance the placement seed and set `retainObjects` to the placed object IDs. The engine requires the retained objects and their dependencies to fit together. To reselect furniture, omit `retainObjects` and change the selection and placement seeds. To rebuild the room, change the geometry seed. To get a different offline plan for the same description, call `/plan` with another `conceptSeed`.

Dynamic results include `layout.geometry` with floor cells, wall segments, partitions and door approaches, plus `layout.zoneCells` for each allocated zone. Diagnostics include seed values, asset selection quantities and rejected placements. The inspector can view architecture and zone stages independently of furniture.

## Asset library

| Method and route           | Input / result                                                                                                                                                    |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET `/assets`              | Built-in assets merged with local/MongoDB overrides.                                                                                                              |
| POST `/assets/validate`    | Full asset metadata. Validates shared JSON Schema and Python semantic rules.                                                                                      |
| PUT `/assets/:id`          | Full metadata; edits always set `approved:false` and increment metadata version.                                                                                  |
| POST `/assets/:id/approve` | `{visualReviewConfirmed:true}`. Verifies all orientation PNGs, decoded image integrity, size, transparency, metadata, and records explicit human visual approval. |
| POST `/references`         | Multipart `image`; PNG/JPEG, maximum 8 MB. Returns storage ID and a local image URL. The same PNG upload route supports custom sprite import.                     |

Python `/assets/inspect` accepts `{asset,pngBase64}` for decoded PNG measurements. Perspective, pixel density appearance, lighting and style remain visual-review responsibilities. Editing metadata does not automatically approve it. Live image generation is deliberately disabled; import/review is available.

## Persistence

| Method and route           | Input / result                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| GET / POST `/projects`     | List projects or create `{name,description?}`.                                            |
| GET `/maps`                | Saved map summaries.                                                                      |
| GET `/maps/:id`            | Complete saved result, including reproduction inputs and asset metadata snapshots.        |
| POST `/maps`               | `{result,name?}`. Revalidates the map before writing.                                     |
| POST `/maps/:id/reproduce` | Regenerate with the saved seeds, configuration, room or scene, and pinned asset metadata. |

Local JSON collections and MongoDB both retain up to 200 records in list responses. Local fallback retains the latest 200 records per collection and serializes atomic file writes. Sprite binaries live in `runtime/uploads`; MongoDB stores file references. There is no delete route in this prototype.

## Optional OpenRouter

| Method and route       | Input / result                                                                     |
| ---------------------- | ---------------------------------------------------------------------------------- |
| GET `/settings`        | Nonsecret role assignments and operational mode.                                   |
| PUT `/settings/models` | Role-to-model-ID dictionary, validated against discovered input/output modalities. |
| GET `/models`          | Cached OpenRouter model discovery (one-hour TTL).                                  |
| GET `/usage`           | Logged calls, token counts and provider-reported costs when present.               |

The adapter uses backend-only `OPENROUTER_API_KEY`. It requests JSON, validates locally against shared schemas, uses an in-memory one-hour/100-entry cache, retries at most three attempts, sets a 45-second request timeout, and optionally uses `OPENROUTER_FALLBACK_MODEL` on the final attempt. Provider errors are sanitized. Cost is `null` when not returned; no estimated cost is invented. Invalid output still records incurred usage. Logged records contain no prompts, image bytes or authorization headers.

Capability discovery follows the official [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models). The previous live adapter still produces the concrete scene contract for existing API clients. The dynamic room UI calls the offline planner. A future provider can return a `RoomSpec` after schema and semantic validation.

## Errors

Malformed contracts return HTTP 422; missing records return 404; unavailable engine/provider returns 503/502; unsupported browser origins return 403. Spatial unsatisfiability is a normal HTTP 200 result with `ok:false`, structured constraint codes and rejected candidate diagnostics. No rejected map is sent to Phaser.
