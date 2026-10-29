"""Programmatic insights. Every statement is built from computed values; nothing is hard-coded.

Each insight carries the metric, period and source used, so it can be traced.
Observations describe the data; recommendations are labelled separately and
cite the observations they rest on.
"""
from __future__ import annotations

from sqlalchemy.engine import Connection

from app.services import analytics, chargers, makers as makers_svc
from app.services import registrations as reg
from app.services.common import Period, pct, to_label, trailing_yoy_window


def fmt_in(n) -> str:
    """Indian grouping, e.g. 1245300 -> 12,45,300."""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts + [tail])


def _ins(id_, kind, category, title, statement, metric, value, unit, period, sources, reasoning=None, based_on=None):
    return {"id": id_, "kind": kind, "category": category, "title": title, "statement": statement,
            "metric": {"name": metric, "value": value, "unit": unit}, "period": period, "sources": sources,
            "reasoning": reasoning, "based_on": based_on or []}


def build(conn: Connection, period: Period) -> list[dict]:
    out: list[dict] = []
    pdict = {"start": to_label(period.start), "end": to_label(period.end)}
    w = trailing_yoy_window(conn, period.end)
    wdict = w.as_dict()
    table = analytics.state_table(conn, period)

    # 1. National trailing-12-month growth and share change
    if w.available:
        yoy = analytics.yoy_block(conn, period.end)
        g = yoy["growth_pct"]
        out.append(_ins("national_growth", "observation", "adoption", "National BEV registrations, trailing 12 months",
            f"{fmt_in(yoy['bev_current'])} battery-electric vehicles were registered in {wdict['current']['start']}–{wdict['current']['end']}, "
            f"{'up' if g >= 0 else 'down'} {abs(g)}% from {fmt_in(yoy['bev_previous'])} in the preceding 12 months.",
            "BEV YoY growth (trailing 12 months)", g, "%", wdict, ["fuel"]))
        if yoy["share_change_pp"] is not None:
            out.append(_ins("national_share", "observation", "adoption", "EV share of new registrations",
                f"BEVs were {yoy['ev_share_current_pct']}% of all new vehicle registrations in the latest 12 months, "
                f"compared with {yoy['ev_share_previous_pct']}% a year earlier ({yoy['share_change_pp']:+} percentage points).",
                "EV share change", yoy["share_change_pp"], "pp", wdict, ["fuel"]))

    # 2. Fastest-growing states (min base applies)
    growers = sorted([r for r in table if r["rank_growth"]], key=lambda r: r["rank_growth"])[:3]
    if growers:
        out.append(_ins("fastest_growing_states", "observation", "states", "Fastest-growing states (BEV, trailing 12 months)",
            "Highest year-over-year BEV growth among states with at least "
            f"{fmt_in(analytics.MIN_PREV_BEV_FOR_GROWTH_RANK)} BEV registrations in the comparison year: "
            + "; ".join(f"{r['state_name']} {r['yoy_growth_pct']:+}% ({fmt_in(r['bev_prev_12m'])} → {fmt_in(r['bev_last_12m'])})" for r in growers) + ".",
            "BEV YoY growth", growers[0]["yoy_growth_pct"], "%", wdict, ["fuel"]))

    # 3. Highest adoption share
    nat = reg.totals(conn, period.start, period.end)
    sharers = sorted([r for r in table if r["rank_share"]], key=lambda r: r["rank_share"])[:3]
    if sharers and nat["ev_share_pct"]:
        top = sharers[0]
        out.append(_ins("high_share_states", "observation", "states", "Highest EV adoption share",
            f"In {pdict['start']}–{pdict['end']}, the highest BEV shares of new registrations were "
            + "; ".join(f"{r['state_name']} {r['ev_share_pct']}%" for r in sharers)
            + f", against a national {nat['ev_share_pct']}%. {top['state_name']}'s share is "
            f"{round(top['ev_share_pct'] / nat['ev_share_pct'], 2)}× the national level.",
            "EV share", top["ev_share_pct"], "%", pdict, ["fuel"]))

    # 4. Concentration of BEV registrations
    by_bev = sorted([r for r in table if r["rank_bev"]], key=lambda r: r["rank_bev"])
    if by_bev and nat["bev"]:
        top5 = sum(r["bev"] for r in by_bev[:5])
        out.append(_ins("state_concentration", "observation", "states", "Geographic concentration",
            f"Five states — {', '.join(r['state_name'] for r in by_bev[:5])} — account for {pct(top5, nat['bev'], 1)}% "
            f"of the {fmt_in(nat['bev'])} BEV registrations in {pdict['start']}–{pdict['end']}.",
            "Top-5 state share of BEV registrations", pct(top5, nat["bev"], 1), "%", pdict, ["fuel"]))

    # 5. Charging pressure
    gap = analytics.charging_gap(conn, period)
    ranked = [r for r in gap["states"] if r["rank"]]
    nr = gap["national"]["bev_per_charger"]
    if ranked and nr:
        hi = ranked[:3]
        out.append(_ins("charging_pressure_high", "observation", "charging", "Highest charging-infrastructure pressure",
            f"Using BEVs registered in {pdict['start']}–{pdict['end']} and the 2025 public-station snapshot, the highest "
            "BEVs-per-station ratios are " + "; ".join(f"{r['state_name']} {r['bev_per_charger']} ({r['relative_to_national']}× national)" for r in hi)
            + f". The national ratio is {nr}. This indicates potential pressure, not utilisation or coverage.",
            "BEV registrations per public charging station", hi[0]["bev_per_charger"], "BEVs per station",
            {**pdict, "charger_snapshot": "2025"}, ["fuel", "chargers_state"]))
        lo = ranked[-3:][::-1]
        out.append(_ins("charging_pressure_low", "observation", "charging", "Lowest charging-infrastructure pressure",
            "The lowest BEVs-per-station ratios (states with at least "
            f"{analytics.SMALL_CHARGER_BASE} stations) are " + "; ".join(f"{r['state_name']} {r['bev_per_charger']}" for r in lo) + ".",
            "BEV registrations per public charging station", lo[0]["bev_per_charger"], "BEVs per station",
            {**pdict, "charger_snapshot": "2025"}, ["fuel", "chargers_state"]))

    # 6. Monthly trend: peak and latest
    series = reg.monthly(conn, period.start, period.end)
    if series:
        peak = max(series, key=lambda r: r["bev"])
        last = series[-1]
        yoy_txt = f" ({last['bev_yoy_pct']:+}% vs the same month a year earlier)" if last["bev_yoy_pct"] is not None else ""
        statement = (f"The latest month, {last['month']}, was also the highest in the period: {fmt_in(last['bev'])} BEV registrations{yoy_txt}."
                     if peak["month"] == last["month"] else
                     f"The highest monthly BEV registrations in the period were {fmt_in(peak['bev'])} in {peak['month']}. "
                     f"The latest month, {last['month']}, recorded {fmt_in(last['bev'])}{yoy_txt}.")
        out.append(_ins("monthly_peak", "observation", "trend", "Monthly peak and latest month", statement,
            "Monthly BEV registrations (peak)", peak["bev"], "registrations", pdict, ["fuel"]))
        shares = [r for r in series if r["ev_share_pct"] is not None]
        if len(shares) >= 2:
            first, final = shares[0], shares[-1]
            out.append(_ins("share_trajectory", "observation", "trend", "EV share trajectory",
                f"Monthly BEV share of new registrations moved from {first['ev_share_pct']}% in {first['month']} "
                f"to {final['ev_share_pct']}% in {final['month']}.",
                "EV share (latest month)", final["ev_share_pct"], "%", pdict, ["fuel"]))

    # 7. Hybrids vs BEV
    t = reg.totals(conn, period.start, period.end)
    if t["bev"]:
        out.append(_ins("powertrain_mix", "observation", "segments", "Electrified powertrain mix",
            f"Strong hybrids ({fmt_in(t['strong_hybrid'])}), plug-in hybrids ({fmt_in(t['plugin_hybrid'])}) and fuel-cell "
            f"vehicles ({fmt_in(t['fcev'])}) together equal {pct(t['strong_hybrid'] + t['plugin_hybrid'] + t['fcev'], t['bev'], 1)}% "
            "of BEV volume; they are reported separately and are not counted as EVs in headline metrics.",
            "Non-BEV electrified registrations as % of BEV", pct(t["strong_hybrid"] + t["plugin_hybrid"] + t["fcev"], t["bev"], 1),
            "%", pdict, ["fuel"]))

    # 8. OMC charger growth
    g = chargers.growth_data(conn, None)
    complete = [y for y in g["financial_years"] if not y["is_partial_year"]]
    if len(complete) >= 2:
        a, b = complete[-2], complete[-1]
        out.append(_ins("omc_growth", "observation", "charging", "OMC charger installations",
            f"Oil marketing companies installed {fmt_in(b['installed'])} stations in {b['fy_label']} vs {fmt_in(a['installed'])} "
            f"in {a['fy_label']} ({b['growth_pct']:+}%). Cumulative OMC installations reached {fmt_in(g['status']['total_installed'])}, "
            f"of which {fmt_in(g['status']['total_operational'])} are reported operational.",
            "OMC installations growth (latest complete FY)", b["growth_pct"], "%",
            {"start": complete[0]["fy_label"], "end": b["fy_label"]}, ["chargers_omc"]))

    # 9. Maker concentration (all fuels — labelled)
    m = makers_svc.makers(conn, period.start, period.end, None, None, False, 1, 10)
    if m["all_fuel"]["total_registrations"]:
        out.append(_ins("maker_concentration_all_fuel", "observation", "manufacturers", "Manufacturer concentration (all fuels)",
            f"The five largest manufacturers by ALL-FUEL registrations ({', '.join(x['maker'] for x in m['all_fuel']['top10'][:5])}) "
            f"hold {m['all_fuel']['top5_share_pct']}% of all registrations. EV market share by maker cannot be computed from this source.",
            "Top-5 maker share (all fuels)", m["all_fuel"]["top5_share_pct"], "%", pdict, ["maker"]))

    # ---- recommendations derived from the observations above -----------
    pressure_growth = [r for r in ranked if r["pressure_tier"] in ("high", "elevated")]
    growth_by_state = {r["state_name"]: r for r in table}
    both = [r for r in pressure_growth if (growth_by_state[r["state_name"]]["yoy_growth_pct"] or 0) > 0
            and growth_by_state[r["state_name"]]["growth_rankable"]]
    if both:
        names = [r["state_name"] for r in both[:5]]
        out.append(_ins("rec_prioritise_charging", "recommendation", "charging", "Prioritise charging-capacity reviews",
            f"Review public charging capacity first in {', '.join(names)}: each has a BEVs-per-station ratio at least "
            f"{analytics.PRESSURE_ELEVATED}× the national level and growing BEV registrations.",
            "States with elevated pressure and positive growth", len(both), "states", wdict, ["fuel", "chargers_state"],
            reasoning=("A high ratio combined with rising registrations suggests demand on public stations may be growing "
                       "faster than supply. Confirm with utilisation, charger-power and location data before investing; "
                       "home and workplace charging are not captured here."),
            based_on=["charging_pressure_high", "fastest_growing_states"]))
    if sharers:
        out.append(_ins("rec_learn_from_leaders", "recommendation", "policy", "Study high-adoption states",
            f"Compare state policies and market structure in {', '.join(r['state_name'] for r in sharers)} with lower-share "
            "states to identify transferable measures.",
            "Highest EV share", sharers[0]["ev_share_pct"], "%", pdict, ["fuel"],
            reasoning="These states show the highest BEV shares; the data cannot attribute this to any single cause.",
            based_on=["high_share_states"]))
    out.append(_ins("rec_data_gaps", "recommendation", "data", "Close the data gaps",
        "Obtain registrations by fuel AND vehicle category (or by fuel AND maker) and a dated, point-level charger dataset "
        "with power ratings. These would enable EV segment analysis, EV market share by maker, and true accessibility metrics.",
        "Unsupported analyses", 3, "analyses", pdict, ["fuel", "maker", "category", "chargers_state"],
        reasoning="Current sources cannot separate EVs by category or manufacturer, and the charger data is a single state-level snapshot.",
        based_on=[]))
    return out
