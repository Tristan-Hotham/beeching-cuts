"""Step 3. Analysis: closures by year, which towns lost their railway, and how those towns compare today.

Reads data/closed_stations.csv, data/open_stations.csv, data/towns.csv (steps 1 and 2) and
_data11/wikipedia_batch11.json.gz (Beeching cuts article, for the report's own figures, quoted with their source).
Writes data/results.json (every number used on the page, in the paper, the blog post and the collage) and
_site_data.json (compact map and chart data for the page; a temporary build file).

Comparisons use built-up areas in England and Wales with 2,000 to 100,000 residents in 2021 (Census outcomes exist
only for England and Wales). Each "lost" town is matched with replacement to the "kept" town in the same region with
the nearest 2021 population (on a log scale, within a factor of 1.25). Regressions add log population, region and
distance to the nearest city of 100,000 or more. All of this is association: the closures picked places that were
smaller, more rural and less used, and 2021 size may itself reflect the closures.
"""
import csv
import gzip
import json
import math
import os
import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "/home/claude/hist"
D = os.path.join(ROOT, "data")
rng = np.random.default_rng(1963)

cs = pd.read_csv(os.path.join(D, "closed_stations.csv"))
op = pd.read_csv(os.path.join(D, "open_stations.csv"))
tw = pd.read_csv(os.path.join(D, "towns.csv"))
st = json.load(open(os.path.join(D, "_station_stats.json")))
R = {}

# ---------------------------------------------------------------- 1. stations
lst = cs[cs.list_page != "Wikidata"]
yrs = cs.year_closed.dropna().astype(int)
R["stations"] = {
    "n_list_pages": st["n_list_pages"], "n_list_rows": int(len(lst)), "n_list_with_year": int(lst.year_closed.notna().sum()),
    "n_wikidata_only_1955_75": int((cs.list_page == "Wikidata").sum()),
    "n_all": int(len(cs)), "n_placed": int(cs.lat.notna().sum()), "share_placed": float(cs.lat.notna().mean()),
    "placing": {k: int(v) for k, v in cs.geo_method.fillna("unplaced").value_counts().items()},
    "wd_items": st["n_wd_items"], "wd_with_close": st["n_wd_with_close"],
    "wd_year_check_n": int(sum(st["wd_year_agreement"].values())), "wd_year_exact": st["wd_year_agreement"].get("exact", 0),
    "wd_year_share_exact": st["wd_year_agreement"].get("exact", 0) / sum(st["wd_year_agreement"].values()),
}
by_year = yrs.value_counts().sort_index()
R["stations"]["first_year"] = int(by_year.index.min())
R["stations"]["by_year"] = {int(k): int(v) for k, v in by_year.items()}
w = cs[(cs.year_closed >= 1955) & (cs.year_closed <= 1975)]
R["stations"]["n_1955_75"] = int(len(w))
R["stations"]["share_1955_75"] = float(len(w) / yrs.size)
R["stations"]["n_1955_75_placed"] = int(w.lat.notna().sum())
R["stations"]["share_1955_75_placed"] = float(w.lat.notna().mean())
R["stations"]["n_1963_70"] = int(((cs.year_closed >= 1963) & (cs.year_closed <= 1970)).sum())
R["stations"]["n_1960s"] = int(((cs.year_closed >= 1960) & (cs.year_closed <= 1969)).sum())
pk = by_year.loc[1945:2000]
R["stations"]["peak_year"] = int(pk.idxmax())
R["stations"]["peak_n"] = int(pk.max())
R["stations"]["n_before_1955"] = int((yrs < 1955).sum())
R["stations"]["n_after_1975"] = int((yrs > 1975).sum())
R["stations"]["n_1930s"] = int(((yrs >= 1930) & (yrs <= 1939)).sum())
dec = (yrs // 10 * 10).value_counts().sort_index()
R["stations"]["by_decade"] = {int(k): int(v) for k, v in dec.items()}
R["stations"]["n_reopen_noted"] = int(lst.reopened_year.notna().sum())
R["stations"]["n_reopen_noted_1955_75"] = int(w.reopened_year.notna().sum())
R["open"] = {"n_national_rail": int(len(op)), "status": {k: int(v) for k, v in op.status_1975.value_counts().items()}}

# the report's own figures, as given in the Wikipedia article (quoted, not computed)
art = json.load(gzip.open(f"{H}/_data11/wikipedia_batch11.json.gz"))["articles"]["The Reshaping of British Railways"]["text"]
assert "2,363 stations" in art and "27 March 1963" in art and "4,300 stations open to passengers in 1960" in art
R["context"] = {"report_stations": 2363, "report_miles": 5000, "report_date": "27 March 1963", "stations_1960": 4300,
                "source": "Wikipedia, Beeching cuts (CC BY-SA 4.0), retrieved 28 October 2026"}

# ---------------------------------------------------------------- 2. towns
tw["logpop"] = np.log(tw.pop2021)
ew = tw[tw.pop2021.notna()].copy()
S = ew[(ew.pop2021 >= 2000) & (ew.pop2021 <= 100000)].copy()
GROUPS = ["kept", "lost", "regained", "lost_late", "lost_early", "new", "none"]
R["towns"] = {"n_bua_gb": int(len(tw)), "n_bua_ew": int(len(ew)), "n_sample": int(len(S)),
              "groups_sample": {g: int((S.group == g).sum()) for g in GROUPS},
              "groups_gb": {g: int((tw.group == g).sum()) for g in GROUPS},
              "groups_scotland": {g: int(((tw.country == "Scotland") & (tw.group == g)).sum()) for g in GROUPS}}
had55 = S[S.group.isin(["kept", "lost", "regained", "lost_late"])]
R["towns"]["n_had_station_1955"] = int(len(had55))
R["towns"]["share_lost_of_had"] = float((had55.group == "lost").mean())
R["towns"]["share_lost_or_regained_of_had"] = float(had55.group.isin(["lost", "regained"]).mean())
R["towns"]["share_regained_of_lostall"] = float((had55.group == "regained").sum() / had55.group.isin(["lost", "regained"]).sum())
# by size band
bands = [(2000, 5000), (5000, 10000), (10000, 20000), (20000, 50000), (50000, 100000)]
bs = []
for lo, hi in bands:
    h = had55[(had55.pop2021 >= lo) & (had55.pop2021 < hi if hi < 100000 else had55.pop2021 <= hi)]
    bs.append({"lo": lo, "hi": hi, "n": int(len(h)), "lost": int((h.group == "lost").sum()), "regained": int((h.group == "regained").sum()),
               "kept": int((h.group == "kept").sum()), "share_lost": float((h.group == "lost").mean())})
R["towns"]["by_size"] = bs
med = {}
for g in ["kept", "lost", "regained"]:
    x = S[S.group == g]
    med[g] = {"n": int(len(x)), "median_pop": float(x.pop2021.median()), "median_km_city": float(x.km_to_city100k.median())}
R["towns"]["medians"] = med
# by region
reg = []
for rg, h in had55.groupby("region"):
    reg.append({"region": rg, "n": int(len(h)), "lost": int((h.group == "lost").sum()), "share_lost": float((h.group == "lost").mean())})
R["towns"]["by_region"] = sorted(reg, key=lambda r: -r["share_lost"])

# largest towns that lost every station and have none today (whole of England and Wales, any size)
L = ew[ew.group == "lost"].sort_values("pop2021", ascending=False)
R["towns"]["n_lost_ew_all"] = int(len(L))
R["towns"]["n_lost_ew_10k"] = int((L.pop2021 >= 10000).sum())
R["towns"]["n_lost_ew_20k"] = int((L.pop2021 >= 20000).sum())
R["towns"]["pop_lost_ew"] = int(L.pop2021.sum())
R["towns"]["n_lost_other_rail"] = int((S[S.group == "lost"].n_other_rail_today > 0).sum())


def short(r):
    return {"name": r.bua22, "pop": int(r.pop2021), "region": r.region, "closed": r.closed_1955_75, "last": int(r.last_closure) if pd.notna(r.last_closure) else None,
            "other": r.other_rail_today if isinstance(r.other_rail_today, str) else ""}


R["towns"]["top_lost"] = [short(r) for r in L.head(25).itertuples()]
G = ew[ew.group == "regained"].sort_values("pop2021", ascending=False)
R["towns"]["n_regained_ew"] = int(len(G))
R["towns"]["top_regained"] = [dict(short(r), today=r.open_today) for r in G.head(25).itertuples()]
SC = tw[(tw.country == "Scotland") & (tw.group.isin(["lost", "regained"]))]
R["towns"]["scotland_regained"] = sorted(tw[(tw.country == "Scotland") & (tw.group == "regained")].bua22.tolist())

# ---------------------------------------------------------------- 3. outcomes
OUT = {"pct_65plus": "Aged 65 or over", "pct_no_car": "Households without a car or van", "pct_in_work": "Adults (16+) in work",
       "pct_sick": "Adults long-term sick or disabled", "pct_managerial": "Adults in managerial or professional jobs",
       "income_fye2023": "Mean household income (MSOA, FYE2023)"}
R["outcomes"] = {"labels": OUT}
S["income_k"] = S.income_fye2023 / 1000
S["logkm"] = np.log1p(S.km_to_city100k)

desc = {}
for g in ["kept", "lost", "regained", "lost_early", "none"]:
    x = S[S.group == g]
    desc[g] = {"n": int(len(x))}
    for o in OUT:
        desc[g][o] = float(x[o].median()) if x[o].notna().any() else None
        desc[g][o + "_n"] = int(x[o].notna().sum())
R["outcomes"]["median"] = desc


def matched(treat, ctrl, outcome, tol=math.log(1.25)):
    """Each treated town against the control town in the same region with the nearest log population."""
    diffs, pairs = [], []
    for rg, t in treat.groupby("region"):
        c = ctrl[(ctrl.region == rg) & ctrl[outcome].notna()]
        if c.empty:
            continue
        cl, cv = c.logpop.values, c[outcome].values
        for r in t.itertuples():
            v = getattr(r, outcome)
            if pd.isna(v):
                continue
            j = np.argmin(np.abs(cl - r.logpop))
            if abs(cl[j] - r.logpop) <= tol:
                diffs.append(v - cv[j])
                pairs.append(j)
    d = np.array(diffs)
    if len(d) < 5:
        return None
    boots = [rng.choice(d, len(d)).mean() for _ in range(2000)]
    return {"n": int(len(d)), "diff": float(d.mean()), "lo": float(np.percentile(boots, 2.5)), "hi": float(np.percentile(boots, 97.5)),
            "share_higher": float((d > 0).mean())}


def models(df, groups=("lost", "regained")):
    out = {}
    df = df[df.group.isin(("kept",) + tuple(groups))].copy()
    for o in OUT:
        y = "income_k" if o == "income_fye2023" else o
        dd = df[df[y].notna()]
        res = {}
        for name, f in (("size_region", f"{y} ~ C(group, Treatment('kept')) + logpop + I(logpop**2) + C(region)"),
                        ("plus_remote", f"{y} ~ C(group, Treatment('kept')) + logpop + I(logpop**2) + C(region) + logkm")):
            m = smf.ols(f, data=dd).fit(cov_type="HC1")
            for g in groups:
                k = f"C(group, Treatment('kept'))[T.{g}]"
                if k in m.params:
                    sc = 1000 if o == "income_fye2023" else 1
                    res[f"{name}_{g}"] = {"b": float(m.params[k] * sc), "lo": float(m.conf_int().loc[k, 0] * sc),
                                          "hi": float(m.conf_int().loc[k, 1] * sc), "p": float(m.pvalues[k])}
            res[f"{name}_n"] = int(m.nobs)
        out[o] = res
    return out


kept, lost, regd = S[S.group == "kept"], S[S.group == "lost"], S[S.group == "regained"]
R["outcomes"]["matched_lost"] = {o: matched(lost, kept, o) for o in OUT}
R["outcomes"]["matched_regained"] = {o: matched(regd, kept, o) for o in OUT}
R["outcomes"]["matched_regained_vs_lost"] = {o: matched(regd, lost, o) for o in OUT}
R["outcomes"]["models"] = models(S)
# checks
chk = {}
for tag, col in (("r1km", "group_1km"), ("r3km", "group_3km")):
    s2 = S.copy()
    s2["group"] = s2[col]
    chk[tag] = {"n_lost": int((s2.group == "lost").sum()), "n_kept": int((s2.group == "kept").sum()),
                "models": models(s2, groups=("lost",))}
s3 = S[~((S.group == "lost") & (S.n_other_rail_today > 0))]
chk["no_other_rail"] = {"n_lost": int((s3.group == "lost").sum()), "models": models(s3, groups=("lost",))}
s4 = S[S.pop2021 >= 5000]
chk["over5k"] = {"n_lost": int((s4.group == "lost").sum()), "n_kept": int((s4.group == "kept").sum()), "models": models(s4, groups=("lost",))}
s5 = S[S.km_to_city100k >= 15]
chk["away_from_cities"] = {"n_lost": int((s5.group == "lost").sum()), "n_kept": int((s5.group == "kept").sum()), "models": models(s5, groups=("lost",))}
s6 = S[S.km_to_city100k < 15]
chk["near_cities"] = {"n_lost": int((s6.group == "lost").sum()), "n_kept": int((s6.group == "kept").sum()), "models": models(s6, groups=("lost",))}
R["checks"] = chk
# remoteness gap: how much further from a city the lost towns are
R["towns"]["km_city_lost_vs_kept"] = float(lost.km_to_city100k.median() - kept.km_to_city100k.median())

# headline numbers used in prose
m = R["outcomes"]["models"]
R["headline"] = {
    "age65_pts": m["pct_65plus"]["size_region_lost"]["b"] * 100,
    "age65_pts_remote": m["pct_65plus"]["plus_remote_lost"]["b"] * 100,
    "nocar_pts": m["pct_no_car"]["size_region_lost"]["b"] * 100,
    "work_pts": m["pct_in_work"]["size_region_lost"]["b"] * 100,
    "sick_pts": m["pct_sick"]["size_region_lost"]["b"] * 100,
    "mgr_pts": m["pct_managerial"]["size_region_lost"]["b"] * 100,
    "income_gbp": m["income_fye2023"]["size_region_lost"]["b"],
    "income_gbp_remote": m["income_fye2023"]["plus_remote_lost"]["b"],
    "income_n": m["income_fye2023"]["size_region_n"],
}

R["headline"]["income_pct_of_kept"] = R["headline"]["income_gbp"] / desc["kept"]["income_fye2023"]
R["headline"]["income_p"] = m["income_fye2023"]["size_region_lost"]["p"]
R["headline"]["mgr_p"] = m["pct_managerial"]["size_region_lost"]["p"]
R["headline"]["nocar_p"] = m["pct_no_car"]["size_region_lost"]["p"]
R["headline"]["age65_p"] = m["pct_65plus"]["size_region_lost"]["p"]
R["headline"]["regained_work_pts"] = m["pct_in_work"]["size_region_regained"]["b"] * 100
R["headline"]["regained_work_p"] = m["pct_in_work"]["size_region_regained"]["p"]
R["headline"]["lost_share_small"] = bs[0]["share_lost"]
R["headline"]["lost_share_large"] = bs[-1]["share_lost"]
R["headline"]["away_income_gbp"] = chk["away_from_cities"]["models"]["income_fye2023"]["size_region_lost"]["b"]
R["headline"]["away_income_p"] = chk["away_from_cities"]["models"]["income_fye2023"]["size_region_lost"]["p"]
R["headline"]["near_income_gbp"] = chk["near_cities"]["models"]["income_fye2023"]["size_region_lost"]["b"]
R["headline"]["near_income_p"] = chk["near_cities"]["models"]["income_fye2023"]["size_region_lost"]["p"]
R["headline"]["near_mgr_pts"] = chk["near_cities"]["models"]["pct_managerial"]["size_region_lost"]["b"] * 100
# named towns used in the text
spot = {}
for nm in ["Leigh (Wigan)", "Washington", "Dunstable", "Skelmersdale", "Witney", "Haverhill", "Portishead", "Consett", "Mansfield",
           "Corby", "Kenilworth", "Ashington (Northumberland)", "Ilkeston", "Clitheroe", "Brighouse", "Okehampton", "Galashiels",
           "Wallsend", "Sale", "Kingswood and Fishponds", "Dudley (Dudley)", "Newcastle-under-Lyme", "Loughborough"]:
    x = tw[tw.bua22 == nm]
    if len(x):
        r = x.iloc[0]
        spot[nm] = {"pop": int(r.pop2021) if pd.notna(r.pop2021) else None, "group": r.group, "closed": r.closed_1955_75 if isinstance(r.closed_1955_75, str) else "",
                    "last": int(r.last_closure) if pd.notna(r.last_closure) else None, "today": r.open_today if isinstance(r.open_today, str) else ""}
R["spot"] = spot
json.dump(R, open(os.path.join(D, "results.json"), "w"), indent=1, default=float)

# ---------------------------------------------------------------- 4. page data
pts = cs[cs.lat.notna() & cs.year_closed.notna()]
site = {
    "closed": [[round(r.lat, 4), round(r.lon, 4), int(r.year_closed), r.name, 1 if pd.notna(r.reopened_year) else 0] for r in pts.itertuples()],
    "open": [[round(r.lat, 4), round(r.lon, 4), r.stationName, {"open_in_1975": 0, "reopened_after_1975": 1, "new_after_1975": 2}[r.status_1975]] for r in op.itertuples()],
    "towns": [[r.bua22, round(r.lat, 4), round(r.lon, 4), int(r.pop2021) if pd.notna(r.pop2021) else 0, r.group,
               r.closed_1955_75 if isinstance(r.closed_1955_75, str) else "", r.open_today if isinstance(r.open_today, str) else "",
               int(r.last_closure) if pd.notna(r.last_closure) else 0,
               *[round(float(getattr(r, o)), 3) if pd.notna(getattr(r, o)) else None for o in ["pct_65plus", "pct_no_car", "pct_in_work", "pct_managerial"]],
               int(r.income_fye2023) if pd.notna(r.income_fye2023) else None, r.region if isinstance(r.region, str) else ""]
              for r in tw.itertuples() if r.group != "none" or (pd.notna(r.pop2021) and r.pop2021 >= 2000)],
}
json.dump(site, open(os.path.join(ROOT, "_site_data.json"), "w"), separators=(",", ":"), ensure_ascii=False)
print(json.dumps({k: R[k] for k in ("stations",)}, default=float)[:1500])
print(json.dumps(R["towns"]["groups_sample"]), R["towns"]["share_lost_of_had"], R["towns"]["by_size"])
print(json.dumps(R["outcomes"]["median"], default=float, indent=0)[:2000])
for o in OUT:
    print(o, {k: (round(v["b"], 4), round(v["p"], 4)) if isinstance(v, dict) else v for k, v in R["outcomes"]["models"][o].items()})
    print("   matched", R["outcomes"]["matched_lost"][o])
for c in chk:
    print(c, chk[c].get("n_lost"), {o: round(chk[c]["models"][o]["size_region_lost"]["b"], 4) for o in OUT})
print("site bytes", os.path.getsize(os.path.join(ROOT, "_site_data.json")))
