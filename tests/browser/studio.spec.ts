import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';

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
  async function walkTo(x: number, y: number) {
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
            { intervals: [20], timeout: 15000 },
          )
          .toBeLessThan(0.13);
      } finally {
        await page.keyboard.up(key);
      }
    }
  }
  await walkTo(generated.layout.entrance.x, generated.layout.entrance.y);
  const path = generated.validation.paths.find((p: any) => p.target === 'group_0_anchor').points;
  for (let i = 1; i < path.length; i++) {
    const prev = path[i - 1],
      p = path[i],
      next = path[i + 1];
    if (!next || p.x - prev.x !== next.x - p.x || p.y - prev.y !== next.y - p.y)
      await walkTo(p.x, p.y);
  }
  await page.keyboard.press('e');
  await expect(page.getByText(/Caretaker: Welcome in/)).toBeVisible();
  const solid = generated.validation.collisions.find((b: any) => b.objectId === 'group_0_anchor');
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
  await expect(page.getByRole('textbox', { name: 'Semantic scene JSON' })).toHaveValue(/tavern/);
  expect(errors).toEqual([]);
});

for (const [concept, seed] of [
  ['library', 2048],
  ['bedroom', 4096],
  ['office', 8192],
] as const) {
  test(`visual baseline: ${concept} seed ${seed}`, async ({ page }) => {
    await page.goto('/');
    await page
      .getByLabel('What are we building?')
      .fill(`A ${concept} with clear functional areas.`);
    await page.getByLabel('Generation seed').fill(String(seed));
    await page.getByRole('button', { name: 'Generate interior', exact: true }).click();
    const canvas = page.locator('canvas');
    await expect(canvas).toHaveAttribute('data-ready', 'true');
    await expect(canvas).toHaveScreenshot(`${concept}-${seed}.png`, { maxDiffPixelRatio: 0.002 });
    await page.screenshot({ path: `docs/screenshots/${concept}-${seed}.png`, fullPage: true });
  });
}

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
