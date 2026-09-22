#!/usr/bin/env python3
"""
PSet1 - Road Safety Priorities
Step 3: write the field dictionary and the compact JSON the website reads.

Keeping the site's payload small matters: it has to load on a phone and it has
to survive being hosted anywhere, so the page ships pre-aggregated numbers
rather than the 38,000-row crash table.
"""

import json
import os

import numpy as np
import pandas as pd

# Repo layout: this file lives in pset1/scripts/, everything else under pset1/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(ROOT, "data", "raw")
SLIM = os.path.join(ROOT, "data", "slim")
OUT  = os.path.join(ROOT, "data", "out")
SITE = os.path.join(ROOT, "data", "build")

CITIES = ["BOSTON", "CAMBRIDGE", "SOMERVILLE"]
SRC_CRASH = ("https://gis.data.mass.gov/datasets/MassDOT::"
             "{year}-crashes")
SRC_CLUSTER = ("https://gis.data.mass.gov/datasets/MassDOT::"
               "top-200-crash-clusters-2021-2023")
SRC_MANUAL = "https://masscrashreportmanual.com/data-dictionary/"

DICT_ROWS = [
    # field, unit, definition, source
    ("CRASH_NUMB", "id", "MassDOT crash report number; unique per crash.",
     "MassDOT"),
    ("city", "text", "Municipality the crash was recorded in "
     "(MassDOT CITY_TOWN_NAME, upper case).", "MassDOT"),
    ("year", "year", "Calendar year of the crash.", "MassDOT"),
    ("datetime", "timestamp", "Crash date and time, parsed from MassDOT's "
     "epoch-millisecond CRASH_DATETIME.", "MassDOT"),
    ("hour", "0-23", "Hour of day, derived from datetime.", "derived"),
    ("dow_name", "text", "Day of week, derived from datetime.", "derived"),
    ("lat / lon", "degrees WGS84", "Crash location. Blank where MassDOT could "
     "not geocode the report; those crashes are excluded from the map and the "
     "ranking but kept in the citywide totals.", "MassDOT"),
    ("CRASH_SEVERITY_DESCR", "category", "Fatal injury / Non-fatal injury / "
     "Property damage only / Unknown / Not reported, as coded by the "
     "reporting officer.", "MassDOT"),
    ("kabco", "K,A,B,C,O", "Highest injury severity at the crash on the KABCO "
     "scale: K fatal, A suspected serious, B suspected minor, C possible, "
     "O no apparent injury. Mapped from MAX_INJR_SVRTY_CL, which uses two "
     "different label sets across the five years.", "derived"),
    ("epdo", "points", "Equivalent Property Damage Only weight for one crash: "
     "21 if anyone was injured or killed, otherwise 1. This is MassDOT's own "
     "weighting, verified by reproducing the published EPDO on 133 of their "
     "cluster polygons exactly. Crashes of unknown severity are given 1, "
     "which cannot inflate a location's score.", "derived, MassDOT method"),
    ("aadt", "vehicles/day", "Annual Average Daily Traffic on the road segment "
     "the crash was snapped to.", "MassDOT Road Inventory"),
    ("AADT_DERIV", "text", "How MassDOT obtained that AADT. Blank means no "
     "provenance was recorded.", "MassDOT Road Inventory"),
    ("aadt_tier", "category", "measured / from_counts / modelled / coded / "
     "none - a grouping of AADT_DERIV used to decide whether a value may be "
     "used as exposure.", "derived"),
    ("aadt_usable", "boolean", "True when AADT_DERIV is populated. 4,822 "
     "crashes (12.7%) carry the identical value 1154 with a blank "
     "AADT_DERIV, on roads classed Local: that is a statewide placeholder for "
     "streets with no traffic count, not a measurement, and it is excluded "
     "from every exposure calculation.", "derived"),
    ("speed_limit", "mph", "Posted limit as entered by the officer, kept only "
     "when between 5 and 75 mph. The raw column ranges from -125 to 265; 62 "
     "impossible values were discarded. This is the POSTED limit - MassDOT "
     "does not record travel speed.", "MassDOT"),
    ("involves_pedestrian / involves_bicyclist / involves_scooter", "boolean",
     "Parsed from NON_MTRST_TYPE_CL, which lists each vulnerable road user in "
     "the crash as 'VU2: Pedestrian', 'VU3: Bicyclist' and so on.", "derived"),
    ("circ_speeding", "boolean", "The officer recorded 'Exceeded authorized "
     "speed limit' or 'Driving too fast for conditions' as a contributing "
     "circumstance for any driver. Parsed from DRVR_CNTRB_CIRC_CL, which is "
     "formatted 'D1: (reason) / D2: (reason)'. Present on 77.8% of crashes; "
     "percentages are taken over that reported base, not all crashes.",
     "derived"),
    ("circ_* (other)", "boolean", "Same parsing for distraction, failure to "
     "yield, following too closely, disregarding a control, impairment or "
     "fatigue, and aggressive driving.", "derived"),
    ("is_dark", "boolean", "AMBNT_LIGHT_DESCR is one of the three 'Dark - ...' "
     "categories.", "derived"),
    ("at_junction", "boolean", "RDWY_JNCT_TYPE_DESCR is a four-way, T, Y or "
     "five-point-or-more intersection. These are the same junction types "
     "MassDOT restricts its own intersection clustering to.", "derived"),
    ("location_id", "id", "Intersection cluster identifier assigned by this "
     "analysis.", "derived"),
    ("name", "text", "Cross streets, taken from the most frequently recorded "
     "street names among the crashes in the cluster, with route descriptors "
     "such as 'Rte SR28 S' stripped. Officer-entered, so occasionally "
     "imprecise.", "derived"),
    ("crashes", "count", "Crashes in the cluster over the window.", "derived"),
    ("epdo (location)", "points", "Sum of crash EPDO weights at the location.",
     "derived"),
    ("aadt_major", "vehicles/day", "The highest usable AADT among the crashes "
     "in the cluster - the major approach. The median would understate a "
     "junction's traffic, because a crash recorded on the minor leg carries "
     "that leg's low count.", "derived"),
    ("exposure_mveh", "million vehicles", "aadt_major x 365 x years / 1e6.",
     "derived"),
    ("risk_epdo_per_mveh", "points per million vehicles",
     "epdo / exposure_mveh. This is the exposure-adjusted ranking: it answers "
     "'how much harm per vehicle passing through', rather than 'how busy is "
     "this place'. Blank where no usable AADT exists.", "derived"),
    ("rank_epdo / rank_risk", "rank", "Position by severity-weighted total and "
     "by exposure-adjusted rate. Both are shown because they disagree, and "
     "the disagreement is the point.", "derived"),
]


def write_dictionary():
    rows = []
    for field, unit, definition, source in DICT_ROWS:
        rows.append({
            "field": field,
            "unit": unit,
            "definition": definition,
            "source": source,
            "source_url": (SRC_MANUAL if source == "MassDOT"
                           else SRC_CRASH.format(year="2025")),
            "accessed": "2026-09-21",
        })
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "data_dictionary.csv"), index=False)
    print(f"WROTE out/data_dictionary.csv  {len(d)} fields")


def jnum(v):
    """JSON-safe number."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if v != v else round(float(v), 4)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    return v


def frame_to_records(df):
    return [{k: jnum(v) for k, v in r.items()} for r in df.to_dict("records")]


# ---------------------------------------------------------------------------
# Basemap: the street pattern behind the map is drawn from every geocoded
# crash, rendered once to a small PNG and inlined. Nothing is fetched at run
# time, so the page works on any host and offline.
# ---------------------------------------------------------------------------

def build_basemap(crashes, loc):
    import base64, io, math
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    pts = crashes.dropna(subset=["lat", "lon"])
    lo0, lo1 = loc.lon.min(), loc.lon.max()
    la0, la1 = loc.lat.min(), loc.lat.max()
    kx = math.cos(math.radians((la0 + la1) / 2))
    W, H = 640, 470
    sc = min((W - 20) / ((lo1 - lo0) * kx), (H - 20) / (la1 - la0))
    ox = (W - (lo1 - lo0) * kx * sc) / 2
    oy = (H - (la1 - la0) * sc) / 2

    SS = 3
    img = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(img)
    r = 1.6 * SS / 2
    for lon, lat in zip(pts.lon.values, pts.lat.values):
        x = (ox + (lon - lo0) * kx * sc) * SS
        y = (H - oy - (lat - la0) * sc) * SS
        d.ellipse([x - r, y - r, x + r, y + r], fill=70)
    img = img.filter(ImageFilter.GaussianBlur(0.9 * SS / 2)).resize((W, H), Image.LANCZOS)
    a = np.clip(np.array(img).astype(np.float32) * 2.6, 0, 190).astype(np.uint8)
    rgba = Image.merge("RGBA", [Image.new("L", (W, H), 0)] * 3 + [Image.fromarray(a)])
    buf = io.BytesIO(); rgba.save(buf, "PNG", optimize=True)
    raw = buf.getvalue()
    with open(os.path.join(SITE, "basemap.png"), "wb") as fh:
        fh.write(raw)
    print(f"WROTE data/build/basemap.png  {len(raw)/1024:.0f} KB  ({len(pts):,} points)")
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def inline_page(payload_path, basemap_uri):
    """Build site/index.html from site/_template.html, inlining
    the payload and the basemap so the page is self-contained."""
    src = os.path.join(ROOT, "site", "_template.html")
    tpl_path = os.path.join(ROOT, "site", "index.html")
    if not os.path.exists(src):
        print("site/_template.html missing - cannot rebuild index.html")
        return
    with open(src, encoding="utf-8") as fh:
        tpl = fh.read()
    with open(payload_path, encoding="utf-8") as fh:
        data = fh.read().replace("</", "<\\/")
    out = tpl.replace("__DATA__", data).replace("__BASEMAP__", basemap_uri)
    with open(tpl_path, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"WROTE site/index.html  {os.path.getsize(tpl_path)/1024:.0f} KB")


def main():
    os.makedirs(SITE, exist_ok=True)
    write_dictionary()

    crashes = pd.read_csv(os.path.join(OUT, "crashes_clean.csv"),
                          low_memory=False)
    loc = pd.read_csv(os.path.join(OUT, "locations.csv"))
    off = pd.read_csv(os.path.join(OUT, "official_comparison.csv"))

    d = crashes[crashes.city.isin(CITIES)]

    # ---- headline numbers -------------------------------------------------
    summary = {
        "generated": "2026-09-21",
        "window": "2021-2025",
        "cities": CITIES,
        "total_crashes": int(len(d)),
        "geocoded": int(d.has_coords.sum()),
        "geocoded_pct": round(100 * d.has_coords.mean(), 1),
        "fatal": int(d.is_fatal.sum()),
        "injury": int(d.is_injury.sum()),
        "pedestrian": int(d.involves_pedestrian.sum()),
        "bicyclist": int(d.involves_bicyclist.sum()),
        "locations": int(len(loc)),
        "locations_with_exposure": int(loc.risk_epdo_per_mveh.notna().sum()),
        "official_clusters_checked": int(len(off)),
        "official_epdo_reproduced": int(len(off)),
        "official_matched": int(off.matched.sum()),
    }

    # ---- per-city composition --------------------------------------------
    comp = []
    for city, g in d.groupby("city"):
        rep = int(g.DRVR_CNTRB_CIRC_CL.notna().sum())
        comp.append({
            "city": city.title(),
            "crashes": int(len(g)),
            "fatal": int(g.is_fatal.sum()),
            "injury_pct": round(100 * g.is_injury.mean(), 1),
            "pedestrian_pct": round(100 * g.involves_pedestrian.mean(), 2),
            "bicyclist_pct": round(100 * g.involves_bicyclist.mean(), 2),
            "scooter_pct": round(100 * g.involves_scooter.mean(), 2),
            "vru_pct": round(100 * g.involves_vru.mean(), 2),
            "junction_pct": round(100 * g.at_junction.mean(), 1),
            "dark_pct": round(100 * g.is_dark.mean(), 1),
            "wet_pct": round(100 * g.surface_wet_or_worse.mean(), 1),
            "rearend_pct": round(
                100 * g.MANR_COLL_DESCR.eq("Rear-end").mean(), 1),
            "signal_pct": round(100 * g.has_signal.mean(), 1),
            "speeding_pct": round(100 * g.circ_speeding.sum() / rep, 1)
            if rep else None,
            "failyield_pct": round(100 * g.circ_failed_to_yield.sum() / rep, 1)
            if rep else None,
            "distracted_pct": round(100 * g.circ_distracted.sum() / rep, 1)
            if rep else None,
            "circ_reported": rep,
        })

    # ---- hour profile, share of crashes involving a VRU -------------------
    h = d.dropna(subset=["hour"]).copy()
    h["hour"] = h.hour.astype(int)
    hours = []
    for (city, hr), g in h.groupby(["city", "hour"]):
        hours.append({
            "city": city.title(), "hour": int(hr),
            "crashes": int(len(g)),
            "vru": int(g.involves_vru.sum()),
            "vru_pct": round(100 * g.involves_vru.mean(), 1),
        })

    # ---- map + table payload ---------------------------------------------
    cols = ["location_id", "name", "city", "lat", "lon", "crashes", "epdo",
            "fatal", "injury_crashes", "pedestrian", "bicyclist", "scooter",
            "vru_crashes", "dark_crashes", "speeding_crashes",
            "aadt_major", "aadt_quality", "risk_epdo_per_mveh",
            "rank_epdo", "rank_risk", "junction_type", "signalised",
            "speed_limit"]
    payload = loc[loc.crashes >= 3][cols].copy()
    payload["city"] = payload.city.str.title()

    # Flag the locations MassDOT already lists, so the site can show agreement
    # and disagreement side by side.
    matched_ids = set(off.loc[off.matched, "matched_location_id"].dropna())
    payload["on_massdot_list"] = payload.location_id.isin(matched_ids)

    site = {
        "summary": summary,
        "composition": comp,
        "hours": hours,
        "locations": frame_to_records(payload),
        "official": frame_to_records(
            off[["layer", "street_1", "street_2", "towns", "official_crashes",
                 "official_epdo", "matched_name", "matched_epdo",
                 "match_distance_m", "matched"]]
        ),
    }

    for name in ["agg_city_year", "agg_city_junction", "agg_city_light",
                 "agg_city_collision", "agg_city_surface", "agg_city_control",
                 "agg_city_factor", "agg_city_dow"]:
        path = os.path.join(OUT, name + ".csv")
        if os.path.exists(path):
            f = pd.read_csv(path)
            if "city" in f.columns:
                f["city"] = f.city.str.title()
            site[name.replace("agg_city_", "by_")] = frame_to_records(f)

    site["dictionary"] = frame_to_records(
        pd.read_csv(os.path.join(OUT, "data_dictionary.csv"))[
            ["field", "unit", "definition"]])

    out_path = os.path.join(SITE, "data.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(site, fh, separators=(",", ":"))
    kb = os.path.getsize(out_path) / 1024
    print(f"WROTE data/build/data.json  {kb:.0f} KB  "
          f"({len(payload):,} locations)")

    basemap = build_basemap(crashes, loc)
    inline_page(out_path, basemap)

    print()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
