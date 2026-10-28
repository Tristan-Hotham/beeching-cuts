# Did Beeching Kill Your Town?

Which towns in Britain lost their railway in the closures of 1955 to 1975, and how do they compare today with similar towns that kept a station? Wikipedia's lists of closed stations, Wikidata, OpenStreetMap, the National Rail station list, Census 2021 and ONS income estimates.

**Interactive version:** https://tristan-hotham.github.io/beeching-cuts/

**Paper:** https://doi.org/10.5281/zenodo.23727114

This repository holds the interactive page, the datasets, the computed results and the analysis code for a data study by Dr Tristan Hotham (Independent researcher).

## Headline results

- Wikipedia's 12 letter pages of closed stations in Great Britain hold 6,907 entries. I placed 93% of all stations on the map, and 96% of those closed in 1955 to 1975.
- 3,331 listed stations closed between 1955 and 1975, 48% of all dated entries. The worst year was 1964, the year after the Beeching report, with 556 closures; 1,819 closed between 1963 and 1970.
- Of 1,720 towns in England and Wales (built-up areas of 2,000 to 100,000 people in 2021) that had a station in 1955, 643 (37%) lost every station by 1975 and still have none; 78 lost their railway and have it back; 981 kept a station.
- The closures picked small places: 50% of station towns of 2,000 to 5,000 people lost their railway for good, against 4% of towns of 50,000 to 100,000.
- Against kept towns of the same size and region, the lost towns have about £1,613 a year lower mean household income (3.1%), 1.3 percentage points fewer adults in managerial or professional jobs and 0.8 points fewer households without a car. Age, employment and long-term sickness show no clear difference.
- The income gap is concentrated near cities: £2,105 for lost towns within 15 km of a city of 100,000 or more, and £261 (easily chance) for those further away.
- 989 built-up areas in England and Wales lost every station and still have none, including Washington (51,878 people) and Leigh (43,532).

These are associations, not causes. The closures were aimed at lightly used lines, which mostly served smaller and more rural places.

## Files

- `index.html`: the interactive page (closure map with a year slider and a town search, charts, tables). Data embedded; works as a single file.
- `header.png`: social card (1200 by 630).
- `data/closed_stations.csv`: every entry in Wikipedia's closed station lists (plus 17 closures of 1955 to 1975 found only in Wikidata): name, linked article, company, closure year, reopening year where noted, coordinates and how they were found (`geo_method`), Wikidata item.
- `data/open_stations.csv`: the 2,609 National Rail stations today, with their Wikidata item and opening years, any matching closed-list entry, and their status at the end of 1975 (open, closed and reopened since, or new since).
- `data/towns.csv`: every built-up area (BUA22) in Great Britain: stations closed (all years and 1955 to 1975), stations open in 1975 and today, other rail stations mapped in OpenStreetMap, the railway group under the main rule and two checks, and for England and Wales the 2021 residents, age, car, work, sickness and class shares and mean household income.
- `data/results.json`: every number quoted on the page, in the paper, the blog post and the collage.
- `data/_station_stats.json`: matching statistics from step 1.
- `code/01_stations.py`: parses the closed station lists, places each station, and works out the 1975 status of today's stations.
- `code/02_towns.py`: links stations to built-up areas, assigns railway groups, adds Census 2021 and income.
- `code/03_analyse.py`: counts, comparisons, regressions and checks; writes `results.json` and a temporary page data file.
- `code/04_build_page.py`: fills `code/page_template.html` from `results.json` to make `index.html`.
- `code/05_header.py`: renders `header.png` with Playwright.
- `release/`: the paper (PDF, LaTeX source and figures), the blog post and figures, and the Zenodo files.
- `reddit/`: the collage and its script.

## How to rerun

The scripts read the source files in place (paths at the top of each script): the Wikipedia and Wikidata/OSM bundles retrieved on 28 October 2026, OS Open Names, ONS geography lookups, Census 2021 tables TS001, TS007A, TS045, TS062 and TS066, the ONS small area income estimates for FYE2023, and a clone of https://github.com/davwheat/uk-railway-stations (stations.csv, October 2026).

```
git clone https://github.com/davwheat/uk-railway-stations /tmp/uk-railway-stations
python3 code/01_stations.py /tmp/uk-railway-stations
python3 code/02_towns.py
python3 code/03_analyse.py
python3 code/04_build_page.py
python3 code/05_header.py [font_dir]
python3 release/paper/figures.py [font_dir]
python3 release/paper/build_paper.py
python3 release/blog/build_post.py
python3 release/build_release_meta.py
python3 reddit/collage.py [font_dir]
```

It needs Python 3 with pandas, numpy, scipy, statsmodels, openpyxl, matplotlib and playwright, and xelatex for the paper.

## Method in brief

- Closure year: the latest year in the "Year closed" cell, ignoring any year given for a reopening. Reopenings are read from the cell and the notes.
- Placing: the Wikidata item whose label matches the station's linked article; otherwise a closed, disused or historic station of the same name in OpenStreetMap (if all such objects lie within 1.5 km of each other); otherwise the place the station is named after in OS Open Names, if that name is unique (in its county where the list gives one).
- Today: National Rail stations only. A station counts as closed at the end of 1975 if a list entry of the same name within 1 km closed in 1950 to 1975 (or earlier with a later reopening noted), or if Wikidata gives it a reopening date after 1975 and a list entry nearby closed; as new if all its Wikidata opening dates are after 1975.
- Towns: a station belongs to a built-up area if it lies within 2 km of its centre, or within 1 km beyond the edge of a circle of the same area. Checks use 1 km or 0.5 km beyond the edge, and 3 km or 1.5 km beyond the edge.
- Comparisons: least-squares regressions of each outcome on the railway group, log 2021 population and its square, and region (robust standard errors); checks add the log distance to the nearest built-up area of 100,000 or more, a nearest-neighbour match on population within region, and subsets.

## Known limits

- Association, not cause: closures picked smaller, more rural, less used places, and 2021 size may itself reflect the closures.
- No town figures from before the closures, so no before and after comparison.
- Wikipedia keeps separate lists for London, Greater Manchester, Merseyside, the West Midlands, Lancashire and Norfolk, which I did not parse; 473 listed stations could not be placed.
- The 1975 status of today's stations comes from automatic matching and will contain some errors, for example where two stations of the same name existed.
- Trams, metros and heritage railways do not count as a railway today.
- Census 2021 outcomes are for England and Wales only; Scottish towns are mapped but not compared. Income estimates exist only for towns with a best-fit MSOA.

## Sources and licences

- Closed station lists and the Beeching cuts article: Wikipedia, "List of closed railway stations in Great Britain" (A to Z) and "Beeching cuts", CC BY-SA 4.0, retrieved 28 October 2026.
- Wikidata (station coordinates and dates): CC0.
- OpenStreetMap (closed station points, other rail stations): © OpenStreetMap contributors, Open Database Licence (ODbL), https://www.openstreetmap.org/copyright
- National Rail stations: uk-railway-stations by David Wheatley (https://github.com/davwheat/uk-railway-stations), derived from Trainline EU's stations data, ODbL.
- Census 2021 (TS001, TS007A, TS045, TS062, TS066) and Income estimates for small areas, England and Wales, financial year ending 2023: Office for National Statistics, Open Government Licence v3.0.
- OS Open Names and ONS geography (BUA22, MSOA and LSOA lookups): contains OS data © Crown copyright and database right 2026; Open Government Licence v3.0.
- Base map tiles: Esri.

The data in `data/` and the text of the page are released under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/), because they derive from Wikipedia lists; the station coordinates derived from OpenStreetMap and the National Rail station list are available under the ODbL. The code (`code/`) is released under the MIT licence (see `LICENSE`).

## Citation

Hotham, T. (2026). Did Beeching Kill Your Town? Britain's Lost Railway Towns, 1955 to 2021. Zenodo. https://doi.org/10.5281/zenodo.23727114

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
