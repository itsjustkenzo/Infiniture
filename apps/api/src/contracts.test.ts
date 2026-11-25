import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { check, baseAssets } from './contracts.js';
import { Store } from './store.js';
test('bundled assets satisfy shared boundary contract', () => {
  for (const asset of baseAssets) assert.doesNotThrow(() => check('asset', asset));
});
test('malformed requests and AI coordinates are rejected', () => {
  assert.throws(() => check('generate', { scene: {}, seed: 'abc' }));
  assert.throws(() => check('scene', { title: 'Invalid', zones: [], groups: [], x: 5, y: 7 }));
  assert.throws(() => check('asset', { id: 'partial' }));
});
test('concurrent local writes are atomic and survive reopening', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'infiniture-test-'));
  try {
    const store = new Store(dir);
    await store.init();
    await Promise.all(
      Array.from({ length: 20 }, (_, i) => store.put('maps', { seed: i }, String(i))),
    );
    const reopened = new Store(dir);
    assert.equal((await reopened.list('maps')).length, 20);
    await reopened.put('maps', { seed: 99 }, '0');
    assert.equal((await reopened.get('maps', '0'))?.seed, 99);
    assert.equal((await reopened.list('maps')).length, 20);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
