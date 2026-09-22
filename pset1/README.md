# Where to Fix the Streets First

A crash-prioritisation tool for **Boston, Cambridge and Somerville**, built on 37,929
MassDOT crash records from 2021–2025.

MIT 1.125 Agentic Computing Apprenticeship — Problem Set 01.

**Live site:** _(Codex Sites URL — add after publishing)_  
**Mirror:** https://yilinjiang7.github.io/mit1.125/pset1/site/  
**Demo video:** _(added after recording)_  
**Repository:** https://github.com/YilinJiang7/mit1.125

---

## What it does

A municipal safety engineer has a fixed budget and several thousand intersections.
Ranking by crash count just finds the busiest roads, which the engineer already knows.
This site ranks every intersection in the three cities by **how much harm happens there
per vehicle that passes through**, and shows why the three cities need different fixes.

- **3,758** intersections ranked, 2,828 of them with a usable traffic denominator
- Two rankings side by side: MassDOT's severity-weighted **EPDO** total, and EPDO **per
  million vehicles**
- Verified against MassDOT's own published cluster layers: the EPDO formula was
  reproduced exactly on **133 of 133** official clusters, and **125** of them were
  matched to an independently computed location within 75 m

## Headline findings

| | Boston | Cambridge | Somerville |
|---|---|---|---|
| Crashes 2021–2025 | 27,212 | 7,552 | 3,165 |
| Involving someone walking or cycling | 4.9% | **13.1%** | 11.4% |
| Cyclist involved | 1.7% | **7.6%** | 6.5% |
| Speeding a contributing factor | **9.0%** | 2.1% | 3.5% |
| In darkness | **36.3%** | 22.0% | 30.1% |
| At a junction | 29.3% | 40.3% | **44.1%** |
| Crashes causing injury | 27.5% | 23.0% | **31.1%** |

Three cities, three different problems: Cambridge's harm concentrates on people walking
and cycling, Boston's on speed and darkness along arterials, Somerville's on intersection
conflict.

---

## Opening the site

`site/index.html` needs no server, no build step and no network. Every byte it uses —
the data, the basemap, the fonts, the interaction code — is inside that one file, so
double-clicking it works. If you would rather serve it:

```bash
python3 -m http.server 8000 --directory site
```

Then open <http://localhost:8000/>.

---

## Reproducing the analysis

Python 3.9+ only. The download and slimming steps need nothing but the standard
library; the analysis step needs pandas, numpy and scipy.

```bash
pip install pandas numpy scipy               # only needed from step 3 on

python3 scripts/fetch_crashes.py             # 1. download from MassDOT  (~1 min)
python3 scripts/slim_data.py                 # 2. keep the analysis columns
python3 scripts/clean_and_score.py           # 3. clean, cluster, score, verify
python3 scripts/build_site_data.py           # 4. dictionary, payload, and the page
```

Each script works out its own paths from where it sits, so it does not matter which
directory you run them from.

Step 4 also writes `site/index.html` itself: it takes `site/_template.html`, inlines
`data/build/data.json` and the base64 basemap, and writes the finished self-contained
page. Edit the template, never `index.html`.

Every number on the site comes out of these four scripts. `fetch_crashes.py` checks each
year's row count against MassDOT's own `returnCountOnly` total and shouts if they differ.

### Two traps in the MassDOT API, recorded so nobody repeats them

- The 2023 service is `MASSDOT_ODP_OPEN_2023v` — **with a trailing `v`**. The predictable
  name returns 404.
- The 2021 service caps a response at **1,000** records; the others cap at 2,000. Paging
  that assumes "a short page means the end of the data" silently keeps 1,000 of 6,169
  rows. The script fetches the full `OBJECTID` list first, then pulls records in ID
  batches.

## Verification

The scoring is checked against MassDOT's own published cluster layers, which carry a
pre-computed `EPDO` value. Re-deriving it with
`(NUM_K_A + NUM_B_C) x 21 + NUM_O x 1` reproduces their number on every cluster:

| Official layer | Clusters in the three cities | EPDO reproduced | Located within 75 m |
|---|---|---|---|
| Top 200 Crash Clusters 2021–2023 | 11 | 11 | 11 |
| HSIP all-mode 2021–2023 | 61 | 61 | 61 |
| HSIP bicycle 2014–2023 | 37 | 37 | 35 |
| HSIP pedestrian 2014–2023 | 24 | 24 | 18 |
| **Total** | **133** | **133** | **125** |

The 8 that did not match on location are all pedestrian or bicycle clusters, where
MassDOT uses a 100 m radius over a 10-year window — a wider net than the 25 m, 5-year
clustering used here, so the difference is expected.

`clean_and_score.py` writes this comparison to `data/out/official_comparison.csv`, and
`fetch_crashes.py` reconciles each year's row count against MassDOT's own
`returnCountOnly` total, so a silently truncated download fails loudly.

Which raises the obvious question: if MassDOT already publishes a priority list, why
build this? Because theirs is statewide, and only **11 of its Top 200 clusters** fall in
these three cities. The rest are suburban arterials. A city budget needs a ranking
computed inside the city, against that city's own traffic.

---

### The AADT placeholder

4,822 crashes (12.7%) carry the identical AADT value **1,154** with an empty
`AADT_DERIV`, almost always on roads classed `Local`. It is a statewide placeholder for
streets with no traffic count, not a measurement. Dividing by it puts quiet residential
side streets at the top of the risk table. An AADT is treated as usable exposure only
when `AADT_DERIV` records how it was obtained.

---

## Files

```
scripts/
  fetch_crashes.py     1. downloads MassDOT crash records + official cluster layers
  slim_data.py         2. reduces the raw 124-column download to the 57 columns used
  clean_and_score.py   3. cleaning, 25 m clustering, EPDO scoring, official verification
  build_site_data.py   4. field dictionary, page payload, and the finished index.html

site/
  _template.html       the page before data is inlined - edit this one
  index.html           the published site: five tabs, self-contained, data inlined
  method.html          redirect kept for older links -> index.html#method
  data/                the collected dataset, zipped - this is the deliverable

data/                  everything the scripts generate. None of it is committed.
  raw/                 MassDOT download, ~120 MB      (step 1)
  slim/                the 57 kept columns, gzipped   (step 2)
  out/                 cleaned dataset + aggregates   (step 3)
  build/               data.json + basemap.png        (step 4)
```

Both HTML pages are fully self-contained: no CDN, no external fonts, no API calls at
run time. They work from a web host, from GitHub Pages, or straight off a USB stick.

---

## Method in three lines

1. **EPDO** — MassDOT's severity weighting: any injury crash counts 21, a
   property-damage-only crash counts 1. Verified by reproducing the published `EPDO`
   value on 133 official cluster polygons exactly.
2. **Clustering** — crashes within 25 m of each other, restricted to four-way, T, Y and
   five-point junctions. Both parameters match MassDOT's published method.
3. **Exposure** — `EPDO ÷ (AADT_major × 365 × 5 years ÷ 1,000,000)` = EPDO points per
   million vehicles.

Full detail, including everything discarded and everything the result cannot prove, is on
the site's **Data & method** and **Limits & reflection** tabs.

---

## Data sources

| Source | What | Licence |
|---|---|---|
| [MassDOT IMPACT open crash data](https://gis.data.mass.gov/datasets/MassDOT::2025-crashes) | 37,929 crash records, 2021–2025 | Public domain |
| [MassDOT Top 200 Crash Clusters 2021–2023](https://gis.data.mass.gov/datasets/MassDOT::top-200-crash-clusters-2021-2023) | Official prioritisation, used for verification | Public domain |
| [MassDOT Top Crash Locations](https://www.mass.gov/info-details/top-crash-locations-and-maps) | Cluster methodology and EPDO weighting | — |
| [MA Law Enforcement Crash Report E-Manual](https://masscrashreportmanual.com/data-dictionary/) | Field definitions (MMUCC 5th ed.) | — |
| [BPDA 2025 neighbourhood population](https://data.boston.gov/dataset/2025-boston-population-estimates-neighborhood-level) | Boston population, context only | — |
| [City of Cambridge ACS by neighbourhood](https://data.cambridgema.gov/d/jabj-v7kz) | Cambridge population, context only | — |

Data accessed 21 September 2026.

---

## A note on what this is

An educational project for a course, not an official product of MassDOT, Boston,
Cambridge or Somerville, and not a safety audit. The rankings are a screening list —
places worth sending an engineer to look at. They are not a finding that any particular
intersection is unsafe. Source data remain attributed to MassDOT and the Massachusetts
RMV.

---

Yilin Jiang · September 2026
