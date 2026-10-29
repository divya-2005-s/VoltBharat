from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Path, Query

from app.routers.deps import Conn, EndQ, PeriodDep, StartQ
from app.schemas import Envelope, StatesData, StateDetail
from app.services import analytics
from app.services import registrations as reg
from app.services.common import meta, resolve_period, resolve_state

router = APIRouter(tags=["states"])

SortKey = Literal["bev", "ev_share_pct", "yoy_growth_pct", "public_chargers", "bev_per_charger", "state_name",
                  "total_registrations"]


@router.get("/states", response_model=Envelope[StatesData], summary="State table with rankings (paginated)")
def list_states(
    f: PeriodDep,
    sort: SortKey = "bev",
    order: Literal["asc", "desc"] = "desc",
    search: Annotated[Optional[str], Query(max_length=80)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    rows = analytics.state_table(f.conn, f.period)
    if search:
        q = search.strip().lower()
        rows = [r for r in rows if q in r["state_name"].lower() or q == r["state_code"].lower()]
    present = [r for r in rows if r[sort] is not None]
    missing = [r for r in rows if r[sort] is None]  # unavailable values always sort last
    present.sort(key=lambda r: r[sort], reverse=(order == "desc"))
    rows = present + missing
    nat = reg.totals(f.conn, f.period.start, f.period.end)
    nat["public_chargers"] = sum(reg.chargers_by_state(f.conn).values())
    nat["yoy"] = analytics.yoy_block(f.conn, f.period.end)
    data = {"national": nat,
            "table": {"rows": rows[(page - 1) * page_size: page * page_size], "page": page, "page_size": page_size,
                      "total_rows": len(rows)}}
    return {"data": data, "meta": meta(f.conn, f.period, ["fuel", "chargers_state"], [
        f"Share ranks exclude states with fewer than {analytics.MIN_TOTAL_FOR_SHARE_RANK:,} total registrations in the period.",
        f"Growth ranks exclude states with fewer than {analytics.MIN_PREV_BEV_FOR_GROWTH_RANK:,} BEVs in the comparison year.",
        "YoY growth compares the 12 months ending at the selected end month with the preceding 12 months."])}


@router.get("/states/{state_name}", response_model=Envelope[StateDetail], summary="Detail for one state")
def get_state(conn: Conn, state_name: Annotated[str, Path(max_length=80)], start: StartQ = None, end: EndQ = None):
    state = resolve_state(conn, state_name)
    period = resolve_period(conn, start, end)
    data = analytics.state_detail(conn, period.start, period.end, state)
    return {"data": data, "meta": meta(conn, period, ["fuel", "maker", "chargers_state", "chargers_omc"],
                                       ["Top makers are ALL-FUEL registrations (the maker source has no fuel field)."],
                                       state=state)}
