"""ETL tests on small synthetic CSVs (the real raw files are never touched)."""
import shutil

import duckdb
import pytest

from etl import clean_chargers, clean_registrations, extract_vahan, validate_data
from etl.clean_chargers import fy_label
from etl.config import discover_sources

RTO_HEADER = '"id","date","state_name","state_code","rto","rto_code","registration_type","registrations"\n'
CAT_HEADER = '"id","date","state_name","state_code","office_name","office_code","vehicle_type","category","registrations"\n'


def write(path, header, rows):
    path.write_text(header + "".join(",".join(f'"{v}"' if isinstance(v, str) else str(v) for v in r) + "\n" for r in rows),
                    encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def isolated_outputs(tmp_path, monkeypatch):
    """Never let tests write into the real data/processed directory."""
    out = tmp_path / "processed"
    out.mkdir()
    for mod in (clean_registrations, clean_chargers, validate_data):
        monkeypatch.setattr(mod, "PROCESSED_DIR", out)
    monkeypatch.setattr(validate_data.run, "__defaults__", (None, out))
    return out


@pytest.fixture
def raw(tmp_path):
    fuel = [
        (1, "2024-01-31", "Andaman & Nicobar Island", "35", "Port Blair DTO", "AN1", "Electric(BOV)", 5),
        (2, "2024-01-31", "Andaman & Nicobar Island", "35", "Port Blair DTO", "AN1", "Petrol", 95),
        (3, "2024-01-31", "Ut Of Dnh And Dd", "38", "Daman", "DD1", "Pure EV", 3),
        (4, "2024-01-31", "Ut Of Dnh And Dd", "38", "Daman", "DD1", "Strong Hybrid EV", 2),
        (5, "2024-01-31", "Haryana", "06", "M/S Pasco Motors LLP, 40 Mile Stone(F.C)", "HR207", "Electric(BOV)", 100000),
        (6, "2024-01-31", "Haryana", "06", "Gurugram", "HR26", "Electric(BOV)", 40),
        (7, "2024-01-31", "West Bengal", "19", "Canning ARTO", "", "Petrol", 11),
        (8, "2024-01-31", "West Bengal", "19", "Canning ARTO", "", "Petrol", 4),     # natural-key duplicate -> summed
        (9, "2024-02-29", "Haryana", "06", "Gurugram", "HR26", "Pure EV", 50),
        (10, "2024-02-29", "Haryana", "06", "Gurugram", "HR26", "Plug-in Hybrid EV", 1),
    ]
    maker = [(1, "2024-01-31", "Haryana", "06", "Gurugram", "HR26", "Ather Energy LTD", 30),
             (2, "2024-01-31", "Haryana", "06", "Gurugram", "HR26", "Ola Electric Technologies PVT LTD", 10),
             (3, "2024-01-31", "Haryana", "06", "Pasco", "HR207", "Hero Motocorp LTD", 999999)]
    cat = []
    i = 0
    for m in range(1, 7):
        for office in ("O1", "O2", "O3", "O4"):
            i += 1
            v = 100 + m
            if m == 3 and office != "O4":
                v = 777777          # same large value in 3 offices -> aggregate leak
            if m == 5 and office == "O4":
                v = 50000           # >10x the office median -> spike
            cat.append((i, f"2024-{m:02d}-01", "Haryana", 6, f"Office {office}", office, "Two Wheeler(Nt)", "Vehicle Category", float(v)))
    d = tmp_path / "data"
    d.mkdir()
    write(d / "registrations-by-fuel-type.csv", RTO_HEADER, fuel)
    shutil.copy(d / "registrations-by-fuel-type.csv", d / "vehicle-registrations-by-fuel-type.csv")
    write(d / "registrations-by-maker.csv", RTO_HEADER, maker)
    write(d / "vahan-vehicle-registrations-by-vehicle-category-test.csv", CAT_HEADER, cat)
    (d / "ev_charging_stations_by_state_2025.csv").write_text(
        "state,public_charging_stations\nHaryana,935\nJammu and Kashmir,185\nLadakh,1\n", encoding="utf-8")
    (d / "ev_charging_stations_omc_yearwise_2026.csv").write_text(
        "state,fy2020_21,fy2021_22,fy2022_23,fy2023_24,fy2024_25,fy2025_26_upto_mar1,decommissioned,total_installed,total_operational\n"
        "Ladakh,0,2,0,0,14,8,0,24,23\nLeh,0,0,0,0,5,0,5,0,0\nHaryana,26,115,205,344,674,23,0,1387,1167\n", encoding="utf-8")
    return d


@pytest.fixture
def built(raw):
    sources = discover_sources(raw)
    con = duckdb.connect()
    extract_vahan.run(con, sources)
    clean_registrations.build_fuel(con)
    return con, sources


def test_discover_sources_and_duplicate_detection(raw):
    s = discover_sources(raw)
    assert s["fuel"].name == "registrations-by-fuel-type.csv"
    assert s["fuel_dup"].name == "vehicle-registrations-by-fuel-type.csv"
    (raw / "registrations-by-maker-2.csv").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Ambiguous"):
        discover_sources(raw)


def test_state_names_standardised(built):
    con, _ = built
    states = {r[0] for r in con.execute("SELECT DISTINCT state_name FROM fuel_state_month").fetchall()}
    assert states == {"Andaman and Nicobar Islands", "Dadra and Nagar Haveli and Daman and Diu", "Haryana", "West Bengal"}


def test_unknown_state_fails_loudly(raw):
    p = raw / "registrations-by-fuel-type.csv"
    p.write_text(p.read_text(encoding="utf-8") + '11,"2024-01-31","Atlantis","99","X","AT1","Petrol",1\n', encoding="utf-8")
    with pytest.raises(extract_vahan.UnknownStateError, match="Atlantis"):
        extract_vahan.run(duckdb.connect(), discover_sources(raw))


def test_unknown_fuel_label_fails_loudly(raw):
    p = raw / "registrations-by-fuel-type.csv"
    p.write_text(p.read_text(encoding="utf-8") + '11,"2024-01-31","Haryana","06","X","HR1","Plasma",1\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Plasma"):
        extract_vahan.run(duckdb.connect(), discover_sources(raw))


def test_ev_classification(built):
    con, _ = built
    rows = dict(con.execute("SELECT fuel_label, bool_or(is_bev) FROM fuel_state_month GROUP BY 1").fetchall())
    assert rows["Electric(BOV)"] and rows["Pure EV"]
    assert not rows["Strong Hybrid EV"] and not rows["Plug-in Hybrid EV"] and not rows["Petrol"]


def test_aggregate_leak_office_excluded_and_totals_exact(built):
    con, _ = built
    hr = con.execute("""SELECT sum(registrations) FROM fuel_state_month
        WHERE state_name = 'Haryana' AND is_bev AND month = DATE '2024-01-01'""").fetchone()[0]
    assert hr == 40  # 100000 from HR207 excluded
    assert con.execute("SELECT sum(registrations) FROM fuel_state_month").fetchone()[0] == 5 + 95 + 3 + 2 + 40 + 11 + 4 + 50 + 1


def test_null_office_code_kept_and_duplicates_summed(built):
    con, _ = built
    r = con.execute("""SELECT registrations, source_rows FROM fuel_state_month
        WHERE state_name = 'West Bengal' AND fuel_label = 'Petrol'""").fetchone()
    assert r == (15, 2)


def test_dates_parsed_to_month_start(built):
    con, _ = built
    months = [str(r[0]) for r in con.execute("SELECT DISTINCT month FROM fuel_state_month ORDER BY 1").fetchall()]
    assert months == ["2024-01-01", "2024-02-01"]


def test_maker_ev_name_flag_and_exclusion(built):
    con, _ = built
    clean_registrations.build_maker(con)
    rows = dict(con.execute("SELECT maker, name_identified_ev_maker FROM maker_state_month").fetchall())
    assert rows == {"Ather Energy LTD": False, "Ola Electric Technologies PVT LTD": True}  # Hero row was HR207


def test_category_outlier_rules(built):
    con, _ = built
    clean_registrations.build_category(con)
    reasons = dict(con.execute("SELECT office_code || '@' || month, outlier_reason FROM category_outliers").fetchall())
    assert {k for k, v in reasons.items() if v == "repeated_value_across_offices"} == {
        "O1@2024-03-01", "O2@2024-03-01", "O3@2024-03-01"}
    assert reasons["O4@2024-05-01"] == "spike_vs_office_median"
    clean, raw_total = con.execute("SELECT sum(registrations), sum(registrations_raw) FROM category_state_month").fetchone()
    assert raw_total - clean == 3 * 777777 + 50000


def test_fy_labels():
    assert fy_label("fy2020_21") == ("FY2020-21", False)
    assert fy_label("fy2025_26_upto_mar1") == ("FY2025-26 (up to 1 Mar 2026)", True)
    with pytest.raises(ValueError):
        fy_label("year2020")


def test_chargers_leh_merged_and_measures_separate(built):
    con, sources = built
    clean_chargers.run(con, sources)
    lad = con.execute("SELECT installed FROM chargers_omc_yearwise WHERE state_name = 'Ladakh' AND fy_label = 'FY2024-25'").fetchone()[0]
    assert lad == 19
    st = con.execute("SELECT decommissioned, total_installed, source_rows FROM chargers_omc_summary WHERE state_name = 'Ladakh'").fetchone()
    assert st[0] == 5 and st[1] == 24 and "Leh" in st[2]
    assert con.execute("SELECT sum(public_charging_stations) FROM chargers_state_snapshot").fetchone()[0] == 935 + 185 + 1


def test_validation_passes_on_clean_data(built, tmp_path):
    con, sources = built
    clean_registrations.build_maker(con)
    clean_registrations.build_category(con)
    clean_chargers.run(con, sources)
    checks = {c.name: c for c in validate_data.run(con, sources, out_dir=tmp_path)}
    assert (tmp_path / "validation_report.json").exists()
    assert checks["fuel_total_reconciles"].status == "pass"
    assert checks["maker_total_reconciles"].status == "pass"
    assert checks["category_total_reconciles"].status == "pass"
    assert checks["fuel_files_duplicate_detected"].data["identical"] is True
    assert checks["charger_snapshot_total"].status == "warn"  # synthetic total differs from the published 29,277
