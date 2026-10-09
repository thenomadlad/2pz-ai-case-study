"""Builds vet_data.ipynb from the cells below (run: uv run --extra notebook python
notebooks/build_vet_data.py). Edit cells here, not in the .ipynb, so diffs stay readable."""
from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
md("""# Vetting the data

Every number the app shows comes from three seed files and the pipeline built on them. This
notebook checks each layer for gaps, duplicates and outliers before anyone trusts the calls.

- **Inputs:** branches (2GIS, hand-collected), communities (DSC census, hand-collected),
  competitors (OpenStreetMap, `scripts/fetch_competitors.py`)
- **Computed:** catchments, branch scores, area 2×2 and what's left in each area

Open it with `just notebook`. Each check prints what it found; the last section lists open
questions."""),
code("""%matplotlib inline
from pathlib import Path
import sys

ROOT = Path.cwd().resolve()
while not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from src.config import settings
from src.features.assign import COMPETITOR_MAX_KM, haversine_km
from src.model import opportunity, rubric
from src.webapp.data import load_baseline
from src.webapp.map import ACTION_COLORS, OPPORTUNITY_COLORS

pd.set_option("display.width", 140)
plt.rcParams.update({"figure.figsize": (9, 5), "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25})
hexcolor = lambda rgb: "#%02x%02x%02x" % tuple(rgb[:3])
ACTION = {k: hexcolor(v) for k, v in ACTION_COLORS.items()}
AREA = {k: hexcolor(v) for k, v in OPPORTUNITY_COLORS.items()}

data = load_baseline(settings)          # the same baseline the app shows
seed = ROOT / "data" / "seed"
branches = pd.read_csv(seed / "branches.csv")
communities = pd.read_csv(seed / "communities.csv")
competitors = pd.read_csv(seed / "competitors.csv")
print(f"{len(branches)} branches · {len(communities)} communities · "
      f"{len(competitors)} competitors")"""),

md("## 1. Inputs\n### Branches"),
code("""branches"""),
code("""DUBAI = dict(lat=(24.7, 25.4), lng=(54.9, 55.7))
checks = {
    "missing rating": branches.loc[branches.rating.isna(), "id"].tolist(),
    "missing review count": branches.loc[branches.review_count.isna(), "id"].tolist(),
    "rating outside 1-5": branches.loc[~branches.rating.between(1, 5) & branches.rating.notna(), "id"].tolist(),
    "outside Dubai box": branches.loc[~branches.lat.between(*DUBAI["lat"]) | ~branches.lng.between(*DUBAI["lng"]), "id"].tolist(),
    "duplicate ids": branches.loc[branches.id.duplicated(), "id"].tolist(),
    "every price missing": bool(branches.avg_price_aed.isna().all()),
}
pd.Series(checks, name="finding").to_frame()"""),
code("""# Branches closer than 1 km to each other: both will fight over the same communities.
pairs = [(a.id, b.id, round(haversine_km(a.lat, a.lng, b.lat, b.lng), 2))
         for i, a in branches.iterrows() for j, b in branches.iterrows() if i < j]
pd.DataFrame(pairs, columns=["branch", "other", "km"]).sort_values("km").head(5)"""),

md("### Communities"),
code("""communities["female_est"] = (communities.population_total * settings.global_female_share).round()
print("female population published for", communities.population_female.notna().sum(), "of",
      len(communities), "communities; the rest are estimated at",
      f"{settings.global_female_share:.0%}")
communities.describe().round(1)"""),
code("""fig, ax = plt.subplots()
ordered = communities.sort_values("population_total")
ax.barh(ordered.name_en, ordered.population_total / 1000, color="#9e9e9e", height=0.7)
ax.axvline(opportunity.MIN_POP / settings.global_female_share / 1000, color="#424242", lw=1.5,
           ls="--", label=f"GROW floor ({opportunity.MIN_POP:,} women)")
ax.set_xlabel("Census population (thousands)")
ax.set_title("Community size: a few industrial areas dominate")
ax.tick_params(axis="y", labelsize=6)
ax.legend(loc="lower right")
fig.set_size_inches(9, 10)
plt.tight_layout()
plt.show()"""),
code("""industrial = communities[communities.name_en.str.contains("Industrial|Investment Park", case=False)]
print(f"{len(industrial)} industrial / worker-housing communities hold "
      f"{industrial.population_total.sum() / communities.population_total.sum():.0%} of the population")
industrial[["name_en", "population_total", "female_est"]]"""),

md("### Competitors"),
code("""competitors["category"].value_counts().rename("count").to_frame()"""),
code("""import re
male = re.compile(r"\\b(?:gents?|men|man|barbers?|barbershop)\\b", re.I)
unnamed = competitors.name.isna() | (competitors.name.fillna("").str.strip() == "")
dup_names = competitors[competitors.name.notna() & competitors.duplicated("name", keep=False)]
pd.Series({
    "unnamed": int(unnamed.sum()),
    "male-only names still present": int(competitors.name.fillna("").str.contains(male).sum()),
    "names appearing more than once": dup_names.name.nunique(),
    "same name within 50 m (likely duplicates)": sum(
        haversine_km(a.lat, a.lng, b.lat, b.lng) < 0.05
        for _, g in dup_names.groupby("name") for i, a in g.iterrows() for j, b in g.iterrows() if i < j),
}, name="finding").to_frame()"""),
code("""# How far each competitor is from its nearest community centre, and what the 3 km cut-off drops.
nearest_km = competitors.apply(lambda k: min(
    haversine_km(k.lat, k.lng, c.lat, c.lng) for c in communities.itertuples()), axis=1)
dropped = (nearest_km > COMPETITOR_MAX_KM).sum()
fig, ax = plt.subplots()
ax.hist(nearest_km, bins=40, color="#616161", rwidth=0.9)
ax.axvline(COMPETITOR_MAX_KM, color="#c62828", lw=2, label=f"cut-off: {COMPETITOR_MAX_KM:g} km")
ax.set_xlabel("Distance to nearest seeded community centre (km)")
ax.set_ylabel("Competitor salons")
ax.set_title(f"{dropped} of {len(competitors)} competitors ({dropped / len(competitors):.0%}) "
             "fall outside every community and are not counted")
ax.legend()
plt.show()"""),
code("""# Where are the dropped ones? Most sit just over the border in Sharjah (the fetch used a
# rectangle, not the emirate boundary); the rest are in Dubai communities missing from the seed.
competitors["dropped"] = nearest_km > COMPETITOR_MAX_KM
fig, ax = plt.subplots(figsize=(8, 8))
kept, gone = competitors[~competitors.dropped], competitors[competitors.dropped]
ax.scatter(kept.lng, kept.lat, s=5, color="#9e9e9e", label=f"counted ({len(kept)})")
ax.scatter(gone.lng, gone.lat, s=14, color="#c62828", label=f"dropped ({len(gone)})")
ax.scatter(communities.lng, communities.lat, s=30, marker="+", color="#212121",
           label="seeded community centre")
ax.set_aspect(1 / 0.906)
ax.set_title("Dropped competitors: a Sharjah cluster (north-east) and unseeded Dubai areas")
ax.legend(loc="lower right")
plt.show()
sharjah = gone[(gone.lat > 25.29) & (gone.lng > 55.36)]
print(f"{len(sharjah)} of {len(gone)} dropped are in the Sharjah corner (lat > 25.29, lng > 55.36)")"""),

md("### Everything on one map"),
code("""fig, ax = plt.subplots(figsize=(9, 9))
ax.scatter(competitors.lng, competitors.lat, s=4, color="#212121", alpha=0.35, label="competitor salon")
ax.scatter(communities.lng, communities.lat, s=communities.population_total / 1500,
           facecolor="none", edgecolor="#757575", lw=1, label="community (sized by population)")
for action, color in ACTION.items():
    ids = [d.branch_id for d in data.decisions if d.action == action]
    b = branches[branches.id.isin(ids)]
    ax.scatter(b.lng, b.lat, s=120, color=color, edgecolor="white", lw=2, label=f"branch: {action}",
               zorder=3)
    for r in b.itertuples():
        ax.annotate(r.id, (r.lng, r.lat), xytext=(6, 4), textcoords="offset points", fontsize=8)
ax.set_aspect(1 / 0.906)   # cos(25°): keep distances honest
ax.set_title("Bedashing branches sit south-west; the north-east (Deira) is the gap")
ax.legend(loc="lower right", fontsize=8)
plt.show()"""),

md("## 2. Catchments\nEach community goes wholly to its straight-line nearest branch."),
code("""feat = pd.DataFrame([f.model_dump() for f in data.features]).set_index("branch_id")
dec = pd.DataFrame([d.model_dump() for d in data.decisions]).set_index("branch_id")
feat["action"] = dec.action
cols = ["female_pop_served", "communities_served", "mean_distance_km", "max_distance_km",
        "contested_share", "competitors_per_10k", "rating", "action"]
feat[cols].sort_values("female_pop_served", ascending=False).round(2)"""),
code("""fig, ax = plt.subplots()
s = feat.sort_values("female_pop_served")
ax.barh(s.index, s.female_pop_served / 1000, color=[ACTION[a] for a in s.action], height=0.6)
ax.axvline(rubric.SIGNALS[0].best / 1000, color="#424242", ls="--", lw=1.5,
           label="demand score caps at 150k")
ax.set_xlabel("Women in catchment (thousands)")
ax.set_title("City Walk's catchment is a straight-line artefact: 9 branches cover all of Dubai")
ax.legend(loc="lower right")
plt.show()"""),

md("## 3. Branch scores"),
code("""scores = pd.DataFrame({d.branch_id: d.scores for d in data.decisions}).T
scores["composite"] = dec.composite
scores["action"] = dec.action
scores["confidence"] = dec.confidence
scores.sort_values("composite", ascending=False).round(2)"""),
code("""fig, ax = plt.subplots(figsize=(9, 3.5))
c = scores.sort_values("composite")
ax.scatter(c.composite, range(len(c)), s=90, color=[ACTION[a] for a in c.action], zorder=3)
ax.set_yticks(range(len(c)), c.index)
for x, label in ((rubric.SHRINK_AT, "SHRINK ≤"), (rubric.PROTECT_AT, "PROTECT ≥")):
    ax.axvline(x, color="#424242", ls="--", lw=1.2)
    ax.text(x + 0.01, 0.02, f"{label} {x}", transform=ax.get_xaxis_transform(), fontsize=8)
ax.set_xlim(0, 1)
ax.set_xlabel("Composite score")
ax.set_title("Most branches sit in the HOLD band; several within 0.05 of a line")
plt.show()"""),
code("""# Equal weights let strong signals hide a fatal one: low demand, but not SHRINK.
scores[scores.demand < 0.1][["demand", "cannibalisation", "competition", "quality", "composite", "action"]]"""),

md("## 4. Areas: the 2×2 and what's left"),
code("""cf = pd.DataFrame([c.model_dump() for c in data.community_features]).set_index("community_id")
op = pd.DataFrame([o.model_dump() for o in data.opportunities]).set_index("community_id")
areas = cf.join(op[["action", "salon_headroom", "uncovered_women", "fair_share", "captured_women_est"]])
fig, ax = plt.subplots(figsize=(9, 6))
for action, color in AREA.items():
    a = areas[areas.action == action]
    ax.scatter(a.nearest_branch_km, a.competitors_per_10k, s=a.female_pop / 400,
               color=color, edgecolor="white", lw=1, label=action, alpha=0.9)
ax.axvline(opportunity.FAR_KM, color="#424242", ls="--", lw=1.2)
ax.axhline(opportunity.UNSATURATED_PER_10K, color="#424242", ls="--", lw=1.2)
YMAX = 20
off_chart = areas[areas.competitors_per_10k > YMAX]
ax.set_ylim(0, YMAX)
ax.set_xlabel("Distance to nearest Bedashing branch (km)")
ax.set_ylabel("Competitor salons per 10k women")
ax.set_title("GROW = bottom-right: far from a branch and under the saturation line")
ax.legend(title="Area call (dot size = women)")
for cid, r in areas[areas.action == "GROW"].iterrows():
    ax.annotate(cid, (r.nearest_branch_km, r.competitors_per_10k), xytext=(5, 3),
                textcoords="offset points", fontsize=7)
plt.show()
print(f"Not shown (over {YMAX} per 10k):", ", ".join(
    f"{cid} ({v:.0f}, {a})" for cid, v, a in zip(off_chart.index, off_chart.competitors_per_10k,
                                                 off_chart.action)))"""),
code("""areas[areas.action != "SKIP"].sort_values(["action", "salon_headroom"], ascending=[True, False])[
    ["name", "action", "female_pop", "competitors", "competitors_per_10k", "nearest_branch_km",
     "salon_headroom", "uncovered_women"]].round(2)"""),
code("""print("Total salon headroom in GROW areas:", areas.loc[areas.action == "GROW", "salon_headroom"].sum())
print("GROW areas with no headroom left:",
      areas.index[(areas.action == "GROW") & (areas.salon_headroom == 0)].tolist())"""),

md("## 5. How sensitive are the calls?\nRe-classify with each threshold nudged, and count the calls that flip."),
code("""def branch_flips(protect, shrink):
    new = scores.composite.map(lambda c: "PROTECT" if c >= protect else "SHRINK" if c <= shrink else "HOLD")
    return int((new != scores.action).sum())

def area_flips(far_km, sat):
    keep = ~(areas.hosts_branch | (areas.female_pop < opportunity.MIN_POP))
    under, unsat = areas.nearest_branch_km > far_km, areas.competitors_per_10k < sat
    new = (under & unsat).map({True: "GROW", False: None}).fillna((under | unsat).map({True: "WATCH", False: "SKIP"}))
    new = new.where(keep, "SKIP")
    capped = areas.name.str.contains("Industrial|Investment Park", case=False) & (new == "GROW")
    new = new.where(~capped, "WATCH")
    return int((new != areas.action).sum())

rows = [("branch PROTECT line", f"{p:.2f}", branch_flips(p, rubric.SHRINK_AT)) for p in (0.60, 0.65, 0.70)]
rows += [("branch SHRINK line", f"{s:.2f}", branch_flips(rubric.PROTECT_AT, s)) for s in (0.30, 0.35, 0.40)]
rows += [("area distance line (km)", k, area_flips(k, opportunity.UNSATURATED_PER_10K)) for k in (4, 5, 6)]
rows += [("area saturation line (/10k)", t, area_flips(opportunity.FAR_KM, t)) for t in (4, 5, 6)]
pd.DataFrame(rows, columns=["threshold", "value", "calls that change"])"""),

md("""## 6. Open questions this raises

Fill in as you go. Starting list from the checks above:

1. **Community coordinates have no recorded source.** Where did each centroid come from?
2. **Competitors outside every community are dropped (101 of 768).** About 60 are in Sharjah
   and rightly excluded. The other ~40 are in Dubai communities the seed doesn't have
   (around 25.1N 55.4E and 25.0-25.1N 55.2E), so competition there is undercounted.
   Adding those communities would fix it.
3. **Industrial areas dominate population** but are mostly male workers. The 49% female
   share is worst exactly where the population is largest.
4. **Branches within 1 km of each other** (section 1) will always score high on
   cannibalisation: is that real overlap or one branch listed twice?
5. **Threshold sensitivity** (section 5): any threshold where a small nudge flips several
   calls needs a stated reason, or a range instead of a line."""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {
    "display_name": "Python 3", "language": "python", "name": "python3"}})
nbf.write(nb, Path(__file__).with_name("vet_data.ipynb"))
print("wrote", Path(__file__).with_name("vet_data.ipynb"))
