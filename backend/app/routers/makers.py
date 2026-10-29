from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.routers.deps import FiltersDep
from app.schemas import Envelope, Makers
from app.services import makers as svc
from app.services.common import meta

router = APIRouter(tags=["makers"])


@router.get("/makers", response_model=Envelope[Makers], summary="Manufacturer rankings (all fuels) and name-identified EV makers")
def get_makers(
    f: FiltersDep,
    search: Annotated[Optional[str], Query(max_length=80)] = None,
    ev_named_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
):
    data = svc.makers(f.conn, f.period.start, f.period.end, f.state, search, ev_named_only, page, page_size)
    return {"data": data, "meta": meta(f.conn, f.period, ["maker", "fuel"], [
        "Maker figures are ALL-FUEL registrations and are not EV market shares."], state=f.state)}
