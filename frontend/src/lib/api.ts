// Centralised API client. Components never call fetch directly.
import type {
  ChargerGrowth, ChargingGap, Envelope, Filters, Health, Insight, Makers, Overview, PolicyData, PolicyEvent, Segments,
  SourcesData, StateDetail, StateRef, StatesData,
} from '@/types/api'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type Params = Record<string, string | number | boolean | undefined | null>

export function buildUrl(path: string, params: Params = {}): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  }
  const q = qs.toString()
  return `${API_BASE_URL}${path}${q ? `?${q}` : ''}`
}

async function request<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(buildUrl(path, params), { signal, headers: { Accept: 'application/json' } })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, 'network_error', 'Cannot reach the VoltBharat API. Check that the backend is running.')
  }
  if (!res.ok) {
    let code = 'http_error'
    let message = `Request failed (${res.status}).`
    try {
      const body = await res.json()
      if (body?.error) ({ code, message } = body.error)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message)
  }
  return res.json() as Promise<T>
}

const f = (x: Filters): Params => ({ start: x.start, end: x.end, state: x.state })

export const api = {
  health: (s?: AbortSignal) => request<Health>('/health', {}, s),
  overview: (x: Filters, s?: AbortSignal) => request<Envelope<Overview>>('/api/v1/overview', f(x), s),
  states: (x: Filters & { sort?: string; order?: string; search?: string; page?: number; page_size?: number }, s?: AbortSignal) =>
    request<Envelope<StatesData>>('/api/v1/states', { start: x.start, end: x.end, sort: x.sort, order: x.order,
      search: x.search, page: x.page, page_size: x.page_size }, s),
  stateDetail: (name: string, x: Filters, s?: AbortSignal) =>
    request<Envelope<StateDetail>>(`/api/v1/states/${encodeURIComponent(name)}`, { start: x.start, end: x.end }, s),
  segments: (x: Filters, s?: AbortSignal) => request<Envelope<Segments>>('/api/v1/segments', f(x), s),
  makers: (x: Filters & { search?: string; ev_named_only?: boolean; page?: number; page_size?: number }, s?: AbortSignal) =>
    request<Envelope<Makers>>('/api/v1/makers', { ...f(x), search: x.search, ev_named_only: x.ev_named_only || undefined,
      page: x.page, page_size: x.page_size }, s),
  chargingGap: (x: Filters, s?: AbortSignal) =>
    request<Envelope<ChargingGap>>('/api/v1/charging-gap', { start: x.start, end: x.end }, s),
  chargerGrowth: (x: Filters, s?: AbortSignal) => request<Envelope<ChargerGrowth>>('/api/v1/chargers/growth', { state: x.state }, s),
  policyEvents: (s?: AbortSignal) => request<Envelope<PolicyEvent[]>>('/api/v1/policy-events', {}, s),
  policy: (x: Filters & { window?: number }, s?: AbortSignal) =>
    request<Envelope<PolicyData>>('/api/v1/policy', { ...f(x), window: x.window }, s),
  insights: (x: Filters, s?: AbortSignal) => request<Envelope<Insight[]>>('/api/v1/insights', { start: x.start, end: x.end }, s),
  sources: (s?: AbortSignal) => request<Envelope<SourcesData>>('/api/v1/sources', {}, s),
  stateRefs: (s?: AbortSignal) => request<Envelope<StateRef[]>>('/api/v1/meta/states', {}, s),
}

export type ExportDataset =
  | 'trend' | 'states' | 'charging_gap' | 'makers' | 'powertrain' | 'categories' | 'chargers_growth'
  | 'policy_comparison' | 'insights'

/** Download a CSV export; resolves with the file name. */
export async function downloadCsv(dataset: ExportDataset, x: Filters): Promise<string> {
  const res = await fetch(buildUrl('/api/v1/export', { dataset, ...f(x) }))
  if (!res.ok) throw new ApiError(res.status, 'export_failed', `Export failed (${res.status}).`)
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? `voltbharat_${dataset}.csv`
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return name
}
