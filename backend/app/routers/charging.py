from typing import Annotated

from fastapi import APIRouter, Query

from app.routers.deps import FiltersDep, PeriodDep
from app.schemas import ChargerGrowth, ChargingGap, Envelope
from app.services import analytics, chargers
from app.services import registrations as reg
from app.services.common import meta

router = APIRouter(tags=["charging"])


@router.get("/charging-gap", response_model=Envelope[ChargingGap], summary="BEV registrations per public charging station")
def get_charging_gap(f: PeriodDep, limit: Annotated[int, Query(ge=1, le=36)] = 36):
    data = analytics.charging_gap(f.conn, f.period)
    data["states"] = data["states"][:limit]
    return {"data": data, "meta": meta(f.conn, f.period, ["fuel", "chargers_state"], [
        "Approximate infrastructure-pressure indicator: BEVs registered in the period divided by public stations in the "
        "2025 snapshot. It is not the number of vehicles per operating charger and says nothing about utilisation, "
        "charger power, location or home charging.",
        f"States with fewer than {analytics.SMALL_CHARGER_BASE} stations are shown but not ranked."],
        charger_snapshot=reg.charger_snapshot_label(f.conn))}


@router.get("/chargers/growth", response_model=Envelope[ChargerGrowth], summary="OMC charger installations by financial year")
def get_charger_growth(f: FiltersDep):
    data = chargers.growth_data(f.conn, f.state)
    m = meta(f.conn, None, ["chargers_omc"], ["Not filtered by the registration date range; uses the source's financial years."],
             state=f.state)
    return {"data": data, "meta": m}
