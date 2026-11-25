# Local API

Express: `http://127.0.0.1:3001/api`. Python OpenAPI and interactive contracts: `http://127.0.0.1:8000/docs`. Vite proxies `/api` and `/uploads`. All servers bind loopback. This prototype has no remote authentication layer and is intended for a single local developer.

## Core pipeline

| Method and route    | Input / result                                                                                                                                                                                                                                                                                                                                  |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET `/health`       | Engine connectivity, storage mode and credential-presence boolean; no secret values.                                                                                                                                                                                                                                                            |
| POST `/plan`        | `{description, density?, decorationDensity?, mode?: "mock" or "live", referenceId?}`. Returns a validated semantic scene. Mock mode explicitly does not analyze uploaded images.                                                                                                                                                                |
| POST `/generate`    | Shared `generate.schema.json`: scene plus width/height, seed, candidate count, search/time budget, player size, densities and weights. Backend uses its approved asset registry. Returns `{ok, layout?, validation?, diagnostics, scene?, assets?, layers?, stages?, reproduction?}`. Failed spatial searches return `ok:false` with no layout. |
| POST `/validate`    | `{request: GenerateRequest, layout: Layout}`. Independent full validation, collision rectangles, player-sized walkability, paths, interactions and NPC positions.                                                                                                                                                                               |
| GET `/capabilities` | Supported relationship names, layers and tile size.                                                                                                                                                                                                                                                                                             |
| GET `/history`      | Recent generation diagnostics, including failed generations.                                                                                                                                                                                                                                                                                    |

Semantic scene groups reference a primary `anchorId`. Object relations reference members in the same group; `separated_from_zone` references a zone. The planner never supplies final coordinates. Unsupported relationships, cycles and invalid references are rejected. Use `packages/shared/scene.schema.json` for the complete contract.

Generation stages are available in the result (`architecture`, `zones`, `groups`, `validation`). The inspector can view architecture and zone stages without furniture, and the full graph/diagnostics are inspectable. There is no independent public zoning mutation endpoint; the engine allocates zones consistently with assembled group requirements.

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

| Method and route           | Input / result                                                                     |
| -------------------------- | ---------------------------------------------------------------------------------- |
| GET / POST `/projects`     | List projects or create `{name,description?}`.                                     |
| GET `/maps`                | Saved map summaries.                                                               |
| GET `/maps/:id`            | Complete saved result, including reproduction inputs and asset metadata snapshots. |
| POST `/maps`               | `{result,name?}`. Revalidates the map before writing.                              |
| POST `/maps/:id/reproduce` | Regenerate using the saved seed, configuration, scene and pinned asset metadata.   |

Local JSON collections and MongoDB both retain up to 200 records in list responses. Local fallback retains the latest 200 records per collection and serializes atomic file writes. Sprite binaries live in `runtime/uploads`; MongoDB stores file references. There is no delete route in this prototype.

## Optional OpenRouter

| Method and route       | Input / result                                                                     |
| ---------------------- | ---------------------------------------------------------------------------------- |
| GET `/settings`        | Nonsecret role assignments and operational mode.                                   |
| PUT `/settings/models` | Role-to-model-ID dictionary, validated against discovered input/output modalities. |
| GET `/models`          | Cached OpenRouter model discovery (one-hour TTL).                                  |
| GET `/usage`           | Logged calls, token counts and provider-reported costs when present.               |

The adapter uses backend-only `OPENROUTER_API_KEY`. It requests JSON, validates locally against shared schemas, uses an in-memory one-hour/100-entry cache, retries at most three attempts, sets a 45-second request timeout, and optionally uses `OPENROUTER_FALLBACK_MODEL` on the final attempt. Provider errors are sanitized. Cost is `null` when not returned; no estimated cost is invented. Invalid output still records incurred usage. Logged records contain no prompts, image bytes or authorization headers.

Capability discovery follows the official [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models). JSON mode is not treated as a schema guarantee: every response is validated again before engine execution. Only scene planning and combined reference-image/scene planning are executable live paths. Asset-manager, image-generator and reviewer model slots are configuration groundwork; those live workflows remain unfinished.

## Errors

Malformed contracts return HTTP 422; missing records return 404; unavailable engine/provider returns 503/502; unsupported browser origins return 403. Spatial unsatisfiability is a normal HTTP 200 result with `ok:false`, structured constraint codes and rejected candidate diagnostics. No rejected map is sent to Phaser.
