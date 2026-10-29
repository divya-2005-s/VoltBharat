import { BatteryCharging, Gauge, PlugZap, TrendingUp } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { barRanking, lineChart } from '@/components/charts/options'
import { useChartTokens } from '@/components/charts/tokens'
import { ChartCard, Delta, KpiCard, Notice, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { LoadingBlock, QueryView } from '@/components/dashboard/states'
import { IndiaMap } from '@/components/maps/IndiaMap'
import { Segmented } from '@/components/ui/overlays'
import { Card } from '@/components/ui/primitives'
import { useOverview } from '@/hooks/queries'
import { useFilters } from '@/hooks/useFilters'
import { usePolicyMarkers } from '@/hooks/usePolicyMarkers'
import { formatCompactIN, formatIN, formatMonth, formatMonthRange, formatPct, formatPP } from '@/lib/formatters'
import type { Overview as OverviewData } from '@/types/api'

export default function Overview() {
  const { filters, setFilters } = useFilters()
  const q = useOverview(filters)
  const tokens = useChartTokens()
  const where = filters.state ?? 'India'
  return (
    <>
      <PageHeader
        title={filters.state ? `${filters.state} overview` : 'India EV overview'}
        description="Battery-electric vehicle (BEV) adoption from VAHAN registrations, with public charging infrastructure. Use the date range and state filters above."
      />
      <QueryView query={q} height={520}>
        {({ data, meta }) => (
          <div className="space-y-5">
            <Kpis data={data} where={where} period={formatMonthRange(meta.period?.start, meta.period?.end)} />
            <div className="grid gap-5 xl:grid-cols-3">
              <TrendCard data={data} where={where} />
              <ChartCard
                title="EV share by state"
                description={`BEV share of new registrations, ${formatMonthRange(meta.period?.start, meta.period?.end)}. Click a state to filter.`}
                info="States with fewer than 10,000 total registrations in the period are drawn neutral: their shares are too volatile to compare."
                png="ev_share_map"
              >
                {() => (
                  <IndiaMap
                    data={data.map.map((m) => ({
                      name: m.state_name,
                      value: m.share_rankable ? m.ev_share_pct : null,
                      note: m.share_rankable ? `${formatIN(m.bev)} BEVs` : `Not compared: small registration base (share ${formatPct(m.ev_share_pct)})`,
                    }))}
                    ramp={tokens.seqGreen}
                    format={(v) => formatPct(v)}
                    valueLabel="EV share"
                    ariaLabel="Choropleth map of India coloured by BEV share of new registrations"
                    selected={filters.state}
                    onSelect={(s) => setFilters({ state: s === filters.state ? undefined : s })}
                    height={400}
                  />
                )}
              </ChartCard>
            </div>
            <div className="grid gap-5 lg:grid-cols-3">
              <TopStates title="Top 5 states by BEV registrations" rows={data.top_states_by_bev.map((r) => ({ label: r.state_name, value: r.value }))}
                format={formatIN} valueName="BEV registrations" description="Total in the selected period (all-India ranking)." />
              <TopStates title="Top 5 states by EV share" rows={data.top_states_by_share.map((r) => ({ label: r.state_name, value: r.value }))}
                format={(v) => formatPct(v, 2)} valueName="EV share" description="Among states with ≥10,000 registrations in the period." />
              <Highlights data={data} where={where} />
            </div>
            <SourceNote meta={meta} extra={<span>Chargers: 2025 state snapshot</span>} />
          </div>
        )}
      </QueryView>
    </>
  )
}

function Kpis({ data, where, period }: { data: OverviewData; where: string; period: string }) {
  const k = data.kpis
  const y = k.yoy
  const win = `${formatMonth(y.window.current.start)} – ${formatMonth(y.window.current.end)}`
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        icon={<PlugZap />}
        label="BEV registrations"
        value={formatIN(k.bev_registrations)}
        period={period}
        definition="Sum of new registrations with fuel label 'Electric(BOV)' or 'Pure EV' (battery-electric). Hybrids and fuel-cell vehicles are excluded."
        comparison={<span className="text-xs text-ink-3">{where} · {k.months} months</span>}
      />
      <KpiCard
        icon={<TrendingUp />}
        label="EV YoY growth"
        value={formatPct(y.growth_pct)}
        period={`12 months to ${formatMonth(y.window.current.end)}`}
        unavailable={y.window.available ? null : y.unavailable_reason}
        definition={`BEV registrations in ${win} vs the preceding 12 months (${formatMonth(y.window.previous.start)} – ${formatMonth(y.window.previous.end)}).`}
        comparison={<span className="text-xs text-ink-3">{formatCompactIN(y.bev_current)} vs {formatCompactIN(y.bev_previous)}</span>}
      />
      <KpiCard
        icon={<Gauge />}
        label="EV share of new registrations"
        value={formatPct(k.ev_share_pct, 2)}
        period={period}
        definition="BEV registrations ÷ registrations of all fuel types × 100, for the same period and area. The comparison is the trailing-12-month share change."
        comparison={y.window.available ? <><Delta value={y.share_change_pp} suffix=" pp" digits={2} /><span className="text-xs text-ink-3">12-mo share {formatPct(y.ev_share_current_pct, 2)}</span></> : undefined}
      />
      <KpiCard
        icon={<BatteryCharging />}
        label="Public charging stations"
        value={formatIN(k.public_chargers)}
        period="2025 state snapshot"
        unavailable={k.public_chargers === null ? 'No charger count for this state in the snapshot.' : null}
        definition="Operational public EV charging stations by state, from the 2025 Government of India snapshot (PIB, Aug-2025). Stations, not individual charging points. Not time-matched to the registration period."
        comparison={<span className="text-xs text-ink-3">{where}</span>}
      />
    </div>
  )
}

function TrendCard({ data, where }: { data: OverviewData; where: string }) {
  const t = useChartTokens()
  const markers = usePolicyMarkers()
  const [mode, setMode] = useState<'count' | 'share'>('count')
  const months = data.trend.map((r) => r.month)
  const option = useMemo(() => mode === 'count'
    ? lineChart(t, months, [{ name: 'BEV registrations', data: data.trend.map((r) => r.bev), color: t.series[0], area: true }], { markers, zoom: months.length > 24 })
    : lineChart(t, months, [{ name: 'EV share', data: data.trend.map((r) => r.ev_share_pct), color: t.series[0], area: true }],
        { markers, zoom: months.length > 24, yFormat: (v) => formatPct(v, 0), tooltipFormat: (v) => formatPct(v, 2) }),
  [mode, t, months, data.trend, markers])
  return (
    <ChartCard
      className="xl:col-span-2"
      title="Monthly BEV registrations"
      description={`${where} · dashed lines mark policy milestones (context, not causation)`}
      info="Monthly totals from the VAHAN fuel-type source. 'EV share' is BEV ÷ all registrations in each month."
      png="monthly_trend"
      csv="trend"
      actions={<Segmented label="Trend measure" value={mode} onChange={setMode} options={[{ value: 'count', label: 'Registrations' }, { value: 'share', label: 'EV share' }]} />}
    >
      {(ref) => data.trend.length ? <EChart ref={ref} option={option} height={360} ariaLabel={`Line chart of monthly ${mode === 'count' ? 'BEV registrations' : 'EV share'} for ${where}`} /> : <LoadingBlock />}
    </ChartCard>
  )
}

function TopStates({ title, rows, format, valueName, description }: {
  title: string; rows: { label: string; value: number | null }[]; format: (v: number | null) => string; valueName: string; description: string
}) {
  const t = useChartTokens()
  const option = useMemo(() => barRanking(t, rows, { format, valueName }), [t, rows, format, valueName])
  return (
    <ChartCard title={title} description={description} png={title.toLowerCase().replace(/\W+/g, '_')}>
      {(ref) => <EChart ref={ref} option={option} height={220} ariaLabel={`Bar chart: ${title}`} />}
    </ChartCard>
  )
}

function Highlights({ data, where }: { data: OverviewData; where: string }) {
  const p = data.powertrain
  const latest = data.latest_month
  const items = [
    { label: 'Battery electric (BEV)', value: p.bev, tone: 'text-accent-ink' },
    { label: 'Strong hybrid', value: p.strong_hybrid },
    { label: 'Plug-in hybrid', value: p.plugin_hybrid },
    { label: 'Fuel cell (hydrogen)', value: p.fcev },
  ]
  return (
    <Card className="p-5">
      <h2 className="text-[15px] font-semibold text-ink">Electrified powertrain highlights</h2>
      <p className="mt-0.5 text-[13px] text-ink-3">{where}, selected period. Only BEVs count as EVs in headline metrics.</p>
      <dl className="mt-4 space-y-2.5">
        {items.map((i) => (
          <div key={i.label} className="flex items-baseline justify-between gap-3 border-b border-border pb-2 last:border-0">
            <dt className="text-sm text-ink-2">{i.label}</dt>
            <dd className={`tabular text-sm font-semibold ${i.tone ?? 'text-ink'}`}>{formatIN(i.value)}</dd>
          </div>
        ))}
      </dl>
      {latest && (
        <div className="mt-4 rounded-lg bg-surface-2 p-3 text-xs text-ink-2">
          Latest month <b>{formatMonth(latest.month)}</b>: {formatIN(latest.bev)} BEVs, {formatPct(latest.ev_share_pct, 2)} share
          {latest.bev_yoy_pct !== null && <>; <Delta value={latest.bev_yoy_pct} /> vs {formatMonth(latest.month.replace(/^(\d{4})/, (y) => String(Number(y) - 1)))}</>}
          {latest.ev_share_prev_year_pct !== null && latest.ev_share_pct !== null && <>; share change {formatPP(latest.ev_share_pct - latest.ev_share_prev_year_pct)}</>}
        </div>
      )}
      <div className="mt-3"><Notice>Electric 2W/3W/car/bus splits are not available: no source records both fuel and vehicle category.</Notice></div>
    </Card>
  )
}
