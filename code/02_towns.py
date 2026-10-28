"""Step 2. Towns: built-up areas (BUA22), their stations past and present, and their Census 2021 profile.

Reads (in place):
  _data8/ons_geo.json               BUA22 centroids and areas, MSOA21 to BUA22 lookup (OGL v3)
  _data8/lsoa21_bua22_lookup.json   LSOA21 to BUA22 best-fit lookup (OGL v3)
  _data8/census/census2021-ts001-lsoa.csv, _data11/census/census2021-{ts007a,ts045,ts062,ts066}-lsoa.csv  (OGL v3)
  _data8/ons_msoa_income_fye2023.xlsx  ONS small area income estimates FYE2023 (OGL v3)
  data/closed_stations.csv, data/open_stations.csv  from step 1

Writes:
  data/towns.csv  every built-up area in Great Britain: its stations (closed by year band, open in 1975, open today),
                  its railway group, and for England and Wales its 2021 residents, age, car, work, class and income

Railway group (main rule: a station counts for a town if it lies within 2 km of the area's centre, or within 1 km
beyond the edge of a circle with the same area as the town if that reaches further; checks use 1 km or 0.5 km beyond
the edge, and 3 km or 1.5 km beyond the edge):
  lost       at least one station closed 1955 to 1975, none open at the end of 1975, none today
  regained   at least one station closed 1955 to 1975, none open at the end of 1975, a National Rail station today
  kept       a station open at the end of 1975 and a National Rail station today
  lost_late  a station open at the end of 1975 but none today
  lost_early stations, all closed before 1955, none today
  new        no station in 1975 or before 1955 closures, but a National Rail station today (new since 1975)
  none       no listed station and none today
"""
import csv
import json
import math
import os
from collections import Counter, defaultdict

import numpy as np
import openpyxl
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "/home/claude/hist"
OUT = os.path.join(ROOT, "data")
KX, KY = 111.32 * math.cos(math.radians(54.0)), 110.57

closed = [r for r in csv.DictReader(open(os.path.join(OUT, "closed_stations.csv"), encoding="utf-8")) if r["lat"]]
openst = list(csv.DictReader(open(os.path.join(OUT, "open_stations.csv"), encoding="utf-8")))
for r in closed:
    r["y"] = int(r["year_closed"]) if r["year_closed"] else None
ctree = cKDTree(np.array([(float(r["lon"]) * KX, float(r["lat"]) * KY) for r in closed]))
# other rail stations mapped in OpenStreetMap today (metro, Underground, heritage lines): railway=station or halt
# more than 300 m from any National Rail station
import gzip, re
B = json.load(gzip.open(f"{H}/_data11/wd_osm_bundle11.json.gz"))["results"]["osm_stations"]["tsv"].split("\n")
nr_tree = cKDTree(np.array([(float(s["lon"]) * KX, float(s["lat"]) * KY) for s in openst]))
other = []
for l in B[1:]:
    f = l.split("\t")
    if len(f) < 8 or not f[1].endswith("Key:railway>") or f[2].strip('"') not in ("station", "halt"):
        continue
    lon, lat = float(f[6]), float(f[7])
    if nr_tree.query((lon * KX, lat * KY))[0] > 0.3:
        other.append((lon, lat, f[3].strip('"')))
other_tree = cKDTree(np.array([(o[0] * KX, o[1] * KY) for o in other]))
print("other rail stations in OSM (not National Rail)", len(other))
otree = cKDTree(np.array([(float(s["lon"]) * KX, float(s["lat"]) * KY) for s in openst]))

# ---------------------------------------------------------------- census by LSOA, summed to BUA22
geo = json.load(open(f"{H}/_data8/ons_geo.json", encoding="utf-8"))
lad_rgn = {r["LAD22CD"]: (r["RGN22NM"] or "Wales") for r in geo["msoa21_bua22_lookup"]}
look = json.load(open(f"{H}/_data8/lsoa21_bua22_lookup.json", encoding="utf-8"))
lsoa_bua = {r["LSOA21CD"]: r["BUA22CD"] for r in look if r["BUA22CD"]}
lsoa_lad = {r["LSOA21CD"]: r["LAD22CD"] for r in look}


def read(path, cols):
    """Return {lsoa: [values]} for the named columns (header text match)."""
    out = {}
    with open(path, encoding="utf-8") as f:
        rd = csv.reader(f)
        hdr = next(rd)
        idx = [hdr.index(c) for c in cols]
        for r in rd:
            out[r[2]] = [int(r[i]) for i in idx]
    return out


C = f"{H}/_data11/census"
pop = read(f"{H}/_data8/census/census2021-ts001-lsoa.csv", ["Residence type: Total; measures: Value"])
age_hdr = next(csv.reader(open(f"{C}/census2021-ts007a-lsoa.csv", encoding="utf-8")))
age = read(f"{C}/census2021-ts007a-lsoa.csv", ["Age: Total"] + [h for h in age_hdr if any(k in h for k in ("65 to 69", "70 to 74", "75 to 79", "80 to 84", "85 years"))])
car = read(f"{C}/census2021-ts045-lsoa.csv", ["Number of cars or vans: Total: All households", "Number of cars or vans: No cars or vans in household"])
P = "National Statistics Socio-economic Classification (NS-SEC): "
sec = read(f"{C}/census2021-ts062-lsoa.csv", [P + "Total: All usual residents aged 16 years and over",
                                               P + "L1, L2 and L3 Higher managerial, administrative and professional occupations",
                                               P + "L4, L5 and L6 Lower managerial, administrative and professional occupations",
                                               P + "L13 Routine occupations", P + "L15 Full-time students"])
E = "Economic activity status: "
eco = read(f"{C}/census2021-ts066-lsoa.csv", [E + "Total: All usual residents aged 16 years and over",
                                               E + "Economically active (excluding full-time students):In employment",
                                               E + "Economically active and a full-time student:In employment",
                                               E + "Economically inactive: Long-term sick or disabled",
                                               E + "Economically inactive: Retired"])
rgn_pop = defaultdict(Counter)
for l, b in lsoa_bua.items():
    if l in pop:
        rgn_pop[b][lad_rgn.get(lsoa_lad[l], "Wales" if l.startswith("W") else "")] += pop[l][0]
# per BUA: pop, age total, 65+, households, no car, NS-SEC total, L1-3, L4-6, L13, L15, 16+ total, in work,
# students in work, long-term sick, retired
agg = defaultdict(lambda: np.zeros(15))
for l, b in lsoa_bua.items():
    if l not in pop:
        continue
    a = age[l]
    agg[b] += np.array([pop[l][0], a[0], sum(a[1:]), car[l][0], car[l][1], *sec[l], *eco[l]], dtype=float)

# income: population-weighted mean of the MSOA estimates that best fit each BUA
msoa_pop = {}
with open(f"{H}/_data8/census/census2021-ts001-msoa.csv", encoding="utf-8") as f:
    for r in csv.reader(f):
        if r[0] == "2021":
            msoa_pop[r[2]] = int(r[3])
inc = {}
ws = openpyxl.load_workbook(f"{H}/_data8/ons_msoa_income_fye2023.xlsx", read_only=True)["Total annual income"]
for i, r in enumerate(ws.iter_rows(values_only=True)):
    if i >= 4 and r[0] and isinstance(r[6], (int, float)):
        inc[r[0]] = r[6]
iw, ip = defaultdict(float), defaultdict(float)
for r in geo["msoa21_bua22_lookup"]:
    b = r["BUA22CD"]
    if b and r["MSOA21CD"] in inc:
        p = msoa_pop.get(r["MSOA21CD"], 0)
        iw[b] += inc[r["MSOA21CD"]] * p
        ip[b] += p

# ---------------------------------------------------------------- stations near each BUA
bua = [b for b in geo["bua22_gb"] if b["BUA22CD"][0] in "EWS"]
big = np.array([(b["LONG"] * KX, b["LAT"] * KY) for b in bua if agg[b["BUA22CD"]][0] >= 100000])
btree = cKDTree(big)


def stations(b, rad):
    p = (b["LONG"] * KX, b["LAT"] * KY)
    cl = [closed[j] for j in ctree.query_ball_point(p, rad)]
    op = [openst[j] for j in otree.query_ball_point(p, rad)]
    c5575 = [r for r in cl if r["y"] and 1955 <= r["y"] <= 1975]
    open75 = [s for s in op if s["status_1975"] == "open_in_1975"] + [r for r in cl if r["y"] and r["y"] > 1975]
    early = [r for r in cl if r["y"] and r["y"] < 1955]
    if c5575 and not open75:
        g = "regained" if op else "lost"
    elif open75:
        g = "kept" if op else "lost_late"
    elif op:
        g = "new"
    elif early:
        g = "lost_early"
    else:
        g = "none"
    return g, cl, op, c5575, open75


rows = []
for b in bua:
    code = b["BUA22CD"]
    req = math.sqrt(b["Shape__Area"] / math.pi) / 1000
    a = agg.get(code)
    r = {"bua22cd": code, "bua22": b["BUA22NM"], "lat": round(b["LAT"], 5), "lon": round(b["LONG"], 5),
         "country": {"E": "England", "W": "Wales", "S": "Scotland"}[code[0]], "radius_km": round(req, 3)}
    if code[0] == "S":
        r["region"] = "Scotland"
    elif a is not None and a[0] > 0:
        r["region"] = rgn_pop[code].most_common(1)[0][0]
        pop_, at, a65, hh, nocar, st, l13, l46, l13r, l15, et, emp, emps, sick, ret = a
        r.update(pop2021=int(pop_), pct_65plus=round(a65 / at, 4), pct_no_car=round(nocar / hh, 4) if hh else "",
                 pct_managerial=round((l13 + l46) / (st - l15), 4) if st - l15 else "",
                 pct_routine=round(l13r / (st - l15), 4) if st - l15 else "",
                 pct_in_work=round((emp + emps) / et, 4) if et else "", pct_sick=round(sick / et, 4) if et else "",
                 income_fye2023=round(iw[code] / ip[code]) if ip[code] else "")
    r["km_to_city100k"] = round(float(btree.query((b["LONG"] * KX, b["LAT"] * KY))[0]), 2)
    for tag, base, edge in (("", 2.0, 1.0), ("_1km", 1.0, 0.5), ("_3km", 3.0, 1.5)):
        rad = max(base, req + edge)
        g, cl, op, c5575, open75 = stations(b, rad)
        r["group" + tag] = g
        if tag == "":
            r["n_closed_all"] = len(cl)
            r["n_closed_1955_75"] = len(c5575)
            r["closed_1955_75"] = "; ".join(f'{x["name"]} ({x["y"]})' for x in sorted(c5575, key=lambda x: x["y"]))
            r["last_closure"] = max([x["y"] for x in cl if x["y"]], default="")
            r["n_open_today"] = len(op)
            r["open_today"] = "; ".join(s["stationName"] for s in op)
            r["n_open_1975"] = len(open75)
            oth = sorted({other[j][2] for j in other_tree.query_ball_point((b["LONG"] * KX, b["LAT"] * KY), rad) if other[j][2]})
            r["n_other_rail_today"] = len(other_tree.query_ball_point((b["LONG"] * KX, b["LAT"] * KY), rad))
            r["other_rail_today"] = "; ".join(oth[:6])
    rows.append(r)

print(Counter(r["group"] for r in rows))
print("England and Wales with population:", sum(1 for r in rows if r.get("pop2021")))
cols = ["bua22cd", "bua22", "country", "region", "lat", "lon", "radius_km", "pop2021", "group", "group_1km", "group_3km",
        "n_closed_all", "n_closed_1955_75", "closed_1955_75", "last_closure", "n_open_1975", "n_open_today", "open_today", "n_other_rail_today", "other_rail_today",
        "pct_65plus", "pct_no_car", "pct_in_work", "pct_sick", "pct_managerial", "pct_routine", "income_fye2023", "km_to_city100k"]
rows.sort(key=lambda r: -(r.get("pop2021") or 0))
with open(os.path.join(OUT, "towns.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
