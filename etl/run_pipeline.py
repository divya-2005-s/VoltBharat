"""Run the full VoltBharat ETL: extract -> clean -> geo -> validate -> (optional) load.

Usage:
  python -m etl.run_pipeline              # build processed files + validation report
  python -m etl.run_pipeline --load-db    # ...and load PostgreSQL (needs DATABASE_URL)

Rerunnable: every output is rebuilt from the raw files; the database load
replaces fact rows inside one transaction, so reruns never duplicate data.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

from etl import build_geo, clean_chargers, clean_registrations, extract_vahan, validate_data
from etl.config import PROCESSED_DIR, REPORTS_DIR, discover_sources, ensure_dirs
from etl.logging_utils import setup_logging

log = logging.getLogger("etl.pipeline")


def write_execution_report(started, finished, steps, checks, sources, loaded) -> None:
    lines = ["# ETL Execution Report\n",
             f"- Started: {started.isoformat(timespec='seconds')}",
             f"- Finished: {finished.isoformat(timespec='seconds')}",
             f"- Database loaded: {'yes' if loaded else 'no'}\n",
             "## Sources\n", "| Key | File |", "|---|---|"]
    lines += [f"| {k} | `{p.name}` |" for k, p in sources.items()]
    lines += ["\n## Steps\n", "| Step | Seconds |", "|---|---|"]
    lines += [f"| {s} | {t:.1f} |" for s, t in steps]
    lines += ["\n## Validation\n", "| Status | Check | Detail |", "|---|---|---|"]
    lines += [f"| {c.status.upper()} | {c.name} | {c.detail.replace('|', '/')} |" for c in checks]
    lines += ["\n## Outputs\n"]
    lines += [f"- `data/processed/{p.name}` ({p.stat().st_size / 1024:,.0f} KB)"
              for p in sorted(PROCESSED_DIR.iterdir()) if p.is_file() and p.suffix in {".csv", ".parquet", ".json"}]
    (REPORTS_DIR / "etl_execution_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--load-db", action="store_true", help="load validated outputs into PostgreSQL")
    args = ap.parse_args(argv)

    setup_logging("pipeline")
    ensure_dirs()
    started = datetime.now(timezone.utc)
    steps: list[tuple[str, float]] = []

    def step(name, fn, *a):
        t = time.perf_counter()
        log.info("== %s", name)
        result = fn(*a)
        steps.append((name, time.perf_counter() - t))
        return result

    try:
        sources = discover_sources()
        con = extract_vahan.connect_staging()
        step("extract_vahan", extract_vahan.run, con, sources)
        step("clean_registrations", clean_registrations.run, con)
        step("clean_chargers", clean_chargers.run, con, sources)
        states = {r[0] for r in con.execute("SELECT state_name FROM ref_states").fetchall()}
        step("build_geo", build_geo.run, states)
        checks = step("validate_data", validate_data.run, con, sources)
        con.close()
    except Exception as exc:  # noqa: BLE001 - top-level: log a clear message and exit non-zero
        log.error("Pipeline failed: %s", exc, exc_info=True)
        return 1

    failed = [c for c in checks if c.status == "fail"]
    loaded = False
    if failed:
        log.error("%d validation checks failed; database NOT loaded: %s", len(failed), [c.name for c in failed])
    elif args.load_db:
        from etl import load_database
        try:
            step("load_database", load_database.run, started, checks)
            loaded = True
        except Exception as exc:  # noqa: BLE001
            log.error("Database load failed (processed files are still valid): %s", exc)
            write_execution_report(started, datetime.now(timezone.utc), steps, checks, sources, False)
            return 2

    finished = datetime.now(timezone.utc)
    write_execution_report(started, finished, steps, checks, sources, loaded)
    (PROCESSED_DIR / "etl_manifest.json").write_text(json.dumps({
        "started_at": started.isoformat(), "finished_at": finished.isoformat(),
        "sources": {k: p.name for k, p in sources.items()},
        "validation": {s: sum(c.status == s for c in checks) for s in ("pass", "warn", "fail")},
        "database_loaded": loaded}, indent=2), encoding="utf-8")
    log.info("Done in %.1fs. Report: %s", sum(t for _, t in steps), REPORTS_DIR / "etl_execution_report.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
