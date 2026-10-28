"""Step 4. Build index.html from code/page_template.html.

Every number in the text is a {{path|format}} token filled from data/results.json, so the page cannot drift from the
analysis. Map data (_site_data.json from step 3) and the parts of results.json the charts need are embedded, so the
page works as a single file.

Usage:
    python3 code/04_build_page.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json"), encoding="utf-8"))
SITE = open(os.path.join(ROOT, "_site_data.json"), encoding="utf-8").read()
tpl = open(os.path.join(ROOT, "code", "page_template.html"), encoding="utf-8").read()


def get(path, root=R):
    v = root
    for k in path.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def fmt(v, f):
    if f is None or f == "raw":
        return str(v)
    if f == "int":
        return f"{round(v):,}"
    if f == "pct":
        return f"{round(v * 100)}%"
    if f == "pct1":
        return f"{v * 100:.1f}%"
    if f == "pctabs":
        return f"{abs(v) * 100:.1f}%"
    if f == "f1":
        return f"{v:.1f}"
    if f == "f2":
        return f"{v:.2f}"
    if f == "gbp":
        return f"£{round(v):,}"
    if f == "gbpabs":
        return f"£{round(abs(v)):,}"
    if f == "pp":
        return f"{'+' if v > 0 else 'minus ' if v < 0 else ''}{abs(v):.1f}"
    if f == "ppabs":
        return f"{abs(v):.1f}"
    raise ValueError(f)


def fill(text):
    used = []

    def sub(m):
        used.append(m.group(1))
        return fmt(get(m.group(1)), m.group(3))
    return re.sub(r"\{\{([^}|]+)(\|(\w+))?\}\}", sub, text), used


if __name__ == "__main__":
    html, used = fill(tpl)
    slim = {"by_year": R["stations"]["by_year"], "peak_year": R["stations"]["peak_year"], "by_size": R["towns"]["by_size"],
            "by_region": R["towns"]["by_region"], "models": R["outcomes"]["models"], "top_lost": R["towns"]["top_lost"],
            "top_regained": R["towns"]["top_regained"]}
    html = html.replace("/*SITE*/", SITE).replace("/*RESULTS*/", json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
    assert "{{" not in html
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html", len(html.encode()), "bytes;", len(used), "tokens filled")
