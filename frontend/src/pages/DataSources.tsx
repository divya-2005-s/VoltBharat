import { CheckCircle2, CircleAlert, CircleX, FileSpreadsheet } from 'lucide-react'

import { PageHeader } from '@/components/dashboard/cards'
import { QueryView } from '@/components/dashboard/states'
import { DataTable } from '@/components/tables/DataTable'
import { Badge, Card } from '@/components/ui/primitives'
import { useSources } from '@/hooks/queries'
import { formatBytes, formatDateTime, formatIN } from '@/lib/formatters'

const statusIcon = { pass: CheckCircle2, warn: CircleAlert, fail: CircleX }
const statusTone = { pass: 'accent', warn: 'warn', fail: 'danger' } as const

export default function DataSources() {
  const q = useSources()
  return (
    <>
      <PageHeader title="Data Sources" description="Provenance, coverage, quality checks, EV classification and metric definitions behind every figure." />
      <QueryView query={q} height={600}>
        {({ data }) => (
          <div className="space-y-6">
            {data.last_run && (
              <Card className="p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-[15px] font-semibold text-ink">Last successful processing</h2>
                  <span className="text-sm text-ink-2">{formatDateTime(data.last_run.finished_at)} · ETL run #{data.last_run.run_id}</span>
                </div>
                <p className="mt-1 text-xs text-ink-3">Rows loaded: {Object.entries(data.last_run.rows_loaded).map(([k, v]) => `${k.replace('fact_', '')} ${formatIN(v)}`).join(' · ')}</p>
                <ul className="mt-4 grid gap-2 md:grid-cols-2">
                  {data.last_run.validation.map((c) => {
                    const Icon = statusIcon[c.status]
                    return (
                      <li key={c.name} className="flex gap-2 rounded-md border border-border p-2.5 text-xs">
                        <Badge tone={statusTone[c.status]} className="h-fit shrink-0"><Icon /> {c.status.toUpperCase()}</Badge>
                        <div className="min-w-0"><p className="font-medium text-ink">{c.name.replaceAll('_', ' ')}</p><p className="break-words text-ink-3">{c.detail}</p></div>
                      </li>
                    )
                  })}
                </ul>
              </Card>
            )}

            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-3">Source files</h2>
              <div className="grid gap-4 lg:grid-cols-2">
                {data.sources.map((s) => (
                  <Card key={s.source_key} className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <FileSpreadsheet className="size-4 text-ink-3" />
                        <h3 className="text-sm font-semibold text-ink">{s.title}</h3>
                      </div>
                      <Badge tone={s.can_identify_ev ? 'accent' : 'neutral'}>{s.can_identify_ev ? 'Identifies EVs' : 'Cannot identify EVs'}</Badge>
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-ink-3 break-all">{s.file_name}</p>
                    <p className="mt-2 text-sm text-ink-2">{s.description}</p>
                    <dl className="mt-3 grid grid-cols-[110px_1fr] gap-x-3 gap-y-1.5 text-xs">
                      <dt className="text-ink-3">Coverage</dt><dd className="text-ink-2">{s.coverage_label}</dd>
                      <dt className="text-ink-3">Grain</dt><dd className="text-ink-2">{s.grain}</dd>
                      <dt className="text-ink-3">Rows / size</dt><dd className="text-ink-2">{formatIN(s.row_count)} rows · {formatBytes(s.size_bytes)}</dd>
                      <dt className="text-ink-3">Used for</dt><dd className="text-ink-2">{s.used_for}</dd>
                      <dt className="text-ink-3">Provenance</dt><dd className="text-ink-2">{s.provenance}</dd>
                      <dt className="text-ink-3">Limitations</dt><dd className="text-warn">{s.limitations}</dd>
                      <dt className="text-ink-3">SHA-256</dt><dd className="font-mono text-[11px] text-ink-3 break-all">{s.sha256}</dd>
                    </dl>
                  </Card>
                ))}
              </div>
            </section>

            <div className="grid gap-5 lg:grid-cols-2">
              <Card className="p-5">
                <h2 className="text-[15px] font-semibold text-ink">EV classification</h2>
                <p className="mt-1 text-sm text-ink-2">{data.classification.headline_ev_definition}</p>
                <div className="mt-3">
                  <DataTable caption="Fuel label classification" dense rowKey={(r) => r.fuel_label} rows={data.classification.labels}
                    columns={[
                      { key: 'l', header: 'VAHAN fuel label', cell: (r) => r.fuel_label },
                      { key: 'c', header: 'Class', cell: (r) => <span className="font-mono text-xs">{r.fuel_class}</span> },
                      { key: 'b', header: 'Counted as EV', cell: (r) => (r.is_bev ? <Badge tone="accent">Yes (BEV)</Badge> : <span className="text-ink-3">No</span>) },
                    ]} />
                </div>
              </Card>
              <div className="space-y-5">
                <Card className="p-5">
                  <h2 className="text-[15px] font-semibold text-ink">Data-quality rules</h2>
                  <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm text-ink-2">{data.quality_rules.map((r) => <li key={r}>{r}</li>)}</ul>
                </Card>
                <Card className="p-5">
                  <h2 className="text-[15px] font-semibold text-ink">Methodology & metric definitions</h2>
                  <dl className="mt-3 space-y-3 text-sm">
                    {data.methodology.map((m) => (
                      <div key={m.metric}>
                        <dt className="font-medium text-ink">{m.metric} <span className="ml-1 text-xs font-normal text-ink-3">({m.source})</span></dt>
                        <dd className="text-ink-2">{m.definition}</dd>
                      </div>
                    ))}
                  </dl>
                </Card>
              </div>
            </div>
            <p className="text-xs text-ink-3">
              State boundaries: community-curated GeoJSON (udit-001/india-maps-data, district level, dissolved to states). Not an official Survey of India
              product; shown for orientation only.
            </p>
          </div>
        )}
      </QueryView>
    </>
  )
}
