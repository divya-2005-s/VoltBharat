import { Scale } from 'lucide-react'
import { useMemo } from 'react'

import { EChart } from '@/components/charts/EChart'
import { lineChart } from '@/components/charts/options'
import { useChartTokens } from '@/components/charts/tokens'
import { ChartCard, Delta, Notice, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { QueryView } from '@/components/dashboard/states'
import { ALL, Select } from '@/components/ui/select'
import { Segmented } from '@/components/ui/overlays'
import { Badge, Card } from '@/components/ui/primitives'
import { usePolicy } from '@/hooks/queries'
import { useFilters, useUrlParam } from '@/hooks/useFilters'
import { usePolicyMarkers } from '@/hooks/usePolicyMarkers'
import { formatIN, formatMonth, formatMonthRange, formatPct, formatPP } from '@/lib/formatters'
import type { PolicyComparison, PolicyData } from '@/types/api'

export default function PolicyImpact() {
  const { filters } = useFilters()
  const [win, setWin] = useUrlParam('window', '6')
  const [focus, setFocus] = useUrlParam('event', ALL)
  const q = usePolicy(filters, Number(win))
  const where = filters.state ?? 'India'
  return (
    <>
      <PageHeader title="Policy Impact"
        description="BEV registrations around FAME-II, EMPS 2024 and PM E-DRIVE milestones. These are associations in time, not causal estimates." />
      <QueryView query={q} height={560}>
        {({ data, meta }) => (
          <div className="space-y-5">
            <Notice tone="warn" icon={<Scale />} title="Read before interpreting">
              <ul className="list-disc space-y-0.5 pl-4">{data.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
            </Notice>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-ink-3">Policy period</span>
              <Select label="Policy period" value={focus} onChange={setFocus} className="w-[230px]"
                options={[{ value: ALL, label: 'All milestones' }, ...data.events.map((e) => ({ value: e.event_id, label: e.short_name }))]} />
              <span className="ml-2 text-sm text-ink-3">Window</span>
              <Segmented label="Comparison window" value={win} onChange={setWin}
                options={[{ value: '3', label: '3 months' }, { value: '6', label: '6 months' }, { value: '12', label: '12 months' }]} />
            </div>
            <Trend data={data} where={where} focus={focus} />
            <Comparisons comps={data.comparisons.filter((c) => focus === ALL || c.event_ids.includes(focus))} where={where} win={Number(win)} />
            <Card className="p-5">
              <h2 className="text-[15px] font-semibold text-ink">Milestones</h2>
              <ol className="mt-3 space-y-3">
                {data.events.filter((e) => focus === ALL || e.event_id === focus).map((e) => (
                  <li key={e.event_id} className="border-l-2 border-accent pl-3">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                      {e.name} <Badge>{e.event_type}</Badge>
                    </div>
                    <div className="text-xs text-ink-3">{e.start_date}{e.end_date ? ` → ${e.end_date}` : ''}</div>
                    <p className="mt-1 text-sm text-ink-2">{e.description}</p>
                    <p className="mt-0.5 text-xs text-ink-3">Source: {e.source}</p>
                  </li>
                ))}
              </ol>
            </Card>
            <SourceNote meta={meta} />
          </div>
        )}
      </QueryView>
    </>
  )
}

function Trend({ data, where, focus }: { data: PolicyData; where: string; focus: string }) {
  const t = useChartTokens()
  const all = usePolicyMarkers()
  const ev = data.events.find((e) => e.event_id === focus)
  const markers = useMemo(() => (ev ? all.filter((m) => m.label.includes(ev.short_name)) : all), [all, ev])
  const months = data.trend.map((r) => r.month)
  const option = useMemo(() => lineChart(t, months, [
    { name: 'BEV registrations', data: data.trend.map((r) => r.bev), color: t.series[0], area: true },
    { name: 'Same month, previous year', data: data.trend.map((r) => r.bev_prev_year), color: t.series[1], dashed: true },
  ], { markers, zoom: months.length > 24 }), [t, months, data.trend, markers])
  return (
    <ChartCard title="Monthly BEV registrations with policy milestones" png="policy_trend" csv="trend"
      description={`${where} · the dashed blue line repeats last year's value to show seasonality`}>
      {(ref) => <EChart ref={ref} option={option} height={380} ariaLabel="Monthly BEV registrations with policy event markers" />}
    </ChartCard>
  )
}

function Comparisons({ comps, where, win }: { comps: PolicyComparison[]; where: string; win: number }) {
  return (
    <ChartCard title={`Before vs after · ${win}-month windows`} csv="policy_comparison"
      description={`${where}. "Before" = the ${win} full months before the milestone month; "after" = the milestone month and the following ${win - 1}. Milestones in the same month are merged.`}>
      {() => (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {comps.map((c) => (
            <div key={c.anchor_id} className="rounded-lg border border-border p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-ink">{c.label}</p>
                  <p className="text-xs text-ink-3">Milestone month {formatMonth(c.anchor_month)}</p>
                </div>
                {!c.available && <Badge>Insufficient data</Badge>}
              </div>
              {c.available ? (
                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <dt className="text-ink-3">Avg monthly BEVs before<div className="text-[11px]">{formatMonthRange(c.before.start, c.before.end)}</div></dt>
                  <dd className="tabular text-right text-sm font-semibold">{formatIN(c.before_avg_monthly_bev)}</dd>
                  <dt className="text-ink-3">Avg monthly BEVs after<div className="text-[11px]">{formatMonthRange(c.after.start, c.after.end)}</div></dt>
                  <dd className="tabular text-right text-sm font-semibold">{formatIN(c.after_avg_monthly_bev)}</dd>
                  <dt className="text-ink-3">Change after vs before</dt>
                  <dd className="text-right"><Delta value={c.change_pct} /></dd>
                  <dt className="text-ink-3">EV share before → after</dt>
                  <dd className="tabular text-right">{formatPct(c.before_ev_share_pct, 2)} → {formatPct(c.after_ev_share_pct, 2)} <span className="text-ink-3">({formatPP(c.share_change_pp)})</span></dd>
                  <dt className="text-ink-3">After vs same months a year earlier</dt>
                  <dd className="text-right">{c.after_vs_same_months_prior_year_pct === null ? <span className="text-ink-3">n/a</span> : <Delta value={c.after_vs_same_months_prior_year_pct} />}</dd>
                </dl>
              ) : (
                <p className="mt-3 text-xs text-ink-3">{c.unavailable_reason}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </ChartCard>
  )
}
