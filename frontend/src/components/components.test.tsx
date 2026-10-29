import type { UseQueryResult } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Delta, KpiCard } from '@/components/dashboard/cards'
import { QueryView } from '@/components/dashboard/states'
import { DataTable } from '@/components/tables/DataTable'
import { TooltipProvider } from '@/components/ui/overlays'
import { ApiError } from '@/lib/api'

const q = (over: Partial<UseQueryResult<string>>) =>
  ({ isPending: false, isError: false, isFetching: false, isPlaceholderData: false, data: undefined, error: null, refetch: vi.fn(), ...over }) as unknown as UseQueryResult<string>

describe('QueryView', () => {
  it('shows a loading skeleton', () => {
    render(<QueryView query={q({ isPending: true })}>{(d) => d}</QueryView>)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
  it('shows a retryable error without inventing figures', () => {
    const refetch = vi.fn()
    render(<QueryView query={q({ isError: true, error: new ApiError(503, 'database_unavailable', 'DB down'), refetch })}>{(d) => d}</QueryView>)
    expect(screen.getByRole('alert')).toHaveTextContent('Data unavailable')
    expect(screen.getByRole('alert')).toHaveTextContent('No figures are shown')
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(refetch).toHaveBeenCalled()
  })
  it('renders data and empty states', () => {
    const { rerender } = render(<QueryView query={q({ data: 'hello' })}>{(d) => <p>{d}</p>}</QueryView>)
    expect(screen.getByText('hello')).toBeInTheDocument()
    rerender(<QueryView query={q({ data: '' })} empty={(d) => d === ''}>{(d) => <p>{d}</p>}</QueryView>)
    expect(screen.getByText(/no data for the selected filters/i)).toBeInTheDocument()
  })
})

describe('KpiCard', () => {
  it('shows value, period and definition trigger', () => {
    render(<TooltipProvider><KpiCard label="BEV registrations" value="95,43,592" period="Jan 2022 – Sep 2026" definition="def" /></TooltipProvider>)
    expect(screen.getByText('95,43,592')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /definition: bev registrations/i })).toBeInTheDocument()
  })
  it('marks unavailable metrics instead of showing zero', () => {
    render(<TooltipProvider><KpiCard label="EV YoY growth" value="0" period="p" definition="d" unavailable="Needs 24 months" /></TooltipProvider>)
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })
  it('Delta handles missing comparisons', () => {
    render(<><Delta value={null} /><Delta value={12.34} /></>)
    expect(screen.getByText('no comparison')).toBeInTheDocument()
    expect(screen.getByText('+12.3%')).toBeInTheDocument()
  })
})

describe('DataTable', () => {
  const rows = [{ n: 'A', v: 1 }, { n: 'B', v: 2 }]
  const cols = [
    { key: 'n', header: 'Name', sortable: true, cell: (r: { n: string }) => r.n },
    { key: 'v', header: 'Value', align: 'right' as const, sortable: true, cell: (r: { v: number }) => r.v },
  ]
  it('sorts, paginates and handles row clicks', () => {
    const onSort = vi.fn()
    const onPage = vi.fn()
    const onRow = vi.fn()
    render(<DataTable caption="t" columns={cols} rows={rows} rowKey={(r) => r.n} sort={{ key: 'v', order: 'desc' }}
      onSort={onSort} onRowClick={onRow} page={{ page: 1, pageSize: 2, total: 5, onPage }} />)
    expect(screen.getByRole('columnheader', { name: /value/i })).toHaveAttribute('aria-sort', 'descending')
    fireEvent.click(screen.getByRole('button', { name: /name/i }))
    expect(onSort).toHaveBeenCalledWith('n')
    fireEvent.click(screen.getByRole('button', { name: /next page/i }))
    expect(onPage).toHaveBeenCalledWith(2)
    expect(screen.getByRole('button', { name: /previous page/i })).toBeDisabled()
    fireEvent.keyDown(screen.getByText('B').closest('tr')!, { key: 'Enter' })
    expect(onRow).toHaveBeenCalledWith(rows[1])
    expect(screen.getByText('1–2 of 5')).toBeInTheDocument()
  })
})
