#!/usr/bin/env python3
"""
PSet1 - Road Safety Priorities
Downloads MassDOT crash data for Boston, Cambridge and Somerville (2021-2025),
plus MassDOT's official crash-cluster layers.

Uses only the Python standard library - nothing to install.

Run:
    cd ~/Desktop/mit1.125/pset1
    python3 fetch_crashes.py

Output (written next to this script, in ./data/):
    crashes_2021.csv ... crashes_2025.csv
    crashes_all.csv                       <- all five years combined
    clusters_top200_2021_2023.geojson
    clusters_hsip_2021_2023.geojson
    clusters_hsip_pedestrian_2014_2023.geojson
    clusters_hsip_bicycle_2014_2023.geojson
    download_log.txt                      <- what was fetched, when, how many rows

Data source: MassDOT IMPACT open crash data (public domain, no API key).
    https://gis.data.mass.gov/
Field definitions: Massachusetts Law Enforcement Crash Report E-Manual
    https://masscrashreportmanual.com/data-dictionary/
"""

import csv
import datetime as dt
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ----------------------------------------------------------------------------
# Configuration - edit these if you want different cities or years
# ----------------------------------------------------------------------------

CITIES = ["BOSTON", "CAMBRIDGE", "SOMERVILLE"]
YEARS = [2021, 2022, 2023, 2024, 2025]

# MassDOT publishes one service per year. NOTE: 2023 has a trailing "v" in its
# service name - without it the endpoint 404s. This is not a typo.
CRASH_SERVICE = {
    2021: "MASSDOT_ODP_OPEN_2021",
    2022: "MASSDOT_ODP_OPEN_2022",
    2023: "MASSDOT_ODP_OPEN_2023v",
    2024: "MASSDOT_ODP_OPEN_2024",
    2025: "MASSDOT_ODP_OPEN_2025",
}

CRASH_HOST = "https://gis.crashdata.dot.mass.gov/arcgis/rest/services/MassDOT"

# MassDOT's own prioritisation layers (polygons).
CLUSTER_HOST = (
    "https://gis.massdot.state.ma.us/arcgis/rest/services/Roads/"
    "CrashClusters_ODP/FeatureServer"
)
CLUSTER_LAYERS = {
    34: "clusters_top200_2021_2023",
    32: "clusters_hsip_2021_2023",
    33: "clusters_hsip_pedestrian_2014_2023",
    35: "clusters_hsip_bicycle_2014_2023",
}

PAGE_SIZE = 2000          # ArcGIS server-side maximum for these services
TIMEOUT = 120             # seconds per request
MAX_RETRIES = 4

# Repo layout: this file lives in pset1/scripts/, everything else under pset1/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(ROOT, "data", "raw")
SLIM = os.path.join(ROOT, "data", "slim")
OUTDIR = RAW

# ----------------------------------------------------------------------------


def log(msg):
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


LOG_LINES = []


def fetch(url, params):
    """GET an ArcGIS REST endpoint with retries. Returns parsed JSON."""
    full = url + "?" + urllib.parse.urlencode(params)
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                full,
                headers={
                    "User-Agent": (
                        "MIT1.125-PSet1-coursework/1.0 "
                        "(academic use; contact via Harvard FAS)"
                    )
                },
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)

            # ArcGIS returns errors with HTTP 200, so check the body.
            if isinstance(data, dict) and "error" in data:
                raise RuntimeError(f"server error: {data['error']}")
            return data

        except Exception as exc:                      # noqa: BLE001
            last_err = exc
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                log(f"    attempt {attempt} failed ({exc}); retrying in {wait}s")
                time.sleep(wait)

    raise RuntimeError(f"gave up after {MAX_RETRIES} attempts: {last_err}")


def where_clause():
    quoted = ",".join(f"'{c}'" for c in CITIES)
    return f"CITY_TOWN_NAME IN ({quoted})"


def page_through(layer_url, where, out_format="json"):
    """Yield every feature from a layer matching `where`.

    Different MassDOT year-services enforce different server-side page limits
    (2021 caps at 1000, the others at 2000). So we advance the offset by the
    number of rows actually returned and keep going until a page comes back
    empty, rather than assuming a short page means the end of the data.
    """
    offset = 0
    pages = 0
    while True:
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true" if out_format == "geojson" else "false",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "f": out_format,
        }
        data = fetch(layer_url + "/query", params)
        feats = data.get("features", [])
        if not feats:
            return
        for f in feats:
            yield f
        offset += len(feats)
        pages += 1
        log(f"    ...{offset} rows")
        if pages > 500:
            log("    STOPPING - more than 500 pages, something is wrong")
            return


def epoch_to_iso(value):
    """MassDOT date fields come back as epoch milliseconds. Make them readable."""
    if value in (None, ""):
        return ""
    try:
        return dt.datetime.utcfromtimestamp(int(value) / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, TypeError, OSError):
        return str(value)


DATE_FIELDS = {"CRASH_DATETIME", "CRASH_DATE", "CRASH_TIME"}


def download_year(year):
    service = CRASH_SERVICE[year]
    layer_url = f"{CRASH_HOST}/{service}/FeatureServer/0"
    log(f"  {year}: querying {service}")

    rows = []
    for feat in page_through(layer_url, where_clause(), out_format="json"):
        attrs = dict(feat.get("attributes", {}))
        # Add readable versions of the epoch-millisecond date fields.
        for fld in list(attrs):
            if fld in DATE_FIELDS:
                attrs[fld + "_ISO"] = epoch_to_iso(attrs[fld])
        rows.append(attrs)

    if not rows:
        log(f"  {year}: NO ROWS RETURNED - check the service name")
        return []

    # Union of keys, so a schema difference between years cannot drop a column.
    fields = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)

    path = os.path.join(OUTDIR, f"crashes_{year}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    size_mb = os.path.getsize(path) / 1_048_576
    log(f"  {year}: {len(rows):,} rows -> crashes_{year}.csv ({size_mb:.1f} MB)")

    # Per-city breakdown, so you can sanity-check against the numbers we verified.
    counts = {}
    for r in rows:
        counts[r.get("CITY_TOWN_NAME", "?")] = (
            counts.get(r.get("CITY_TOWN_NAME", "?"), 0) + 1
        )
    for city in sorted(counts):
        log(f"        {city}: {counts[city]:,}")

    return rows


def download_clusters():
    for layer_id, name in CLUSTER_LAYERS.items():
        log(f"  layer {layer_id}: {name}")
        try:
            feats = list(
                page_through(
                    f"{CLUSTER_HOST}/{layer_id}", "1=1", out_format="geojson"
                )
            )
        except Exception as exc:                      # noqa: BLE001
            log(f"    SKIPPED - {exc}")
            continue

        if not feats:
            log("    no features returned")
            continue

        path = os.path.join(OUTDIR, name + ".geojson")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {"type": "FeatureCollection", "features": feats}, fh
            )
        size_mb = os.path.getsize(path) / 1_048_576
        log(f"    {len(feats):,} polygons -> {name}.geojson ({size_mb:.1f} MB)")


def combine(all_rows):
    if not all_rows:
        return
    fields = []
    seen = set()
    for r in all_rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)

    path = os.path.join(OUTDIR, "crashes_all.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)
    size_mb = os.path.getsize(path) / 1_048_576
    log(f"COMBINED: {len(all_rows):,} rows -> crashes_all.csv ({size_mb:.1f} MB)")


def main():
    os.makedirs(OUTDIR, exist_ok=True)

    log("=" * 64)
    log("MassDOT crash data download")
    log(f"Cities : {', '.join(CITIES)}")
    log(f"Years  : {', '.join(str(y) for y in YEARS)}")
    log(f"Output : {OUTDIR}")
    log("=" * 64)

    started = time.time()
    all_rows = []
    failures = []

    log("STEP 1 of 2 - crash records")
    for year in YEARS:
        try:
            all_rows.extend(download_year(year))
        except Exception as exc:                      # noqa: BLE001
            log(f"  {year}: FAILED - {exc}")
            failures.append(str(year))

    if all_rows:
        combine(all_rows)

    log("")
    log("STEP 2 of 2 - MassDOT official crash clusters")
    download_clusters()

    elapsed = time.time() - started
    log("")
    log("=" * 64)
    log(f"Done in {elapsed / 60:.1f} minutes. {len(all_rows):,} crash rows total.")
    if failures:
        log(f"FAILED YEARS: {', '.join(failures)}")
        log("Re-run the script - it will fetch everything again.")
    log(f"Accessed: {dt.datetime.now().astimezone().isoformat()}")
    log("=" * 64)

    with open(os.path.join(OUTDIR, "download_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG_LINES) + "\n")
    print(f"\nLog written to {os.path.join(OUTDIR, 'download_log.txt')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Re-run the script to start over.")
        sys.exit(1)
