#!/usr/bin/env python3
"""
PSet1 - Road Safety Priorities
Step 1.5: slim the downloaded data so it can be transferred for analysis.

The raw MassDOT download is ~54 MB across 124 columns. This keeps only the
columns the analysis actually uses, writes one gzipped CSV per year, and
converts the largest cluster polygon file to a compact centroid table.

Nothing is thrown away permanently - the full files stay in ./data/ and remain
the archival copy. This only writes a smaller working copy into ./data/slim/.

Uses only the Python standard library.

Run:
    cd ~/Desktop/mit1.125/pset1
    python3 slim_data.py
"""

import csv
import gzip
import json
import os
import sys

# Repo layout: this file lives in pset1/scripts/, everything else under pset1/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(ROOT, "data", "raw")
SLIM = os.path.join(ROOT, "data", "slim")
DATA = RAW

YEARS = [2021, 2022, 2023, 2024, 2025]

# Columns the analysis needs, grouped by purpose.
KEEP = [
    # identity, time, place
    "CRASH_NUMB", "CITY_TOWN_NAME", "YEAR",
    "CRASH_DATETIME_ISO", "CRASH_DATE_TEXT", "CRASH_TIME_2", "CRASH_HOUR",
    "LAT", "LON", "IS_GEOCODED", "GEOCODING_METHOD_NAME",
    # street naming - needed to label the ranked locations
    "RDWY", "NEAR_INT_RDWY", "DIST_DIRC_FROM_INT",
    "STREETNAME", "FROMSTREETNAME", "TOSTREETNAME",
    # severity - the numerator
    "CRASH_SEVERITY_DESCR", "MAX_INJR_SVRTY_CL",
    "NUMB_FATAL_INJR", "NUMB_NONFATAL_INJR", "NUMB_VEHC",
    # exposure and road geometry - the denominator and the context
    "AADT", "AADT_YEAR", "AADT_DERIV",
    "SPEED_LIMIT", "SPEED_LIM", "NUM_LANES", "OPP_LANES",
    "F_CLASS", "F_F_CLASS", "JURISDICTN", "URBAN_TYPE",
    "LT_SIDEWLK", "RT_SIDEWLK", "CURB", "MED_TYPE",
    # conditions
    "AMBNT_LIGHT_DESCR", "WEATH_COND_DESCR", "ROAD_SURF_COND_DESCR",
    "ROAD_CNTRB_DESCR",
    # controls and junction type - what treatment is already there
    "TRAF_CNTRL_DEVC_TYPE_DESCR", "TRAF_CNTRL_DEVC_FUNC_DESCR",
    "RDWY_JNCT_TYPE_DESCR", "TRAFY_DESCR_DESCR",
    # crash type and behaviour
    "MANR_COLL_DESCR", "FIRST_HRMF_EVENT_DESCR",
    "DRVR_CNTRB_CIRC_CL", "DRVR_DISTRACTED_CL",
    "HIT_RUN_DESCR", "WORK_ZONE_RELD_DESCR", "SCHL_BUS_RELD_DESCR",
    # vulnerable road users
    "NON_MTRST_TYPE_CL", "NON_MTRST_ACTN_CL", "NON_MTRST_LOC_CL",
    "AGE_NONMTRST_YNGST", "AGE_NONMTRST_OLDEST",
]

CLUSTER_COMPACT = [
    "clusters_hsip_pedestrian_2014_2023",
]

LOG = []


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


def centroid(geom):
    """Rough centroid: mean of all coordinate pairs in the geometry."""
    xs, ys = [], []

    def walk(node):
        if (isinstance(node, list) and len(node) == 2
                and all(isinstance(v, (int, float)) for v in node)):
            xs.append(node[0])
            ys.append(node[1])
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(geom.get("coordinates", []))
    if not xs:
        return "", ""
    return round(sum(xs) / len(xs), 6), round(sum(ys) / len(ys), 6)


def slim_year(year):
    src = os.path.join(DATA, f"crashes_{year}.csv")
    if not os.path.exists(src):
        log(f"  {year}: MISSING {src}")
        return None

    with open(src, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        available = reader.fieldnames or []
        cols = [c for c in KEEP if c in available]
        missing = [c for c in KEEP if c not in available]

        rows = 0
        no_coord = 0
        no_aadt = 0
        by_city = {}

        dst = os.path.join(SLIM, f"crashes_{year}.csv.gz")
        with gzip.open(dst, "wt", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for rec in reader:
                slim = {c: (rec.get(c) or "").strip() for c in cols}
                writer.writerow(slim)
                rows += 1
                if not slim.get("LAT") or not slim.get("LON"):
                    no_coord += 1
                if not slim.get("AADT"):
                    no_aadt += 1
                city = slim.get("CITY_TOWN_NAME", "?")
                by_city[city] = by_city.get(city, 0) + 1

    size_kb = os.path.getsize(dst) / 1024
    log(f"  {year}: {rows:,} rows, {len(cols)} cols -> "
        f"slim/crashes_{year}.csv.gz ({size_kb:.0f} KB)")
    for city in sorted(by_city):
        log(f"        {city}: {by_city[city]:,}")
    log(f"        missing coordinates: {no_coord:,} "
        f"({100 * no_coord / rows:.1f}%)" if rows else "")
    log(f"        missing AADT:        {no_aadt:,} "
        f"({100 * no_aadt / rows:.1f}%)" if rows else "")
    if missing:
        log(f"        columns requested but not in file: {', '.join(missing)}")
    return rows


def compact_clusters(name):
    src = os.path.join(DATA, name + ".geojson")
    if not os.path.exists(src):
        log(f"  MISSING {src}")
        return

    with open(src, encoding="utf-8") as fh:
        data = json.load(fh)
    feats = data.get("features", [])
    if not feats:
        log(f"  {name}: no features")
        return

    keys, seen = [], set()
    for f in feats:
        for k in (f.get("properties") or {}):
            if k not in seen:
                seen.add(k)
                keys.append(k)

    dst = os.path.join(SLIM, name + "_centroids.csv")
    with open(dst, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=keys + ["LON", "LAT"],
                                extrasaction="ignore")
        writer.writeheader()
        for f in feats:
            row = dict(f.get("properties") or {})
            lon, lat = centroid(f.get("geometry") or {})
            row["LON"] = lon
            row["LAT"] = lat
            writer.writerow(row)

    size_kb = os.path.getsize(dst) / 1024
    log(f"  {name}: {len(feats):,} polygons -> "
        f"slim/{name}_centroids.csv ({size_kb:.0f} KB)")


def main():
    if not os.path.isdir(DATA):
        print(f"ERROR: no data folder at {DATA}. Run fetch_crashes.py first.")
        sys.exit(1)
    os.makedirs(SLIM, exist_ok=True)

    log("=" * 64)
    log("Slimming downloaded data for analysis")
    log(f"Source : {DATA}")
    log(f"Output : {SLIM}")
    log("=" * 64)

    log("Crash records:")
    total = 0
    for year in YEARS:
        n = slim_year(year)
        if n:
            total += n

    log("")
    log("Cluster polygons (large ones converted to centroids):")
    for name in CLUSTER_COMPACT:
        compact_clusters(name)

    log("")
    log("=" * 64)
    log(f"Done. {total:,} rows slimmed.")
    total_kb = sum(
        os.path.getsize(os.path.join(SLIM, f))
        for f in os.listdir(SLIM)
    ) / 1024
    log(f"slim/ folder is now {total_kb:.0f} KB total.")
    log("=" * 64)

    with open(os.path.join(SLIM, "slim_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
