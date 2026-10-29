import { Eye, Lightbulb } from 'lucide-react'

import { CsvButton, PageHeader, SourceNote } from '@/components/dashboard/cards'
import { EmptyState, QueryView } from '@/components/dashboard/states'
import { Badge, Card } from '@/components/ui/primitives'
import { useInsights } from '@/hooks/queries'
import { useFilters } from '@/hooks/useFilters'
import { formatIN } from '@/lib/formatters'
import { SOURCE_LABELS } from '@/lib/utils'
import type { Insight } from '@/types/api'

function value(i: Insight) {
  const v = i.metric.value
  if (v === null) return '—'
  if (i.metric.unit === '%') return `${v > 0 && i.metric.name.toLowerCase().includes('growth') ? '+' : ''}${v}%`
  if (i.metric.unit === 'pp') return `${v > 0 ? '+' : ''}${v} pp`
  return `${formatIN(v)} ${i.metric.unit}`
}

function period(p: Insight['period']) {
  if (p.current && typeof p.current === 'object') return ''
  return [p.start, p.end].filter(Boolean).join(' – ') + (p.charger_snapshot ? ` · chargers ${p.charger_snapshot}` : '')
}

function InsightCard({ i, titles }: { i: Insight; titles: Record<string, string> }) {
  const rec = i.kind === 'recommendation'
  const p = i.period as unknown as { current?: { start: string; end: string } }
  return (
    <Card className={`p-5 ${rec ? 'border-accent/40' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          {rec ? <Lightbulb className="size-4 text-accent-ink" /> : <Eye className="size-4 text-ink-3" />}
          <h3 className="text-sm font-semibold text-ink">{i.title}</h3>
        </div>
        <Badge tone={rec ? 'accent' : 'neutral'}>{rec ? 'Recommendation' : 'Observation'}</Badge>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink-2">{i.statement}</p>
      {i.reasoning && <p className="mt-2 text-[13px] leading-relaxed text-ink-3"><b className="font-medium text-ink-2">Reasoning:</b> {i.reasoning}</p>}
      <dl className="mt-3 grid gap-x-4 gap-y-1 border-t border-border pt-3 text-xs text-ink-3 sm:grid-cols-[auto_1fr]">
        <dt>Metric</dt><dd className="text-ink-2">{i.metric.name}: <b className="tabular">{value(i)}</b></dd>
        <dt>Period</dt><dd className="text-ink-2">{p.current ? `${p.current.start} – ${p.current.end} (vs previous 12 months)` : period(i.period)}</dd>
        <dt>Source</dt><dd className="text-ink-2">{i.sources.map((s) => SOURCE_LABELS[s] ?? s).join(' · ')}</dd>
        {i.based_on.length > 0 && <><dt>Based on</dt><dd className="text-ink-2">{i.based_on.map((b) => titles[b] ?? b).join('; ')}</dd></>}
      </dl>
    </Card>
  )
}

export default function Insights() {
  const { filters } = useFilters()
  const q = useInsights(filters)
  return (
    <>
      <PageHeader title="Insights" description="Generated from the database for the selected period. Each insight shows its metric, period and source; recommendations cite the observations they rest on.">
        <CsvButton dataset="insights" label="Export insights" />
      </PageHeader>
      <QueryView query={q} height={600} empty={(d) => d.data.length === 0}>
        {({ data, meta }) => {
          const titles = Object.fromEntries(data.map((i) => [i.id, i.title]))
          const obs = data.filter((i) => i.kind === 'observation')
          const recs = data.filter((i) => i.kind === 'recommendation')
          return (
            <div className="space-y-6">
              <section>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">Observations · {obs.length}</h2>
                <div className="grid gap-4 lg:grid-cols-2">{obs.map((i) => <InsightCard key={i.id} i={i} titles={titles} />)}</div>
              </section>
              <section>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">Recommendations · {recs.length}</h2>
                {recs.length ? <div className="grid gap-4 lg:grid-cols-2">{recs.map((i) => <InsightCard key={i.id} i={i} titles={titles} />)}</div>
                  : <EmptyState title="No recommendations for this period" />}
              </section>
              <SourceNote meta={meta} />
            </div>
          )
        }}
      </QueryView>
    </>
  )
}
