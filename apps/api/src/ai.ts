import { createHash } from 'node:crypto';
import { check, schemas, baseAssets } from './contracts.js';
import { store } from './store.js';

export const roles = ['planner', 'vision', 'asset_manager', 'image', 'reviewer'] as const;
export type Role = (typeof roles)[number];
export const assignments: Record<Role, string> = {
  planner: process.env.OPENROUTER_PLANNER_MODEL || '',
  vision: process.env.OPENROUTER_VISION_MODEL || '',
  asset_manager: process.env.OPENROUTER_ASSET_MANAGER_MODEL || '',
  image: process.env.OPENROUTER_IMAGE_MODEL || '',
  reviewer: process.env.OPENROUTER_REVIEWER_MODEL || '',
};
const cache = new Map<string, { expires: number; value: any }>();
let modelCache: { expires: number; data: any[] } | undefined;
export async function models(): Promise<any[]> {
  if (modelCache && modelCache.expires > Date.now()) return modelCache.data;
  const res = await fetch('https://openrouter.ai/api/v1/models?output_modalities=all', {
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok)
    throw Object.assign(new Error('OpenRouter model discovery unavailable'), { status: 502 });
  const body: any = await res.json();
  if (!Array.isArray(body.data)) throw new Error('Malformed model discovery response');
  modelCache = { expires: Date.now() + 3600000, data: body.data };
  return body.data;
}
export async function configure(body: Record<string, string>) {
  const available = await models();
  for (const [role, id] of Object.entries(body)) {
    if (!roles.includes(role as Role) || typeof id !== 'string')
      throw Object.assign(new Error('Unknown model role'), { status: 422 });
    if (!id) continue;
    const model = available.find((m) => m.id === id);
    if (!model) throw Object.assign(new Error('Unknown model ID'), { status: 422 });
    if (role === 'image' && !model.architecture?.output_modalities?.includes('image'))
      throw Object.assign(new Error('Model does not produce images'), { status: 422 });
    if (
      ['vision', 'reviewer'].includes(role) &&
      !model.architecture?.input_modalities?.includes('image')
    )
      throw Object.assign(new Error('Model does not accept images'), { status: 422 });
  }
  Object.assign(assignments, body);
  await store.put('settings', { assignments }, 'ai');
  return assignments;
}
export async function planWithAI(description: string, image?: string) {
  if (!process.env.OPENROUTER_API_KEY)
    throw Object.assign(
      new Error('Set OPENROUTER_API_KEY in the backend environment to use live planning'),
      { status: 503 },
    );
  const role: Role = image ? 'vision' : 'planner';
  const primary = assignments[role];
  if (!primary) throw Object.assign(new Error(`Configure a ${role} model first`), { status: 422 });
  const available = await models();
  const model = available.find((m) => m.id === primary);
  if (!model || (image && !model.architecture?.input_modalities?.includes('image')))
    throw Object.assign(new Error('Configured model lacks required input capabilities'), {
      status: 422,
    });
  const key = createHash('sha256')
    .update(JSON.stringify([primary, description, image, schemas.scene, baseAssets]))
    .digest('hex');
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now()) return { ...hit.value, cached: true };
  const messages = [
    {
      role: 'system',
      content: `You are a semantic interior scene planner. Return JSON matching this schema: ${JSON.stringify(schemas.scene)}. Never provide coordinates. Use only these approved assets: ${JSON.stringify(baseAssets.filter((a) => !['architecture', 'character'].includes(a.category)).map((a) => ({ id: a.id, category: a.category, footprint: a.footprint, supportedOrientations: a.supportedOrientations, requiresWall: a.requiresWall, requiresSurface: a.requiresSurface, surfaceSockets: a.surfaceSockets })))}. Limit to 3 zones and 4 furniture groups. Every non-anchor object must relate to another member. Use north-facing chairs south of tables with facing_object distance 2. Put storage zones at north wall. Use a coherent hearth_pixel style. Reference tags should describe recognized asset categories. Required surface items need attached_to_surface relations. Do not invent asset IDs.`,
    },
    {
      role: 'user',
      content: image
        ? [
            { type: 'text', text: description },
            { type: 'image_url', image_url: { url: image } },
          ]
        : description,
    },
  ];
  const fallback = process.env.OPENROUTER_FALLBACK_MODEL;
  let failure = 'AI planning failed';
  for (let attempt = 0; attempt < 3; attempt++) {
    const selected = attempt === 2 && fallback ? fallback : primary;
    try {
      const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
          'Content-Type': 'application/json',
          'X-Title': 'Infiniture local prototype',
        },
        body: JSON.stringify({
          model: selected,
          messages,
          temperature: 0.3,
          max_tokens: 6000,
          response_format: { type: 'json_object' },
        }),
        signal: AbortSignal.timeout(45000),
      });
      if (!res.ok) {
        failure = `OpenRouter request failed (${res.status})`;
        if (res.status < 500 && res.status !== 429) break;
        continue;
      }
      const body: any = await res.json();
      const content = body.choices?.[0]?.message?.content;
      await store.put('ai_usage', {
        role,
        model: selected,
        success: true,
        promptTokens: body.usage?.prompt_tokens ?? 0,
        completionTokens: body.usage?.completion_tokens ?? 0,
        cost: body.usage?.cost ?? null,
      });
      const scene = JSON.parse(content);
      check('scene', scene);
      const value = { scene, mode: 'live', model: selected, cached: false };
      if (cache.size >= 100) cache.delete(cache.keys().next().value!);
      cache.set(key, { expires: Date.now() + 3600000, value });
      return value;
    } catch (e) {
      failure =
        e instanceof SyntaxError
          ? 'Model returned invalid JSON'
          : (e as Error).message.startsWith('Invalid scene')
            ? 'Model returned invalid scene schema'
            : 'AI request timed out or failed validation';
    }
  }
  await store.put('ai_usage', { role, model: primary, success: false, error: failure, cost: null });
  throw Object.assign(new Error(failure), { status: 502 });
}
