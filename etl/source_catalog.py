"""Human-readable provenance and limitations for each source, loaded into data_sources."""

VAHAN_PROVENANCE = ("VAHAN national vehicle registry (Ministry of Road Transport & Highways) dashboard extract, "
                    "supplied as a local CSV. The original download URL and extraction date were not recorded with the file.")

CATALOG = {
    "fuel": dict(
        title="Vehicle registrations by fuel type",
        description="Monthly new-vehicle registrations by RTO and fuel label.",
        provenance=VAHAN_PROVENANCE,
        grain="month x RTO x fuel label (aggregated to month x state x fuel label)",
        can_identify_ev=True,
        used_for="All EV adoption metrics: BEV registrations, EV share, growth, powertrain mix, charging-gap numerator.",
        limitations=("Office HR207 (a national aggregate mis-recorded as an office) is excluded. "
                     "BEV label changed from 'Electric(BOV)' to 'Pure EV' during 2024; both are counted as BEV. "
                     "No vehicle-category field, so EV registrations cannot be split into 2W/3W/4W/bus. "
                     "VAHAN may not include every registering authority in every month."),
    ),
    "fuel_dup": dict(
        title="Vehicle registrations by fuel type (duplicate copy)",
        description="Byte-identical copy of the fuel-type file.",
        provenance=VAHAN_PROVENANCE,
        grain="identical to fuel",
        can_identify_ev=True,
        used_for="Not used (duplicate). Checked by SHA-256 on every ETL run.",
        limitations="Adding it to the primary fuel file would double-count every registration.",
    ),
    "maker": dict(
        title="Vehicle registrations by maker",
        description="Monthly new-vehicle registrations by RTO and manufacturer name.",
        provenance=VAHAN_PROVENANCE,
        grain="month x RTO x maker (aggregated to month x state x maker)",
        can_identify_ev=False,
        used_for="All-fuel manufacturer rankings; a name-identified EV-maker subset (lower bound).",
        limitations=("No fuel field: cannot compute EV market share by manufacturer. "
                     "Manufacturers selling both EVs and ICE vehicles cannot be split. "
                     "Office HR207 is excluded."),
    ),
    "category": dict(
        title="Vehicle registrations by vehicle category",
        description="Monthly new-vehicle registrations by registering office and vehicle category.",
        provenance=VAHAN_PROVENANCE,
        grain="month x office x vehicle category (aggregated to month x state x category)",
        can_identify_ev=False,
        used_for="All-fuel vehicle-category mix, Jan-2019..May-2024, for states that pass validation.",
        limitations=("No fuel field: cannot identify EVs. Contains aggregate values leaked into office rows; "
                     "an outlier rule removes them and states whose cleaned totals differ from the fuel file by >5% "
                     "are flagged. Telangana and Lakshadweep are absent. Coverage ends May-2024."),
    ),
    "chargers_state": dict(
        title="Public EV charging stations by state (2025)",
        description="Operational public EV charging stations per state/UT.",
        provenance=("Government of India data published by PIB (annexure dated Aug-2025, inputs from the Ministry of Power); "
                    "also stated in a Lok Sabha written reply by the MoS Heavy Industries. Total 29,277."),
        grain="state snapshot",
        can_identify_ev=False,
        used_for="Charging-gap denominator; state charger counts.",
        limitations=("Single snapshot without an exact as-of date beyond 2025. Counts stations, not charging points, "
                     "power rating, utilisation or uptime. No geographic coverage within states."),
    ),
    "chargers_omc": dict(
        title="EV charging stations installed by oil marketing companies, by financial year",
        description="Charging stations installed by OMCs per state and financial year, with decommissioned and operational totals.",
        provenance="Government of India parliamentary/ministry data (file supplied locally; FY2025-26 covers up to 1 March 2026).",
        grain="state x financial year",
        can_identify_ev=False,
        used_for="Charger installation growth over time (OMC network only).",
        limitations=("Covers OMC-installed stations only; never added to the state snapshot. FY2025-26 is partial. "
                     "'total_installed' is net of decommissioned stations in some rows; 'Leh' row merged into Ladakh."),
    ),
}
