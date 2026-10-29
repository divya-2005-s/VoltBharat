import { useMemo } from 'react'

import { useTheme } from '@/hooks/useTheme'

export interface ChartTokens {
  mode: 'light' | 'dark'
  surface: string
  text: string
  text2: string
  text3: string
  grid: string
  axis: string
  border: string
  series: [string, string, string, string]
  other: string
  warning: string
  critical: string
  neutral: string
  /** single-hue sequential ramps, light -> dark (lightest = near zero) */
  seqGreen: string[]
  seqAmber: string[]
}

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

export function readTokens(mode: 'light' | 'dark'): ChartTokens {
  return {
    mode,
    surface: css('--surface') || '#fff',
    text: css('--text'),
    text2: css('--text-2'),
    text3: css('--text-3'),
    grid: css('--chart-grid'),
    axis: css('--chart-axis'),
    border: css('--border'),
    series: [css('--series-1'), css('--series-2'), css('--series-3'), css('--series-4')],
    other: css('--series-other'),
    warning: css('--status-warning') || '#fab219',
    critical: css('--status-critical') || '#d03b3b',
    neutral: css('--status-neutral') || '#9ca3af',
    seqGreen: mode === 'dark'
      ? ['#0f2a24', '#0f4a3a', '#0b6b50', '#0e8c66', '#16b07f', '#4fd1a5']
      : ['#e6f7f0', '#b9ead6', '#7fd6b6', '#3dbb8f', '#0e9a6e', '#06704f'],
    seqAmber: mode === 'dark'
      ? ['#2a2112', '#4a3512', '#7a4f10', '#b0670f', '#e07b12', '#f59e0b']
      : ['#fff4e0', '#fde3b0', '#fbc56f', '#f59e3a', '#dd6f1c', '#b0470f'],
  }
}

/** Tokens recomputed whenever the resolved theme changes. */
export function useChartTokens(): ChartTokens {
  const { resolved } = useTheme()
  return useMemo(() => readTokens(resolved), [resolved])
}
