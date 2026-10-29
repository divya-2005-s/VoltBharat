"""Pure unit tests for metric helpers (no database)."""
import pytest

from app.routers.trends import aggregate
from app.services.common import growth, months_between, pct, shift, to_id, to_label
from app.services.insights import fmt_in


def test_month_ids_round_trip():
    assert to_id("2024-03") == 202403
    assert to_label(202403) == "2024-03"


@pytest.mark.parametrize("start,delta,expected", [(202401, -1, 202312), (202412, 1, 202501), (202609, -23, 202410),
                                                   (202403, 12, 202503), (202401, 0, 202401)])
def test_shift(start, delta, expected):
    assert shift(start, delta) == expected


def test_months_between_inclusive():
    assert months_between(202201, 202609) == 57
    assert months_between(202401, 202401) == 1


def test_pct_and_growth_handle_zero_and_missing():
    assert pct(1, 4) == 25.0
    assert pct(1, 0) is None and pct(None, 5) is None
    assert growth(150, 100) == 50.0
    assert growth(5, 0) is None and growth(None, 5) is None and growth(5, None) is None


def test_indian_number_format():
    assert fmt_in(1245300) == "12,45,300"
    assert fmt_in(999) == "999"
    assert fmt_in(100000) == "1,00,000"
    assert fmt_in(95431234) == "9,54,31,234"


def _m(month, bev, total=100):
    return {"month": month, "bev": bev, "total": total, "strong_hybrid": 0, "plugin_hybrid": 0, "fcev": 0}


def test_fy_aggregation_flags_partial_years_and_skips_their_growth():
    series = [_m("2023-03", 10)] + [_m(f"{2023 + (m < 4)}-{m:02d}", 1) for m in list(range(4, 13)) + list(range(1, 4))] \
             + [_m("2024-04", 5)]
    out = {r["period"]: r for r in aggregate(series, "fy")}
    assert out["FY2022-23"]["is_partial"] and out["FY2022-23"]["months"] == 1
    assert not out["FY2023-24"]["is_partial"] and out["FY2023-24"]["bev"] == 12
    assert out["FY2023-24"]["bev_growth_pct"] is None  # previous FY is partial
    assert out["FY2024-25"]["bev_growth_pct"] is None  # current FY is partial
