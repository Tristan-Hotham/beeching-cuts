"""Reddit collage (2400 x 3000 px). Reads only data/ files.
Usage: python3 reddit/collage.py [font_dir]
"""
import json
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
F = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/-home-claude/c232619d-81e0-53f3-9de6-41e973630753/scratchpad/fonts"
for f in ["FrauncesVar.ttf", "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "SourceSerif4-Regular.ttf", "SourceSerif4-Semibold.ttf", "SourceSerif4-It.ttf"]:
    fm.fontManager.addfont(os.path.join(F, f))
DISP = fm.FontProperties(fname=os.path.join(F, "FrauncesVar.ttf"), weight=900)
SER, MONO = "Source Serif 4", "IBM Plex Mono"
BG, FG, MUT, LANDC, EDGE = "#E7EEE4", "#1C211D", "#5C665E", "#F6F8F2", "#C3CFC0"
HOT, KEPT, EARLY = "#A8322B", "#1E6B45", "#A9B3A8"
CM = LinearSegmentedColormap.from_list("yrs", ["#E3A33B", "#D2602F", "#A8322B", "#5E1A2E"])

R = json.load(open(os.path.join(ROOT, "data", "results.json")))
CS = pd.read_csv(os.path.join(ROOT, "data", "closed_stations.csv"))
OP = pd.read_csv(os.path.join(ROOT, "data", "open_stations.csv"))
K = np.cos(np.radians(54.5))
land = []
for ft in json.load(open("/home/claude/hist/_data3/ne/geojson/ne_10m_land.geojson"))["features"]:
    g = ft["geometry"]
    for p in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
        r = np.array(p[0])
        if ((r[:, 0] > -11) & (r[:, 0] < 3) & (r[:, 1] > 49) & (r[:, 1] < 61)).any():
            land.append(r)

S, T, H = R["stations"], R["towns"], R["headline"]
fig = plt.figure(figsize=(12, 15), dpi=200, facecolor=BG)
fig.text(0.04, 0.968, "Did Beeching kill your town?", fontproperties=DISP, fontsize=50, color=FG, va="top")
fig.text(0.04, 0.917, f"Every station in Wikipedia's lists of closed stations in Great Britain, placed on the map and coloured\n"
         f"by the year it shut. {S['n_1955_75']:,} closed between 1955 and 1975, the era of the Beeching report (1963).",
         family=SER, fontsize=15.5, color=FG, va="top", linespacing=1.15)

# hero map
ax = fig.add_axes([0.03, 0.315, 0.55, 0.55])
for r in land:
    ax.fill(r[:, 0] * K, r[:, 1], color=LANDC, ec=EDGE, lw=0.6, zorder=0)
P = CS[CS.lat.notna() & CS.year_closed.notna()]
e = P[(P.year_closed < 1955) | (P.year_closed > 1975)]
ax.scatter(e.lon * K, e.lat, s=1.6, color=EARLY, lw=0, alpha=0.7, zorder=1, rasterized=True)
ax.scatter(OP.lon * K, OP.lat, s=1.3, color=KEPT, lw=0, alpha=0.8, zorder=2, rasterized=True)
m = P[(P.year_closed >= 1955) & (P.year_closed <= 1975)].sort_values("year_closed")
sc = ax.scatter(m.lon * K, m.lat, s=5.5, c=m.year_closed, cmap=CM, vmin=1955, vmax=1975, lw=0, alpha=0.95, zorder=3, rasterized=True)
ax.set_xlim(-6.4 * K, 1.9 * K)
ax.set_ylim(49.9, 58.75)
ax.set_aspect("equal")
ax.axis("off")
cax = fig.add_axes([0.07, 0.300, 0.22, 0.009])
cb = fig.colorbar(sc, cax=cax, orientation="horizontal", ticks=[1955, 1960, 1965, 1970, 1975])
cb.outline.set_visible(False)
cax.tick_params(labelsize=10, colors=FG, length=0)
for t in cax.get_xticklabels():
    t.set_family(MONO)
fig.text(0.07, 0.313, "Year closed, 1955 to 1975", family=MONO, fontsize=10.5, color=FG)
fig.text(0.33, 0.309, "●", color=EARLY, fontsize=11, va="center")
fig.text(0.345, 0.309, "closed before 1955 or after 1975", family=MONO, fontsize=10, color=MUT, va="center")
fig.text(0.33, 0.297, "●", color=KEPT, fontsize=11, va="center")
fig.text(0.345, 0.297, f"National Rail station today ({R['open']['n_national_rail']:,})", family=MONO, fontsize=10, color=MUT, va="center")

# right column numbers
tx = fig.add_axes([0.6, 0.32, 0.38, 0.53])
tx.axis("off")
notes = [(f"{S['peak_n']:,}", f"stations closed in {S['peak_year']}, the year after\nthe report: the worst year in the lists."),
         (f"{T['groups_sample']['lost']:,}", f"towns of 2,000 to 100,000 people in England\nand Wales lost every station by 1975 and\nhave none today ({T['share_lost_of_had'] * 100:.0f}% of those with one in 1955)."),
         (f"{H['lost_share_small'] * 100:.0f}% vs {H['lost_share_large'] * 100:.0f}%", "of station towns lost their railway for good:\ntowns of 2,000 to 5,000 people against\ntowns of 50,000 to 100,000."),
         (f"£{abs(H['income_gbp']):,.0f}", f"lower household income a year ({abs(H['income_pct_of_kept']) * 100:.1f}%)\nthan towns of the same size and region\nthat kept a station. No clear gap in age,\nwork or sickness.")]
for (big, small), y in zip(notes, [1.0, 0.76, 0.50, 0.26]):
    tx.text(0, y, big, fontproperties=DISP, fontsize=30, color=HOT, va="top", transform=tx.transAxes)
    tx.text(0, y - 0.075, small, family=SER, fontsize=12.5, color=FG, va="top", transform=tx.transAxes, linespacing=1.15)

# bottom row: closures per year and share lost by size
a1 = fig.add_axes([0.07, 0.095, 0.50, 0.14], facecolor=BG)
by = {int(k): v for k, v in S["by_year"].items()}
ys = list(range(1945, 1986))
a1.bar(ys, [by.get(y, 0) for y in ys], width=0.8, color=[CM((y - 1955) / 20) if 1955 <= y <= 1975 else EARLY for y in ys])
for s_ in ("top", "right"):
    a1.spines[s_].set_visible(False)
a1.spines["left"].set_color(MUT)
a1.spines["bottom"].set_color(MUT)
a1.tick_params(colors=MUT, labelsize=10)
for t in a1.get_xticklabels() + a1.get_yticklabels():
    t.set_family(MONO)
a1.axvline(1963, color=FG, lw=0.9, ls=(0, (2, 3)))
a1.text(1962.4, by[S["peak_year"]] * 0.98, "1963\nreport", family=MONO, fontsize=10, color=FG, ha="right", va="top")
a1.text(S["peak_year"] + 0.9, by[S["peak_year"]], f"{S['peak_year']}: {by[S['peak_year']]}", family=MONO, fontsize=10, color=FG, va="center")
fig.text(0.04, 0.258, "STATIONS CLOSED EACH YEAR, 1945 TO 1985", family=MONO, fontsize=11, color=MUT)

a2 = fig.add_axes([0.72, 0.095, 0.24, 0.14], facecolor=BG)
bs = T["by_size"]
lab = [f"{b['lo'] // 1000}k to {b['hi'] // 1000}k" for b in bs]
yy = np.arange(len(bs))[::-1]
a2.barh(yy, [b["share_lost"] * 100 for b in bs], color=HOT, height=0.62)
a2.set_yticks(yy, lab)
for y_, b in zip(yy, bs):
    a2.text(b["share_lost"] * 100 + 2, y_, f"{b['share_lost'] * 100:.0f}%", va="center", family=MONO, fontsize=10, color=FG)
a2.set_xlim(0, 70)
a2.set_xticks([])
for s_ in ("top", "right", "bottom"):
    a2.spines[s_].set_visible(False)
a2.spines["left"].set_color(MUT)
a2.tick_params(colors=FG, labelsize=10, length=0)
for t in a2.get_yticklabels():
    t.set_family(MONO)
fig.text(0.62, 0.258, "SHARE LOST FOR GOOD, BY TOWN SIZE", family=MONO, fontsize=11, color=MUT)

fig.text(0.04, 0.060, "Association, not cause: the closures picked smaller, more rural, less used places, and comparing towns of the same size today cannot see any people they lost.",
         family=SER, style="italic", fontsize=10.5, color=FG)
fig.text(0.04, 0.012, "Data: Wikipedia, List of closed railway stations in Great Britain (CC BY-SA 4.0); Wikidata (CC0); OpenStreetMap contributors (ODbL);\n"
         "uk-railway-stations, D. Wheatley / Trainline EU (ODbL); ONS Census 2021 and small area income FYE2023, ONS built-up areas (OGL v3);\n"
         "OS Open Names, contains OS data © Crown copyright and database right 2026; Natural Earth. Analysis and chart: Tristan Hotham, with Python and matplotlib.",
         family=MONO, fontsize=9, color=MUT, linespacing=1.2)
fig.savefig(os.path.join(HERE, "did_beeching_kill_your_town.png"), facecolor=BG, dpi=200)
print("ok")
