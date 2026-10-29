from fastapi import APIRouter

from app.routers.deps import PeriodDep
from app.schemas import Envelope, Insight
from app.services import insights
from app.services.common import meta

router = APIRouter(tags=["insights"])


@router.get("/insights", response_model=Envelope[list[Insight]], summary="Programmatically generated insights")
def get_insights(f: PeriodDep):
    return {"data": insights.build(f.conn, f.period),
            "meta": meta(f.conn, f.period, ["fuel", "maker", "chargers_state", "chargers_omc"],
                         ["Every insight is computed from the database at request time; recommendations cite the "
                          "observations they rest on."])}
