"""Generate reports/analysis_report.md and reports/insights_report.pdf from the live API code paths.

Usage: python -m etl.generate_reports
Requires the loaded database (DATABASE_URL). Every number comes from the same
service functions the dashboard uses, so the report and the UI cannot disagree.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from etl.config import PROJECT_ROOT, REPORTS_DIR  # noqa: E402
from etl.logging_utils import setup_logging  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.common import to_label  # noqa: E402
from app.services.insights import fmt_in  # noqa: E402
from app.services.policy import _effective_month  # noqa: E402

log = logging.getLogger("etl.reports")
FIG_DIR = REPORTS_DIR / "figures"
GREEN, BLUE, ORANGE, VIOLET, GREY = "#059669", "#2a78d6", "#eb6834", "#6250d6", "#9ca3af"
CRITICAL, WARNING = "#d03b3b", "#fab219"


def lakh(v, _=None):
    return f"{v / 1e5:.1f} L" if v >= 1e5 else f"{v:,.0f}"


def style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color="#0b1220")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(colors="#4b5563", labelsize=8)
    ax.grid(axis="y", color="#eef0f3")
    ax.set_axisbelow(True)


def figures(d: dict) -> dict[str, str]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    trend = d["overview"]["trend"]
    months = [r["month"] for r in trend]

    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=150)
    ax.plot(months, [r["bev"] for r in trend], color=GREEN, lw=2)
    ax.fill_between(months, [r["bev"] for r in trend], color=GREEN, alpha=0.08)
    for e in d["markers"]:
        if e["month"] in months:
            ax.axvline(e["month"], color=GREY, ls="--", lw=0.8)
            ax.text(e["month"], ax.get_ylim()[1] * 0.98, e["label"], rotation=90, fontsize=6, color="#4b5563", va="top", ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(lakh))
    ax.set_xticks(months[::6])
    ax.tick_params(axis="x", rotation=0)
    style(ax, "Monthly BEV registrations, India (dashed: policy milestones)")
    fig.tight_layout()
    out["trend"] = str(FIG_DIR / "monthly_bev.png")
    fig.savefig(out["trend"])
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 2.8), dpi=150)
    ax.plot(months, [r["ev_share_pct"] for r in trend], color=GREEN, lw=2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xticks(months[::6])
    style(ax, "BEV share of new vehicle registrations, India")
    fig.tight_layout()
    out["share"] = str(FIG_DIR / "ev_share.png")
    fig.savefig(out["share"])
    plt.close(fig)

    gap = [s for s in d["gap"]["states"] if s["rank"]][:12][::-1]
    colors = [CRITICAL if s["pressure_tier"] == "high" else WARNING if s["pressure_tier"] == "elevated" else GREY for s in gap]
    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=150)
    ax.barh([s["state_name"] for s in gap], [s["bev_per_charger"] for s in gap], color=colors, height=0.6)
    for i, s in enumerate(gap):
        ax.text(s["bev_per_charger"], i, f"  {s['bev_per_charger']:.0f}  ({s['pressure_tier']})", va="center", fontsize=7, color="#4b5563")
    ax.axvline(d["gap"]["national"]["bev_per_charger"], color="#0b1220", lw=0.8, ls=":")
    style(ax, "BEV registrations per public charging station (top 12; dotted = national)")
    ax.grid(axis="x", color="#eef0f3")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    out["gap"] = str(FIG_DIR / "charging_gap.png")
    fig.savefig(out["gap"])
    plt.close(fig)

    fy = d["omc"]["financial_years"]
    fig, ax = plt.subplots(figsize=(9, 2.8), dpi=150)
    ax.bar([y["fy_label"].replace(" (up to 1 Mar 2026)", "*") for y in fy], [y["installed"] for y in fy],
           color=[GREY if y["is_partial_year"] else BLUE for y in fy], width=0.55)
    style(ax, "OMC charging stations installed per financial year (* partial year)")
    fig.tight_layout()
    out["omc"] = str(FIG_DIR / "omc_growth.png")
    fig.savefig(out["omc"])
    plt.close(fig)
    return out


def collect() -> dict:
    c = TestClient(app)

    def get(path):
        r = c.get(path)
        r.raise_for_status()
        return r.json()

    ov = get("/api/v1/overview")
    events = get("/api/v1/policy-events")["data"]
    markers = []
    for e in events:
        # same rule as the API and dashboard: first full month in which the change applies
        markers.append({"month": to_label(_effective_month(date.fromisoformat(e["start_date"]))), "label": e["short_name"]})
    return {
        "overview": ov["data"], "meta": ov["meta"],
        "trend_fy": get("/api/v1/trend?granularity=fy")["data"],
        "states": get("/api/v1/states?page_size=100")["data"],
        "gap": get("/api/v1/charging-gap")["data"],
        "gap_12m": get(f"/api/v1/charging-gap?start={ov['data']['kpis']['yoy']['window']['current']['start']}")["data"],
        "omc": get("/api/v1/chargers/growth")["data"],
        "makers": get("/api/v1/makers?page_size=10")["data"],
        "segments": get("/api/v1/segments")["data"],
        "policy": get("/api/v1/policy?window=6")["data"],
        "insights": get("/api/v1/insights")["data"],
        "sources": get("/api/v1/sources")["data"],
        "markers": markers,
    }


def rel(path: str) -> str:
    """Figure path relative to reports/, with forward slashes for Markdown."""
    from pathlib import Path
    return Path(path).relative_to(REPORTS_DIR).as_posix()


def pct(v, d=2):
    return "n/a" if v is None else f"{v:.{d}f}%"


def markdown(d: dict, figs: dict) -> str:
    k = d["overview"]["kpis"]
    y = k["yoy"]
    m = d["meta"]
    rows = d["states"]["table"]["rows"]
    L = []
    a = L.append
    a("# VoltBharat — Analysis Report\n")
    a(f"_Generated {datetime.now():%d %b %Y %H:%M} by `etl/generate_reports.py` from the VoltBharat database "
      f"(last ETL run {m['last_processed_at'][:16].replace('T', ' ')} UTC). Registration coverage "
      f"{m['data_coverage']['start']} to {m['data_coverage']['end']}._\n")
    a("All figures are computed by the same service code the dashboard uses. **EV = battery-electric vehicles (BEV)**: "
      "VAHAN fuel labels `Electric(BOV)` and `Pure EV`. See `reports/data_audit.md` for data quality and the exclusions "
      "applied (notably office HR207, a national aggregate mis-recorded as an RTO).\n")

    a("## 1. How are EV registrations growing?\n")
    a(f"- **{fmt_in(k['bev_registrations'])} BEVs** were registered from {m['period']['start']} to {m['period']['end']} "
      f"({k['months']} months), **{pct(k['ev_share_pct'])}** of {fmt_in(k['total_registrations'])} new registrations.")
    a(f"- Trailing 12 months ({y['window']['current']['start']}–{y['window']['current']['end']}): {fmt_in(y['bev_current'])} BEVs, "
      f"**{y['growth_pct']:+}%** vs {fmt_in(y['bev_previous'])} in the previous 12 months; share {pct(y['ev_share_previous_pct'])} → "
      f"{pct(y['ev_share_current_pct'])}.")
    a(f"\n![Monthly BEV registrations]({rel(figs['trend'])})\n")
    a(f"![EV share]({rel(figs['share'])})\n")
    a("| Financial year | Months in data | BEV | All registrations | EV share | BEV growth vs previous FY |\n|---|---|---|---|---|---|")
    for r in d["trend_fy"]:
        a(f"| {r['period']}{' (partial)' if r['is_partial'] else ''} | {r['months']} | {fmt_in(r['bev'])} | {fmt_in(r['total'])} | "
          f"{pct(r['ev_share_pct'])} | {'n/a' if r['bev_growth_pct'] is None else f'{r['bev_growth_pct']:+}%'} |")

    a("\n## 2. Which states lead?\n")
    a("| Rank | State | BEV registrations | EV share | Share rank | YoY growth (12 mo) |\n|---|---|---|---|---|---|")
    for r in sorted([r for r in rows if r["rank_bev"]], key=lambda r: r["rank_bev"])[:10]:
        a(f"| {r['rank_bev']} | {r['state_name']} | {fmt_in(r['bev'])} | {pct(r['ev_share_pct'])} | {r['rank_share'] or '—'} | "
          f"{'n/a' if r['yoy_growth_pct'] is None else f'{r['yoy_growth_pct']:+}%'} |")
    a("\nHighest EV share (states with ≥10,000 registrations in the period):\n")
    a("| Share rank | State | EV share | BEVs |\n|---|---|---|---|")
    for r in sorted([r for r in rows if r["rank_share"]], key=lambda r: r["rank_share"])[:10]:
        a(f"| {r['rank_share']} | {r['state_name']} | {pct(r['ev_share_pct'])} | {fmt_in(r['bev'])} |")

    seg = d["segments"]
    a("\n## 3. Which vehicle categories contribute most?\n")
    a(f"**Not answerable with these sources.** {seg['ev_category_split_reason']}\n")
    a("What can be reported is the electrified powertrain mix (fuel-type source):\n")
    a("| Powertrain | Registrations | Share of electrified |\n|---|---|---|")
    for t in seg["powertrain"]["totals"]:
        a(f"| {t['label']} | {fmt_in(t['registrations'])} | {pct(t['share_pct'])} |")
    cat = seg["all_fuel_categories"]
    if cat["available"]:
        a(f"\nAll-fuel context ({cat['period']['start']}–{cat['period']['end']}, {len(cat['states_included'])} validated states; NOT EV-specific):\n")
        a("| Category group | Registrations (all fuels) | Share |\n|---|---|---|")
        for t in cat["totals"]:
            a(f"| {t['group']} | {fmt_in(t['registrations'])} | {pct(t['share_pct'])} |")

    mk = d["makers"]
    a("\n## 4. Which manufacturers lead the EV market?\n")
    a(f"**EV market share by manufacturer cannot be computed.** {mk['ev_market_share_reason']}\n")
    a(f"Name-identified EV makers ({mk['ev_named']['definition']}) registered {fmt_in(mk['ev_named']['total_registrations'])} vehicles, "
      f"equal to {pct(mk['ev_named']['coverage_of_bev_pct'], 1)} of BEV registrations in the fuel source — a lower bound only.\n")
    a("| Rank | Name-identified EV maker | Registrations |\n|---|---|---|")
    for x in mk["ev_named"]["top10"]:
        a(f"| {x['rank_within_ev_named']} | {x['maker']} | {fmt_in(x['registrations'])} |")

    g = d["gap"]
    a("\n## 5. Which states have the highest EV registrations relative to public chargers?\n")
    a(f"Indicator: BEVs registered {m['period']['start']}–{m['period']['end']} ÷ public stations in the 2025 snapshot. "
      f"National: {g['national']['bev_per_charger']} BEVs per station. Approximate infrastructure pressure only; "
      "not utilisation, power or coverage. States with <25 stations are not ranked.\n")
    a(f"![Charging gap]({rel(figs['gap'])})\n")
    a("| Rank | State | BEVs per station | × national | BEVs | Stations | Tier |\n|---|---|---|---|---|---|---|")
    for s in [s for s in g["states"] if s["rank"]][:12]:
        a(f"| {s['rank']} | {s['state_name']} | {s['bev_per_charger']} | {s['relative_to_national']} | {fmt_in(s['bev'])} | "
          f"{fmt_in(s['public_chargers'])} | {s['pressure_tier']} |")
    g12 = d["gap_12m"]
    top12 = [s for s in g12["states"] if s["rank"]][:5]
    a(f"\nSensitivity: using only the latest 12 months of registrations, the national ratio is {g12['national']['bev_per_charger']} and the top five are "
      + ", ".join(f"{s['state_name']} ({s['bev_per_charger']})" for s in top12) + ".")

    o = d["omc"]
    a("\n## 6. How has public charging infrastructure grown?\n")
    a(f"{o['measure']}\n")
    a(f"![OMC growth]({rel(figs['omc'])})\n")
    a("| Financial year | Installed | Cumulative | Growth vs previous FY |\n|---|---|---|---|")
    for yr in o["financial_years"]:
        a(f"| {yr['fy_label']} | {fmt_in(yr['installed'])} | {fmt_in(yr['cumulative_installed'])} | "
          f"{'n/a' if yr['growth_pct'] is None else f'{yr['growth_pct']:+}%'} |")
    a(f"\nTotal installed {fmt_in(o['status']['total_installed'])}; reported operational {fmt_in(o['status']['total_operational'])}; "
      f"decommissioned {fmt_in(o['status']['decommissioned'])}. The 2025 state snapshot of all public stations is "
      f"{fmt_in(g['national']['public_chargers'])}; the two measures are never added.")

    p = d["policy"]
    a("\n## 7. Registration trends around policy milestones\n")
    a("Six-month windows before and after each milestone (associations, not causal estimates):\n")
    a("| Milestone | Month | Avg monthly BEV before | after | Change | EV share before → after | After vs same months a year earlier |\n|---|---|---|---|---|---|---|")
    for c in p["comparisons"]:
        if c["available"]:
            a(f"| {c['label']} | {c['anchor_month']} | {fmt_in(c['before_avg_monthly_bev'])} | {fmt_in(c['after_avg_monthly_bev'])} | "
              f"{c['change_pct']:+}% | {pct(c['before_ev_share_pct'])} → {pct(c['after_ev_share_pct'])} | "
              f"{'n/a' if c['after_vs_same_months_prior_year_pct'] is None else f'{c['after_vs_same_months_prior_year_pct']:+}%'} |")
        else:
            a(f"| {c['label']} | {c['anchor_month']} | — | — | — | — | {c['unavailable_reason']} |")
    a("\nCaveats:\n")
    for cv in p["caveats"]:
        a(f"- {cv}")

    a("\n## 8. Insights and recommendations\n")
    for kind in ("observation", "recommendation"):
        a(f"### {kind.capitalize()}s\n")
        for i in [i for i in d["insights"] if i["kind"] == kind]:
            a(f"- **{i['title']}.** {i['statement']}" + (f" _Reasoning: {i['reasoning']}_" if i["reasoning"] else "")
              + f" (source: {', '.join(i['sources'])})")
        a("")

    a("## Limitations\n")
    for s in d["sources"]["sources"]:
        if s["source_key"] != "fuel_dup":
            a(f"- **{s['title']}**: {s['limitations']}")
    a("- State boundaries in the map are community-curated (not an official Survey of India product).")
    return "\n".join(L) + "\n"


def pdf(d: dict, figs: dict, path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=colors.HexColor("#0b1426"), fontSize=18)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#047857"), fontSize=12, spaceBefore=10)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12.5)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, textColor=colors.HexColor("#6b7280"))
    k = d["overview"]["kpis"]
    y = k["yoy"]
    m = d["meta"]

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story = [Paragraph("VoltBharat — India EV Insights Report", h1),
             Paragraph(f"Registrations {m['data_coverage']['start']} to {m['data_coverage']['end']} (VAHAN fuel-type source); "
                       f"public charging stations: 2025 state snapshot. Generated {datetime.now():%d %b %Y}.", small),
             Spacer(1, 8)]
    kp = [["BEV registrations", "EV share", "BEV YoY (12 mo)", "Public stations"],
          [fmt_in(k["bev_registrations"]), pct(k["ev_share_pct"]), f"{y['growth_pct']:+}%", fmt_in(k["public_chargers"])],
          [f"{m['period']['start']} to {m['period']['end']}", "same period", f"to {y['window']['current']['end']}", "2025 snapshot"]]
    t = Table(kp, colWidths=[4.2 * cm] * 4)
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("FONTSIZE", (0, 1), (-1, 1), 14),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#4b5563")), ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#6b7280")),
                           ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eef0f3")),
                           ("BOTTOMPADDING", (0, 1), (-1, 1), 6)]))
    story += [t, Spacer(1, 8), Image(figs["trend"], width=17 * cm, height=6.4 * cm), Image(figs["share"], width=17 * cm, height=5.3 * cm)]
    story += [Paragraph("Observations", h2)]
    for i in [i for i in d["insights"] if i["kind"] == "observation"]:
        story.append(Paragraph(f"<b>{esc(i['title'])}.</b> {esc(i['statement'])} <font color='#6b7280' size='7'>[{', '.join(i['sources'])}]</font>", body))
        story.append(Spacer(1, 3))
    story += [PageBreak(), Paragraph("Charging infrastructure pressure", h2),
              Paragraph(f"BEVs registered {m['period']['start']}–{m['period']['end']} per public station (2025 snapshot). "
                        "A high ratio indicates potential pressure on public charging, not utilisation or coverage.", body),
              Image(figs["gap"], width=17 * cm, height=7.2 * cm), Image(figs["omc"], width=17 * cm, height=5.3 * cm),
              Paragraph("Recommendations", h2)]
    for i in [i for i in d["insights"] if i["kind"] == "recommendation"]:
        story.append(Paragraph(f"<b>{esc(i['title'])}.</b> {esc(i['statement'])}", body))
        if i["reasoning"]:
            story.append(Paragraph(f"<i>Reasoning:</i> {esc(i['reasoning'])}", small))
        story.append(Spacer(1, 4))
    story += [Paragraph("Data notes", h2)]
    for r in d["sources"]["quality_rules"]:
        story.append(Paragraph(f"• {esc(r)}", small))
    story.append(Paragraph("• Policy associations are not causal. EV segment and EV-by-maker splits are not available from these sources.", small))
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                      title="VoltBharat Insights Report").build(story)


def main() -> None:
    setup_logging("reports")
    d = collect()
    figs = figures(d)
    (REPORTS_DIR / "analysis_report.md").write_text(markdown(d, figs), encoding="utf-8")
    pdf(d, figs, REPORTS_DIR / "insights_report.pdf")
    log.info("Wrote analysis_report.md, insights_report.pdf and %d figures", len(figs))


if __name__ == "__main__":
    main()
