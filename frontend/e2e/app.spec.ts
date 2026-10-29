import { expect, test } from '@playwright/test'

const PAGES = [
  ['Overview', /India EV overview/, '/'],
  ['State Explorer', /State Explorer/, '/states'],
  ['Vehicle Segments', /Vehicle Segments/, '/segments'],
  ['Manufacturers', /Manufacturers/, '/manufacturers'],
  ['Charging Gap', /Charging Gap/, '/charging-gap'],
  ['Policy Impact', /Policy Impact/, '/policy'],
  ['Insights', /Insights/, '/insights'],
  ['Data Sources', /Data Sources/, '/sources'],
] as const

test('every sidebar link loads its page without errors', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  await page.goto('/')
  for (const [link, heading, path] of PAGES) {
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: link }).click()
    await expect(page).toHaveURL((u) => u.pathname === path)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading)
    await expect(page.getByRole('alert')).toHaveCount(0)
  }
  expect(errors).toEqual([])
})

test('date preset and state filter update the URL and the KPIs', async ({ page }) => {
  await page.goto('/')
  const kpi = page.locator('text=BEV registrations').first().locator('xpath=ancestor::div[contains(@class,"rounded-xl")]')
  const allIndia = await kpi.locator('.tabular').first().textContent()

  await page.getByRole('combobox', { name: 'Date range preset' }).click()
  await page.getByRole('option', { name: 'Calendar 2025' }).click()
  await expect(page).toHaveURL(/start=2025-01&end=2025-12/)
  await expect(kpi.locator('.tabular').first()).not.toHaveText(allIndia ?? '')

  await page.getByRole('combobox', { name: 'State filter' }).click()
  await page.getByRole('option', { name: 'Kerala' }).click()
  await expect(page).toHaveURL(/state=Kerala/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Kerala overview')

  // filters survive navigation
  await page.getByRole('link', { name: 'Vehicle Segments' }).click()
  await expect(page).toHaveURL(/segments\?.*start=2025-01.*state=Kerala/)
})

test('theme toggle switches dark mode', async ({ page }) => {
  await page.goto('/')
  const html = page.locator('html')
  const wasDark = await html.evaluate((el) => el.classList.contains('dark'))
  await page.getByRole('button', { name: /switch to (dark|light) mode/i }).click()
  await expect(html).toHaveClass(wasDark ? /^(?!.*dark)/ : /dark/)
})

test('state explorer: clicking a table row opens the state detail', async ({ page }) => {
  await page.goto('/states')
  await page.getByRole('row', { name: /Karnataka/ }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: 'Karnataka' })).toBeVisible()
  await expect(dialog.getByText('BEVs per public station')).toBeVisible()
  await expect(page).toHaveURL(/selected=Karnataka/)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
})

test('state table sorts and searches', async ({ page }) => {
  await page.goto('/states')
  await page.getByLabel('Search states').fill('pradesh')
  await expect(page.getByRole('row')).toHaveCount(6) // header + 5 Pradesh states
  await page.getByRole('button', { name: /^State \/ UT/ }).click()
  await expect(page).toHaveURL(/sort=state_name/)
})

test('CSV export downloads a file and shows a toast', async ({ page }) => {
  await page.goto('/charging-gap')
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download charging_gap as CSV' }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/^voltbharat_charging_gap_.*\.csv$/)
  await expect(page.getByText('CSV downloaded')).toBeVisible()
})

test('unsupported analyses are explained, not fabricated', async ({ page }) => {
  await page.goto('/manufacturers')
  await expect(page.getByText('EV market share by manufacturer cannot be calculated from this data')).toBeVisible()
  await page.goto('/segments')
  await expect(page.getByText(/Electric 2W \/ 3W \/ car \/ bus \/ goods splits are not available/)).toBeVisible()
})

test('mobile: navigation drawer works @mobile', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Open menu' }).click()
  await page.getByRole('link', { name: 'Charging Gap' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Charging Gap/)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})
