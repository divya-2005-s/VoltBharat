-- VoltBharat analytical views. CREATE OR REPLACE keeps this file rerunnable.

-- Powertrain mix per state and month. "bev" is the headline EV measure.
CREATE OR REPLACE VIEW v_ev_state_month AS
SELECT
    d.date_id,
    d.month_start,
    d.fy_label,
    s.state_id,
    s.state_name,
    sum(f.registrations) FILTER (WHERE df.is_bev)                          AS bev,
    sum(f.registrations) FILTER (WHERE df.fuel_class = 'strong_hybrid')    AS strong_hybrid,
    sum(f.registrations) FILTER (WHERE df.fuel_class = 'plugin_hybrid')    AS plugin_hybrid,
    sum(f.registrations) FILTER (WHERE df.fuel_class = 'fcev')             AS fcev,
    sum(f.registrations) FILTER (WHERE df.fuel_class = 'other_hybrid')     AS other_hybrid,
    sum(f.registrations)                                                    AS total_all_fuels
FROM fact_registrations_fuel f
JOIN dim_date d   USING (date_id)
JOIN dim_state s  USING (state_id)
JOIN dim_fuel df  USING (fuel_id)
GROUP BY d.date_id, d.month_start, d.fy_label, s.state_id, s.state_name;

CREATE OR REPLACE VIEW v_ev_national_month AS
SELECT
    date_id, month_start, fy_label,
    coalesce(sum(bev), 0)            AS bev,
    coalesce(sum(strong_hybrid), 0)  AS strong_hybrid,
    coalesce(sum(plugin_hybrid), 0)  AS plugin_hybrid,
    coalesce(sum(fcev), 0)           AS fcev,
    coalesce(sum(other_hybrid), 0)   AS other_hybrid,
    sum(total_all_fuels)             AS total_all_fuels
FROM v_ev_state_month
GROUP BY date_id, month_start, fy_label;

-- State snapshot chargers alongside state attributes.
CREATE OR REPLACE VIEW v_state_chargers AS
SELECT s.state_id, s.state_name, s.state_code, s.region, c.public_charging_stations, c.snapshot_label
FROM dim_state s
LEFT JOIN fact_chargers c USING (state_id);
