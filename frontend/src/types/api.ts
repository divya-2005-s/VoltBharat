// Mirrors backend/app/schemas.py. Every endpoint returns Envelope<T>.

export interface PeriodOut {
  start: string
  end: string
  months?: number | null
}

export interface Meta {
  period: PeriodOut | null
  sources: string[]
  notes: string[]
  data_coverage: PeriodOut
  last_processed_at: string | null
  state?: string | null
  charger_snapshot?: string
  granularity?: string
}

export interface Envelope<T> {
  data: T
  meta: Meta
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}

export interface MonthPoint {
  month: string
  bev: number
  strong_hybrid: number
  plugin_hybrid: number
  fcev: number
  other_hybrid: number
  total: number
  ev_share_pct: number | null
  bev_prev_year: number | null
  bev_yoy_pct: number | null
  ev_share_prev_year_pct: number | null
}

export interface Window {
  start: string
  end: string
}

export interface YoY {
  window: { current: Window; previous: Window; available: boolean }
  bev_current: number | null
  bev_previous: number | null
  growth_pct: number | null
  ev_share_current_pct: number | null
  ev_share_previous_pct: number | null
  share_change_pp: number | null
  unavailable_reason?: string | null
}

export interface Powertrain {
  bev: number
  strong_hybrid: number
  plugin_hybrid: number
  fcev: number
  other_hybrid: number
}

export interface Overview {
  kpis: {
    bev_registrations: number
    total_registrations: number
    ev_share_pct: number | null
    yoy: YoY
    public_chargers: number | null
    charger_snapshot: string
    months: number
  }
  latest_month: MonthPoint | null
  trend: MonthPoint[]
  map: { state_name: string; ev_share_pct: number | null; bev: number | null; share_rankable: boolean }[]
  top_states_by_bev: { state_name: string; value: number | null; share_of_national_pct: number | null }[]
  top_states_by_share: { state_name: string; value: number | null; bev: number | null }[]
  powertrain: Powertrain
  selected_state: string | null
}

export interface StateRow {
  state_name: string
  state_code: string
  state_type: string
  region: string
  bev: number | null
  total_registrations: number | null
  ev_share_pct: number | null
  strong_hybrid: number | null
  bev_last_12m: number | null
  bev_prev_12m: number | null
  yoy_growth_pct: number | null
  public_chargers: number | null
  bev_per_charger: number | null
  share_rankable: boolean
  growth_rankable: boolean
  rank_bev: number | null
  rank_share: number | null
  rank_growth: number | null
}

export interface Page<T> {
  rows: T[]
  page: number
  page_size: number
  total_rows: number
}

export interface StatesData {
  national: { bev: number; total: number; ev_share_pct: number | null; public_chargers: number; yoy: YoY }
  table: Page<StateRow>
}

export interface MakerRow {
  maker: string
  name_identified_ev_maker: boolean
  registrations: number
  rank?: number | null
  share_of_all_registrations_pct?: number | null
  rank_within_ev_named?: number | null
  share_within_ev_named_pct?: number | null
}

export interface OmcYear {
  fy_label: string
  fy_order?: number | null
  is_partial_year: boolean
  installed: number
  cumulative_installed?: number | null
  growth_pct?: number | null
}

export interface StateDetail {
  summary: StateRow
  national_ev_share_pct: number | null
  trend: MonthPoint[]
  powertrain: Powertrain
  yoy: YoY
  top_makers_all_fuels: MakerRow[]
  omc_installations: OmcYear[]
}

export interface Segments {
  ev_category_split_supported: boolean
  ev_category_split_reason: string
  powertrain: {
    series: ({ month: string } & Record<'bev' | 'strong_hybrid' | 'plugin_hybrid' | 'fcev', number>)[]
    totals: { key: string; label: string; registrations: number; share_pct: number | null }[]
  }
  all_fuel_categories: {
    coverage: Window
    available: boolean
    reason: string | null
    states_included: string[]
    period?: Window | null
    series: ({ month: string } & Record<string, number | string>)[]
    totals: { group: string; registrations: number; share_pct: number | null }[]
    groups: string[]
  }
}

export interface Makers {
  ev_market_share_supported: boolean
  ev_market_share_reason: string
  all_fuel: {
    total_registrations: number
    maker_count: number
    top10: MakerRow[]
    top5_share_pct: number | null
    top10_share_pct: number | null
  }
  ev_named: {
    definition: string
    maker_count: number
    total_registrations: number
    bev_registrations_fuel_source: number
    coverage_of_bev_pct: number | null
    top10: MakerRow[]
  }
  table: Page<MakerRow>
}

export type PressureTier = 'high' | 'elevated' | 'typical'

export interface GapRow {
  state_name: string
  state_code: string
  bev: number | null
  public_chargers: number | null
  bev_per_charger: number | null
  relative_to_national: number | null
  pressure_tier: PressureTier | null
  small_charger_base: boolean
  rankable: boolean
  unrankable_reason: string | null
  rank: number | null
}

export interface ChargingGap {
  national: { bev: number; public_chargers: number; bev_per_charger: number | null }
  thresholds: { high: number; elevated: number; small_charger_base: number }
  states: GapRow[]
}

export interface ChargerGrowth {
  measure: string
  financial_years: OmcYear[]
  status: { decommissioned: number; total_installed: number; total_operational: number }
  by_state: { state_name: string; total_installed: number; total_operational: number; decommissioned: number }[]
  notes: string[]
}

export interface PolicyEvent {
  event_id: string
  name: string
  short_name: string
  start_date: string
  end_date: string | null
  event_type: string
  description: string
  source: string
}

export interface PolicyComparison {
  anchor_id: string
  event_id: string
  event_ids: string[]
  label: string
  anchor_month: string
  window_months: number
  before: Window
  after: Window
  available: boolean
  unavailable_reason?: string | null
  before_avg_monthly_bev?: number | null
  after_avg_monthly_bev?: number | null
  change_pct?: number | null
  before_ev_share_pct?: number | null
  after_ev_share_pct?: number | null
  share_change_pp?: number | null
  after_vs_same_months_prior_year_pct?: number | null
  prior_year_window?: Window | null
}

export interface PolicyData {
  events: PolicyEvent[]
  comparisons: PolicyComparison[]
  trend: MonthPoint[]
  caveats: string[]
}

export interface Insight {
  id: string
  kind: 'observation' | 'recommendation'
  category: string
  title: string
  statement: string
  metric: { name: string; value: number | null; unit: string }
  period: Record<string, string | undefined>
  sources: string[]
  reasoning: string | null
  based_on: string[]
}

export interface DataSource {
  source_key: string
  file_name: string
  title: string
  description: string
  provenance: string
  grain: string
  coverage_start: string | null
  coverage_end: string | null
  coverage_label: string
  row_count: number | null
  size_bytes: number | null
  sha256: string | null
  can_identify_ev: boolean
  used_for: string
  limitations: string
  processed_at: string
}

export interface SourcesData {
  sources: DataSource[]
  classification: {
    headline_ev_definition: string
    separate_classes: string[]
    labels: { fuel_label: string; fuel_class: string; is_bev: boolean }[]
  }
  quality_rules: string[]
  methodology: { metric: string; definition: string; source: string }[]
  last_run: {
    run_id: number
    started_at: string
    finished_at: string
    rows_loaded: Record<string, number>
    validation: { name: string; status: 'pass' | 'warn' | 'fail'; detail: string }[]
  } | null
}

export interface StateRef {
  state_name: string
  state_code: string
  state_type: string
  region: string
}

export interface Health {
  status: 'ok' | 'degraded'
  database: 'ok' | 'unavailable'
  last_successful_etl: string | null
  version: string
}

export interface Filters {
  start?: string
  end?: string
  state?: string
}
