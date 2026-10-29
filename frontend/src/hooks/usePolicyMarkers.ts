import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import type { MarkerSpec } from '@/components/charts/options'
import { api } from '@/lib/api'
import { shiftMonth } from '@/lib/formatters'

/** First full month a dated change applies (same rule as the backend's comparisons). */
export function effectiveMonth(isoDate: string): string {
  const ym = isoDate.slice(0, 7)
  return isoDate.slice(8, 10) === '01' ? ym : shiftMonth(ym, 1)
}

/** Policy milestones as chart markers; markers in the same month are merged into one label. */
export function usePolicyMarkers(): MarkerSpec[] {
  const { data } = useQuery({ queryKey: ['policy-events'], queryFn: ({ signal }) => api.policyEvents(signal), staleTime: 30 * 60_000 })
  return useMemo(() => {
    const byMonth = new Map<string, string[]>()
    const add = (m: string, l: string) => byMonth.set(m, [...(byMonth.get(m) ?? []), l])
    for (const e of data?.data ?? []) {
      add(effectiveMonth(e.start_date), e.event_type === 'scheme' ? `${e.short_name} start` : e.short_name)
      if (e.end_date && e.event_type === 'scheme') {
        const d = new Date(`${e.end_date}T00:00:00Z`)
        d.setUTCDate(d.getUTCDate() + 1)
        add(effectiveMonth(d.toISOString().slice(0, 10)), `${e.short_name} end`)
      }
    }
    return [...byMonth.entries()].map(([month, labels]) => ({ month, label: labels.join(' / ') }))
  }, [data])
}
