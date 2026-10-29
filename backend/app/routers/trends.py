from typing import Literal

from fastapi import APIRouter, Query

from app.routers.deps import FiltersDep
from app.schemas import Envelope
from app.services import registrations as reg
from app.services.common import meta, pct

router = APIRouter(tags=["trends"])


def aggregate(series: list[dict], granularity: str) -> list[dict]:
    if granularity == "month":
        return series
    buckets: dict[str, dict] = {}
    for r in series:
        y, m = map(int, r["month"].split("-"))
        key = str(y) if granularity == "year" else f"FY{y if m >= 4 else y - 1}-{str((y if m >= 4 else y - 1) + 1)[2:]}"
        b = buckets.setdefault(key, {"period": key, "months": 0, "bev": 0, "total": 0, "strong_hybrid": 0,
                                     "plugin_hybrid": 0, "fcev": 0})
        b["months"] += 1
        for k in ("bev", "total", "strong_hybrid", "plugin_hybrid", "fcev"):
            b[k] += r[k]
    out, prev = [], None
    for b in buckets.values():
        b["ev_share_pct"] = pct(b["bev"], b["total"])
        b["is_partial"] = b["months"] < 12
        # growth only between two complete periods
        b["bev_growth_pct"] = (round(100.0 * (b["bev"] - prev["bev"]) / prev["bev"], 1)
                               if prev and not prev["is_partial"] and not b["is_partial"] and prev["bev"] else None)
        out.append(b)
        prev = b
    return out


@router.get("/trend", response_model=Envelope[list[dict]], summary="EV registration time series")
def get_trend(f: FiltersDep, granularity: Literal["month", "fy", "year"] = Query("month")):
    series = reg.monthly(f.conn, f.period.start, f.period.end, f.state)
    notes = [] if granularity == "month" else ["Partial periods (fewer than 12 months in range) are flagged and not compared."]
    return {"data": aggregate(series, granularity),
            "meta": meta(f.conn, f.period, ["fuel"], notes, granularity=granularity, state=f.state)}
