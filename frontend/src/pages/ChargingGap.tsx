import { AlertOctagon, AlertTriangle, CircleCheck, Info } from 'lucide-react'
import { EChart } from '@/components/charts/EChart'
import { barRanking, columnChart, scatterGap } from '@/components/charts/options'
import { useChartTokens, type ChartTokens } from '@/components/charts/tokens'
import { ChartCard, KpiCard, Notice, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { QueryView } from '@/components/dashboard/states'
import { IndiaMap } from '@/components/maps/IndiaMap'
import { DataTable, type Column } from '@/components/tables/DataTable'
import { Badge } from '@/components/ui/primitives'
import { useChargerGrowth, useChargingGap } from '@/hooks/queries'
import { useFilters } from '@/hooks/useFilters'
import { formatIN, formatMonthRange, formatRatio, formatSignedPct } from '@/lib/formatters'
import type { GapRow, PressureTier } from '@/types/api'

function tierColor(t: ChartTokens, tier: PressureTier | null) {
  return tier === 'high' ? t.critical : tier === 'elevated' ? t.warning : t.neutral
}

/** Status is never colour-alone: icon + label. */
export function TierBadge({ row }: { row: GapRow }) {
  if (!row.rankable) return <Badge><Info /> Not ranked</Badge>
  if (row.pressure_tier === 'high') return <Badge tone="danger"><AlertOctagon /> High</Badge>
  if (row.pressure_tier === 'elevated') return <Badge tone="warn"><AlertTriangle /> Elevated</Badge>
  return <Badge><CircleCheck /> Typical</Badge>
}

export default function ChargingGap() {
  const { filters } = useFilters()
  const q = useChargingGap(filters)
  const g = useChargerGrowth({})
  const t = useChartTokens()

  return (
    <>
      <PageHeader title="Charging Gap"
        description="Where EV registrations are high relative to public charging stations — an approximate infrastructure-pressure indicator." />
      <QueryView query={q} height={600}>
        {({ data, meta }) => {
          const period = formatMonthRange(meta.period?.start, meta.period?.end)
          const ranked = data.states.filter((s) => s.rank !== null)
          return (
            <div className="space-y-5">
              <Notice title="How to read this">
                <b>BEVs per public station</b> = BEV registrations in <b>{period}</b> ÷ public charging stations in the <b>2025 state snapshot</b>.
                The two are not time-matched. A high ratio signals <i>potential</i> pressure on public charging; it does not measure
                charger utilisation, power, uptime, location or home/workplace charging. Tiers compare each state with the national ratio
                (≥{data.thresholds.elevated}× elevated, ≥{data.thresholds.high}× high). States with fewer than {data.thresholds.small_charger_base} stations are not ranked.
              </Notice>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard label="National BEVs per station" value={formatRatio(data.national.bev_per_charger)} period={period}
                  definition="All-India BEV registrations in the period ÷ all public stations (2025 snapshot)." />
                <KpiCard label="BEV registrations" value={formatIN(data.national.bev)} period={period} definition="Numerator of the ratio." />
                <KpiCard label="Public charging stations" value={formatIN(data.national.public_chargers)} period="2025 snapshot" definition="Denominator of the ratio." />
                <KpiCard label="States at high pressure" value={formatIN(ranked.filter((r) => r.pressure_tier === 'high').length)}
                  period={`${ranked.filter((r) => r.pressure_tier === 'elevated').length} more elevated`} definition={`Ranked states with a ratio ≥ ${data.thresholds.high}× national.`} />
              </div>
              <div className="grid gap-5 xl:grid-cols-5">
                <ChartCard className="xl:col-span-3" title="BEVs per public charging station" description="Darker = more BEVs per station. Grey = not ranked." png="charging_gap_map">
                  {() => (
                    <IndiaMap
                      data={data.states.map((s) => ({ name: s.state_name, value: s.rankable ? s.bev_per_charger : null,
                        note: s.rankable ? `${formatIN(s.bev)} BEVs · ${formatIN(s.public_chargers)} stations · ${s.relative_to_national}× national` : s.unrankable_reason ?? undefined }))}
                      ramp={t.seqAmber}
                      format={formatRatio}
                      valueLabel="BEVs per station"
                      ariaLabel="Map of India coloured by BEV registrations per public charging station"
                      height={460}
                    />
                  )}
                </ChartCard>
                <ChartCard className="xl:col-span-2" title="Highest infrastructure pressure" description="Top 12 ranked states; colour = tier (see table for labels)." png="charging_gap_bars">
                  {(ref) => <EChart ref={ref} height={460} ariaLabel="Bar chart of states with the highest BEVs per station"
                    option={barRanking(t, ranked.slice(0, 12).map((r) => ({ label: r.state_name, value: r.bev_per_charger, color: tierColor(t, r.pressure_tier) })),
                      { format: formatRatio, valueName: 'BEVs per station' })} />}
                </ChartCard>
              </div>
              <div className="grid gap-5 xl:grid-cols-5">
                <ChartCard className="xl:col-span-2" title="Registrations vs stations" description="Log scales. Higher and further left = more BEVs per station. High/elevated states are labelled; hover any point." png="charging_gap_scatter">
                  {(ref) => <EChart ref={ref} height={420} ariaLabel="Scatter plot of BEV registrations against public stations by state"
                    option={scatterGap(t, data.states.filter((s) => s.bev && s.public_chargers).map((s) => ({
                      name: s.state_name, code: s.state_code, x: s.public_chargers!, y: s.bev!, color: s.rankable ? tierColor(t, s.pressure_tier) : t.other,
                      tier: s.rankable ? s.pressure_tier ?? '' : 'not ranked',
                      label: s.pressure_tier === 'high' || s.pressure_tier === 'elevated' })))} />}
                </ChartCard>
                <ChartCard className="xl:col-span-3" title="Ranked states" csv="charging_gap">
                  {() => <GapTable rows={data.states} />}
                </ChartCard>
              </div>
              <OmcGrowth query={g} />
              <SourceNote meta={meta} extra={<span>Charger snapshot: 2025</span>} />
            </div>
          )
        }}
      </QueryView>
    </>
  )
}

function GapTable({ rows }: { rows: GapRow[] }) {
  const columns: Column<GapRow>[] = [
    { key: 'rank', header: '#', cell: (r) => <span className="tabular text-ink-3">{r.rank ?? '—'}</span> },
    { key: 'state', header: 'State / UT', cell: (r) => <span className="font-medium">{r.state_name}</span> },
    { key: 'ratio', header: 'BEVs / station', align: 'right', cell: (r) => formatRatio(r.bev_per_charger) },
    { key: 'rel', header: 'vs national', align: 'right', hideBelow: 'sm', cell: (r) => (r.relative_to_national === null ? '—' : `${r.relative_to_national.toFixed(2)}×`) },
    { key: 'bev', header: 'BEVs', align: 'right', hideBelow: 'md', cell: (r) => formatIN(r.bev) },
    { key: 'ch', header: 'Stations', align: 'right', hideBelow: 'md', cell: (r) => formatIN(r.public_chargers) },
    { key: 'tier', header: 'Tier', cell: (r) => <TierBadge row={r} /> },
  ]
  return <div className="max-h-[420px] overflow-y-auto"><DataTable caption="States ranked by BEVs per station" columns={columns} rows={rows} rowKey={(r) => r.state_name} dense /></div>
}

function OmcGrowth({ query }: { query: ReturnType<typeof useChargerGrowth> }) {
  const t = useChartTokens()
  return (
    <QueryView query={query} height={300}>
      {({ data }) => {
        const fy = data.financial_years
        return (
          <ChartCard title="Annual OMC charging-station installations" png="omc_growth" csv="chargers_growth"
            description={`${data.measure} Grey bar = partial year.`}
            footer={data.notes.join(' ')}>
            {(ref) => (
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <EChart ref={ref} height={280} ariaLabel="Column chart of OMC station installations by financial year"
                    option={omcColumnOption(t, fy)} />
                </div>
                <dl className="space-y-3 text-sm">
                  {fy.filter((y) => y.growth_pct !== null).slice(-2).map((y) => (
                    <div key={y.fy_label} className="flex justify-between gap-3 border-b border-border pb-2">
                      <dt className="text-ink-2">{y.fy_label} vs previous FY</dt>
                      <dd className="tabular font-semibold">{formatSignedPct(y.growth_pct)}</dd>
                    </div>
                  ))}
                  <div className="flex justify-between gap-3 border-b border-border pb-2"><dt className="text-ink-2">Total installed</dt><dd className="tabular font-semibold">{formatIN(data.status.total_installed)}</dd></div>
                  <div className="flex justify-between gap-3 border-b border-border pb-2"><dt className="text-ink-2">Reported operational</dt><dd className="tabular font-semibold">{formatIN(data.status.total_operational)}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-ink-2">Decommissioned</dt><dd className="tabular font-semibold">{formatIN(data.status.decommissioned)}</dd></div>
                </dl>
              </div>
            )}
          </ChartCard>
        )
      }}
    </QueryView>
  )
}

function omcColumnOption(t: ChartTokens, fy: { fy_label: string; installed: number; is_partial_year: boolean }[]) {
  return columnChart(t, fy.map((y) => y.fy_label), fy.map((y) => y.installed), {
    valueName: 'Stations installed', colors: fy.map((y) => (y.is_partial_year ? t.other : t.series[1])),
    notes: fy.map((y) => (y.is_partial_year ? 'Partial year: not comparable with full years' : '')),
  })
}

