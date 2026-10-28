"""Step 5. Make header.png (1200x630 social card) by rendering a small HTML card with Playwright.

Usage:
    python3 code/05_header.py [font_dir]

Fonts come from Google Fonts. Where Google Fonts is unreachable, pass a folder holding
FrauncesVar.ttf, IBMPlexMono-Regular.ttf, IBMPlexMono-Medium.ttf and SourceSerif4-Regular.ttf.
"""
import asyncio
import csv
import json
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json")))
FONTS = sys.argv[1] if len(sys.argv) > 1 else None
pts = [[round(float(r["lon"]), 3), round(float(r["lat"]), 3), int(r["year_closed"])]
       for r in csv.DictReader(open(os.path.join(ROOT, "data", "closed_stations.csv"), encoding="utf-8")) if r["lat"] and r["year_closed"]]
dek = (f"{R['stations']['n_1955_75']:,} stations closed between 1955 and 1975. "
       f"{R['towns']['groups_sample']['lost']:,} towns in England and Wales lost every one and still have none.")

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,900&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">
<style>
body{margin:0;width:1200px;height:630px;background:#F4EFE3;color:#1F1C17;overflow:hidden;position:relative;font-family:'Source Serif 4',Georgia,serif}
.l{position:absolute;left:72px;top:60px;width:640px}
.k{font:500 17px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#625B4E;display:flex;gap:14px;align-items:center}
.k b{background:#A8322B;color:#fff;padding:8px 10px;font-weight:500}
h1{font:900 96px/.9 'Fraunces',Georgia,serif;letter-spacing:-.02em;margin:24px 0 0}
h1 em{font-style:normal;color:#A8322B}
p{font-size:27px;line-height:1.34;margin:24px 0 0;color:#2B2720;max-width:560px}
.f{position:absolute;left:72px;bottom:36px;font:400 15px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#625B4E}
canvas{position:absolute;right:16px;top:8px}
</style></head><body>
<div class="l"><div class="k"><b>Data study</b><span>History × data</span></div>
<h1>Did Beeching<br>kill <em>your town?</em></h1>
<p>__DEK__</p></div>
<div class="f">Dr Tristan Hotham · Independent researcher</div>
<canvas id="c" width="900" height="1228" style="width:450px;height:614px"></canvas>
<script>
const P = __PTS__;
const cv = document.getElementById("c"), x = cv.getContext("2d"); x.scale(2, 2);
const k = Math.cos(54.5 * Math.PI / 180), lo0 = -6.3, lo1 = 1.8, la0 = 50.0, la1 = 58.7;
const sc = Math.min(450 / ((lo1 - lo0) * k), 614 / (la1 - la0));
const X = l => (l - lo0) * k * sc + (450 - (lo1 - lo0) * k * sc) / 2, Y = l => (la1 - l) * sc;
P.filter(p => p[2] < 1955 || p[2] > 1975).forEach(p => { x.beginPath(); x.arc(X(p[0]), Y(p[1]), 1.3, 0, 7); x.fillStyle = "rgba(140,131,115,.45)"; x.fill(); });
P.filter(p => p[2] >= 1955 && p[2] <= 1975).forEach(p => { x.beginPath(); x.arc(X(p[0]), Y(p[1]), 1.7, 0, 7); x.fillStyle = "rgba(168,50,43,.85)"; x.fill(); });
</script></body></html>"""
html = HTML.replace("__DEK__", dek).replace("__PTS__", json.dumps(pts, separators=(",", ":")))
if FONTS:
    css = "".join(f"@font-face{{font-family:'{fam}';src:url(file://{FONTS}/{f});font-weight:{w}}}" for fam, f, w in
                  [("Fraunces", "FrauncesVar.ttf", "100 900"), ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "400"),
                   ("IBM Plex Mono", "IBMPlexMono-Medium.ttf", "500"), ("Source Serif 4", "SourceSerif4-Regular.ttf", "400")])
    html = html.replace('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,900&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">', f"<style>{css}</style>")


async def main():
    tmp = os.path.join(ROOT, "_header.html")
    open(tmp, "w", encoding="utf-8").write(html)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto("file://" + tmp)
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=os.path.join(ROOT, "header.png"))
        await b.close()
    os.remove(tmp)


asyncio.run(main())
print("header.png written")
