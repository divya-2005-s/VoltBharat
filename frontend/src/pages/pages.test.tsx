import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useFilters } from '@/hooks/useFilters'
import { LocationProbe, meta, mockFetch, renderWithProviders } from '@/test/utils'

import Overview from './Overview'

// Canvas charts cannot render in jsdom; replace the chart and map with labelled stubs.
vi.mock('@/components/charts/EChart', () => ({
  EChart: ({ ariaLabel }: { ariaLabel: string }) => <div role="img" aria-label={ariaLabel} />,
}))
vi.mock('@/components/maps/IndiaMap', () => ({
  IndiaMap: ({ ariaLabel, onSelect }: { ariaLabel: string; onSelect?: (s: string) => void }) => (
    <button type="button" aria-label={ariaLabel} onClick={() => onSelect?.('Kerala')}>map</button>
  ),
}))

const month = { month: '2026-09', bev: 337311, strong_hybrid: 1, plugin_hybrid: 0, fcev: 0, other_hybrid: 0, total: 2569811,
  ev_share_pct: 13.13, bev_prev_year: 191554, bev_yoy_pct: 76.1, ev_share_prev_year_pct: 9.92 }
const overview = (bev: number) => ({
  kpis: { bev_registrations: bev, total_registrations: 127633967, ev_share_pct: 7.48, public_chargers: 29277, charger_snapshot: '2025', months: 57,
    yoy: { window: { current: { start: '2025-10', end: '2026-09' }, previous: { start: '2024-10', end: '2025-09' }, available: true },
      bev_current: 3201718, bev_previous: 2247991, growth_pct: 42.4, ev_share_current_pct: 9.61, ev_share_previous_pct: 8.1, share_change_pp: 1.51 } },
  latest_month: month, trend: [month], map: [], top_states_by_bev: [], top_states_by_share: [],
  powertrain: { bev, strong_hybrid: 253771, plugin_hybrid: 141, fcev: 26, other_hybrid: 0 }, selected_state: null,
})

function routes(over: { overviewStatus?: number } = {}) {
  return mockFetch((url) => {
    if (url.pathname === '/api/v1/meta/states') {
      return { body: { data: [{ state_name: 'Kerala', state_code: 'KL', state_type: 'State', region: 'South' }], meta } }
    }
    if (url.pathname === '/api/v1/policy-events') return { body: { data: [], meta } }
    if (url.pathname === '/api/v1/overview') {
      if (over.overviewStatus) {
        return { status: over.overviewStatus, body: { error: { code: 'database_unavailable', message: 'The analytics database is unavailable.' } } }
      }
      return { body: { data: overview(url.searchParams.get('state') === 'Kerala' ? 106886 : 9543592), meta } }
    }
    return undefined
  })
}

describe('Overview page', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('renders KPIs from the API with Indian formatting', async () => {
    routes()
    renderWithProviders(<Overview />)
    expect(await screen.findAllByText('95,43,592')).not.toHaveLength(0)
    expect(screen.getByText('42.4%')).toBeInTheDocument()
    expect(screen.getByText('29,277')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /monthly bev registrations for india/i })).toBeInTheDocument()
  })

  it('shows an error state (no fallback numbers) when the API is unavailable', async () => {
    routes({ overviewStatus: 503 })
    renderWithProviders(<Overview />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Data unavailable')
    expect(screen.queryByText('95,43,592')).not.toBeInTheDocument()
  })

  it('selecting a state on the map updates the URL filter and refetches', async () => {
    const fetchMock = routes()
    renderWithProviders(<><Overview /><LocationProbe /></>)
    fireEvent.click(await screen.findByRole('button', { name: /choropleth/i }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('state=Kerala'))
    expect(await screen.findAllByText('1,06,886')).not.toHaveLength(0)
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('state=Kerala'))).toBe(true)
  })
})

function FilterProbe() {
  const { filters, setFilters } = useFilters()
  return (
    <>
      <span data-testid="f">{JSON.stringify(filters)}</span>
      <button type="button" onClick={() => setFilters({ start: '2025-01', end: '2025-12' })}>set</button>
      <button type="button" onClick={() => setFilters({ start: undefined })}>clear</button>
    </>
  )
}

describe('useFilters', () => {
  it('reads, validates and writes URL filters', () => {
    renderWithProviders(<><FilterProbe /><LocationProbe /></>, { route: '/?start=2024-13&state=Goa' })
    expect(screen.getByTestId('f')).toHaveTextContent('{"state":"Goa"}') // invalid month ignored
    fireEvent.click(screen.getByText('set'))
    const loc = screen.getByTestId('location').textContent ?? ''
    expect(loc).toContain('start=2025-01')
    expect(loc).toContain('end=2025-12')
    expect(loc).toContain('state=Goa') // other filters preserved
    fireEvent.click(screen.getByText('clear'))
    expect(screen.getByTestId('location')).not.toHaveTextContent('start=')
  })
})
