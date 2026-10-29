import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { Filters } from '@/types/api'

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/

/** Global filters persisted in the URL (?start=YYYY-MM&end=YYYY-MM&state=Name). */
export function useFilters() {
  const [params, setParams] = useSearchParams()
  const filters: Filters = useMemo(() => {
    const start = params.get('start') ?? undefined
    const end = params.get('end') ?? undefined
    return {
      start: start && MONTH.test(start) ? start : undefined,
      end: end && MONTH.test(end) ? end : undefined,
      state: params.get('state') || undefined,
    }
  }, [params])

  const setFilters = useCallback(
    (patch: Partial<Filters>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(patch)) {
            if (v) next.set(k, v)
            else next.delete(k)
          }
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  return { filters, setFilters }
}

/** Set several page-local URL params in ONE navigation (separate calls would overwrite each other). */
export function useSetUrlParams() {
  const [, setParams] = useSearchParams()
  return useCallback(
    (patch: Record<string, string | undefined>) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(patch)) {
            if (v) next.set(k, v)
            else next.delete(k)
          }
          return next
        },
        { replace: true },
      ),
    [setParams],
  )
}

/** Page-local URL parameter (e.g. sort, tab), kept alongside the global filters. */
export function useUrlParam(key: string, fallback: string) {
  const [params, setParams] = useSearchParams()
  const value = params.get(key) ?? fallback
  const setValue = useCallback(
    (v: string) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (v && v !== fallback) next.set(key, v)
          else next.delete(key)
          return next
        },
        { replace: true },
      ),
    [key, fallback, setParams],
  )
  return [value, setValue] as const
}
