import { useEffect, useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { echarts, type EChartsOption } from '@/components/charts/echarts'
import { tooltipBase } from '@/components/charts/options'
import { useChartTokens } from '@/components/charts/tokens'
import { cn } from '@/lib/utils'

export interface MapDatum {
  name: string
  value: number | null // null = unavailable / not comparable (drawn neutral)
  note?: string
}

interface Props {
  data: MapDatum[]
  ramp: string[]
  format: (v: number | null) => string
  valueLabel: string
  ariaLabel: string
  selected?: string | null
  onSelect?: (state: string) => void
  height?: number
}

let geoPromise: Promise<boolean> | null = null

/** Loads data/reference/india_states.geojson (copied to /geo) once and registers it. */
function loadGeo(): Promise<boolean> {
  geoPromise ??= fetch('/geo/india_states.geojson')
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .then((geo) => {
      echarts.registerMap('india', geo)
      return true
    })
    .catch(() => {
      geoPromise = null // allow a retry on next mount
      return false
    })
  return geoPromise
}

export function IndiaMap({ data, ramp, format, valueLabel, ariaLabel, selected, onSelect, height = 440 }: Props) {
  const t = useChartTokens()
  const [geo, setGeo] = useState<'loading' | 'ok' | 'failed'>('loading')

  useEffect(() => {
    let alive = true
    loadGeo().then((ok) => alive && setGeo(ok ? 'ok' : 'failed'))
    return () => {
      alive = false
    }
  }, [])

  const values = data.map((d) => d.value).filter((v): v is number => v !== null)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 1

  const option = useMemo<EChartsOption>(() => ({
    tooltip: {
      ...tooltipBase(t),
      trigger: 'item',
      formatter: (p: { name: string; data?: MapDatum }) =>
        `<b>${p.name}</b><br/>${valueLabel}: <b>${format(p.data?.value ?? null)}</b>${p.data?.note ? `<div style="color:${t.text3};margin-top:4px;max-width:220px;white-space:normal">${p.data.note}</div>` : ''}`,
    },
    visualMap: {
      type: 'continuous',
      min,
      max,
      left: 8,
      bottom: 8,
      itemHeight: 110,
      itemWidth: 10,
      calculable: false,
      inRange: { color: ramp },
      text: [format(max), format(min)],
      textStyle: { color: t.text3, fontSize: 11 },
      seriesIndex: 0,
    },
    series: [{
      type: 'map',
      map: 'india',
      roam: false,
      layoutCenter: ['50%', '50%'],
      layoutSize: '100%',
      aspectScale: 0.95,
      selectedMode: false,
      itemStyle: { areaColor: t.mode === 'dark' ? '#1f2937' : '#e5e7eb', borderColor: t.surface, borderWidth: 0.8 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: undefined, borderColor: t.text, borderWidth: 1.5 } },
      data: data.map((d) => ({
        name: d.name,
        value: d.value ?? undefined,
        note: d.note,
        itemStyle: d.name === selected ? { borderColor: t.text, borderWidth: 2 } : undefined,
      })),
    }],
  }), [data, ramp, format, valueLabel, selected, min, max, t])

  if (geo === 'failed') return <MapFallback data={data} ramp={ramp} min={min} max={max} format={format} onSelect={onSelect} selected={selected} />
  if (geo === 'loading') return <div className="animate-pulse rounded-lg bg-surface-2" style={{ height }} aria-label="Loading map" />
  return <EChart option={option} height={height} ariaLabel={ariaLabel} onClick={(p) => p.name && onSelect?.(p.name)} />
}

/** Fallback when the boundary file is unavailable: a ranked, colour-keyed grid of states. */
function MapFallback({ data, ramp, min, max, format, onSelect, selected }: {
  data: MapDatum[]; ramp: string[]; min: number; max: number; format: (v: number | null) => string
  onSelect?: (s: string) => void; selected?: string | null
}) {
  const color = (v: number | null) => {
    if (v === null || max === min) return 'var(--surface-2)'
    const i = Math.min(ramp.length - 1, Math.floor(((v - min) / (max - min)) * ramp.length))
    return ramp[i]
  }
  const sorted = [...data].sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity))
  return (
    <div>
      <p className="mb-2 text-xs text-ink-3">Map boundaries could not be loaded; showing states ranked instead.</p>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        {sorted.map((d) => (
          <button
            key={d.name}
            type="button"
            onClick={() => onSelect?.(d.name)}
            className={cn('flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-left text-xs hover:bg-surface-2',
              selected === d.name && 'ring-2 ring-accent')}
          >
            <span className="size-3 shrink-0 rounded-sm" style={{ background: color(d.value) }} />
            <span className="flex-1 truncate text-ink-2">{d.name}</span>
            <span className="tabular font-medium text-ink">{format(d.value)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
