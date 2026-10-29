from fastapi import APIRouter

from app.routers.deps import FiltersDep
from app.schemas import Envelope, Overview
from app.services import analytics
from app.services.common import meta

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=Envelope[Overview], summary="Executive KPIs, trend, map and top states")
def get_overview(f: FiltersDep):
    data = analytics.overview(f.conn, f.period.start, f.period.end, f.state)
    notes = ["EV = battery-electric vehicles (fuel labels 'Electric(BOV)' and 'Pure EV'). Hybrids are reported separately.",
             "Public chargers are a 2025 state snapshot, not time-matched to the registration period."]
    return {"data": data, "meta": meta(f.conn, f.period, ["fuel", "chargers_state"], notes, state=f.state)}
