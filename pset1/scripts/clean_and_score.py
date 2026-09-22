#!/usr/bin/env python3
"""
PSet1 - Road Safety Priorities: Boston / Cambridge / Somerville
Step 2: clean the MassDOT crash extract, derive the analysis columns, cluster
crashes into intersections, and score each intersection.

METHOD, IN ONE PARAGRAPH
    Crash counts alone rank busy roads, not dangerous ones. So every location
    is scored with MassDOT's own Equivalent Property Damage Only (EPDO)
    weighting - any injury crash counts 21, a property-damage-only crash
    counts 1 - and that score is then divided by traffic exposure (AADT x 365
    x years) to give EPDO points per million vehicles. Crashes are grouped
    into intersections with the same 25-metre search radius MassDOT uses, and
    restricted to the same junction types, so the result can be compared
    directly against MassDOT's published Top 200 Crash Clusters.

INPUTS   data/slim/crashes_20*.csv.gz          (from fetch_crashes.py + slim_data.py)
OUTPUTS  data/out/crashes_clean.csv                 the collected dataset
         out/locations.csv                     ranked intersections, 2021-2025
         out/locations_2021_2023.csv           same, MassDOT's comparison window
         out/agg_*.csv                         small aggregates for the website
         out/data_dictionary.csv               field definitions
         out/clean_log.txt
"""

import collections
import glob
import json
import math
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

pd.set_option("display.width", 200)

# Repo layout: this file lives in pset1/scripts/, everything else under pset1/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(ROOT, "data", "raw")
SLIM = os.path.join(ROOT, "data", "slim")
OUT  = os.path.join(ROOT, "data", "out")

IN_GLOB = os.environ.get("PSET1_IN", os.path.join(SLIM, "crashes_*.csv.gz"))
CLUSTER_DIR = os.environ.get("PSET1_CLUSTERS", RAW)

YEARS_ALL = [2021, 2022, 2023, 2024, 2025]
CITIES = ["BOSTON", "CAMBRIDGE", "SOMERVILLE"]

# MassDOT's intersection-cluster methodology: 25 m search radius, and only
# crashes the officer coded as one of these junction types.
CLUSTER_RADIUS_M = 25
JUNCTION_TYPES = [
    "Four-way intersection",
    "T-intersection",
    "Y-intersection",
    "Five-point or more",
]

# MassDOT EPDO weighting, verified against their published cluster layer:
# for Boston cluster Id 212, NUM_K_A=5, NUM_B_C=11, NUM_O=5, EPDO=341
# and (5 + 11) * 21 + 5 * 1 = 341.
EPDO_INJURY = 21
EPDO_PDO = 1

# MassDOT stores an AADT on every crash, but 4,822 of them (14.3%) carry the
# identical value 1154 with an EMPTY AADT_DERIV field, on roads classed Local.
# That is a statewide placeholder for local streets with no traffic count, not
# a measurement - and using it as a denominator would make quiet side streets
# the most dangerous places in the region. An AADT is therefore treated as
# usable exposure only when MassDOT documented how it was derived.
AADT_MEASURED = {
    "Actual",
    "MassDOT Highway Special Count",
    "RPA Count",
    "Calculated from Partial Counts",
    "Doubled from single direction",
    "AADT synchronized with other stations on the segment",
}
AADT_FROM_COUNTS = {
    "Derived from count data that is three or more years old",
    "Derived from counts collected on or adjacent to the section duri",
    "Derived from factoring counts from the previous year count-base",
    "Grown",
    "Grown from Prior Year HPMS Network",
}
AADT_MODELLED = {
    "Estimate",
    "Derived from an estimate",
    "Pulled back from HPMS network estimation routine",
    "Modified by Ramp Balancing",
}


def aadt_tier(v):
    if v is None or (isinstance(v, float) and v != v) or v == "":
        return "none"
    if v in AADT_MEASURED:
        return "measured"
    if v in AADT_FROM_COUNTS:
        return "from_counts"
    if v in AADT_MODELLED:
        return "modelled"
    return "coded"          # undocumented numeric codes such as "12" / "14"


# Street-name tidying. The officer-entered road fields carry route descriptors
# ("MORTON STREET Rte UNKNOW", "FELLSWAY Rte SR28 S") and slash-joined pairs.
ROUTE_RE = re.compile(r"\s+Rte\b.*$", re.IGNORECASE)
NOISE_RE = re.compile(r"^(ramp[- ]|unknown$|unnamed$)", re.IGNORECASE)

LOG = []


def log(msg=""):
    print(msg, flush=True)
    LOG.append(str(msg))


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load():
    files = sorted(glob.glob(IN_GLOB))
    if not files:
        sys.exit(f"No input files matched {IN_GLOB}")
    df = pd.concat(
        [pd.read_csv(f, dtype=str, low_memory=False) for f in files],
        ignore_index=True,
    )
    log(f"Loaded {len(df):,} rows from {len(files)} files")
    return df


# ---------------------------------------------------------------------------
# Clean and derive
# ---------------------------------------------------------------------------

KABCO_MAP = {
    # current MMUCC-style labels
    "Fatal injury (K)": "K",
    "Suspected Serious Injury (A)": "A",
    "Suspected Minor Injury (B)": "B",
    "Possible Injury (C)": "C",
    "No Apparent Injury (O)": "O",
    # legacy labels that still appear in the older years
    "Non-fatal injury - Incapacitating": "A",
    "Non-fatal injury - Non-incapacitating": "B",
    "Non-fatal injury - Possible": "C",
    "No injury": "O",
}

VRU_PATTERNS = {
    "pedestrian": r"Pedestrian",
    "bicyclist": r"Bicyclist",
    "scooter": r"Motorized Scooter Rider|Skateboarder",
}

CIRC_FLAGS = {
    "speeding": (
        "Exceeded authorized speed limit",
        "Driving too fast for conditions",
    ),
    "exceeded_limit": ("Exceeded authorized speed limit",),
    "distracted": ("Distracted", "Inattention"),
    "failed_to_yield": ("Failed to yield right of way",),
    "followed_too_closely": ("Followed too closely",),
    "disregarded_control": (
        "Disregarded traffic signs, signals, road markings",
    ),
    "impaired_or_fatigued": (
        "Physical impairment", "Fatigued/asleep", "Illness",
    ),
    "aggressive": (
        "Operating vehicle in erratic, reckless, careless, negligent "
        "or aggressive manner",
    ),
}

DARK = {
    "Dark - lighted roadway",
    "Dark - roadway not lighted",
    "Dark - unknown roadway lighting",
}


def num(series, lo=None, hi=None):
    s = pd.to_numeric(series, errors="coerce")
    if lo is not None:
        s = s.where(s >= lo)
    if hi is not None:
        s = s.where(s <= hi)
    return s


def clean(df):
    log()
    log("CLEANING")

    # Every text field in this export is padded to a fixed width.
    obj = df.select_dtypes(include="object").columns
    for c in obj:
        df[c] = df[c].str.strip()
    df = df.replace({"": np.nan})
    log(f"  stripped padding from {len(obj)} text columns")

    df["city"] = df["CITY_TOWN_NAME"].str.upper()
    df["year"] = num(df["YEAR"]).astype("Int64")

    ts = pd.to_datetime(df["CRASH_DATETIME_ISO"], errors="coerce")
    df["datetime"] = ts
    df["hour"] = ts.dt.hour
    df["dow"] = ts.dt.dayofweek                     # 0 = Monday
    df["dow_name"] = ts.dt.day_name()
    df["month"] = ts.dt.month
    df["is_weekend"] = df["dow"].isin([5, 6])
    log(f"  parsed timestamps: {ts.notna().sum():,} of {len(df):,}")

    df["lat"] = num(df["LAT"], 41.0, 43.5)
    df["lon"] = num(df["LON"], -72.5, -69.5)
    df["has_coords"] = df["lat"].notna() & df["lon"].notna()
    log(f"  usable coordinates: {df['has_coords'].sum():,} "
        f"({100 * df['has_coords'].mean():.1f}%) - "
        f"{(~df['has_coords']).sum():,} dropped from the map and the ranking")

    # AADT is stored as text and is absent on many records.
    df["aadt"] = num(df["AADT"], 1, None)
    df["aadt_year"] = num(df["AADT_YEAR"], 1990, 2026)
    df["aadt_tier"] = df["AADT_DERIV"].map(aadt_tier)
    df["aadt_usable"] = df["aadt"].notna() & df["aadt_tier"].ne("none")
    placeholder = int((df["aadt"] == 1154).sum())
    log(f"  AADT present: {df['aadt'].notna().sum():,} "
        f"({100 * df['aadt'].notna().mean():.1f}%), median "
        f"{df['aadt'].median():,.0f}")
    log(f"  AADT = 1154 placeholder on {placeholder:,} crashes "
        f"({100 * placeholder / len(df):.1f}%) - excluded from exposure")
    log(f"  AADT usable as exposure: {df['aadt_usable'].sum():,} "
        f"({100 * df['aadt_usable'].mean():.1f}%)")
    for tier, n in df["aadt_tier"].value_counts().items():
        log(f"        {tier:12} {n:7,}")

    # SPEED_LIMIT is officer-entered and contains impossible values
    # (the raw column ranges from -125 to 265 mph).
    raw_sl = pd.to_numeric(df["SPEED_LIMIT"], errors="coerce")
    df["speed_limit"] = num(df["SPEED_LIMIT"], 5, 75)
    bad = int(((raw_sl.notna()) & (df["speed_limit"].isna())).sum())
    log(f"  speed limit: {df['speed_limit'].notna().sum():,} kept, "
        f"{bad:,} impossible values discarded (outside 5-75 mph)")

    df["num_lanes"] = num(df["NUM_LANES"], 0, 20)
    df["n_fatal"] = num(df["NUMB_FATAL_INJR"]).fillna(0).astype(int)
    df["n_nonfatal"] = num(df["NUMB_NONFATAL_INJR"]).fillna(0).astype(int)
    df["n_vehicles"] = num(df["NUMB_VEHC"])

    # --- severity -----------------------------------------------------------
    sev = df["CRASH_SEVERITY_DESCR"]
    df["is_fatal"] = sev.eq("Fatal injury")
    df["is_injury"] = sev.isin(["Fatal injury", "Non-fatal injury"])
    df["is_pdo"] = sev.eq("Property damage only (none injured)")
    df["severity_known"] = sev.isin(
        ["Fatal injury", "Non-fatal injury",
         "Property damage only (none injured)"]
    )
    df["kabco"] = df["MAX_INJR_SVRTY_CL"].map(KABCO_MAP)

    log(f"  severity: {df['is_fatal'].sum():,} fatal, "
        f"{(df['is_injury'] & ~df['is_fatal']).sum():,} non-fatal injury, "
        f"{df['is_pdo'].sum():,} property-damage-only, "
        f"{(~df['severity_known']).sum():,} unknown/not reported")

    # EPDO. Unknown severity is treated as property-damage-only, which is the
    # conservative choice: it cannot inflate a location's score.
    df["epdo"] = np.where(df["is_injury"], EPDO_INJURY, EPDO_PDO)

    # --- vulnerable road users ---------------------------------------------
    vru = df["NON_MTRST_TYPE_CL"].fillna("")
    for name, pat in VRU_PATTERNS.items():
        df["involves_" + name] = vru.str.contains(pat, case=False, regex=True)
    df["involves_vru"] = (
        df["involves_pedestrian"] | df["involves_bicyclist"]
        | df["involves_scooter"]
    )
    log(f"  vulnerable users: {df['involves_pedestrian'].sum():,} pedestrian, "
        f"{df['involves_bicyclist'].sum():,} bicyclist, "
        f"{df['involves_scooter'].sum():,} scooter/skateboard")

    # --- contributing circumstances ----------------------------------------
    # Format is "D1: (Distracted) / D2: (No improper driving)" - one block per
    # vehicle, each holding a comma-separated list inside parentheses.
    circ = df["DRVR_CNTRB_CIRC_CL"].fillna("")
    for name, needles in CIRC_FLAGS.items():
        pat = "|".join(re.escape(n) for n in needles)
        df["circ_" + name] = circ.str.contains(pat, case=False, regex=True)
    log(f"  contributing circumstances recorded on "
        f"{circ.ne('').sum():,} crashes "
        f"({100 * circ.ne('').mean():.1f}%); "
        f"speeding-related: {df['circ_speeding'].sum():,}")

    # --- environment and road ----------------------------------------------
    df["is_dark"] = df["AMBNT_LIGHT_DESCR"].isin(DARK)
    df["light_group"] = df["AMBNT_LIGHT_DESCR"].map(
        lambda v: "Dark" if v in DARK
        else "Daylight" if v == "Daylight"
        else "Dawn/Dusk" if v in ("Dawn", "Dusk")
        else "Unknown"
    )
    df["surface_wet_or_worse"] = df["ROAD_SURF_COND_DESCR"].isin(
        ["Wet", "Snow", "Ice", "Slush", "Water (standing, moving)"]
    )
    df["at_junction"] = df["RDWY_JNCT_TYPE_DESCR"].isin(JUNCTION_TYPES)
    df["has_signal"] = df["TRAF_CNTRL_DEVC_TYPE_DESCR"].isin(
        ["Traffic control signal", "Flashing traffic control signal",
         "Pedestrian Crossing signal/beacon"]
    )
    df["has_sign_control"] = df["TRAF_CNTRL_DEVC_TYPE_DESCR"].isin(
        ["Stop signs", "Yield signs", "School zone signs"]
    )
    df["no_control"] = df["TRAF_CNTRL_DEVC_TYPE_DESCR"].eq("No controls")

    log(f"  at a junction: {df['at_junction'].sum():,} "
        f"({100 * df['at_junction'].mean():.1f}%)")
    log(f"  in darkness:   {df['is_dark'].sum():,} "
        f"({100 * df['is_dark'].mean():.1f}%)")

    return df


# ---------------------------------------------------------------------------
# Cluster crashes into intersections
# ---------------------------------------------------------------------------

def cluster_points(lat, lon, radius_m):
    """Union-find over pairs within radius_m, using a local flat projection."""
    lat0 = float(np.mean(lat))
    m_per_deg_lat = 111_132.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    xy = np.column_stack([
        (lon - np.mean(lon)) * m_per_deg_lon,
        (lat - lat0) * m_per_deg_lat,
    ])

    parent = np.arange(len(xy))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    tree = cKDTree(xy)
    for a, b in tree.query_pairs(radius_m):
        union(a, b)

    roots = np.array([find(i) for i in range(len(xy))])
    _, labels = np.unique(roots, return_inverse=True)
    return labels


def tidy_street(v):
    """Strip route descriptors and casing noise from an officer-entered name."""
    if not isinstance(v, str):
        return None
    v = ROUTE_RE.sub("", v).strip(" /,-")
    if len(v) < 2 or NOISE_RE.match(v):
        return None
    return " ".join(w.capitalize() if not w.isdigit() else w
                    for w in v.split())


def intersection_name(group):
    """Label a cluster with its two most frequently named cross streets."""
    tally = collections.Counter()
    for col, weight in (("RDWY", 3), ("NEAR_INT_RDWY", 3),
                        ("STREETNAME", 2), ("FROMSTREETNAME", 1),
                        ("TOSTREETNAME", 1)):
        if col not in group.columns:
            continue
        for raw in group[col].dropna():
            for part in str(raw).split("/"):
                name = tidy_street(part)
                if name:
                    tally[name] += weight

    if not tally:
        return "Unnamed location"

    picked, keys = [], []
    for name, _ in tally.most_common(6):
        key = (name.lower().replace("street", "st").replace("avenue", "ave")
               .replace("road", "rd").replace("boulevard", "blvd")
               .replace("parkway", "pkwy").replace(".", "").strip())
        if any(key in k or k in key for k in keys):
            continue
        keys.append(key)
        picked.append(name)
        if len(picked) == 2:
            break
    return " & ".join(picked)


def disambiguate(loc):
    """A wide junction - a divided boulevard, an interchange - splits into more
    than one 25 m cluster, and every piece carries the same pair of street
    names. Rather than an arbitrary (1)/(2), label each piece by where it sits
    relative to the others, which also explains why there is more than one."""
    dup = loc["name"].duplicated(keep=False)
    if not dup.any():
        return loc

    COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    for name, idx in loc[dup].groupby("name").groups.items():
        idx = list(idx)
        lat0 = loc.loc[idx, "lat"].mean()
        lon0 = loc.loc[idx, "lon"].mean()
        kx = math.cos(math.radians(lat0))
        tags = {}
        for i in idx:
            dx = (loc.loc[i, "lon"] - lon0) * kx
            dy = loc.loc[i, "lat"] - lat0
            ang = (math.degrees(math.atan2(dx, dy)) + 360) % 360
            tags[i] = COMPASS[int((ang + 22.5) % 360 // 45)]
        # A compass tag is only useful if it is unique within the group.
        if len(set(tags.values())) == len(idx):
            for i in idx:
                loc.loc[i, "name"] = f"{name} ({tags[i]} approach)"
        else:
            for n, i in enumerate(sorted(idx,
                    key=lambda j: -loc.loc[j, "epdo"]), start=1):
                loc.loc[i, "name"] = f"{name} (site {n})"
    return loc


def build_locations(df, years, label):
    sub = df[
        df["has_coords"]
        & df["at_junction"]
        & df["year"].isin(years)
        & df["city"].isin(CITIES)
    ].copy()

    n_years = len(years)
    log()
    log(f"CLUSTERING ({label}): {len(sub):,} geocoded junction crashes "
        f"across {n_years} years")

    if sub.empty:
        return pd.DataFrame()

    sub["cluster"] = cluster_points(
        sub["lat"].to_numpy(), sub["lon"].to_numpy(), CLUSTER_RADIUS_M
    )
    log(f"  -> {sub['cluster'].nunique():,} distinct locations "
        f"at a {CLUSTER_RADIUS_M} m radius")

    rows = []
    for cid, g in sub.groupby("cluster"):
        crashes = len(g)
        epdo = int(g["epdo"].sum())

        # Exposure uses only AADT values MassDOT documented a provenance for,
        # and takes the MAJOR approach (the maximum) rather than the median:
        # a crash recorded on the minor leg of an intersection carries that
        # leg's low AADT, which would understate how much traffic the junction
        # actually handles.
        usable = g.loc[g["aadt_usable"], "aadt"].dropna()
        aadt_major = float(usable.max()) if len(usable) else np.nan
        aadt_all = g["aadt"].dropna()

        if aadt_major == aadt_major and aadt_major > 0:
            exposure_mveh = aadt_major * 365 * n_years / 1_000_000
            risk = epdo / exposure_mveh
        else:
            exposure_mveh = np.nan
            risk = np.nan

        rows.append({
            "location_id": f"{label}-{cid:05d}",
            "name": intersection_name(g),
            "city": g["city"].mode().iat[0],
            "lat": round(float(g["lat"].mean()), 6),
            "lon": round(float(g["lon"].mean()), 6),
            "crashes": crashes,
            "epdo": epdo,
            "fatal": int(g["is_fatal"].sum()),
            "injury_crashes": int(g["is_injury"].sum()),
            "pdo_crashes": int(g["is_pdo"].sum()),
            "kabc_K": int((g["kabco"] == "K").sum()),
            "kabc_A": int((g["kabco"] == "A").sum()),
            "kabc_B": int((g["kabco"] == "B").sum()),
            "kabc_C": int((g["kabco"] == "C").sum()),
            "pedestrian": int(g["involves_pedestrian"].sum()),
            "bicyclist": int(g["involves_bicyclist"].sum()),
            "scooter": int(g["involves_scooter"].sum()),
            "vru_crashes": int(g["involves_vru"].sum()),
            "vru_share": round(float(g["involves_vru"].mean()), 4),
            "dark_crashes": int(g["is_dark"].sum()),
            "dark_share": round(float(g["is_dark"].mean()), 4),
            "wet_crashes": int(g["surface_wet_or_worse"].sum()),
            "speeding_crashes": int(g["circ_speeding"].sum()),
            "aadt_major": (round(aadt_major, 0)
                           if aadt_major == aadt_major else np.nan),
            "aadt_any_median": (round(float(aadt_all.median()), 0)
                                if len(aadt_all) else np.nan),
            "aadt_usable_crashes": int(len(usable)),
            "aadt_quality": (g.loc[g["aadt_usable"], "aadt_tier"].mode().iat[0]
                             if len(usable) else "none"),
            "speed_limit": (round(float(g["speed_limit"].median()), 0)
                            if g["speed_limit"].notna().any() else np.nan),
            "signalised": bool(g["has_signal"].mean() > 0.5),
            "sign_controlled": bool(g["has_sign_control"].mean() > 0.5),
            "uncontrolled": bool(g["no_control"].mean() > 0.5),
            "junction_type": g["RDWY_JNCT_TYPE_DESCR"].mode().iat[0],
            "exposure_mveh": (round(exposure_mveh, 2)
                              if exposure_mveh == exposure_mveh else np.nan),
            "risk_epdo_per_mveh": (round(risk, 3) if risk == risk else np.nan),
            "years": n_years,
        })

    loc = pd.DataFrame(rows)

    # Two rankings: the raw severity-weighted total (what MassDOT publishes),
    # and the exposure-adjusted rate (what answers "where is it dangerous per
    # vehicle, rather than merely busy").
    loc["rank_epdo"] = loc["epdo"].rank(ascending=False, method="min").astype(int)
    scored = loc["risk_epdo_per_mveh"].notna()
    loc["rank_risk"] = np.nan
    loc.loc[scored, "rank_risk"] = (
        loc.loc[scored, "risk_epdo_per_mveh"]
        .rank(ascending=False, method="min")
    )

    loc = loc.sort_values("epdo", ascending=False).reset_index(drop=True)
    loc = disambiguate(loc)
    log(f"  locations with an AADT denominator: {int(scored.sum()):,} "
        f"of {len(loc):,} ({100 * scored.mean():.1f}%)")
    return loc


# ---------------------------------------------------------------------------
# Aggregates for the website
# ---------------------------------------------------------------------------

def aggregates(df):
    out = {}
    d = df[df["city"].isin(CITIES)]

    out["agg_city_year"] = (
        d.groupby(["city", "year"], observed=True)
        .agg(crashes=("epdo", "size"),
             epdo=("epdo", "sum"),
             fatal=("is_fatal", "sum"),
             injury=("is_injury", "sum"),
             pedestrian=("involves_pedestrian", "sum"),
             bicyclist=("involves_bicyclist", "sum"),
             vru=("involves_vru", "sum"),
             dark=("is_dark", "sum"),
             speeding=("circ_speeding", "sum"),
             at_junction=("at_junction", "sum"))
        .reset_index()
    )

    out["agg_city_hour"] = (
        d.dropna(subset=["hour"])
        .groupby(["city", "hour"], observed=True)
        .agg(crashes=("epdo", "size"),
             vru=("involves_vru", "sum"),
             pedestrian=("involves_pedestrian", "sum"),
             bicyclist=("involves_bicyclist", "sum"))
        .reset_index()
    )

    out["agg_city_dow"] = (
        d.dropna(subset=["dow"])
        .groupby(["city", "dow", "dow_name"], observed=True)
        .agg(crashes=("epdo", "size"), vru=("involves_vru", "sum"))
        .reset_index()
    )

    for col, name in [
        ("RDWY_JNCT_TYPE_DESCR", "junction"),
        ("light_group", "light"),
        ("MANR_COLL_DESCR", "collision"),
        ("ROAD_SURF_COND_DESCR", "surface"),
        ("TRAF_CNTRL_DEVC_TYPE_DESCR", "control"),
    ]:
        out["agg_city_" + name] = (
            d.groupby(["city", col], observed=True)
            .agg(crashes=("epdo", "size"),
                 injury=("is_injury", "sum"),
                 vru=("involves_vru", "sum"))
            .reset_index()
            .rename(columns={col: name})
        )

    # Contributing circumstances, long format
    circ_cols = [c for c in d.columns if c.startswith("circ_")]
    recs = []
    for city, g in d.groupby("city", observed=True):
        base = int(g["DRVR_CNTRB_CIRC_CL"].notna().sum())
        for c in circ_cols:
            recs.append({
                "city": city,
                "factor": c.replace("circ_", ""),
                "crashes": int(g[c].sum()),
                "crashes_with_any_circumstance": base,
                "share_of_reported": round(g[c].sum() / base, 4) if base else np.nan,
            })
    out["agg_city_factor"] = pd.DataFrame(recs)

    return out


# ---------------------------------------------------------------------------
# Compare our ranking with MassDOT's published clusters
# ---------------------------------------------------------------------------

def _load_official(path):
    """Official clusters come either as GeoJSON polygons or, for the largest
    layer, as a pre-computed centroid CSV. Normalise both to records."""
    if path.endswith(".csv"):
        d = pd.read_csv(path)
        return [{"properties": r, "geometry": None,
                 "_lon": r.get("LON"), "_lat": r.get("LAT")}
                for r in d.to_dict("records")]
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)
    return [{"properties": f.get("properties") or {},
             "geometry": f.get("geometry") or {},
             "_lon": None, "_lat": None}
            for f in gj.get("features", [])]


def compare_official(loc, path, tag="top200"):
    if not os.path.exists(path):
        log(f"  (official cluster file not found at {path})")
        return None

    recs = []
    for f in _load_official(path):
        p = f["properties"]
        towns = (p.get("TOWNS") or "").upper()
        if not any(c in towns for c in CITIES):
            continue
        if f["_lon"] is not None and f["_lon"] == f["_lon"]:
            cx, cy = float(f["_lon"]), float(f["_lat"])
        else:
            coords, geom = [], f["geometry"] or {}

            def walk(node):
                if (isinstance(node, list) and len(node) == 2
                        and all(isinstance(v, (int, float)) for v in node)):
                    coords.append(node)
                elif isinstance(node, list):
                    for ch in node:
                        walk(ch)

            walk(geom.get("coordinates", []))
            if not coords:
                continue
            arr = np.array(coords)
            cx, cy = float(arr[:, 0].mean()), float(arr[:, 1].mean())
        recs.append({
            "official_id": p.get("Id"),
            "official_rank": p.get("Rank"),
            "towns": p.get("TOWNS"),
            "street_1": p.get("L1STREET"),
            "street_2": p.get("L2STREET"),
            "official_crashes": p.get("CrashCount"),
            "official_epdo": p.get("EPDO"),
            "num_K_A": p.get("NUM_K_A"),
            "num_B_C": p.get("NUM_B_C"),
            "num_O": p.get("NUM_O"),
            "lon": round(cx, 6),
            "lat": round(cy, 6),
        })

    off = pd.DataFrame(recs)
    off.insert(0, "layer", tag)
    log()
    log(f"OFFICIAL COMPARISON [{tag}]: {len(off):,} MassDOT clusters fall in "
        f"our three cities")
    if off.empty or loc.empty:
        return off

    # Verify we reproduce MassDOT's EPDO arithmetic exactly.
    chk = off.dropna(subset=["num_K_A", "num_B_C", "num_O", "official_epdo"])
    if len(chk):
        recomputed = ((chk["num_K_A"] + chk["num_B_C"]) * EPDO_INJURY
                      + chk["num_O"] * EPDO_PDO)
        match = int((recomputed == chk["official_epdo"]).sum())
        log(f"  EPDO formula check: reproduced {match:,} of {len(chk):,} "
            f"published EPDO values exactly "
            f"((K_A + B_C) x {EPDO_INJURY} + O x {EPDO_PDO})")

    # Nearest of our locations to each official cluster centroid.
    lat0 = float(loc["lat"].mean())
    mlat, mlon = 111_132.0, 111_320.0 * math.cos(math.radians(lat0))
    ours = np.column_stack([loc["lon"] * mlon, loc["lat"] * mlat])
    theirs = np.column_stack([off["lon"] * mlon, off["lat"] * mlat])
    tree = cKDTree(ours)
    dist, idx = tree.query(theirs, k=1)

    off["matched_location_id"] = loc["location_id"].to_numpy()[idx]
    off["matched_name"] = loc["name"].to_numpy()[idx]
    off["matched_epdo"] = loc["epdo"].to_numpy()[idx]
    off["match_distance_m"] = np.round(dist, 1)
    off["matched"] = off["match_distance_m"] <= 75

    log(f"  {int(off['matched'].sum()):,} of {len(off):,} official clusters "
        f"matched one of our locations within 75 m")
    return off


# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)

    df = clean(load())

    # The archival cleaned dataset - this is the "collected dataset" deliverable.
    keep_derived = [
        "CRASH_NUMB", "city", "year", "datetime", "hour", "dow_name", "month",
        "is_weekend", "lat", "lon", "has_coords",
        "CRASH_SEVERITY_DESCR", "kabco", "is_fatal", "is_injury", "is_pdo",
        "severity_known", "epdo", "n_fatal", "n_nonfatal", "n_vehicles",
        "aadt", "aadt_year", "AADT_DERIV", "aadt_tier", "aadt_usable",
        "speed_limit", "num_lanes",
        "involves_pedestrian", "involves_bicyclist", "involves_scooter",
        "involves_vru",
        "AMBNT_LIGHT_DESCR", "light_group", "is_dark",
        "ROAD_SURF_COND_DESCR", "surface_wet_or_worse",
        "WEATH_COND_DESCR",
        "RDWY_JNCT_TYPE_DESCR", "at_junction",
        "TRAF_CNTRL_DEVC_TYPE_DESCR", "has_signal", "has_sign_control",
        "no_control",
        "MANR_COLL_DESCR", "FIRST_HRMF_EVENT_DESCR", "HIT_RUN_DESCR",
        "F_CLASS", "JURISDICTN", "LT_SIDEWLK", "RT_SIDEWLK",
        "RDWY", "NEAR_INT_RDWY", "STREETNAME", "FROMSTREETNAME",
        "TOSTREETNAME",
        "DRVR_CNTRB_CIRC_CL", "NON_MTRST_TYPE_CL", "NON_MTRST_LOC_CL",
    ] + [c for c in df.columns if c.startswith("circ_")]

    clean_df = df[[c for c in keep_derived if c in df.columns]]
    clean_df.to_csv(os.path.join(OUT, "crashes_clean.csv"), index=False)
    log()
    log(f"WROTE data/out/crashes_clean.csv  {len(clean_df):,} rows x "
        f"{len(clean_df.columns)} cols")

    loc = build_locations(df, YEARS_ALL, "all")
    loc.to_csv(os.path.join(OUT, "locations.csv"), index=False)
    log(f"WROTE data/out/locations.csv  {len(loc):,} locations")

    loc3 = build_locations(df, [2021, 2022, 2023], "w3")
    loc3.to_csv(os.path.join(OUT, "locations_2021_2023.csv"), index=False)
    log(f"WROTE data/out/locations_2021_2023.csv  {len(loc3):,} locations")

    frames = []
    for path, tag, target in [
        (os.path.join(CLUSTER_DIR, "clusters_top200_2021_2023.geojson"), "top200", loc3),
        (os.path.join(CLUSTER_DIR, "clusters_hsip_2021_2023.geojson"), "hsip_all", loc3),
        (os.path.join(SLIM, "clusters_hsip_pedestrian_2014_2023_centroids.csv"), "hsip_ped", loc),
        (os.path.join(CLUSTER_DIR, "clusters_hsip_bicycle_2014_2023.geojson"), "hsip_bike", loc),
    ]:
        part = compare_official(target, path, tag)
        if part is not None and not part.empty:
            frames.append(part)
    if frames:
        off = pd.concat(frames, ignore_index=True)
        off.to_csv(os.path.join(OUT, "official_comparison.csv"), index=False)
        log(f"WROTE data/out/official_comparison.csv  {len(off):,} rows")

    for name, frame in aggregates(df).items():
        frame.to_csv(os.path.join(OUT, name + ".csv"), index=False)
        log(f"WROTE data/out/{name}.csv  {len(frame):,} rows")

    with open(os.path.join(OUT, "clean_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
