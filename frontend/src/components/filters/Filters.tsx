import { CalendarRange, MapPin } from 'lucide-react'
import { useMemo } from 'react'

import { ALL, Select, type Option } from '@/components/ui/select'
import { useBootstrap } from '@/hooks/queries'
import { useFilters } from '@/hooks/useFilters'
import { formatMonth, monthRange, shiftMonth } from '@/lib/formatters'

export interface Preset {
  id: string
  label: string
  start: string
  end: string
}

/** Presets derived from the actual data coverage (never hard-coded dates). */
export function buildPresets(first: string, last: string): Preset[] {
  const out: Preset[] = [{ id: 'all', label: 'All data', start: first, end: last }]
  const l12 = shiftMonth(last, -11)
  if (l12 >= first) out.push({ id: 'l12', label: 'Last 12 months', start: l12, end: last })
  const lastYear = Number(last.slice(0, 4))
  for (const y of [lastYear - 1, lastYear - 2]) {
    if (`${y}-01` >= first && `${y}-12` <= last) out.push({ id: `cy${y}`, label: `Calendar ${y}`, start: `${y}-01`, end: `${y}-12` })
  }
  // Complete Indian financial years (Apr-Mar), latest first
  let fy = Number(last.slice(5)) >= 3 ? lastYear - 1 : lastYear - 2
  for (let i = 0; i < 2; i += 1, fy -= 1) {
    const s = `${fy}-04`
    const e = `${fy + 1}-03`
    if (s >= first && e <= last) out.push({ id: `fy${fy}`, label: `FY${fy}-${String(fy + 1).slice(2)}`, start: s, end: e })
  }
  return out
}

export function DateRangeFilter() {
  const { data } = useBootstrap()
  const { filters, setFilters } = useFilters()
  const cov = data?.meta.data_coverage
  const months = useMemo(() => (cov ? monthRange(cov.start, cov.end) : []), [cov])
  const presets = useMemo(() => (cov ? buildPresets(cov.start, cov.end) : []), [cov])
  if (!cov) return <div className="h-9 w-56 animate-pulse rounded-md bg-surface-2" />

  const start = filters.start ?? cov.start
  const end = filters.end ?? cov.end
  const active = presets.find((p) => p.start === start && p.end === end)?.id ?? 'custom'
  const opts = (filter: (m: string) => boolean): Option[] =>
    [...months].reverse().filter(filter).map((m) => ({ value: m, label: formatMonth(m), group: m.slice(0, 4) }))

  const apply = (s: string, e: string) => setFilters({ start: s === cov.start ? undefined : s, end: e === cov.end ? undefined : e })

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Select
        label="Date range preset"
        value={active}
        onChange={(id) => {
          const p = presets.find((x) => x.id === id)
          if (p) apply(p.start, p.end)
        }}
        options={[...presets.map((p) => ({ value: p.id, label: p.label })), ...(active === 'custom' ? [{ value: 'custom', label: 'Custom range' }] : [])]}
        icon={<CalendarRange className="size-4 text-ink-3" />}
        className="w-[170px]"
      />
      <Select label="From month" value={start} onChange={(s) => apply(s, s > end ? s : end)} options={opts(() => true)} className="w-[118px]" />
      <span className="text-xs text-ink-3">to</span>
      <Select label="To month" value={end} onChange={(e) => apply(e < start ? e : start, e)} options={opts(() => true)} className="w-[118px]" />
    </div>
  )
}

export function StateFilter() {
  const { data } = useBootstrap()
  const { filters, setFilters } = useFilters()
  const options: Option[] = [
    { value: ALL, label: 'All India' },
    ...(data?.data ?? []).map((s) => ({ value: s.state_name, label: s.state_name, group: s.state_type === 'UT' ? 'Union territories' : 'States' })),
  ]
  return (
    <Select
      label="State filter"
      value={filters.state ?? ALL}
      onChange={(v) => setFilters({ state: v === ALL ? undefined : v })}
      options={options}
      icon={<MapPin className="size-4 text-ink-3" />}
      className="w-[200px]"
    />
  )
}
