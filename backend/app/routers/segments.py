from fastapi import APIRouter

from app.routers.deps import FiltersDep
from app.schemas import Envelope, Segments
from app.services import segments as svc
from app.services.common import meta

router = APIRouter(tags=["segments"])


@router.get("/segments", response_model=Envelope[Segments], summary="EV powertrain mix and all-fuel category context")
def get_segments(f: FiltersDep):
    data = svc.segments(f.conn, f.period.start, f.period.end, f.state)
    return {"data": data, "meta": meta(f.conn, f.period, ["fuel", "category"], [
        "EV registrations cannot be split by vehicle category with the available sources.",
        "Category figures are ALL FUELS and limited to states whose data validated."], state=f.state)}
