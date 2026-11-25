import express from 'express';
import multer from 'multer';
import path from 'node:path';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { root, check, baseAssets } from './contracts.js';
import { store } from './store.js';
import { assignments, configure, models, planWithAI } from './ai.js';

const app = express();
const engine = process.env.ENGINE_URL || 'http://127.0.0.1:8000';
app.disable('x-powered-by');
app.use(express.json({ limit: '3mb' }));
// Local prototype: bind loopback and reject browser writes from other origins.
app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && !/^http:\/\/(localhost|127\.0\.0\.1):(5174|3001)$/.test(origin))
    return res.status(403).json({ error: 'Untrusted origin' });
  next();
});
const asyncRoute =
  (fn: any) => (req: express.Request, res: express.Response, next: express.NextFunction) =>
    Promise.resolve(fn(req, res)).catch(next);
export async function engineCall(route: string, body?: any) {
  let res: Response;
  try {
    res = await fetch(engine + route, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(65000),
    });
  } catch {
    throw Object.assign(new Error('Procedural engine unavailable. Start the Python service.'), {
      status: 503,
    });
  }
  const data = await res.json();
  if (!res.ok)
    throw Object.assign(new Error('Engine rejected the request'), {
      status: res.status,
      details: data,
    });
  return data;
}
async function assets() {
  const overrides = await store.list('assets');
  return [
    ...baseAssets.filter((a) => !overrides.some((o) => o.id === a.id)),
    ...overrides.map(({ createdAt, updatedAt, ...a }) => a),
  ];
}
app.get(
  '/api/health',
  asyncRoute(async (_: any, res: any) => {
    let engineStatus = 'offline';
    try {
      await engineCall('/health');
      engineStatus = 'online';
    } catch {}
    res.json({
      status: engineStatus === 'online' ? 'ok' : 'degraded',
      engine: engineStatus,
      storage: store.status,
      warning: store.warning,
      ai: process.env.AI_MODE || 'mock',
      openrouterConfigured: !!process.env.OPENROUTER_API_KEY,
    });
  }),
);
app.get(
  '/api/assets',
  asyncRoute(async (_: any, res: any) => res.json(await assets())),
);
app.post(
  '/api/assets/validate',
  asyncRoute(async (req: any, res: any) => {
    check('asset', req.body);
    res.json(await engineCall('/assets/validate', req.body));
  }),
);
app.put(
  '/api/assets/:id',
  asyncRoute(async (req: any, res: any) => {
    check('asset', req.body);
    if (req.params.id !== req.body.id)
      throw Object.assign(new Error('Asset ID mismatch'), { status: 422 });
    const a = req.body;
    const sprites = [a.sprite, ...Object.values(a.orientationSprites)] as string[];
    if (sprites.some((s) => !/^\/(assets\/[a-zA-Z0-9_-]+\.png|uploads\/[a-f0-9-]+\.png)$/.test(s)))
      throw Object.assign(
        new Error('Sprites must be local validated PNG uploads or bundled assets'),
        { status: 422 },
      );
    await engineCall('/assets/validate', a);
    const old = (await assets()).find((v) => v.id === a.id);
    // Metadata edits always return to review; a separate explicit approval action is required.
    res.json(
      await store.put('assets', { ...a, approved: false, version: (old?.version || 0) + 1 }, a.id),
    );
  }),
);
app.post(
  '/api/assets/:id/approve',
  asyncRoute(async (req: any, res: any) => {
    const a = (await assets()).find((v) => v.id === req.params.id);
    if (!a) throw Object.assign(new Error('Asset not found'), { status: 404 });
    if (req.body.visualReviewConfirmed !== true)
      throw Object.assign(
        new Error('Confirm perspective, pixel density, proportions and style review'),
        { status: 422 },
      );
    for (const sprite of new Set([a.sprite, ...Object.values(a.orientationSprites)] as string[])) {
      const file = sprite.startsWith('/assets/')
        ? path.join(root, 'apps/web/public', sprite)
        : path.join(root, 'runtime', sprite);
      const image = await readFile(file);
      if (
        image.length < 24 ||
        image.toString('hex', 0, 8) !== '89504e470d0a1a0a' ||
        image.readUInt32BE(16) !== a.spriteSize.width ||
        image.readUInt32BE(20) !== a.spriteSize.height
      )
        throw Object.assign(new Error('Sprite dimensions or PNG format do not match metadata'), {
          status: 422,
        });
      const inspection = await engineCall('/assets/inspect', {
        asset: a,
        pngBase64: image.toString('base64'),
      });
      if (!inspection.valid)
        throw Object.assign(new Error(inspection.failures.join('; ')), { status: 422 });
    }
    check('asset', a);
    await engineCall('/assets/validate', a);
    res.json(await store.put('assets', { ...a, approved: true }, a.id));
  }),
);
app.post(
  '/api/plan',
  asyncRoute(async (req: any, res: any) => {
    const { referenceId, mode, ...input } = req.body;
    check('plan', input);
    let result;
    if (mode === 'live') {
      let image: string | undefined;
      if (referenceId) {
        const r = await store.get('references', referenceId);
        if (!r) throw Object.assign(new Error('Reference not found'), { status: 404 });
        image = `data:${r.mime};base64,${(await readFile(path.join(root, 'runtime/uploads', r.filename))).toString('base64')}`;
      }
      result = await planWithAI(input.description, image);
    } else {
      result = await engineCall('/plan', input);
      if (referenceId)
        result.notice += ' Uploaded reference is stored but not analyzed in mock mode.';
    }
    await store.put('scenes', { ...result, referenceId: referenceId || null });
    res.json(result);
  }),
);
app.post(
  '/api/generate',
  asyncRoute(async (req: any, res: any) => {
    check('generate', req.body);
    const request = { ...req.body, assets: await assets() };
    const result = await engineCall('/generate', request);
    await store.put('history', {
      ok: result.ok,
      title: req.body.room?.title ?? req.body.scene?.title ?? 'Untitled room',
      diagnostics: result.diagnostics,
    });
    res.json(result);
  }),
);
app.post(
  '/api/validate',
  asyncRoute(async (req: any, res: any) => {
    check('validate', req.body);
    res.json(await engineCall('/validate', req.body));
  }),
);
app.get(
  '/api/capabilities',
  asyncRoute(async (_: any, res: any) => res.json(await engineCall('/capabilities'))),
);
app.get(
  '/api/maps',
  asyncRoute(async (_: any, res: any) =>
    res.json(
      (await store.list('maps')).map(({ result, ...m }) => ({
        ...m,
        title: result.scene.title,
        seed: result.layout.seed,
        score: result.diagnostics.candidates.find(
          (c: any) => c.index === result.diagnostics.selectedCandidate,
        )?.score?.total,
      })),
    ),
  ),
);
app.get(
  '/api/maps/:id',
  asyncRoute(async (req: any, res: any) => {
    const m = await store.get('maps', req.params.id);
    if (!m) return res.status(404).json({ error: 'Map not found' });
    res.json(m);
  }),
);
app.post(
  '/api/maps/:id/reproduce',
  asyncRoute(async (req: any, res: any) => {
    const m = await store.get('maps', req.params.id);
    if (!m) return res.status(404).json({ error: 'Map not found' });
    res.json(await engineCall('/generate', m.result.reproduction));
  }),
);
app.post(
  '/api/maps',
  asyncRoute(async (req: any, res: any) => {
    const result = req.body.result;
    if (!result?.ok)
      throw Object.assign(new Error('Only successful maps can be saved'), { status: 422 });
    const request = { request: result.reproduction, layout: result.layout };
    check('validate', request);
    const validation = await engineCall('/validate', request);
    if (!validation.valid)
      throw Object.assign(new Error('Map failed independent validation'), {
        status: 422,
        details: validation.failures,
      });
    res.json(
      await store.put('maps', {
        result: { ...result, validation },
        name: String(req.body.name || result.scene.title).slice(0, 160),
      }),
    );
  }),
);
app.get(
  '/api/history',
  asyncRoute(async (_: any, res: any) => res.json(await store.list('history'))),
);
app.get(
  '/api/projects',
  asyncRoute(async (_: any, res: any) => res.json(await store.list('projects'))),
);
app.post(
  '/api/projects',
  asyncRoute(async (req: any, res: any) => {
    if (typeof req.body.name !== 'string' || !req.body.name.trim())
      throw Object.assign(new Error('Project name required'), { status: 422 });
    res.json(
      await store.put('projects', {
        name: req.body.name.slice(0, 160),
        description: String(req.body.description || '').slice(0, 4000),
      }),
    );
  }),
);
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024, files: 1 },
});
app.post(
  '/api/references',
  upload.single('image'),
  asyncRoute(async (req: any, res: any) => {
    if (!req.file) throw Object.assign(new Error('Image is required'), { status: 422 });
    const bytes = req.file.buffer as Buffer;
    const png = bytes.length >= 24 && bytes.toString('hex', 0, 8) === '89504e470d0a1a0a';
    const jpeg = bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
    if (!png && !jpeg) throw Object.assign(new Error('Use a PNG or JPEG image'), { status: 422 });
    if (png && (bytes.readUInt32BE(16) > 4096 || bytes.readUInt32BE(20) > 4096))
      throw Object.assign(new Error('Image dimensions must be at most 4096 pixels'), {
        status: 422,
      });
    const id = randomUUID();
    const filename = id + (png ? '.png' : '.jpg');
    await writeFile(path.join(root, 'runtime/uploads', filename), bytes);
    res.json(
      await store.put(
        'references',
        {
          filename,
          mime: png ? 'image/png' : 'image/jpeg',
          url: `/uploads/${filename}`,
          originalName: req.file.originalname,
        },
        id,
      ),
    );
  }),
);
app.use(
  '/uploads',
  express.static(path.join(root, 'runtime/uploads'), {
    setHeaders: (res) => {
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.setHeader('Content-Security-Policy', "default-src 'none'");
    },
  }),
);
app.get(
  '/api/settings',
  asyncRoute(async (_: any, res: any) =>
    res.json({
      assignments,
      mode: process.env.AI_MODE || 'mock',
      keyConfigured: !!process.env.OPENROUTER_API_KEY,
      storage: store.status,
      assetGenerationEnabled: false,
    }),
  ),
);
app.put(
  '/api/settings/models',
  asyncRoute(async (req: any, res: any) => res.json(await configure(req.body))),
);
app.get(
  '/api/models',
  asyncRoute(async (_: any, res: any) => res.json(await models())),
);
app.get(
  '/api/usage',
  asyncRoute(async (_: any, res: any) => res.json(await store.list('ai_usage'))),
);
app.use((err: any, _: any, res: express.Response, __: any) =>
  res.status(err.status || (err.code === 'LIMIT_FILE_SIZE' ? 413 : 500)).json({
    error: err.status
      ? err.message
      : err.code === 'LIMIT_FILE_SIZE'
        ? 'Image exceeds 8 MB'
        : 'Internal request failed',
    ...(err.details ? { details: err.details } : {}),
  }),
);
await mkdir(path.join(root, 'runtime/uploads'), { recursive: true });
await store.init();
const settings = await store.get('settings', 'ai');
if (settings?.assignments) Object.assign(assignments, settings.assignments);
app.listen(Number(process.env.PORT || 3001), '127.0.0.1', () =>
  console.log(
    `Infiniture API http://127.0.0.1:${process.env.PORT || 3001} · storage: ${store.status}`,
  ),
);
