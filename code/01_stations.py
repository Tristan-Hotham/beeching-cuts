"""Step 1. Closed stations: parse the Wikipedia lists, place each station, and build the stations open today.

Reads (in place):
  _data11/wikipedia_batch11.json.gz  "List of closed railway stations in Great Britain: A" to "W to Z" (CC BY-SA 4.0)
  _data11/wd_osm_bundle11.json.gz    wd_stations (Wikidata, CC0) and osm_stations (OpenStreetMap, ODbL)
  osnames_gb.tsv                     OS Open Names (OGL v3), last-resort placing by town name
  uk-railway-stations/stations.csv   National Rail stations open today (davwheat/uk-railway-stations, ODbL;
                                     from Trainline EU's stations data), cloned from GitHub; path as argv[1]

Writes:
  data/closed_stations.csv  one row per list entry: name, link, company, closure year, reopening year if noted,
                            coordinates and how they were found
  data/open_stations.csv    National Rail stations today, with a flag for those that were closed at the end of
                            1975 (reopened or rebuilt since) or that are new since 1975

Usage:
  python3 code/01_stations.py /path/to/uk-railway-stations
"""
import csv
import gzip
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import numpy as np
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "/home/claude/hist"
NR_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TMPDIR", "/tmp"), "uk-railway-stations")
OUT = os.path.join(ROOT, "data")
KX, KY = 111.32 * math.cos(math.radians(54.0)), 110.57


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("saint ", "st ").replace("st. ", "st ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def km(a, b):
    return math.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY)


# ---------------------------------------------------------------- 1. parse the lists
A = json.load(gzip.open(f"{H}/_data11/wikipedia_batch11.json.gz"))["articles"]
pages, seen = [], set()
for k, v in A.items():
    if k.startswith("List of closed railway stations in Britain:") and not v["missing"] and v["title"] not in seen:
        seen.add(v["title"])
        pages.append(v)


def strip_markup(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{efn.*?\}\}", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return s


def plain(s):
    s = re.sub(r"\{\{(?:[Ss]tnlnk|rws|[Ss]tnlink|stn)\|([^}|]+)(?:\|[^}]*)?\}\}", r"\1", s)
    s = re.sub(r"\{\{[Cc]irca\|([^}]*)\}\}", r"c. \1", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", "; ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"\s+[\u2013\u2014]\s+", ", ", s)
    s = re.sub(r"(\d)[\u2013\u2014](\d)", r"\1 to \2", s).replace("\u2013", " ").replace("\u2014", " ")
    return re.sub(r"\s+", " ", s).strip(" ;")


rows = []
for pg in pages:
    letter = pg["title"].split(":")[-1].strip().replace("–", " to ")
    text = strip_markup(pg["text"])
    for tb in re.findall(r"\{\|(.*?)\n\|\}", text, re.S):
        for r in tb.split("\n|-")[1:]:
            r = r.strip("\n")
            if not r.startswith("|") or r.startswith("|}"):
                continue
            cells = [c.strip() for c in re.split(r"\n\||\|\|", "\n" + r)[1:]]
            if len(cells) < 3 or not cells[0]:
                continue
            raw = cells[0]
            # link target
            target = None
            m = re.match(r"\{\{(?:[Ss]tnlnk|rws|[Ss]tnlink)\|([^}|]+)(?:\|([^}|]+))?\}\}", raw)
            if m:
                target = (m.group(1).strip() + (f" ({m.group(2).strip()})" if m.group(2) else "") + " railway station")
                alt_target = None if m.group(2) else m.group(1).strip() + " railway station"
            else:
                m = re.match(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", raw)
                if m:
                    target = m.group(1).strip()
                alt_target = None
            name = plain(raw)
            hint = re.search(r"\(\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*\)\s*$", raw)
            company = plain(cells[1]) if len(cells) > 1 else ""
            ycell = cells[2] if len(cells) > 2 else ""
            notes = plain(cells[3]) if len(cells) > 3 else ""
            ytext = plain(ycell)
            low = (ytext + " " + notes).lower()
            reopen = None
            mm = re.search(r"(?:re-?opened|reopening|new station opened|now reopened)\D{0,40}?(\d{4})", low)
            if mm:
                reopen = int(mm.group(1))
            ypart = re.split(r"re-?open|new station|now reopened", ytext.lower())[0]
            years = [int(y) for y in re.findall(r"(?<!\d)(1[89]\d\d|20[0-2]\d)(?!\d)", ypart)]
            year = max(years) if years else None
            rows.append({"name": name, "link": target or "", "alt_link": alt_target or "", "county_hint": hint.group(1) if hint else "",
                         "company": company, "year_closed": year, "year_cell": ytext, "notes": notes,
                         "reopened_year": reopen, "reopen_noted": int(bool(re.search(r"re-?open|new station|now preserved|heritage", low))),
                         "list_page": letter})
print("list rows", len(rows), "with year", sum(1 for r in rows if r["year_closed"]))

# ---------------------------------------------------------------- 2. Wikidata and OSM stations
B = json.load(gzip.open(f"{H}/_data11/wd_osm_bundle11.json.gz"))["results"]


def tsv(key):
    lines = B[key]["tsv"].split("\n")
    hdr = [h.lstrip("?") for h in lines[0].split("\t")]
    return [dict(zip(hdr, l.split("\t"))) for l in lines[1:] if l]


wd = defaultdict(lambda: {"label": "", "coords": [], "open": set(), "close": set(), "use": set()})
for r in tsv("wd_stations"):
    q = r["s"].rsplit("/", 1)[-1].rstrip(">")
    it = wd[q]
    if r["label"]:
        it["label"] = r["label"].split('"')[1]
    m = re.match(r"POINT\(([-\d.]+) ([-\d.]+)\)", r["coord"])
    if m:
        c = (float(m.group(1)), float(m.group(2)))
        if c not in it["coords"]:
            it["coords"].append(c)
    for k in ("open", "close"):
        if r[k][:4].isdigit():
            it[k].add(int(r[k][:4]))
    if r["dis"][:4].isdigit():
        it["close"].add(int(r["dis"][:4]))
    if r["use"]:
        it["use"].add(r["use"].rsplit("/", 1)[-1].rstrip(">"))
for q, it in wd.items():
    if it["coords"]:
        it["lon"] = sum(c[0] for c in it["coords"]) / len(it["coords"])
        it["lat"] = sum(c[1] for c in it["coords"]) / len(it["coords"])
wd_by_label = defaultdict(list)
for q, it in wd.items():
    if it["label"] and it.get("lat") and 49.8 < it["lat"] < 61 and -8.7 < it["lon"] < 2:
        wd_by_label[norm(it["label"])].append(q)
print("wikidata station items", len(wd))

osm_closed = defaultdict(list)
osm_all = []
for r in tsv("osm_stations"):
    k = r["k"].rsplit(":", 1)[-1].rstrip(">") if "Key:" in r["k"] else r["k"]
    key = r["k"].split("Key:")[-1].rstrip(">")
    nm = r["name"].split('"')[1] if r["name"].startswith('"') else ""
    try:
        lon, lat = float(r["lon"]), float(r["lat"])
    except ValueError:
        continue
    osm_all.append({"key": key, "v": r["v"].strip('"'), "name": nm, "lon": lon, "lat": lat, "osm": r["osm"].strip("<>")})
    if key.startswith(("disused:", "abandoned:", "historic", "was:")) and nm:
        osm_closed[norm(nm)].append((lon, lat, r["osm"].strip("<>")))
print("osm station objects", len(osm_all))

osn = defaultdict(list)
with open(f"{H}/osnames_gb.tsv", encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["type"] == "populatedPlace" and r["local_type"] in ("City", "Town", "Village", "Hamlet", "Suburban Area", "Other Settlement"):
            osn[norm(r["name1"])].append((float(r["lon"]), float(r["lat"]), r["county"] or r["district"], r["local_type"]))

# ---------------------------------------------------------------- 3. place each closed station
SUFFIX = re.compile(r"\s+(halt|platform|station|junction|road|central|town|north|south|east|west|high level|low level|"
                    r"new|old|lower|upper|bridge|gate|sidings|parkway)$")
method = Counter()
wd_used = Counter()
for r in rows:
    r["lat"] = r["lon"] = None
    r["wikidata"] = ""
    r["geo_method"] = ""
    cands = []
    for t in (r["link"], r["alt_link"], re.sub(r"\s*\((?:1st|2nd|3rd|first|second|third)\)\s*$", "", r["name"], flags=re.I) + " railway station"):
        if t:
            cands = wd_by_label.get(norm(t), [])
            if len(cands) > 1 and r["year_closed"]:
                cc = [q for q in cands if r["year_closed"] in wd[q]["close"]]
                cands = cc or cands
            if cands:
                break
    if len(cands) == 1 or (len(cands) > 1 and max(km((wd[a]["lon"], wd[a]["lat"]), (wd[b]["lon"], wd[b]["lat"])) for a in cands for b in cands) < 1.5):
        q = cands[0]
        r.update(lat=round(wd[q]["lat"], 5), lon=round(wd[q]["lon"], 5), wikidata=q, geo_method="wikidata_label")
        wd_used[q] += 1
        method["wikidata_label"] += 1
        continue
    base = re.sub(r"\s*\([^)]*\)\s*", " ", r["name"]).strip()
    oc = osm_closed.get(norm(base), [])
    if oc and max(km(a[:2], b[:2]) for a in oc for b in oc) < 1.5:
        r.update(lat=round(oc[0][1], 5), lon=round(oc[0][0], 5), geo_method="osm_closed_station_name", osm=oc[0][2])
        method["osm_closed_station_name"] += 1
        continue
    # last resort: the place the station is named after, if that name is unique in OS Open Names
    nm = norm(base)
    nm2 = SUFFIX.sub("", nm)
    if nm2 == nm or not nm.endswith(" road"):
        pc = osn.get(nm2, [])
        par = re.findall(r"\(([^)]*)\)", r["name"])
        hint = r["county_hint"] or (par[-1] if par else "")
        if hint:
            pc = [p for p in pc if norm(hint).split(" ")[0] in norm(p[2])]
        if len(pc) == 1:
            r.update(lat=round(pc[0][1], 5), lon=round(pc[0][0], 5), geo_method="osnames_place")
            method["osnames_place"] += 1
            continue
    method["unplaced"] += 1
print("placing:", dict(method))

# Wikidata closure year agreement (a check on the list's years)
agree = Counter()
for r in rows:
    if r["wikidata"] and r["year_closed"] and wd[r["wikidata"]]["close"]:
        ys = wd[r["wikidata"]]["close"]
        agree["exact" if r["year_closed"] in ys else ("within1" if any(abs(y - r["year_closed"]) <= 1 for y in ys) else "differ")] += 1
print("wikidata closure year agreement", dict(agree))

# ---------------------------------------------------------------- 4. stations open today (National Rail)
nr = list(csv.DictReader(open(os.path.join(NR_DIR, "stations.csv"), encoding="utf-8")))
nr = [s for s in nr if s["lat"] and s["constituentCountry"] in ("england", "scotland", "wales")]
for s in nr:
    s["lat"], s["lon"] = float(s["lat"]), float(s["long"])
print("National Rail stations", len(nr))


def tokens(s):
    return {t for t in norm(re.sub(r"\([^)]*\)", " ", s)).split() if t not in ("railway", "station", "halt", "and", "the", "for", "on", "upon", "road")}


def full_tokens(s):
    return {t for t in norm(s).split() if t not in ("railway", "station", "halt", "and", "the", "for", "on", "upon", "1st", "2nd", "first", "second")}


TOWNISH = {"town", "central", "general", "high", "low", "level", "north", "south", "east", "west", "joint", "new", "parkway"}
# a reopened station that the lists leave unplaced takes the point of the National Rail station of the same name
nr_by_tokens = defaultdict(list)
for s in nr:
    nr_by_tokens[frozenset(tokens(s["stationName"]) - TOWNISH)].append(s)
for r in rows:
    if r["lat"] is None and r["reopened_year"]:
        c = nr_by_tokens.get(frozenset(tokens(r["name"]) - TOWNISH), [])
        if len(c) == 1:
            r.update(lat=round(c[0]["lat"], 5), lon=round(c[0]["lon"], 5), geo_method="national_rail_name")
            method["unplaced"] -= 1
            method["national_rail_name"] += 1

# ---------------------------------------------------------------- 5. Wikidata closures 1955 to 1975 missing from the lists
placed = np.array([(r["lon"] * KX, r["lat"] * KY) for r in rows if r["lat"] is not None])
ptree = cKDTree(placed)
wd_extra = []
for q, it in wd.items():
    if not it.get("lat") or not it["close"] or q in wd_used or not it["label"].endswith("railway station"):
        continue
    if 54.0 < it["lat"] < 55.4 and it["lon"] < -5.45:   # Northern Ireland
        continue
    y = max(it["close"])
    if 1955 <= y <= 1975 and 49.8 < it["lat"] < 61 and -8.7 < it["lon"] < 2:
        d, _ = ptree.query((it["lon"] * KX, it["lat"] * KY))
        if d > 0.5:
            wd_extra.append({"name": it["label"].replace(" railway station", ""), "link": it["label"], "company": "",
                             "year_closed": y, "year_cell": "", "reopened_year": None, "reopen_noted": 0, "notes": "",
                             "lat": round(it["lat"], 5), "lon": round(it["lon"], 5), "geo_method": "wikidata_only",
                             "wikidata": q, "list_page": "Wikidata"})
print("Wikidata stations closed 1955 to 1975, in Great Britain, with no list station within 500 m:", len(wd_extra),
      [w["name"] for w in wd_extra])
rows.extend(wd_extra)

# ---------------------------------------------------------------- 6. which of today's stations were closed at the end of 1975
wd_pts = [(q, it) for q, it in wd.items() if it.get("lat")]
wtree = cKDTree(np.array([(it["lon"] * KX, it["lat"] * KY) for _, it in wd_pts]))
placed_rows = [r for r in rows if r["lat"] is not None]
ctree = cKDTree(np.array([(r["lon"] * KX, r["lat"] * KY) for r in placed_rows]))
for s in nr:
    p = (s["lon"] * KX, s["lat"] * KY)
    tk = tokens(s["stationName"])
    best = None
    for j in wtree.query_ball_point(p, 1.0):
        q, it = wd_pts[j]
        if tokens(it["label"]) & tk:
            d = km((it["lon"], it["lat"]), (s["lon"], s["lat"]))
            if best is None or d < best[0]:
                best = (d, q)
    s["wikidata"] = best[1] if best else ""
    opens = sorted(wd[best[1]]["open"]) if best else []
    s["wd_open_years"] = ";".join(map(str, opens))
    # list entries for the same station: within 1 km, closed 1950 to 1975 (or earlier with a reopening noted), and
    # the same name, or a name that contains the other's when the list notes a reopening after 1975
    closed_then, nearby = [], []
    for j in ctree.query_ball_point(p, 1.0):
        r = placed_rows[j]
        rt = tokens(r["name"])
        if not (r["year_closed"] and r["year_closed"] <= 1975 and rt):
            continue
        if not (r["year_closed"] >= 1950 or r["reopen_noted"]):
            continue
        if rt & tk:
            nearby.append(r)
        same = full_tokens(r["name"]) == full_tokens(s["stationName"])
        reo = r["reopened_year"] and r["reopened_year"] > 1975 and (rt <= tk or tk <= rt or (rt - TOWNISH) == (tk - TOWNISH))
        if same or reo:
            closed_then.append(r)
    s["closed_list_match"] = "; ".join(f'{r["name"]} ({r["year_closed"]}' + (f', reopened {r["reopened_year"]})' if r["reopened_year"] else ")") for r in closed_then)
    reopened_by_1975 = any(r["reopened_year"] and r["reopened_year"] <= 1975 for r in closed_then)
    if closed_then and not reopened_by_1975:
        st = "reopened_after_1975"
    elif opens and min(opens) > 1975:
        st = "new_after_1975"
    elif opens and min(opens) <= 1975 and max(opens) > 1975 and nearby and not reopened_by_1975:
        st = "reopened_after_1975"
    else:
        st = "open_in_1975"
    s["status_1975"] = st
print("open stations by 1975 status", Counter(s["status_1975"] for s in nr))
print("placing:", dict(method))

# store the linked article as a URL-style title (en dashes in titles percent-encoded)
for r in rows:
    r["link"] = r["link"].replace(" ", "_").replace("\u2013", "%E2%80%93").replace("\u2014", "%E2%80%94")
cols = ["name", "link", "company", "year_closed", "year_cell", "reopened_year", "reopen_noted", "notes", "lat", "lon",
        "geo_method", "wikidata", "list_page"]
with open(os.path.join(OUT, "closed_stations.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(OUT, "open_stations.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["stationName", "crsCode", "constituentCountry", "lat", "lon", "wikidata", "wd_open_years",
                                      "closed_list_match", "status_1975"], extrasaction="ignore")
    w.writeheader()
    w.writerows(nr)
json.dump({"n_list_pages": len(pages), "n_rows": len(rows), "n_with_year": sum(1 for r in rows if r["year_closed"]),
           "placing": dict(method), "wd_year_agreement": dict(agree), "n_wd_items": len(wd),
           "n_wd_with_close": sum(1 for it in wd.values() if it["close"]), "n_osm_objects": len(osm_all),
           "wd_extra_1955_75": len(wd_extra),
           "n_nr": len(nr), "nr_status": dict(Counter(s["status_1975"] for s in nr))},
          open(os.path.join(OUT, "_station_stats.json"), "w"), indent=1)
