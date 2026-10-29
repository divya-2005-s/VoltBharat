import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { vi } from 'vitest'

import { Providers } from '@/app/providers'

export function renderWithProviders(ui: ReactElement, { route = '/' } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Providers client={client}>{ui}</Providers>
    </MemoryRouter>,
  )
}

export function LocationProbe() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname + loc.search}</div>
}

type Handler = (url: URL) => { status?: number; body: unknown } | undefined

/** Replace fetch with a router of canned API responses. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input))
    const r = handler(url)
    if (!r) return new Response(JSON.stringify({ error: { code: 'not_found', message: 'no mock' } }), { status: 404 })
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export const meta = {
  period: { start: '2022-01', end: '2026-09', months: 57 },
  sources: ['fuel'],
  notes: [],
  data_coverage: { start: '2022-01', end: '2026-09' },
  last_processed_at: '2026-10-29T09:07:25+00:00',
}
