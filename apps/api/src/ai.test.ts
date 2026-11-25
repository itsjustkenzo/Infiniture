import test from 'node:test';
import assert from 'node:assert/strict';
import { assignments, configure, planWithAI } from './ai.js';
import { store } from './store.js';
test('OpenRouter adapter validates capabilities, caches valid JSON, tracks usage and rejects malformed output', async () => {
  const originalFetch = globalThis.fetch;
  const originalPut = store.put;
  const originalKey = process.env.OPENROUTER_API_KEY;
  const calls: any[] = [];
  const records: any[] = [];
  let malformed = false;
  const scene = {
    title: 'Provider test',
    zones: [{ id: 'z', purpose: 'Research' }],
    groups: [
      { id: 'g', zoneId: 'z', anchorId: 'desk', objects: [{ id: 'desk', assetId: 'desk' }] },
    ],
  };
  try {
    process.env.OPENROUTER_API_KEY = 'test-only-not-a-real-key';
    assignments.planner = 'test/model';
    store.put = async (c: string, data: any) => {
      records.push({ collection: c, ...data });
      return { id: 'test', createdAt: '', updatedAt: '', ...data };
    };
    globalThis.fetch = (async (url: any, options: any) => {
      calls.push({ url, options });
      if (String(url).includes('/models?'))
        return new Response(
          JSON.stringify({
            data: [
              {
                id: 'test/model',
                architecture: { input_modalities: ['text'], output_modalities: ['text'] },
              },
            ],
          }),
          { status: 200 },
        );
      return new Response(
        JSON.stringify({
          choices: [{ message: { content: malformed ? 'not JSON' : JSON.stringify(scene) } }],
          usage: { prompt_tokens: 100, completion_tokens: 60, cost: 0.001 },
        }),
        { status: 200 },
      );
    }) as typeof fetch;
    await assert.rejects(() => configure({ image: 'test/model' }), /does not produce images/);
    const first = await planWithAI('unique cache fixture');
    assert.equal(first.scene.title, 'Provider test');
    assert.equal(first.cached, false);
    const second = await planWithAI('unique cache fixture');
    assert.equal(second.cached, true);
    assert.equal(calls.filter((c) => String(c.url).includes('chat/completions')).length, 1);
    assert.equal(records.filter((r) => r.collection === 'ai_usage')[0].cost, 0.001);
    malformed = true;
    await assert.rejects(() => planWithAI('malformed fixture'), /invalid JSON/);
    assert.equal(records.at(-1).success, false);
    assert(!JSON.stringify(records).includes('test-only-not-a-real-key'));
  } finally {
    globalThis.fetch = originalFetch;
    store.put = originalPut;
    assignments.planner = '';
    if (originalKey === undefined) delete process.env.OPENROUTER_API_KEY;
    else process.env.OPENROUTER_API_KEY = originalKey;
  }
});
