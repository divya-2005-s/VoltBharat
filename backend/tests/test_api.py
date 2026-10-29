"""API tests against the loaded PostgreSQL database.

Expected values are recomputed from the database independently of the
service code, so a wrong aggregation in the API fails the test.
"""
import csv
import io

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db

ENDPOINTS = ["/api/v1/overview", "/api/v1/trend", "/api/v1/states", "/api/v1/states/Karnataka", "/api/v1/segments",
             "/api/v1/makers", "/api/v1/charging-gap", "/api/v1/chargers/growth", "/api/v1/policy-events",
             "/api/v1/policy", "/api/v1/insights", "/api/v1/sources", "/api/v1/meta/states"]


@pytest.mark.parametrize("url", ENDPOINTS)
def test_every_endpoint_returns_envelope(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["data_coverage"]["start"] == "2022-01"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def _bev(db, s, e, state=None):
    return int(db.execute(text("""SELECT coalesce(sum(f.registrations), 0) FROM fact_registrations_fuel f
        JOIN dim_fuel d USING (fuel_id) JOIN dim_state st USING (state_id)
        WHERE d.fuel_label IN ('Electric(BOV)', 'Pure EV') AND f.date_id BETWEEN :s AND :e
          AND (CAST(:st AS TEXT) IS NULL OR st.state_name = :st)"""), {"s": s, "e": e, "st": state}).scalar())


def _total(db, s, e, state=None):
    return int(db.execute(text("""SELECT sum(f.registrations) FROM fact_registrations_fuel f JOIN dim_state st USING (state_id)
        WHERE f.date_id BETWEEN :s AND :e AND (CAST(:st AS TEXT) IS NULL OR st.state_name = :st)"""),
        {"s": s, "e": e, "st": state}).scalar())


def test_overview_kpis_match_independent_sql(client, db):
    k = client.get("/api/v1/overview?start=2025-01&end=2025-12").json()["data"]["kpis"]
    bev, total = _bev(db, 202501, 202512), _total(db, 202501, 202512)
    assert k["bev_registrations"] == bev
    assert k["total_registrations"] == total
    assert k["ev_share_pct"] == round(100 * bev / total, 2)
    assert k["public_chargers"] == 29277
    cur, prev = _bev(db, 202501, 202512), _bev(db, 202401, 202412)
    assert k["yoy"]["growth_pct"] == round(100 * (cur - prev) / prev, 1)


def test_overview_state_filter(client, db):
    k = client.get("/api/v1/overview?state=tamil%20nadu&start=2024-04&end=2025-03").json()["data"]["kpis"]
    assert k["bev_registrations"] == _bev(db, 202404, 202503, "Tamil Nadu")
    assert k["public_chargers"] == 1781


def test_yoy_unavailable_without_24_months(client):
    y = client.get("/api/v1/overview?end=2023-06").json()["data"]["kpis"]["yoy"]
    assert y["growth_pct"] is None and y["window"]["available"] is False and y["unavailable_reason"]


def test_trend_sums_to_overview_and_has_monthly_yoy(client):
    trend = client.get("/api/v1/trend?start=2023-01&end=2023-12").json()["data"]
    assert len(trend) == 12
    total = client.get("/api/v1/overview?start=2023-01&end=2023-12").json()["data"]["kpis"]["bev_registrations"]
    assert sum(r["bev"] for r in trend) == total
    jan = trend[0]
    assert jan["bev_yoy_pct"] == round(100 * (jan["bev"] - jan["bev_prev_year"]) / jan["bev_prev_year"], 1)


def test_hr207_aggregate_is_not_in_haryana(client):
    """With the leaked national aggregate excluded, Haryana is a few percent of India, not ~50%."""
    rows = client.get("/api/v1/trend?state=Haryana&start=2023-01&end=2023-12").json()["data"]
    nat = client.get("/api/v1/trend?start=2023-01&end=2023-12").json()["data"]
    share = sum(r["total"] for r in rows) / sum(r["total"] for r in nat)
    assert share < 0.10


def test_states_sort_search_and_pagination(client):
    d = client.get("/api/v1/states?sort=bev&order=desc&page_size=5").json()["data"]
    rows = d["table"]["rows"]
    assert len(rows) == 5 and d["table"]["total_rows"] == 36
    assert [r["bev"] for r in rows] == sorted([r["bev"] for r in rows], reverse=True)
    p2 = client.get("/api/v1/states?sort=bev&order=desc&page_size=5&page=2").json()["data"]["table"]["rows"]
    assert rows[-1]["bev"] >= p2[0]["bev"]
    s = client.get("/api/v1/states?search=pradesh").json()["data"]["table"]["rows"]
    assert {r["state_name"] for r in s} >= {"Uttar Pradesh", "Madhya Pradesh", "Andhra Pradesh"}


def test_state_shares_sum_to_national(client):
    d = client.get("/api/v1/states?page_size=100").json()["data"]
    assert sum(r["bev"] for r in d["table"]["rows"]) == d["national"]["bev"]


def test_state_detail_unknown_state_404(client):
    r = client.get("/api/v1/states/Atlantis")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_state"


@pytest.mark.parametrize("qs,code", [("start=2024-13", "invalid_request"), ("start=24-01", "invalid_request"),
                                     ("start=2025-05&end=2025-01", "invalid_period"),
                                     ("start=2030-01&end=2030-02", "period_out_of_range")])
def test_period_validation(client, qs, code):
    r = client.get(f"/api/v1/overview?{qs}")
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_period_is_clamped_with_note(client):
    r = client.get("/api/v1/overview?start=2020-01&end=2022-06").json()
    assert r["meta"]["period"]["start"] == "2022-01"
    assert any("limited to available data" in n for n in r["meta"]["notes"])


def test_page_size_validation(client):
    assert client.get("/api/v1/states?page_size=0").status_code == 422
    assert client.get("/api/v1/states?sort=drop_table").status_code == 422


def test_charging_gap_ratio_and_ranking(client, db):
    d = client.get("/api/v1/charging-gap?start=2025-01&end=2025-12").json()["data"]
    ka = next(r for r in d["states"] if r["state_name"] == "Karnataka")
    assert ka["public_chargers"] == 6097
    assert ka["bev_per_charger"] == round(_bev(db, 202501, 202512, "Karnataka") / 6097, 1)
    ranked = [r for r in d["states"] if r["rank"]]
    assert [r["bev_per_charger"] for r in ranked] == sorted([r["bev_per_charger"] for r in ranked], reverse=True)
    assert all(not r["rank"] for r in d["states"] if r["small_charger_base"])
    assert d["national"]["public_chargers"] == 29277


def test_segments_declares_ev_category_split_unsupported(client):
    d = client.get("/api/v1/segments").json()["data"]
    assert d["ev_category_split_supported"] is False
    keys = {t["key"] for t in d["powertrain"]["totals"]}
    assert keys == {"bev", "strong_hybrid", "plugin_hybrid", "fcev"}
    cat = d["all_fuel_categories"]
    assert cat["available"] and "Telangana" not in cat["states_included"]


def test_segments_excludes_unvalidated_state(client):
    cat = client.get("/api/v1/segments?state=Arunachal%20Pradesh").json()["data"]["all_fuel_categories"]
    assert cat["available"] is False and cat["reason"]


def test_makers_never_claim_ev_share(client):
    d = client.get("/api/v1/makers?page_size=10").json()["data"]
    assert d["ev_market_share_supported"] is False
    assert d["all_fuel"]["top10"][0]["share_of_all_registrations_pct"] > 0
    assert all(m["name_identified_ev_maker"] for m in d["ev_named"]["top10"])
    ev = client.get("/api/v1/makers?ev_named_only=true&page_size=200").json()["data"]["table"]
    assert all(m["name_identified_ev_maker"] for m in ev["rows"])


def test_charger_growth_uses_source_fy_labels(client):
    d = client.get("/api/v1/chargers/growth").json()["data"]
    labels = [y["fy_label"] for y in d["financial_years"]]
    assert labels[0] == "FY2020-21" and labels[-1].startswith("FY2025-26 (up to 1 Mar")
    assert d["financial_years"][-1]["growth_pct"] is None  # partial year never compared
    assert d["status"]["total_installed"] == sum(s["total_installed"] for s in d["by_state"])


def test_policy_comparisons_merge_same_month_and_flag_unavailable(client):
    comps = client.get("/api/v1/policy?window=6").json()["data"]["comparisons"]
    by_month = {c["anchor_month"]: c for c in comps}
    assert "fame2" in by_month["2024-04"]["event_ids"] and "emps" in by_month["2024-04"]["event_ids"]
    assert by_month["2026-04"]["event_ids"] == ["pm_edrive_2w_end"]  # 31 Mar end -> first month without incentive
    assert by_month["2019-04"]["available"] is False


def test_insights_are_traceable(client):
    data = client.get("/api/v1/insights").json()["data"]
    assert data
    for i in data:
        assert i["sources"] and i["period"] and i["metric"]["name"]
        if i["kind"] == "recommendation":
            assert i["reasoning"]


def test_export_csv(client):
    r = client.get("/api/v1/export?dataset=states&start=2025-01&end=2025-12")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "voltbharat_states_2025-01_2025-12" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 36 and "bev_per_charger" in rows[0]
    assert client.get("/api/v1/export?dataset=nope").status_code == 422


def test_sources_and_classification(client):
    d = client.get("/api/v1/sources").json()["data"]
    keys = {s["source_key"] for s in d["sources"]}
    assert {"fuel", "maker", "category", "chargers_state", "chargers_omc"} <= keys
    bev = {l["fuel_label"] for l in d["classification"]["labels"] if l["is_bev"]}
    assert bev == {"Electric(BOV)", "Pure EV"}
    assert d["last_run"]["validation"]
