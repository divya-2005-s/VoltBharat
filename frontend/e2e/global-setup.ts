import { chromium, type FullConfig } from '@playwright/test'

/**
 * Warm the local preview server once before parallel workers start. Without this, two browsers
 * requesting the large vendor bundle at the same instant right after start-up occasionally got
 * net::ERR_CONNECTION_RESET from `vite preview` on Windows, leaving the first page blank.
 */
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL!
  const browser = await chromium.launch()
  const page = await browser.newPage()
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await page.goto(baseURL, { waitUntil: 'load' })
      await page.getByRole('navigation', { name: 'Main' }).waitFor({ timeout: 15_000 })
      break
    } catch (e) {
      if (attempt === 3) throw new Error(`App did not render at ${baseURL}: ${(e as Error).message}`)
    }
  }
  await browser.close()
}
