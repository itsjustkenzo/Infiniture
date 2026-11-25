import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser',
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    browserName: 'chromium',
    channel: 'msedge',
    headless: true,
    viewport: { width: 1480, height: 1080 },
    screenshot: 'only-on-failure',
  },
  outputDir: 'runtime/browser-results',
  reporter: [['list'], ['json', { outputFile: 'docs/browser-test-results.json' }]],
});
