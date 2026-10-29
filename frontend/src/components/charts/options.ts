// Option builders. Rules: one y-axis per chart, thin marks (2px lines, rounded bar ends),
// recessive grid, crosshair/hover tooltips with exact Indian-formatted values,
// colour follows the entity (BEV is always series-1 green).
import { formatCompactIN, formatIN, formatMonth } from '@/lib/formatters'

import type { EChartsOption } from './echarts'
import type { ChartTokens } from './tokens'

type Fmt = (v: number | null) => string

export function tooltipBase(t: ChartTokens) {
  return {
    backgroundColor: t.surface,
    borderColor: t.border,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: { color: t.text, fontSize: 12 },
    extraCssText: 'box-shadow: 0 6px 20px rgba(0,0,0,.12); border-radius: 8px;',
  }
}

function axisCommon(t: ChartTokens) {
  return {
    axisLine: { lineStyle: { color: t.grid } },
    axisTick: { show: false },
    axisLabel: { color: t.text3, fontSize: 11 },
    splitLine: { lineStyle: { color: t.grid } },
  }
}

const dot = (color: string) =>
  `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${color};margin-right:6px"></span>`

export interface MarkerSpec {
  month: string // YYYY-MM on the x axis
  label: string
}

export interface LineSeriesSpec {
  name: string
  data: (number | null)[]
  color: string
  area?: boolean
  dashed?: boolean
}

/** Time-series line chart on a category month axis, with optional policy markers. */
export function lineChart(t: ChartTokens, months: string[], series: LineSeriesSpec[], opts: {
  yFormat?: Fmt
  tooltipFormat?: Fmt
  markers?: MarkerSpec[]
  zoom?: boolean
  stacked?: boolean
  yName?: string
} = {}): EChartsOption {
  const yFormat = opts.yFormat ?? formatCompactIN
  const tipFormat = opts.tooltipFormat ?? formatIN
  const markers = (opts.markers ?? []).filter((m) => months.includes(m.month))
  return {
    color: series.map((s) => s.color),
    grid: { left: 8, right: 16, top: series.length > 1 ? 36 : 16, bottom: opts.zoom ? 56 : 8, containLabel: true },
    legend: series.length > 1
      ? { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.text2, fontSize: 12 } }
      : undefined,
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: t.axis, type: 'dashed' } },
      formatter: (ps: { axisValue: string; seriesName: string; value: number | null; color: string }[]) => {
        const m = ps[0]?.axisValue
        const ev = markers.filter((x) => x.month === m).map((x) => `<div style="color:${t.text3};margin-top:4px">● ${x.label}</div>`).join('')
        return `<div style="font-weight:600;margin-bottom:4px">${formatMonth(m)}</div>` +
          ps.map((p) => `<div style="display:flex;justify-content:space-between;gap:16px">${dot(p.color)}<span style="flex:1;color:${t.text2}">${p.seriesName}</span><b>${tipFormat(p.value)}</b></div>`).join('') + ev
      },
    },
    xAxis: {
      type: 'category',
      data: months,
      boundaryGap: false,
      ...axisCommon(t),
      splitLine: { show: false },
      axisLabel: { color: t.text3, fontSize: 11, formatter: (v: string) => formatMonth(v).replace(' 20', " '") },
    },
    yAxis: {
      type: 'value',
      name: opts.yName,
      nameTextStyle: { color: t.text3, fontSize: 11, align: 'left' },
      ...axisCommon(t),
      axisLabel: { color: t.text3, fontSize: 11, formatter: (v: number) => yFormat(v) },
    },
    dataZoom: opts.zoom
      ? [{ type: 'inside' }, { type: 'slider', height: 22, bottom: 8, borderColor: t.border, fillerColor: 'rgba(16,185,129,0.12)',
          textStyle: { color: t.text3 }, labelFormatter: (_: number, v: string) => formatMonth(v) }]
      : undefined,
    series: series.map((s, i) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      stack: opts.stacked ? 'total' : undefined,
      showSymbol: false,
      symbolSize: 8,
      smooth: false,
      lineStyle: { width: 2, type: s.dashed ? 'dashed' : 'solid' },
      areaStyle: s.area || opts.stacked ? { opacity: opts.stacked ? 0.85 : 0.08 } : undefined,
      emphasis: { focus: 'series' },
      markLine: i === 0 && markers.length
        ? {
            symbol: 'none',
            silent: false,
            lineStyle: { color: t.axis, type: 'dashed', width: 1 },
            label: { color: t.text2, fontSize: 10, position: 'insideEndTop',
              // merged milestones: show the first, full list is in the tooltip
              formatter: (p: { name: string }) => { const parts = p.name.split(' / '); return parts.length > 1 ? `${parts[0]} +${parts.length - 1}` : parts[0] } },
            data: markers.map((m) => ({ xAxis: m.month, name: m.label })),
          }
        : undefined,
    })),
  }
}

/** Horizontal ranking bars (sorted by the caller, top first). */
export function barRanking(t: ChartTokens, rows: { label: string; value: number | null; color?: string }[], opts: {
  format?: Fmt
  color?: string
  valueName?: string
} = {}): EChartsOption {
  const fmt = opts.format ?? formatIN
  const data = [...rows].reverse()
  return {
    grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'item',
      formatter: (p: { name: string; value: number }) => `<b>${p.name}</b><br/>${opts.valueName ?? 'Value'}: <b>${fmt(p.value)}</b>`,
    },
    xAxis: { type: 'value', ...axisCommon(t), axisLabel: { show: false }, splitLine: { show: false } },
    yAxis: { type: 'category', data: data.map((r) => r.label), ...axisCommon(t), axisLine: { show: false },
      axisLabel: { color: t.text2, fontSize: 12 } },
    series: [{
      type: 'bar',
      data: data.map((r) => ({ value: r.value, itemStyle: { color: r.color ?? opts.color ?? t.series[0] } })),
      barMaxWidth: 16,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.text2, fontSize: 11, formatter: (p: { value: number }) => fmt(p.value) },
    }],
  }
}

/** Vertical bars over ordered categories (e.g. financial years). */
export function columnChart(t: ChartTokens, labels: string[], values: (number | null)[], opts: {
  format?: Fmt
  color?: string
  colors?: string[]
  valueName?: string
  notes?: string[]
} = {}): EChartsOption {
  const fmt = opts.format ?? formatIN
  return {
    grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'item',
      formatter: (p: { name: string; value: number; dataIndex: number }) =>
        `<b>${p.name}</b><br/>${opts.valueName ?? 'Value'}: <b>${fmt(p.value)}</b>${opts.notes?.[p.dataIndex] ? `<div style="color:${t.text3};margin-top:4px">${opts.notes[p.dataIndex]}</div>` : ''}`,
    },
    xAxis: { type: 'category', data: labels, ...axisCommon(t), splitLine: { show: false },
      axisLabel: { color: t.text3, fontSize: 11, interval: 0, formatter: (v: string) => v.replace(/ \(.*\)/, '*') } },
    yAxis: { type: 'value', ...axisCommon(t), axisLabel: { color: t.text3, fontSize: 11, formatter: (v: number) => formatCompactIN(v) } },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({ value: v, itemStyle: { color: opts.colors?.[i] ?? opts.color ?? t.series[0] } })),
      barMaxWidth: 40,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top', color: t.text2, fontSize: 11, formatter: (p: { value: number }) => formatCompactIN(p.value) },
    }],
  }
}

/** Donut for part-to-whole with <= 4 named slices + optional neutral "Other". */
export function donut(t: ChartTokens, slices: { name: string; value: number; color: string }[], opts: { format?: Fmt } = {}): EChartsOption {
  const fmt = opts.format ?? formatIN
  return {
    tooltip: {
      ...tooltipBase(t),
      trigger: 'item',
      formatter: (p: { name: string; value: number; percent: number }) => `<b>${p.name}</b><br/>${fmt(p.value)} (${p.percent.toFixed(1)}%)`,
    },
    legend: { bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.text2, fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['52%', '74%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 },
      label: { show: true, color: t.text2, fontSize: 11, formatter: (p: { percent: number }) => (p.percent >= 3 ? `${p.percent.toFixed(1)}%` : '') },
      labelLine: { length: 6, length2: 6 },
      data: slices.map((s) => ({ name: s.name, value: s.value, itemStyle: { color: s.color } })),
    }],
  }
}

/** Scatter of BEV registrations vs chargers; point colour carries the pressure tier. */
export function scatterGap(t: ChartTokens, points: { name: string; code: string; x: number; y: number; color: string; tier: string; label?: boolean }[]): EChartsOption {
  return {
    grid: { left: 8, right: 24, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'item',
      formatter: (p: { data: { name: string; value: [number, number]; tier: string } }) =>
        `<b>${p.data.name}</b><br/>Public stations: <b>${formatIN(p.data.value[0])}</b><br/>BEV registrations: <b>${formatIN(p.data.value[1])}</b><br/>BEVs per station: <b>${(p.data.value[1] / p.data.value[0]).toFixed(1)}</b><br/>Tier: ${p.data.tier}`,
    },
    xAxis: { type: 'log', name: 'Public charging stations (log)', nameLocation: 'middle', nameGap: 28,
      nameTextStyle: { color: t.text3, fontSize: 11 }, ...axisCommon(t), axisLabel: { color: t.text3, fontSize: 11, formatter: (v: number) => formatCompactIN(v) } },
    yAxis: { type: 'log', name: 'BEV registrations (log)', nameTextStyle: { color: t.text3, fontSize: 11, align: 'left' },
      ...axisCommon(t), axisLabel: { color: t.text3, fontSize: 11, formatter: (v: number) => formatCompactIN(v) } },
    series: [{
      type: 'scatter',
      symbolSize: 11,
      itemStyle: { borderColor: t.surface, borderWidth: 2, opacity: 0.95 },
      label: { show: true, position: 'right', color: t.text2, fontSize: 10, formatter: (p: { data: { code: string; showLabel: boolean } }) => (p.data.showLabel ? p.data.code : '') },
      data: points.map((p) => ({ name: p.name, value: [p.x, p.y], tier: p.tier, code: p.code, showLabel: p.label ?? true, itemStyle: { color: p.color } })),
      emphasis: { scale: 1.4 },
    }],
  }
}

