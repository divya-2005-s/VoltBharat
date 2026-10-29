from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.routers.deps import Conn, FiltersDep
from app.schemas import Envelope, PolicyData, PolicyEvent
from app.services import policy
from app.services import registrations as reg
from app.services.common import meta

router = APIRouter(tags=["policy"])


@router.get("/policy-events", response_model=Envelope[list[PolicyEvent]], summary="Policy milestones")
def get_policy_events(conn: Conn):
    return {"data": policy.events(conn), "meta": meta(conn, None, ["policy_events"], policy.CAVEATS[:1])}


@router.get("/policy", response_model=Envelope[PolicyData], summary="Monthly trend with before/after comparisons")
def get_policy(f: FiltersDep, window: Annotated[int, Query(ge=3, le=12, description="Months before and after")] = 6,
               event_id: Annotated[Optional[str], Query(max_length=40)] = None):
    comps = policy.comparisons(f.conn, window, f.state)
    if event_id:
        comps = [c for c in comps if event_id in c["event_ids"]]
    data = {"events": policy.events(f.conn), "comparisons": comps,
            "trend": reg.monthly(f.conn, f.period.start, f.period.end, f.state), "caveats": policy.CAVEATS}
    return {"data": data, "meta": meta(f.conn, f.period, ["fuel"], [
        "Comparison windows are fixed around each milestone and do not follow the date filter."], state=f.state)}
