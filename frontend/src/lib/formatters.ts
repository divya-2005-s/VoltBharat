// Indian number formatting and consistent date labels.

const inInt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const NA = '—'

/** 1245300 -> "12,45,300". null/undefined -> "—" (unavailable, never 0). */
export function formatIN(n: number | null | undefined): string {
  return n === null || n === undefined || Number.isNaN(n) ? NA : inInt.format(n)
}

/** Compact Indian units: 1.2 L (lakh), 3.4 Cr (crore). */
export function formatCompactIN(n: number | null | undefined): string {
  if (n === null || n === undefined) return NA
  const a = Math.abs(n)
  if (a >= 1e7) return `${trim(n / 1e7)} Cr`
  if (a >= 1e5) return `${trim(n / 1e5)} L`
  if (a >= 1e3) return `${trim(n / 1e3)}K`
  return inInt.format(n)
}

function trim(x: number): string {
  return x.toFixed(x >= 100 ? 0 : x >= 10 ? 1 : 2).replace(/\.?0+$/, '')
}

export function formatPct(n: number | null | undefined, digits = 1): string {
  return n === null || n === undefined ? NA : `${n.toFixed(digits)}%`
}

export function formatSignedPct(n: number | null | undefined, digits = 1): string {
  return n === null || n === undefined ? NA : `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`
}

export function formatPP(n: number | null | undefined): string {
  return n === null || n === undefined ? NA : `${n > 0 ? '+' : ''}${n.toFixed(2)} pp`
}

export function formatRatio(n: number | null | undefined): string {
  return n === null || n === undefined ? NA : n.toLocaleString('en-IN', { maximumFractionDigits: 1, minimumFractionDigits: 1 })
}

/** "2026-09" -> "Sep 2026" */
export function formatMonth(ym: string | null | undefined): string {
  if (!ym) return NA
  const [y, m] = ym.split('-').map(Number)
  return `${MONTHS[m - 1]} ${y}`
}

export function formatMonthRange(a?: string | null, b?: string | null): string {
  return `${formatMonth(a)} – ${formatMonth(b)}`
}

/** ISO timestamp -> "29 Oct 2026, 14:27" (local time). */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return NA
  const d = new Date(iso)
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

export function formatBytes(b: number | null | undefined): string {
  if (!b) return NA
  if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toFixed(1)} MB`
  if (b >= 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${b} B`
}

/** All months between two YYYY-MM values, inclusive. */
export function monthRange(start: string, end: string): string[] {
  const out: string[] = []
  let [y, m] = start.split('-').map(Number)
  const [ey, em] = end.split('-').map(Number)
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`)
    m += 1
    if (m > 12) {
      m = 1
      y += 1
    }
  }
  return out
}

export function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split('-').map(Number)
  const t = y * 12 + (m - 1) + delta
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`
}
