import { test, expect } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';
import fs from 'node:fs/promises';

async function walkTo(page: Page, canvas: Locator, x: number, y: number) {
  for (const [axis, target, negative, positive] of [
    ['x', x, 'a', 'd'],
    ['y', y, 'w', 's'],
  ] as const) {
    const start = Number(await canvas.getAttribute(`data-player-${axis}`));
    if (Math.abs(start - target) < 0.13) continue;
    const key = target > start ? positive : negative;
    await page.keyboard.down(key);
    try {
      await expect
        .poll(
          async () => Math.abs(Number(await canvas.getAttribute(`data-player-${axis}`)) - target),
          {
            intervals: [20],
            timeout: 15000,
          },
        )
        .toBeLessThan(0.13);
    } finally {
      await page.keyboard.up(key);
    }
  }
}

async function followPath(page: Page, canvas: Locator, path: { x: number; y: number }[]) {
  for (let i = 1; i < path.length; i++) {
    const prev = path[i - 1],
      p = path[i],
      next = path[i + 1];
    if (!next || p.x - prev.x !== next.x - p.x || p.y - prev.y !== next.y - p.y) {
      await walkTo(page, canvas, p.x, p.y);
    }
  }
}

test('generation identifies invalid form values and backend fields', async ({ page, request }) => {
  const plan = await request.post('http://127.0.0.1:8000/plan', {
    data: { description: 'tavern' },
  });
  expect(plan.ok()).toBeTruthy();
  let planCalls = 0;
  await page.route('**/api/plan', (route) => {
    planCalls++;
    return route.fulfill({ response: plan });
  });
  await page.route('**/api/generate', async (route) => {
    const layout = await request.post('http://127.0.0.1:8000/generate', {
      data: route.request().postDataJSON(),
    });
    expect((await layout.json()).ok).toBe(true);
    await route.fulfill({ response: layout });
  });
  await page.route(
    '**/api/generate',
    async (route) => {
      // Exercise the real Express schema rejection without persisting a test generation.
      const payload = route.request().postDataJSON();
      const invalid = await route.fetch({ postData: { ...payload, candidates: 0 } });
      expect(invalid.status()).toBe(422);
      await route.fulfill({ response: invalid });
    },
    { times: 1 },
  );

  await page.goto('/');
  const width = page.getByRole('spinbutton', { name: /^Width/ });
  const generate = page.getByRole('button', { name: 'Generate interior', exact: true });
  await width.fill('11');
  await generate.click();
  await expect(page.getByRole('status')).toContainText(
    'Width must be a whole number from 12 to 64.',
  );
  expect(planCalls).toBe(0);

  await width.fill('28');
  await generate.click();
  await expect(page.getByRole('status')).toContainText('candidates: must be >= 1');
  await generate.click();
  await expect(page.locator('canvas')).toHaveAttribute('data-ready', 'true');
});

test('game keys stay in the focused map and room description typing works', async ({
  page,
  request,
}) => {
  // Get a real layout directly from the engine so this test does not persist generation history.
  const plan = await request.post('http://127.0.0.1:8000/plan', {
    data: { description: 'tavern' },
  });
  expect(plan.ok()).toBeTruthy();
  const layout = await request.post('http://127.0.0.1:8000/generate', {
    data: { scene: (await plan.json()).scene },
  });
  expect((await layout.json()).ok).toBe(true);
  await page.route('**/api/plan', (route) => route.fulfill({ response: plan }));
  await page.route('**/api/generate', (route) => route.fulfill({ response: layout }));

  await page.goto('/');
  await page.getByRole('button', { name: 'Generate interior', exact: true }).click();
  const canvas = page.locator('canvas');
  await expect(canvas).toHaveAttribute('data-ready', 'true');

  const description = page.getByLabel('What are we building?');
  await description.fill('');
  await description.pressSequentially('esqwad');
  await description.press('ArrowLeft');
  await description.press('x');
  await expect(description).toHaveValue('esqwaxd');

  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await canvas.click();
  await expect(canvas).toHaveAttribute('data-player-y', /\d/);
  const startY = Number(await canvas.getAttribute('data-player-y'));
  await page.keyboard.down('ArrowUp');
  try {
    await expect
      .poll(async () => Number(await canvas.getAttribute('data-player-y')))
      .toBeLessThan(startY - 0.5);
  } finally {
    await page.keyboard.up('ArrowUp');
  }
  await page.keyboard.press('e');
  await expect(page.getByText('Move closer to the caretaker to talk.')).toBeVisible();

  await description.fill('');
  await description.pressSequentially('quiet space');
  await expect(description).toHaveValue('quiet space');
});

test('generate, inspect, play, save and reload a coherent map', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => {
    errors.push(e.message);
    console.log('Browser runtime error:', e.stack);
  });
  const health = await request.get('/api/health');
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).engine).toBe('online');
  await page.goto('/');
  await page.getByLabel('Room shape').selectOption('rectangle');
  await page.getByLabel('Vary dimensions by seed').uncheck();
  await expect(page.getByRole('heading', { name: 'Interior map generator' })).toBeVisible();
  const generation = page.waitForResponse((r) => r.url().endsWith('/api/generate'));
  await page.getByRole('button', { name: 'Generate interior', exact: true }).click();
  const generated = await (await generation).json();
  await expect(page.locator('canvas')).toHaveAttribute('data-ready', 'true');
  await expect(page.getByText('Passed', { exact: true })).toBeVisible();
  await fs.mkdir('docs/screenshots', { recursive: true });
  await page.screenshot({ path: 'docs/screenshots/studio-tavern.png', fullPage: true });
  await page.getByRole('button', { name: 'Layout inspector', exact: true }).click();
  await expect(page.getByText('Candidate comparison', { exact: true })).toBeVisible();
  await page.getByLabel('Relationships', { exact: true }).check();
  await page.screenshot({ path: 'docs/screenshots/inspector-tavern.png', fullPage: true });
  await page.getByRole('button', { name: 'Play mode', exact: true }).click();
  await expect(page.locator('canvas')).toHaveAttribute('data-ready', 'true');
  const canvas = page.locator('canvas');
  await canvas.click();
  await expect(canvas).toHaveAttribute('data-player-y', /\d/);
  const beforeY = Number(await canvas.getAttribute('data-player-y'));
  await page.keyboard.down('w');
  await page.waitForTimeout(700);
  await page.keyboard.up('w');
  await expect
    .poll(async () => Number(await canvas.getAttribute('data-player-y')))
    .toBeLessThan(beforeY - 0.5);
  // Return to the entrance, then follow the independently validated route using real keyboard input.
  await walkTo(page, canvas, generated.layout.entrance.x, generated.layout.entrance.y);
  const primaryId = generated.scene.groups.find(
    (g: any) => g.id === generated.scene.npcs[0].groupId,
  ).anchorId;
  const path = generated.validation.paths.find((p: any) => p.target === primaryId).points;
  await followPath(page, canvas, path);
  await page.keyboard.press('e');
  await expect(page.getByText(/Caretaker: Welcome in/)).toBeVisible();
  const solid = generated.validation.collisions.find((b: any) => b.objectId === primaryId);
  await page.keyboard.down('w');
  await page.waitForTimeout(900);
  await page.keyboard.up('w');
  const stoppedY = Number(await canvas.getAttribute('data-player-y'));
  expect(stoppedY).toBeGreaterThanOrEqual(
    solid.y + solid.height + generated.layout.playerSize / 2 - 0.01,
  );
  expect(stoppedY).toBeLessThan(solid.y + solid.height + 0.45);
  await page.screenshot({ path: 'docs/screenshots/play-tavern.png', fullPage: true });
  await page.getByRole('button', { name: 'Save map', exact: true }).click();
  await expect(page.getByText(/Map saved with its scene/)).toBeVisible();
  await page.getByRole('button', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your saved worlds' })).toBeVisible();
  await page.locator('.saved-map').first().click();
  await expect(page.locator('canvas')).toBeVisible();
  await page.getByRole('button', { name: /Asset library/ }).click();
  await expect(page.locator('.asset-card')).toHaveCount(32);
  await page.getByRole('textbox', { name: 'Search assets' }).fill('bookshelf');
  await expect(page.locator('.asset-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Scene planner', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Room specification JSON' })).toHaveValue(
    /tavern/,
  );
  expect(errors).toEqual([]);
});

for (const [concept, seed, shape] of [
  ['library', 2048, 'l_shape'],
  ['bedroom', 4096, 'alcove'],
  ['office', 8192, 'orthogonal'],
] as const) {
  test(`visual baseline: ${concept} seed ${seed}`, async ({ page }) => {
    await page.goto('/');
    await page
      .getByLabel('What are we building?')
      .fill(`A ${concept} with clear functional areas.`);
    await page.getByLabel('Geometry seed').fill(String(seed));
    await page.getByLabel('Placement seed').fill(String(seed));
    await page.getByLabel('Room shape').selectOption(shape);
    await page.getByRole('button', { name: 'Generate interior', exact: true }).click();
    const canvas = page.locator('canvas');
    await expect(canvas).toHaveAttribute('data-ready', 'true');
    await expect(canvas).toHaveScreenshot(`${concept}-${seed}.png`, { maxDiffPixelRatio: 0.002 });
    await page.screenshot({ path: `docs/screenshots/${concept}-${seed}.png`, fullPage: true });
  });
}

test('regeneration scopes preserve or rebuild the intended parts of a room', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Room shape').selectOption('l_shape');
  await page.getByLabel('Entrances', { exact: true }).fill('3');
  await page.getByLabel('Add internal partition').check();
  const receive = () => page.waitForResponse((r) => r.url().endsWith('/api/generate'));
  const first = receive();
  await page.getByRole('button', { name: 'Generate interior', exact: true }).click();
  const original = await (await first).json();
  expect(original.ok).toBe(true);
  expect(original.layout.geometry.shape).toBe('l_shape');
  expect(original.layout.geometry.doors).toHaveLength(3);
  expect(original.layout.geometry.partitions.length).toBeGreaterThan(0);
  async function regenerate(mode: string) {
    await page.getByLabel('Regeneration mode').selectOption(mode);
    const response = receive();
    await page.getByRole('button', { name: 'Regenerate', exact: true }).click();
    const result = await (await response).json();
    expect(result.ok, JSON.stringify(result.diagnostics.failures)).toBe(true);
    return result;
  }
  const arranged = await regenerate('arrange');
  const assets = (map: any) =>
    map.layout.placements.map((p: any) => [p.id, p.assetId].join(':')).sort();
  expect(arranged.layout.geometry).toEqual(original.layout.geometry);
  expect(assets(arranged)).toEqual(assets(original));
  const selected = await regenerate('furniture');
  expect(selected.layout.geometry).toEqual(original.layout.geometry);
  expect(selected.diagnostics.seeds.selection).not.toEqual(original.diagnostics.seeds.selection);
  const rebuilt = await regenerate('geometry');
  expect(rebuilt.layout.geometry).not.toEqual(original.layout.geometry);
  const replanned = await regenerate('variant');
  expect(replanned.reproduction.room.conceptSeed).not.toEqual(
    original.reproduction.room.conceptSeed,
  );
  expect(replanned.reproduction.room.groups).not.toEqual(original.reproduction.room.groups);
  await page.getByRole('button', { name: 'Layout inspector', exact: true }).click();
  await page.getByLabel('Floor cells', { exact: true }).check();
  await page.getByLabel('Wall segments', { exact: true }).check();
  await page.getByLabel('Entrances', { exact: true }).check();
  await expect(page.getByRole('heading', { name: 'Room geometry', exact: true })).toBeVisible();
  await expect(page.getByText('Furniture selection and seeds', { exact: true })).toBeVisible();

  // Find a route to a walkable cell bordering a partition and attempt to cross it.
  const layout = replanned.layout,
    floor = new Set<string>(replanned.validation.reachable.map((p: any) => `${p.x},${p.y}`));
  const border = layout.geometry.partitions.flatMap((p: any) =>
    [
      [p.x + 1, p.y, 'a'],
      [p.x - 1, p.y, 'd'],
      [p.x, p.y + 1, 'w'],
      [p.x, p.y - 1, 's'],
    ].filter(([x, y]) => floor.has(`${x},${y}`)),
  );
  expect(border.length).toBeGreaterThan(0);
  const [tx, ty, key] = border[0] as [number, number, string];
  const start = [Math.floor(layout.entrance.x), Math.floor(layout.entrance.y)];
  const queue = [start],
    parents = new Map<string, number[]>([[start.join(','), start]]);
  for (const [x, y] of queue) {
    if (x === tx && y === ty) break;
    for (const cell of [
      [x - 1, y],
      [x + 1, y],
      [x, y - 1],
      [x, y + 1],
    ]) {
      const id = cell.join(',');
      if (floor.has(id) && !parents.has(id)) {
        parents.set(id, [x, y]);
        queue.push(cell);
      }
    }
  }
  const path = [];
  let at = [tx, ty];
  while (at.join(',') !== start.join(',')) {
    path.push({ x: at[0] + 0.5, y: at[1] + 0.5 });
    at = parents.get(at.join(','))!;
  }
  path.push(layout.entrance);
  await page.getByRole('button', { name: 'Play mode', exact: true }).click();
  const canvas = page.locator('canvas');
  await expect(canvas).toHaveAttribute('data-ready', 'true');
  await canvas.click();
  await expect(canvas).toHaveAttribute('data-player-y', /\d/);
  await followPath(page, canvas, path.reverse());
  const horizontal = key === 'a' || key === 'd';
  const coord = horizontal ? tx : ty;
  const axis = horizontal ? 'x' : 'y';
  await page.keyboard.down(key);
  await page.waitForTimeout(500);
  await page.keyboard.up(key);
  const stopped = Number(await canvas.getAttribute(`data-player-${axis}`));
  const boundary =
    key === 'a' || key === 'w' ? coord + layout.playerSize / 2 : coord + 1 - layout.playerSize / 2;
  expect(Math.abs(stopped - boundary)).toBeLessThan(0.12);
});

test('reference upload, invalid scene rejection and mobile layout', async ({ page, request }) => {
  await page.goto('/');
  await page.locator('.upload-zone input').setInputFiles('apps/web/public/assets/table.png');
  await expect(page.getByText('Reference attached')).toBeVisible();
  const invalid = await request.post('/api/generate', {
    data: { scene: { title: 'broken' }, seed: 0 },
  });
  expect(invalid.status()).toBe(422);
  const forbidden = await request.post('/api/projects', {
    headers: { Origin: 'https://untrusted.example' },
    data: { name: 'invalid' },
  });
  expect(forbidden.status()).toBe(403);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy();
  await page.screenshot({ path: 'docs/screenshots/mobile-studio.png', fullPage: true });
});

test('API map validation rejects modified solid overlaps', async ({ request }) => {
  const scene = (
    await (await request.post('/api/plan', { data: { description: 'office' } })).json()
  ).scene;
  const response = await request.post('/api/generate', {
    data: { scene, seed: 123, candidates: 2 },
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  expect(result.ok).toBeTruthy();
  const ps = result.layout.placements;
  const first = ps.find((p: any) => p.assetId === 'desk');
  const other = ps.find((p: any) => p.assetId === 'table');
  other.x = first.x;
  other.y = first.y;
  const save = await request.post('/api/maps', { data: { result } });
  expect(save.status()).toBe(422);
});
