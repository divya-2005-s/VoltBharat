"""Dissolve the district-level India GeoJSON into one simplified feature per state/UT.

Input : data/reference/_geo_source/india.geojson  (district polygons, property 'st_nm')
Output: data/reference/india_states.geojson       (property 'name' = canonical state name)
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from etl.config import REFERENCE_DIR

log = logging.getLogger("etl.geo")
SOURCE = REFERENCE_DIR / "_geo_source" / "india.geojson"
OUTPUT = REFERENCE_DIR / "india_states.geojson"
SIMPLIFY_TOLERANCE = 0.01  # degrees (~1 km); keeps the file small for the browser


def run(canonical_states: set[str]) -> None:
    if not SOURCE.exists():
        log.warning("GeoJSON source %s missing; map pages will show their fallback.", SOURCE)
        return
    if OUTPUT.exists() and OUTPUT.stat().st_mtime >= SOURCE.stat().st_mtime:
        log.info("india_states.geojson is up to date")
        return
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    parts = defaultdict(list)
    for f in src["features"]:
        if f.get("geometry"):
            parts[f["properties"]["st_nm"]].append(shape(f["geometry"]).buffer(0))
    unknown = set(parts) - canonical_states
    if unknown:
        raise ValueError(f"GeoJSON state names not in states.csv: {sorted(unknown)}")
    features = []
    for name in sorted(parts):
        geom = unary_union(parts[name]).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        features.append({"type": "Feature", "properties": {"name": name}, "geometry": mapping(geom)})
    out = {"type": "FeatureCollection", "features": features}
    OUTPUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    log.info("Wrote %s (%d states, %.0f KB)", OUTPUT.name, len(features), OUTPUT.stat().st_size / 1024)
