import { defineConfig, devices } from '@playwright/test'

// E2E tests run against the real stack: start the API first
// (uvicorn app.main:app --app-dir backend) with a loaded database.
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  timeout: 45_000,
  retries: 0,
  // One worker: the local `vite preview` server on Windows intermittently stalled/reset connections when
  // two browsers loaded the app simultaneously (observed as net::ERR_CONNECTION_RESET on vendor.js).
  workers: 1,
  reporter: [['list']],
  // Runs against a production build (vite preview), not the dev server.
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure', acceptDownloads: true },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } }, grepInvert: /@mobile/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
  webServer: {
    command: 'npm run build && npx vite preview --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 180_000,
  },
})
