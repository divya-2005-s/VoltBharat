import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { barRanking, columnChart, lineChart } from '@/components/charts/options'
import { useChartTokens } from '@/components/charts/tokens'
import { ChartCard, Delta, KpiCard, Notice, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { ErrorState, LoadingBlock, QueryView } from '@/components/dashboard/states'
import { IndiaMap } from '@/components/maps/IndiaMap'
import { DataTable, type Column } from '@/components/tables/DataTable'
import { Segmented, Sheet } from '@/components/ui/overlays'
import { Badge, Input } from '@/components/ui/primitives'
import { useStateDetail, useStates } from '@/hooks/queries'
import { useFilters, useSetUrlParams, useUrlParam } from '@/hooks/useFilters'
import { usePolicyMarkers } from '@/hooks/usePolicyMarkers'
import { formatCompactIN, formatIN, formatMonth, formatMonthRange, formatPct, formatRatio, formatSignedPct } from '@/lib/formatters'
import type { StateRow } from '@/types/api'

type Metric = 'ev_share_pct' | 'bev' | 'yoy_growth_pct' | 'bev_per_charger'
const METRICS: { value: Metric; label: string; full: string; format: (v: number | null) => string }[] = [
  { value: 'ev_share_pct', label: 'EV share', full: 'EV share of new registrations', format: (v) => formatPct(v, 2) },
  { value: 'bev', label: 'BEVs', full: 'BEV registrations', format: formatIN },
  { value: 'yoy_growth_pct', label: 'YoY growth', full: 'BEV growth, trailing 12 months', format: formatSignedPct },
  { value: 'bev_per_charger', label: 'BEVs / station', full: 'BEV registrations per public station', format: formatRatio },
]

/** A state's value for the map, or null with a reason when not comparable. */
function metricValue(r: StateRow, m: Metric): { value: number | null; note?: string } {
  if (m === 'ev_share_pct' && !r.share_rankable) return { value: null, note: 'Small registration base: not compared' }
  if (m === 'yoy_growth_pct' && !r.growth_rankable) return { value: null, note: 'Fewer than 1,000 BEVs in the comparison year: not compared' }
  if (m === 'bev_per_charger' && r.public_chargers !== null && r.public_chargers < 25) return { value: null, note: 'Fewer than 25 stations: ratio unstable' }
  return { value: r[m] }
}

export default function StateExplorer() {
  const { filters } = useFilters()
  const t = useChartTokens()
  const [metric, setMetric] = useUrlParam('metric', 'ev_share_pct') as [Metric, (v: string) => void]
  const [selected, setSelected] = useUrlParam('selected', '')
  const [sort] = useUrlParam('sort', 'bev')
  const [order] = useUrlParam('order', 'desc')
  const setUrl = useSetUrlParams()
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(1)
  useEffect(() => {
    const id = setTimeout(() => { setDebounced(search); setPage(1) }, 250)
    return () => clearTimeout(id)
  }, [search])

  const all = useStates(filters, { sort: metric, order: 'desc', page: 1, page_size: 100 })
  const table = useStates(filters, { sort, order, search: debounced || undefined, page, page_size: 12 })
  const m = METRICS.find((x) => x.value === metric) ?? METRICS[0]

  const columns: Column<StateRow>[] = [
    { key: 'state_name', header: 'State / UT', sortable: true, cell: (r) => (
      <span className="font-medium">{r.state_name}{r.state_type === 'UT' && <Badge className="ml-1.5">UT</Badge>}</span>) },
    { key: 'bev', header: 'BEV registrations', align: 'right', sortable: true, cell: (r) => formatIN(r.bev) },
    { key: 'ev_share_pct', header: 'EV share', align: 'right', sortable: true, cell: (r) => (
      <span className={r.share_rankable ? '' : 'text-ink-3'} title={r.share_rankable ? undefined : 'Small registration base'}>{formatPct(r.ev_share_pct, 2)}</span>) },
    { key: 'yoy_growth_pct', header: 'YoY growth', align: 'right', sortable: true, hideBelow: 'sm', cell: (r) => r.yoy_growth_pct === null ? '—' : <Delta value={r.yoy_growth_pct} /> },
    { key: 'public_chargers', header: 'Public stations', align: 'right', sortable: true, hideBelow: 'md', cell: (r) => formatIN(r.public_chargers) },
    { key: 'bev_per_charger', header: 'BEVs / station', align: 'right', sortable: true, hideBelow: 'md', cell: (r) => formatRatio(r.bev_per_charger) },
  ]

  return (
    <>
      <PageHeader title="State Explorer" description="Compare states and union territories. Click a state on the map or in the table for its detail." />
      <div className="space-y-5">
        <div className="grid gap-5 xl:grid-cols-5">
          <ChartCard
            className="xl:col-span-3"
            title={m.full}
            description="Neutral grey = not compared (small base or no data), not zero."
            png={`map_${metric}`}
            actions={<Segmented label="Map metric" value={metric} onChange={setMetric} options={METRICS.map(({ value, label }) => ({ value, label }))} />}
          >
            {() => (
              <QueryView query={all} height={460}>
                {({ data }) => (
                  <IndiaMap
                    data={data.table.rows.map((r) => ({ name: r.state_name, ...metricValue(r, metric) }))}
                    ramp={metric === 'bev_per_charger' ? t.seqAmber : t.seqGreen}
                    format={m.format}
                    valueLabel={m.label}
                    ariaLabel={`Map of India coloured by ${m.full}`}
                    selected={selected || null}
                    onSelect={setSelected}
                    height={460}
                  />
                )}
              </QueryView>
            )}
          </ChartCard>
          <ChartCard className="xl:col-span-2" title={`Top 15 · ${m.label}`} description="Comparable states only." png={`compare_${metric}`} csv="states">
            {(ref) => (
              <QueryView query={all} height={460}>
                {({ data }) => {
                  const rows = data.table.rows.map((r) => ({ r, ...metricValue(r, metric) })).filter((x) => x.value !== null).slice(0, 15)
                  return <EChart ref={ref} height={460} ariaLabel={`Bar chart of top states by ${m.full}`}
                    option={barRanking(t, rows.map((x) => ({ label: x.r.state_name, value: x.value })), {
                      format: m.format, valueName: m.label, color: metric === 'bev_per_charger' ? t.seqAmber[4] : t.series[0] })}
                    onClick={(p) => p.name && setSelected(p.name)} />
                }}
              </QueryView>
            )}
          </ChartCard>
        </div>

        <ChartCard
          title="All states and union territories"
          description="Sortable and searchable. YoY growth: trailing 12 months to the selected end month vs the previous 12."
          csv="states"
          actions={
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-ink-3" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search states" aria-label="Search states" className="h-9 w-48 pl-8" />
            </div>
          }
        >
          {() => (
            <QueryView query={table} height={420}>
              {({ data, meta }) => (
                <>
                  <DataTable
                    caption="States table"
                    columns={columns}
                    rows={data.table.rows}
                    rowKey={(r) => r.state_name}
                    sort={{ key: sort, order: order as 'asc' | 'desc' }}
                    onSort={(k) => {
                      const nextOrder = k === sort ? (order === 'desc' ? 'asc' : 'desc') : k === 'state_name' ? 'asc' : 'desc'
                      // defaults (bev/desc) are dropped from the URL to keep it clean
                      setUrl({ sort: k === 'bev' ? undefined : k, order: nextOrder === 'desc' ? undefined : nextOrder })
                      setPage(1)
                    }}
                    onRowClick={(r) => setSelected(r.state_name)}
                    selectedKey={selected}
                    page={{ page, pageSize: data.table.page_size, total: data.table.total_rows, onPage: setPage }}
                  />
                  <div className="mt-3"><SourceNote meta={meta} /></div>
                </>
              )}
            </QueryView>
          )}
        </ChartCard>
      </div>
      <StateDrawer name={selected || undefined} onClose={() => setSelected('')} />
    </>
  )
}

function StateDrawer({ name, onClose }: { name?: string; onClose: () => void }) {
  const { filters } = useFilters()
  const q = useStateDetail(name, filters)
  const t = useChartTokens()
  const markers = usePolicyMarkers()
  const d = q.data?.data
  const trend = useMemo(() => d ? lineChart(t, d.trend.map((r) => r.month), [
    { name: 'BEV registrations', data: d.trend.map((r) => r.bev), color: t.series[0], area: true },
  ], { markers }) : null, [d, t, markers])
  const omc = useMemo(() => d ? columnChart(t, d.omc_installations.map((o) => o.fy_label), d.omc_installations.map((o) => o.installed), {
    valueName: 'OMC stations installed', colors: d.omc_installations.map((o) => (o.is_partial_year ? t.other : t.series[1])),
    notes: d.omc_installations.map((o) => (o.is_partial_year ? 'Partial year' : '')),
  }) : null, [d, t])

  return (
    <Sheet open={!!name} onOpenChange={(o) => !o && onClose()} title={name ?? ''}
      description={q.data ? formatMonthRange(q.data.meta.period?.start, q.data.meta.period?.end) : undefined}>
      {q.isPending ? <LoadingBlock height={500} /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : d && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <KpiCard label="BEV registrations" value={formatIN(d.summary.bev)} period={`Rank #${d.summary.rank_bev ?? '—'} of 36`}
              definition="Battery-electric registrations in the selected period." />
            <KpiCard label="EV share" value={formatPct(d.summary.ev_share_pct, 2)}
              period={`India ${formatPct(d.national_ev_share_pct, 2)}${d.summary.rank_share ? ` · rank #${d.summary.rank_share}` : ' · not ranked (small base)'}`}
              definition="BEV ÷ all registrations in the state, selected period." />
            <KpiCard label="YoY growth" value={formatSignedPct(d.yoy.growth_pct)} period={`12 months to ${formatMonth(d.yoy.window.current.end)}`}
              unavailable={d.yoy.window.available ? null : d.yoy.unavailable_reason} definition="Trailing 12 months vs the previous 12 months." />
            <KpiCard label="BEVs per public station" value={formatRatio(d.summary.bev_per_charger)}
              period={`${formatIN(d.summary.public_chargers)} stations (2025 snapshot)`}
              definition="Approximate pressure indicator: BEVs registered in the period ÷ public stations in the 2025 snapshot." />
          </div>
          <ChartCard title="Monthly BEV registrations" png={`${name}_trend`}>
            {(ref) => trend && <EChart ref={ref} option={trend} height={240} ariaLabel={`Monthly BEV registrations in ${name}`} />}
          </ChartCard>
          <ChartCard title="OMC charging stations installed" description="Oil-marketing-company stations by financial year (grey = partial year)." png={`${name}_omc`}>
            {(ref) => omc && (d.omc_installations.length ? <EChart ref={ref} option={omc} height={200} ariaLabel={`OMC installations by year in ${name}`} />
              : <p className="text-sm text-ink-3">No OMC data for this state.</p>)}
          </ChartCard>
          <ChartCard title="Top manufacturers (all fuels)" description="Not EV-specific: the maker source has no fuel field.">
            {() => (
              <ol className="space-y-1.5 text-sm">
                {d.top_makers_all_fuels.map((mk, i) => (
                  <li key={mk.maker} className="flex items-center justify-between gap-3">
                    <span className="truncate text-ink-2">{i + 1}. {mk.maker} {mk.name_identified_ev_maker && <Badge tone="accent">EV in name</Badge>}</span>
                    <span className="tabular font-medium">{formatCompactIN(mk.registrations)}</span>
                  </li>
                ))}
              </ol>
            )}
          </ChartCard>
          <Notice>Strong hybrids registered here in the period: {formatIN(d.powertrain.strong_hybrid)} (not counted as EVs).</Notice>
        </div>
      )}
    </Sheet>
  )
}
