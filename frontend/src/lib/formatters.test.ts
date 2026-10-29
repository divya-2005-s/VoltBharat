import { describe, expect, it } from 'vitest'

import { buildPresets } from '@/components/filters/Filters'

import { formatCompactIN, formatIN, formatMonth, formatPct, formatSignedPct, monthRange, NA, shiftMonth } from './formatters'

describe('Indian number formatting', () => {
  it('uses lakh/crore grouping', () => {
    expect(formatIN(1245300)).toBe('12,45,300')
    expect(formatIN(95431234)).toBe('9,54,31,234')
    expect(formatIN(999)).toBe('999')
  })
  it('distinguishes unavailable from zero', () => {
    expect(formatIN(null)).toBe(NA)
    expect(formatIN(undefined)).toBe(NA)
    expect(formatIN(0)).toBe('0')
    expect(formatPct(null)).toBe(NA)
    expect(formatPct(0)).toBe('0.0%')
  })
  it('compacts to lakh and crore', () => {
    expect(formatCompactIN(3_201_718)).toBe('32 L')
    expect(formatCompactIN(95_431_234)).toBe('9.54 Cr')
    expect(formatCompactIN(1_550)).toBe('1.55K')
  })
  it('signs percentages', () => {
    expect(formatSignedPct(42.4)).toBe('+42.4%')
    expect(formatSignedPct(-4.6)).toBe('-4.6%')
  })
})

describe('months', () => {
  it('formats and iterates months', () => {
    expect(formatMonth('2026-09')).toBe('Sep 2026')
    expect(monthRange('2025-11', '2026-02')).toEqual(['2025-11', '2025-12', '2026-01', '2026-02'])
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2025-12', 1)).toBe('2026-01')
  })
})

describe('date presets come from coverage, not hard-coded dates', () => {
  it('builds complete calendar and financial years only', () => {
    const p = Object.fromEntries(buildPresets('2022-01', '2026-09').map((x) => [x.id, x]))
    expect(p.all).toMatchObject({ start: '2022-01', end: '2026-09' })
    expect(p.l12).toMatchObject({ start: '2025-10', end: '2026-09' })
    expect(p.cy2025).toMatchObject({ start: '2025-01', end: '2025-12' })
    expect(p.fy2025).toMatchObject({ label: 'FY2025-26', start: '2025-04', end: '2026-03' })
    expect(p.fy2024).toMatchObject({ start: '2024-04', end: '2025-03' })
  })
  it('omits presets the data cannot fully cover', () => {
    const ids = buildPresets('2026-01', '2026-06').map((x) => x.id)
    expect(ids).toEqual(['all'])
  })
})
