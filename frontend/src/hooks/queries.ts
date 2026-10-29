// TanStack Query hooks. Query keys include every filter that changes the result.
import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Filters } from '@/types/api'

const keep = { placeholderData: keepPreviousData }

export const useBootstrap = () =>
  useQuery({ queryKey: ['meta', 'states'], queryFn: ({ signal }) => api.stateRefs(signal), staleTime: 10 * 60_000 })

export const useOverview = (f: Filters) =>
  useQuery({ queryKey: ['overview', f.start, f.end, f.state], queryFn: ({ signal }) => api.overview(f, signal), ...keep })

export const useStates = (f: Filters, opts: { sort: string; order: string; search?: string; page: number; page_size: number }) =>
  useQuery({
    queryKey: ['states', f.start, f.end, opts.sort, opts.order, opts.search ?? '', opts.page, opts.page_size],
    queryFn: ({ signal }) => api.states({ ...f, ...opts }, signal),
    ...keep,
  })

export const useStateDetail = (name: string | undefined, f: Filters) =>
  useQuery({
    queryKey: ['state', name, f.start, f.end],
    queryFn: ({ signal }) => api.stateDetail(name!, f, signal),
    enabled: !!name,
    ...keep,
  })

export const useSegments = (f: Filters) =>
  useQuery({ queryKey: ['segments', f.start, f.end, f.state], queryFn: ({ signal }) => api.segments(f, signal), ...keep })

export const useMakers = (f: Filters, opts: { search?: string; ev_named_only?: boolean; page: number; page_size: number }) =>
  useQuery({
    queryKey: ['makers', f.start, f.end, f.state, opts.search ?? '', !!opts.ev_named_only, opts.page, opts.page_size],
    queryFn: ({ signal }) => api.makers({ ...f, ...opts }, signal),
    ...keep,
  })

export const useChargingGap = (f: Filters) =>
  useQuery({ queryKey: ['charging-gap', f.start, f.end], queryFn: ({ signal }) => api.chargingGap(f, signal), ...keep })

export const useChargerGrowth = (f: Filters) =>
  useQuery({ queryKey: ['charger-growth', f.state], queryFn: ({ signal }) => api.chargerGrowth(f, signal), ...keep })

export const usePolicy = (f: Filters, window: number) =>
  useQuery({
    queryKey: ['policy', f.start, f.end, f.state, window],
    queryFn: ({ signal }) => api.policy({ ...f, window }, signal),
    ...keep,
  })

export const useInsights = (f: Filters) =>
  useQuery({ queryKey: ['insights', f.start, f.end], queryFn: ({ signal }) => api.insights(f, signal), ...keep })

export const useSources = () => useQuery({ queryKey: ['sources'], queryFn: ({ signal }) => api.sources(signal) })
