"""Response schemas. Every endpoint returns {"data": ..., "meta": Meta}."""
from __future__ import annotations

from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PeriodOut(BaseModel):
    start: str = Field(examples=["2022-01"])
    end: str = Field(examples=["2026-09"])
    months: Optional[int] = None


class Meta(BaseModel):
    period: Optional[PeriodOut] = None
    sources: list[str] = Field(description="data_sources.source_key values used")
    notes: list[str] = []
    data_coverage: PeriodOut
    last_processed_at: Optional[str] = None
    model_config = {"extra": "allow"}


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------- shared
class MonthPoint(BaseModel):
    month: str
    bev: int
    strong_hybrid: int
    plugin_hybrid: int
    fcev: int
    other_hybrid: int
    total: int
    ev_share_pct: Optional[float]
    bev_prev_year: Optional[int]
    bev_yoy_pct: Optional[float]
    ev_share_prev_year_pct: Optional[float]


class Window(BaseModel):
    start: str
    end: str


class YoYWindow(BaseModel):
    current: Window
    previous: Window
    available: bool


class YoY(BaseModel):
    window: YoYWindow
    bev_current: Optional[int]
    bev_previous: Optional[int]
    growth_pct: Optional[float]
    ev_share_current_pct: Optional[float]
    ev_share_previous_pct: Optional[float]
    share_change_pp: Optional[float]
    unavailable_reason: Optional[str] = None


class Powertrain(BaseModel):
    bev: int
    strong_hybrid: int
    plugin_hybrid: int
    fcev: int
    other_hybrid: int


# ---------------------------------------------------------------- overview
class Kpis(BaseModel):
    bev_registrations: int
    total_registrations: int
    ev_share_pct: Optional[float]
    yoy: YoY
    public_chargers: Optional[int]
    charger_snapshot: str
    months: int


class MapPoint(BaseModel):
    state_name: str
    ev_share_pct: Optional[float]
    bev: Optional[int]
    share_rankable: bool


class TopState(BaseModel):
    state_name: str
    value: Optional[float]
    bev: Optional[int] = None
    share_of_national_pct: Optional[float] = None


class Overview(BaseModel):
    kpis: Kpis
    latest_month: Optional[MonthPoint]
    trend: list[MonthPoint]
    map: list[MapPoint]
    top_states_by_bev: list[TopState]
    top_states_by_share: list[TopState]
    powertrain: Powertrain
    selected_state: Optional[str]


# ---------------------------------------------------------------- states
class StateRow(BaseModel):
    state_name: str
    state_code: str
    state_type: str
    region: str
    bev: Optional[int]
    total_registrations: Optional[int]
    ev_share_pct: Optional[float]
    strong_hybrid: Optional[int] = None
    bev_last_12m: Optional[int]
    bev_prev_12m: Optional[int]
    yoy_growth_pct: Optional[float]
    public_chargers: Optional[int]
    bev_per_charger: Optional[float]
    share_rankable: bool
    growth_rankable: bool
    rank_bev: Optional[int]
    rank_share: Optional[int]
    rank_growth: Optional[int]


class Page(BaseModel, Generic[T]):
    rows: list[T]
    page: int
    page_size: int
    total_rows: int


class StatesData(BaseModel):
    national: dict[str, Any]
    table: Page[StateRow]


class MakerRow(BaseModel):
    maker: str
    name_identified_ev_maker: bool
    registrations: int
    rank: Optional[int] = None
    share_of_all_registrations_pct: Optional[float] = None
    rank_within_ev_named: Optional[int] = None
    share_within_ev_named_pct: Optional[float] = None


class OmcYear(BaseModel):
    fy_label: str
    fy_order: Optional[int] = None
    is_partial_year: bool
    installed: int
    cumulative_installed: Optional[int] = None
    growth_pct: Optional[float] = None


class StateDetail(BaseModel):
    summary: StateRow
    national_ev_share_pct: Optional[float]
    trend: list[MonthPoint]
    powertrain: Powertrain
    yoy: YoY
    top_makers_all_fuels: list[MakerRow]
    omc_installations: list[OmcYear]


# ---------------------------------------------------------------- segments
class PowertrainTotal(BaseModel):
    key: str
    label: str
    registrations: int
    share_pct: Optional[float]


class PowertrainBlock(BaseModel):
    series: list[dict[str, Any]]
    totals: list[PowertrainTotal]


class CategoryTotal(BaseModel):
    group: str
    registrations: int
    share_pct: Optional[float]


class CategoryBlock(BaseModel):
    coverage: Window
    available: bool
    reason: Optional[str]
    states_included: list[str]
    period: Optional[Window] = None
    series: list[dict[str, Any]]
    totals: list[CategoryTotal]
    groups: list[str] = []


class Segments(BaseModel):
    ev_category_split_supported: bool
    ev_category_split_reason: str
    powertrain: PowertrainBlock
    all_fuel_categories: CategoryBlock


# ---------------------------------------------------------------- makers
class AllFuelMakers(BaseModel):
    total_registrations: int
    maker_count: int
    top10: list[MakerRow]
    top5_share_pct: Optional[float]
    top10_share_pct: Optional[float]


class EvNamedMakers(BaseModel):
    definition: str
    maker_count: int
    total_registrations: int
    bev_registrations_fuel_source: int
    coverage_of_bev_pct: Optional[float]
    top10: list[MakerRow]


class Makers(BaseModel):
    ev_market_share_supported: bool
    ev_market_share_reason: str
    all_fuel: AllFuelMakers
    ev_named: EvNamedMakers
    table: Page[MakerRow]


# ---------------------------------------------------------------- charging
class GapRow(BaseModel):
    state_name: str
    state_code: str
    bev: Optional[int]
    public_chargers: Optional[int]
    bev_per_charger: Optional[float]
    relative_to_national: Optional[float]
    pressure_tier: Optional[Literal["high", "elevated", "typical"]]
    small_charger_base: bool
    rankable: bool
    unrankable_reason: Optional[str]
    rank: Optional[int]


class GapNational(BaseModel):
    bev: int
    public_chargers: int
    bev_per_charger: Optional[float]


class ChargingGap(BaseModel):
    national: GapNational
    thresholds: dict[str, float]
    states: list[GapRow]


class OmcStatus(BaseModel):
    decommissioned: int
    total_installed: int
    total_operational: int


class OmcStateRow(BaseModel):
    state_name: str
    total_installed: int
    total_operational: int
    decommissioned: int


class ChargerGrowth(BaseModel):
    measure: str
    financial_years: list[OmcYear]
    status: OmcStatus
    by_state: list[OmcStateRow]
    notes: list[str]


# ---------------------------------------------------------------- policy
class PolicyEvent(BaseModel):
    event_id: str
    name: str
    short_name: str
    start_date: str
    end_date: Optional[str]
    event_type: str
    description: str
    source: str


class PolicyComparison(BaseModel):
    anchor_id: str
    event_id: str
    event_ids: list[str]
    label: str
    anchor_month: str
    window_months: int
    before: Window
    after: Window
    available: bool
    unavailable_reason: Optional[str] = None
    before_avg_monthly_bev: Optional[int] = None
    after_avg_monthly_bev: Optional[int] = None
    change_pct: Optional[float] = None
    before_ev_share_pct: Optional[float] = None
    after_ev_share_pct: Optional[float] = None
    share_change_pp: Optional[float] = None
    after_vs_same_months_prior_year_pct: Optional[float] = None
    prior_year_window: Optional[Window] = None


class PolicyData(BaseModel):
    events: list[PolicyEvent]
    comparisons: list[PolicyComparison]
    trend: list[MonthPoint]
    caveats: list[str]


# ---------------------------------------------------------------- insights
class InsightMetric(BaseModel):
    name: str
    value: Optional[float]
    unit: str


class Insight(BaseModel):
    id: str
    kind: Literal["observation", "recommendation"]
    category: str
    title: str
    statement: str
    metric: InsightMetric
    period: dict[str, Any]
    sources: list[str]
    reasoning: Optional[str]
    based_on: list[str]


# ---------------------------------------------------------------- sources / health
class SourcesData(BaseModel):
    sources: list[dict[str, Any]]
    classification: dict[str, Any]
    quality_rules: list[str]
    methodology: list[dict[str, str]]
    last_run: Optional[dict[str, Any]]


class StateRef(BaseModel):
    state_name: str
    state_code: str
    state_type: str
    region: str


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    last_successful_etl: Optional[str] = None
    version: str
