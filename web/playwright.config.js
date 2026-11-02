// Run from the repo root: npx playwright test -c web/playwright.config.js
// Chromium comes from `npx playwright install chromium`, or from PLAYWRIGHT_BROWSERS_PATH when it is set.
const crypto = require('node:crypto');
const os = require('node:os');
const path = require('node:path');
const { defineConfig } = require('@playwright/test');

// Artifacts go to a temp directory named by this checkout's path, so the repo stays clean and the mutant runner's
// parallel copies of the tree never clear each other's output.
const outputDir = path.join(os.tmpdir(), `haptura-pw-${crypto.createHash('sha1').update(__dirname).digest('hex').slice(0, 8)}`);

module.exports = defineConfig({
  testDir: 'tests',
  outputDir,
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  reporter: 'list',
  use: { browserName: 'chromium' },
});
