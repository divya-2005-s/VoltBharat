"""Policy milestones and before/after comparisons. Associations, not causal estimates."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.services import registrations as reg
from app.services.common import fuel_coverage, growth, shift, to_label

CAVEATS = [
    "A before/after difference is an association, not proof that a policy caused it.",
    "Other influences overlap these windows: new model launches, battery and fuel prices, state EV policies and road-tax "
    "waivers, festive-season demand (Oct-Nov), financial-year-end buying (March), supply constraints and pre-buying "
    "ahead of announced subsidy cuts.",
    "Several schemes overlap or follow each other directly (FAME-II ended 31 Mar 2024 and EMPS began 1 Apr 2024), so "
    "their effects cannot be separated with this data.",
    "Registrations are counted when vehicles are registered, which can lag sales.",
]


def _effective_month(d: date) -> int:
    """First full calendar month in which the change applies."""
    m = d.year * 100 + d.month
    return m if d.day == 1 else shift(m, 1)


@cached
def events(conn: Connection) -> list[dict]:
    rows = conn.execute(text("""SELECT event_id, name, short_name, start_date, end_date, event_type, description, source
        FROM policy_events ORDER BY start_date""")).mappings().all()
    return [{**dict(r), "start_date": r["start_date"].isoformat(),
             "end_date": r["end_date"].isoformat() if r["end_date"] else None} for r in rows]


def _anchors(conn) -> list[dict]:
    """Comparison anchors. Milestones falling in the same month are merged: their effects cannot be separated."""
    raw = []
    for e in events(conn):
        start = date.fromisoformat(e["start_date"])
        raw.append((e["event_id"], f"{e['short_name']} begins" if e["event_type"] == "scheme" else e["short_name"],
                    _effective_month(start), "start"))
        if e["end_date"] and e["event_type"] == "scheme":
            end = date.fromisoformat(e["end_date"])
            raw.append((e["event_id"], f"{e['short_name']} ends", _effective_month(end + timedelta(days=1)), "end"))
    merged: dict[int, dict] = {}
    for event_id, label, month, kind in sorted(raw, key=lambda r: r[2]):
        a = merged.setdefault(month, {"anchor_id": f"{event_id}:{kind}", "event_id": event_id, "event_ids": [],
                                      "label": label, "anchor_month": month})
        if a["event_ids"]:
            a["label"] += f" / {label}"
        a["event_ids"].append(event_id)
    return list(merged.values())


@cached
def comparisons(conn: Connection, window: int, state: str | None) -> list[dict]:
    cov = fuel_coverage(conn)
    out = []
    for a in _anchors(conn):
        m = a["anchor_month"]
        before = (shift(m, -window), shift(m, -1))
        after = (m, shift(m, window - 1))
        prior_year_after = (shift(after[0], -12), shift(after[1], -12))
        item = {**a, "anchor_month": to_label(m), "window_months": window,
                "before": {"start": to_label(before[0]), "end": to_label(before[1])},
                "after": {"start": to_label(after[0]), "end": to_label(after[1])}, "available": False}
        if before[0] < cov.first or after[1] > cov.last:
            item["unavailable_reason"] = (f"Needs data from {to_label(before[0])} to {to_label(after[1])}; "
                                          f"available {to_label(cov.first)} to {to_label(cov.last)}.")
            out.append(item)
            continue
        b = reg.totals(conn, *before, state)
        f = reg.totals(conn, *after, state)
        item.update(available=True,
                    before_avg_monthly_bev=round(b["bev"] / window), after_avg_monthly_bev=round(f["bev"] / window),
                    change_pct=growth(f["bev"], b["bev"]),
                    before_ev_share_pct=b["ev_share_pct"], after_ev_share_pct=f["ev_share_pct"],
                    share_change_pp=round(f["ev_share_pct"] - b["ev_share_pct"], 2)
                    if b["ev_share_pct"] is not None and f["ev_share_pct"] is not None else None)
        if prior_year_after[0] >= cov.first:
            py = reg.totals(conn, *prior_year_after, state)
            item["after_vs_same_months_prior_year_pct"] = growth(f["bev"], py["bev"])
            item["prior_year_window"] = {"start": to_label(prior_year_after[0]), "end": to_label(prior_year_after[1])}
        else:
            item["after_vs_same_months_prior_year_pct"] = None
        out.append(item)
    return out
