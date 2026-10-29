import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'

import { echarts, type EChartsOption } from './echarts'
import { useChartTokens } from './tokens'

export interface EChartHandle {
  /** PNG data URL of the chart at 2x resolution, on the current surface colour. */
  toPng: () => string | null
}

interface Props {
  option: EChartsOption
  height?: number | string
  ariaLabel: string
  onClick?: (params: { name?: string; data?: unknown; seriesName?: string }) => void
  className?: string
}

/** Thin ECharts wrapper: init once, update on option change, resize with its container. */
export const EChart = forwardRef<EChartHandle, Props>(function EChart({ option, height = 320, ariaLabel, onClick, className }, ref) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  const clickRef = useRef(onClick)
  useEffect(() => {
    clickRef.current = onClick
  }, [onClick])
  const tokens = useChartTokens()

  useEffect(() => {
    if (!el.current) return
    const c = echarts.init(el.current, undefined, { renderer: 'canvas' })
    chart.current = c
    c.on('click', (p) => clickRef.current?.(p as never))
    const ro = new ResizeObserver(() => c.resize())
    ro.observe(el.current)
    return () => {
      ro.disconnect()
      c.dispose()
      chart.current = null
    }
  }, [])

  useEffect(() => {
    chart.current?.setOption(
      { aria: { enabled: true, label: { description: ariaLabel } }, textStyle: { fontFamily: 'Inter Variable, sans-serif' }, ...option },
      { notMerge: true },
    )
  }, [option, ariaLabel])

  useImperativeHandle(ref, () => ({
    toPng: () => chart.current?.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: tokens.surface }) ?? null,
  }), [tokens.surface])

  return <div ref={el} role="img" aria-label={ariaLabel} className={className} style={{ height, width: '100%' }} />
})
