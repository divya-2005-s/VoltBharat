import { CircleSlash } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { donut, lineChart } from '@/components/charts/options'
import { useChartTokens, type ChartTokens } from '@/components/charts/tokens'
import { ChartCard, Notice, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { EmptyState, QueryView } from '@/components/dashboard/states'
import { Segmented } from '@/components/ui/overlays'
import { useBootstrap, useSegments } from '@/hooks/queries'
import { useFilters } from '@/hooks/useFilters'
import { formatIN, formatMonthRange, formatPct } from '@/lib/formatters'
import type { Segments as SegmentsData } from '@/types/api'

// All-fuel categories: three named groups + neutral "Other" (series cap; colour follows the group).
const NAMED = ['Two-wheelers', 'Light motor vehicles (cars/jeeps)', 'Three-wheelers'] as const
const catColor = (t: ChartTokens, g: string) => ({ [NAMED[0]]: t.series[1], [NAMED[1]]: t.series[2], [NAMED[2]]: t.series[3] } as Record<string, string>)[g] ?? t.other

function foldCategories(data: SegmentsData['all_fuel_categories']) {
  const series = data.series.map((row) => {
    const out: Record<string, number> = { Other: 0 }
    for (const [k, v] of Object.entries(row)) {
      if (k === 'month') continue
      if ((NAMED as readonly string[]).includes(k)) out[k] = Number(v)
      else out.Other += Number(v)
    }
    return { month: String(row.month), values: out }
  })
  const groups = [...NAMED, 'Other']
  const totals = groups.map((g) => ({ group: g, value: series.reduce((a, r) => a + (r.values[g] ?? 0), 0) }))
  return { series, groups, totals }
}

export default function Segments() {
  const { filters } = useFilters()
  const q = useSegments(filters)
  const where = filters.state ?? 'India'
  return (
    <>
      <PageHeader title="Vehicle Segments"
        description="What the data can and cannot say about EV segments. EV-specific views use only the fuel-type source." />
      <QueryView query={q} height={600}>
        {({ data, meta }) => (
          <div className="space-y-5">
            <Notice tone="warn" icon={<CircleSlash />} title="Electric 2W / 3W / car / bus / goods splits are not available">
              {data.ev_category_split_reason}
            </Notice>
            <h2 className="pt-1 text-sm font-semibold uppercase tracking-wide text-ink-3">EV-specific · electrified powertrains</h2>
            <Powertrain data={data} where={where} period={formatMonthRange(meta.period?.start, meta.period?.end)} />
            <h2 className="pt-3 text-sm font-semibold uppercase tracking-wide text-ink-3">Context · all-fuel vehicle categories (not EV-specific)</h2>
            <Categories data={data} />
            <SourceNote meta={meta} />
          </div>
        )}
      </QueryView>
    </>
  )
}

function Powertrain({ data, where, period }: { data: SegmentsData; where: string; period: string }) {
  const t = useChartTokens()
  const [view, setView] = useState<'bev' | 'hybrid'>('bev')
  const months = data.powertrain.series.map((r) => r.month)
  const tot = Object.fromEntries(data.powertrain.totals.map((x) => [x.key, x.registrations]))
  const others = (tot.strong_hybrid ?? 0) + (tot.plugin_hybrid ?? 0) + (tot.fcev ?? 0)
  const ratio = others ? Math.round((tot.bev ?? 0) / others) : null
  const line = useMemo(() => view === 'bev'
    ? lineChart(t, months, [{ name: 'Battery electric (BEV)', data: data.powertrain.series.map((r) => r.bev), color: t.series[0], area: true }], { zoom: months.length > 24 })
    : lineChart(t, months, [
        { name: 'Strong hybrid', data: data.powertrain.series.map((r) => r.strong_hybrid), color: t.series[1] },
        { name: 'Plug-in hybrid', data: data.powertrain.series.map((r) => r.plugin_hybrid), color: t.series[2] },
        { name: 'Fuel cell', data: data.powertrain.series.map((r) => r.fcev), color: t.series[3] },
      ], { zoom: months.length > 24 }),
  [view, t, months, data.powertrain.series])
  const pie = useMemo(() => {
    const colors: Record<string, string> = { bev: t.series[0], strong_hybrid: t.series[1], plugin_hybrid: t.series[2], fcev: t.series[3] }
    return donut(t, data.powertrain.totals.map((s) => ({ name: s.label, value: s.registrations, color: colors[s.key] })))
  }, [t, data.powertrain.totals])
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <ChartCard className="xl:col-span-2" title="Monthly electrified registrations" csv="powertrain" png="powertrain_trend"
        description={`${where} · BEV and the other powertrains are shown separately${ratio ? ` (BEV volume is ${ratio}× theirs combined)` : ''} so each keeps a readable axis.`}
        actions={<Segmented label="Powertrain view" value={view} onChange={setView} options={[{ value: 'bev', label: 'BEV' }, { value: 'hybrid', label: 'Hybrids & fuel cell' }]} />}>
        {(ref) => <EChart ref={ref} option={line} height={320} ariaLabel="Monthly electrified powertrain registrations" />}
      </ChartCard>
      <ChartCard title="Powertrain distribution" description={period} png="powertrain_donut"
        info="Share of electrified registrations (BEV + strong hybrid + plug-in hybrid + fuel cell). Mild/other hybrid labels are excluded.">
        {(ref) => (
          <>
            <EChart ref={ref} option={pie} height={260} ariaLabel="Donut chart of electrified powertrain distribution" />
            <table className="mt-2 w-full text-xs">
              <caption className="sr-only">Powertrain totals</caption>
              <tbody>
                {data.powertrain.totals.map((s) => (
                  <tr key={s.key} className="border-t border-border">
                    <td className="py-1 text-ink-2">{s.label}</td>
                    <td className="tabular py-1 text-right font-medium">{formatIN(s.registrations)}</td>
                    <td className="tabular py-1 text-right text-ink-3">{s.registrations > 0 && s.share_pct === 0 ? '<0.01%' : formatPct(s.share_pct, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </ChartCard>
    </div>
  )
}

function Categories({ data }: { data: SegmentsData }) {
  const t = useChartTokens()
  const cat = data.all_fuel_categories
  const { data: refs } = useBootstrap()
  const excluded = (refs?.data ?? []).map((r) => r.state_name).filter((n) => !cat.states_included.includes(n))
  const [mode, setMode] = useState<'count' | 'share'>('count')
  const folded = useMemo(() => foldCategories(cat), [cat])
  const area = useMemo(() => {
    const months = folded.series.map((r) => r.month)
    const totals = folded.series.map((r) => folded.groups.reduce((a, g) => a + (r.values[g] ?? 0), 0))
    return lineChart(t, months, folded.groups.map((g) => ({
      name: g,
      color: catColor(t, g),
      data: folded.series.map((r, i) => {
        const v = r.values[g] ?? 0
        return mode === 'share' ? (totals[i] ? Math.round((1000 * v) / totals[i]) / 10 : null) : v
      }),
    })), mode === 'share'
      ? { stacked: true, yFormat: (v) => formatPct(v, 0), tooltipFormat: (v) => formatPct(v), zoom: months.length > 24 }
      : { stacked: true, zoom: months.length > 24 })
  }, [folded, mode, t])
  const pie = useMemo(() => donut(t, folded.totals.map((g) => ({ name: g.group, value: g.value, color: catColor(t, g.group) }))), [folded, t])

  if (!cat.available) {
    return <EmptyState title="All-fuel category data not shown">{cat.reason} Category coverage: {formatMonthRange(cat.coverage.start, cat.coverage.end)}.</EmptyState>
  }
  const desc = `All fuels · ${formatMonthRange(cat.period?.start, cat.period?.end)} · ${cat.states_included.length} validated states`
  return (
    <>
      <Notice>
        Source covers {formatMonthRange(cat.coverage.start, cat.coverage.end)} and has no fuel field. Office rows with leaked aggregate values were
        removed, and only states whose cleaned totals match the fuel-type source within 5% are included
        {excluded.length > 0 && <> (excluded or absent: {excluded.join(', ')})</>}. “Other” = goods,
        passenger (bus/taxi) and other categories.
      </Notice>
      <div className="grid gap-5 xl:grid-cols-3">
        <ChartCard className="xl:col-span-2" title="Monthly registrations by vehicle category" description={desc} csv="categories" png="category_trend"
          actions={<Segmented label="Category measure" value={mode} onChange={setMode} options={[{ value: 'count', label: 'Registrations' }, { value: 'share', label: 'Share %' }]} />}>
          {(ref) => <EChart ref={ref} option={area} height={320} ariaLabel="Stacked area chart of registrations by vehicle category, all fuels" />}
        </ChartCard>
        <ChartCard title="Category distribution" description={desc} png="category_donut">
          {(ref) => <EChart ref={ref} option={pie} height={320} ariaLabel="Donut chart of vehicle category distribution, all fuels" />}
        </ChartCard>
      </div>
    </>
  )
}
