import { defineConfig } from '@playwright/test'

const SITE_URL = 'http://127.0.0.1:4176/kanto-first-person/'

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: 'line',
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4176',
    url: SITE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  use: {
    baseURL: SITE_URL,
    browserName: 'chromium',
    channel: 'chrome',
    headless: true,
    reducedMotion: 'reduce',
  },
})
