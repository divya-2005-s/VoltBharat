import { CircleSlash, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { barRanking, donut } from '@/components/charts/options'
import { useChartTokens } from '@/components/charts/tokens'
import { ChartCard, KpiCard, Notice, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { QueryView } from '@/components/dashboard/states'
import { DataTable, type Column } from '@/components/tables/DataTable'
import { Segmented } from '@/components/ui/overlays'
import { Badge, Input } from '@/components/ui/primitives'
import { useMakers } from '@/hooks/queries'
import { useFilters, useUrlParam } from '@/hooks/useFilters'
import { formatIN, formatMonthRange, formatPct } from '@/lib/formatters'
import type { MakerRow, Makers } from '@/types/api'

export default function Manufacturers() {
  const { filters } = useFilters()
  const [view, setView] = useUrlParam('view', 'all')
  const evOnly = view === 'ev'
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  // Page resets to 1 whenever the view, filters or search change (derived, not an effect).
  const resetKey = [view, filters.start, filters.end, filters.state, debounced].join('|')
  const [paging, setPaging] = useState({ key: resetKey, page: 1 })
  const page = paging.key === resetKey ? paging.page : 1
  const setPage = (p: number) => setPaging({ key: resetKey, page: p })
  useEffect(() => {
    const id = setTimeout(() => setDebounced(search), 250)
    return () => clearTimeout(id)
  }, [search])
  const q = useMakers(filters, { search: debounced || undefined, ev_named_only: evOnly, page, page_size: 15 })

  return (
    <>
      <PageHeader title="Manufacturers" description="Manufacturer rankings from VAHAN maker registrations. Read the note below before interpreting shares." />
      <QueryView query={q} height={560}>
        {({ data, meta }) => (
          <div className="space-y-5">
            <Notice tone="warn" icon={<CircleSlash />} title="EV market share by manufacturer cannot be calculated from this data">
              {data.ev_market_share_reason} The “name-identified EV makers” view is a lower bound: {data.ev_named.definition}
            </Notice>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="All-fuel registrations" value={formatIN(data.all_fuel.total_registrations)} period={formatMonthRange(meta.period?.start, meta.period?.end)}
                definition="Every registration in the maker source for the period and area, all fuels." />
              <KpiCard label="Top-5 maker share (all fuels)" value={formatPct(data.all_fuel.top5_share_pct)} period={`${formatIN(data.all_fuel.maker_count)} makers`}
                definition="Share of all-fuel registrations held by the five largest makers. Not an EV share." />
              <KpiCard label="Name-identified EV makers" value={formatIN(data.ev_named.maker_count)} period={`${formatIN(data.ev_named.total_registrations)} registrations`}
                definition={data.ev_named.definition} />
              <KpiCard label="Their volume vs BEV total" value={formatPct(data.ev_named.coverage_of_bev_pct)}
                period={`of ${formatIN(data.ev_named.bev_registrations_fuel_source)} BEVs (fuel source)`}
                definition="Name-identified EV makers' registrations ÷ BEV registrations from the fuel-type source. Shows how incomplete the name-based subset is; the two sources are separate extracts." />
            </div>
            <div className="flex items-center gap-3">
              <Segmented label="Maker view" value={view} onChange={setView}
                options={[{ value: 'all', label: 'All makers (all fuels)' }, { value: 'ev', label: 'Name-identified EV makers' }]} />
            </div>
            <Charts data={data} evOnly={evOnly} />
            <ChartCard title={evOnly ? 'Name-identified EV makers' : 'Manufacturer ranking (all fuels)'} csv="makers"
              description="Ranks are by all-fuel registrations in the selected period and area."
              actions={
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-ink-3" />
                  <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search makers" aria-label="Search makers" className="h-9 w-52 pl-8" />
                </div>
              }>
              {() => <MakerTable data={data} evOnly={evOnly} onPage={setPage} />}
            </ChartCard>
            <SourceNote meta={meta} />
          </div>
        )}
      </QueryView>
    </>
  )
}

function Charts({ data, evOnly }: { data: Makers; evOnly: boolean }) {
  const t = useChartTokens()
  const top = evOnly ? data.ev_named.top10 : data.all_fuel.top10
  const total = evOnly ? data.ev_named.total_registrations : data.all_fuel.total_registrations
  const bar = useMemo(() => barRanking(t, top.map((m) => ({ label: shorten(m.maker), value: m.registrations })), {
    valueName: 'Registrations (all fuels)', color: evOnly ? t.series[0] : t.series[1] }), [t, top, evOnly])
  const pie = useMemo(() => {
    const four = top.slice(0, 4)
    const rest = total - four.reduce((a, m) => a + m.registrations, 0)
    return donut(t, [...four.map((m, i) => ({ name: shorten(m.maker), value: m.registrations, color: t.series[i] })),
      { name: 'All other makers', value: rest, color: t.other }])
  }, [t, top, total])
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <ChartCard className="xl:col-span-2" title={`Top 10 ${evOnly ? 'name-identified EV makers' : 'manufacturers'}`} png="top_makers"
        description="All-fuel registrations (the source cannot isolate EVs).">
        {(ref) => <EChart ref={ref} option={bar} height={340} ariaLabel="Bar chart of top manufacturers by registrations" />}
      </ChartCard>
      <ChartCard title={evOnly ? 'Share within name-identified EV makers' : 'Share of all registrations'} png="maker_share"
        description={evOnly ? 'Concentration inside the name-based subset only.' : 'All fuels — not an EV market share.'}>
        {(ref) => <EChart ref={ref} option={pie} height={340} ariaLabel="Donut chart of manufacturer share" />}
      </ChartCard>
    </div>
  )
}

function MakerTable({ data, evOnly, onPage }: { data: Makers; evOnly: boolean; onPage: (p: number) => void }) {
  const columns: Column<MakerRow>[] = [
    { key: 'rank', header: '#', cell: (r) => <span className="tabular text-ink-3">{evOnly ? r.rank_within_ev_named : r.rank}</span> },
    { key: 'maker', header: 'Manufacturer', cell: (r) => <span className="font-medium">{r.maker}{r.name_identified_ev_maker && !evOnly && <Badge tone="accent" className="ml-1.5">EV in name</Badge>}</span> },
    { key: 'registrations', header: 'Registrations (all fuels)', align: 'right', cell: (r) => formatIN(r.registrations) },
    evOnly
      ? { key: 'share', header: 'Share within subset', align: 'right', hideBelow: 'sm', cell: (r) => formatPct(r.share_within_ev_named_pct, 2) }
      : { key: 'share', header: 'Share of all registrations', align: 'right', hideBelow: 'sm', cell: (r) => formatPct(r.share_of_all_registrations_pct, 2) },
  ]
  return (
    <DataTable caption="Manufacturer ranking" columns={columns} rows={data.table.rows} rowKey={(r) => r.maker} dense
      page={{ page: data.table.page, pageSize: data.table.page_size, total: data.table.total_rows, onPage }} />
  )
}

function shorten(name: string) {
  return name.replace(/\s*(PVT\.?|Private)?\s*(LTD\.?|Limited)\s*$/i, '').replace(/\s+\(P\)/, '').slice(0, 34)
}
