import { ArrowDownRight, ArrowUpRight, Download, ImageDown, Info, Minus } from 'lucide-react'
import { useRef, useState, type ReactNode, type RefObject } from 'react'
import { toast } from 'sonner'

import type { EChartHandle } from '@/components/charts/EChart'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/overlays'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/primitives'
import { useFilters } from '@/hooks/useFilters'
import { downloadCsv, type ExportDataset } from '@/lib/api'
import { formatDateTime, formatMonthRange } from '@/lib/formatters'
import { cn, SOURCE_LABELS } from '@/lib/utils'
import type { Meta } from '@/types/api'

export function InfoTip({ children, label = 'About this metric' }: { children: ReactNode; label?: string }) {
  return (
    <Tip content={children}>
      <button type="button" aria-label={label} className="rounded text-ink-3 hover:text-ink">
        <Info className="size-3.5" />
      </button>
    </Tip>
  )
}

export function CsvButton({ dataset, label = 'CSV' }: { dataset: ExportDataset; label?: string }) {
  const { filters } = useFilters()
  const [busy, setBusy] = useState(false)
  return (
    <Button
      size="sm"
      variant="ghost"
      disabled={busy}
      aria-label={`Download ${dataset} as CSV`}
      onClick={async () => {
        setBusy(true)
        try {
          const name = await downloadCsv(dataset, filters)
          toast.success('CSV downloaded', { description: name })
        } catch (e) {
          toast.error('Export failed', { description: (e as Error).message })
        } finally {
          setBusy(false)
        }
      }}
    >
      <Download /> {label}
    </Button>
  )
}

export function PngButton({ chart, name }: { chart: RefObject<EChartHandle | null>; name: string }) {
  return (
    <Button
      size="sm"
      variant="ghost"
      aria-label="Download chart as PNG"
      onClick={() => {
        const url = chart.current?.toPng()
        if (!url) return toast.error('Chart is not ready yet')
        const a = Object.assign(document.createElement('a'), { href: url, download: `voltbharat_${name}.png` })
        a.click()
        toast.success('Chart image downloaded')
      }}
    >
      <ImageDown /> PNG
    </Button>
  )
}

/** Card with title, definition tooltip and export actions. `children` receives a chart ref for PNG export. */
export function ChartCard({ title, description, info, csv, png, actions, children, className, footer }: {
  title: string
  description?: ReactNode
  info?: ReactNode
  csv?: ExportDataset
  png?: string
  actions?: ReactNode
  children: (chartRef: RefObject<EChartHandle | null>) => ReactNode
  className?: string
  footer?: ReactNode
}) {
  const ref = useRef<EChartHandle>(null)
  return (
    <Card className={cn('flex min-w-0 flex-col', className)}>
      <CardHeader>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <CardTitle>{title}</CardTitle>
            {info && <InfoTip>{info}</InfoTip>}
          </div>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1">
          {actions}
          {png && <PngButton chart={ref} name={png} />}
          {csv && <CsvButton dataset={csv} />}
        </div>
      </CardHeader>
      <CardContent className="flex-1">{children(ref)}</CardContent>
      {footer && <div className="border-t border-border px-5 py-2.5 text-xs text-ink-3">{footer}</div>}
    </Card>
  )
}

export function Delta({ value, suffix = '%', positiveIsGood = true, digits = 1 }: {
  value: number | null | undefined
  suffix?: string
  positiveIsGood?: boolean
  digits?: number
}) {
  if (value === null || value === undefined) return <span className="text-xs text-ink-3">no comparison</span>
  const up = value > 0
  const flat = value === 0
  const good = flat ? null : up === positiveIsGood
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight
  return (
    <span className={cn('inline-flex items-center gap-0.5 text-xs font-semibold tabular',
      good === null ? 'text-ink-3' : good ? 'text-accent-ink' : 'text-danger')}>
      <Icon className="size-3.5" aria-hidden />
      {up ? '+' : ''}{value.toFixed(digits)}{suffix}
    </span>
  )
}

export function KpiCard({ label, value, unit, period, comparison, definition, unavailable, icon }: {
  label: string
  value: string
  unit?: string
  period: string
  comparison?: ReactNode
  definition: ReactNode
  unavailable?: string | null
  icon?: ReactNode
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
          {icon && <span className="text-accent-ink [&_svg]:size-4">{icon}</span>}
          {label}
          <InfoTip label={`Definition: ${label}`}>{definition}</InfoTip>
        </div>
      </div>
      {unavailable ? (
        <>
          <div className="mt-2 text-2xl font-semibold text-ink-3">Unavailable</div>
          <p className="mt-1 text-xs text-ink-3">{unavailable}</p>
        </>
      ) : (
        <>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="tabular text-[26px] font-semibold leading-none tracking-tight text-ink">{value}</span>
            {unit && <span className="text-sm text-ink-3">{unit}</span>}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            {comparison}
            <span className="text-xs text-ink-3">{period}</span>
          </div>
        </>
      )}
    </Card>
  )
}

const noticeTone = {
  info: 'border-info-border bg-info-soft',
  warn: 'border-warn-border bg-warn-soft',
}

export function Notice({ title, children, tone = 'info', icon }: { title?: string; children: ReactNode; tone?: 'info' | 'warn'; icon?: ReactNode }) {
  return (
    <div className={cn('flex gap-3 rounded-lg border px-4 py-3 text-[13px] leading-relaxed text-ink-2', noticeTone[tone])}>
      <span className={cn('mt-0.5 shrink-0 [&_svg]:size-4', tone === 'warn' ? 'text-warn' : 'text-ink-3')}>{icon ?? <Info />}</span>
      <div>
        {title && <p className="font-semibold text-ink">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}

export function SourceNote({ meta, extra }: { meta?: Meta; extra?: ReactNode }) {
  if (!meta) return null
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3">
      {meta.period && <span>Period: <b className="font-medium text-ink-2">{formatMonthRange(meta.period.start, meta.period.end)}</b></span>}
      {meta.sources.length > 0 && <span>Source: {meta.sources.map((s) => SOURCE_LABELS[s] ?? s).join(' · ')}</span>}
      {extra}
      {meta.last_processed_at && <span>Processed {formatDateTime(meta.last_processed_at)}</span>}
      {meta.notes.filter((n) => n.startsWith('Period limited')).map((n) => <span key={n} className="text-warn">{n}</span>)}
    </div>
  )
}

export function PageHeader({ title, description, children }: { title: string; description: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-3">{description}</p>
      </div>
      {children}
    </div>
  )
}
