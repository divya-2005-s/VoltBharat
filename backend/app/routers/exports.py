"""CSV exports of the same figures the dashboard shows."""
import csv
import io
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.routers.deps import FiltersDep
from app.services import analytics, chargers, insights, makers, policy, segments
from app.services import registrations as reg
from app.services.common import to_label

router = APIRouter(tags=["exports"])

Dataset = Literal["trend", "states", "charging_gap", "makers", "powertrain", "categories", "chargers_growth",
                  "policy_comparison", "insights"]


def _rows(f, dataset: str) -> list[dict]:
    c, p, s = f.conn, f.period, f.state
    if dataset == "trend":
        return reg.monthly(c, p.start, p.end, s)
    if dataset == "states":
        return analytics.state_table(c, p)
    if dataset == "charging_gap":
        return analytics.charging_gap(c, p)["states"]
    if dataset == "makers":
        return makers.maker_totals(c, p.start, p.end, s)
    if dataset == "powertrain":
        return segments.segments(c, p.start, p.end, s)["powertrain"]["series"]
    if dataset == "categories":
        return segments.segments(c, p.start, p.end, s)["all_fuel_categories"]["series"]
    if dataset == "chargers_growth":
        return chargers.growth_data(c, s)["financial_years"]
    if dataset == "policy_comparison":
        return [{k: (v if not isinstance(v, dict) else f"{v['start']}..{v['end']}") for k, v in r.items()}
                for r in policy.comparisons(c, 6, s)]
    rows = insights.build(c, p)
    return [{"id": r["id"], "kind": r["kind"], "title": r["title"], "statement": r["statement"],
             "metric": r["metric"]["name"], "value": r["metric"]["value"], "unit": r["metric"]["unit"],
             "sources": ";".join(r["sources"])} for r in rows]


@router.get("/export", summary="Download a dataset as CSV", response_class=StreamingResponse,
            responses={200: {"content": {"text/csv": {}}}})
def export(f: FiltersDep, dataset: Dataset):
    rows = _rows(f, dataset)
    buf = io.StringIO()
    if rows:
        fields = list(rows[0].keys())
        for r in rows[1:]:
            fields += [k for k in r if k not in fields]
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    suffix = f"{to_label(f.period.start)}_{to_label(f.period.end)}" + (f"_{f.state.replace(' ', '-')}" if f.state else "")
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="voltbharat_{dataset}_{suffix}.csv"'})
