"""'What would change the call' as a tree: the call at the top, the scored signals under it, their inputs
under those. Each scored row is shaded red (-1, pushes toward SHRINK / fails the test) to green (+1, toward
PROTECT / passes); context rows are not scored and stay unshaded."""
import pandas as pd
import streamlit as st

from src.model import growth, scorecard

RED, GREEN = (198, 40, 40), (46, 125, 50)


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def _colour(effect: float | None) -> str:
    if effect is None or pd.isna(effect):
        return ""
    rgb = GREEN if effect >= 0 else RED
    return f"background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {0.12 + 0.5 * abs(effect):.2f})"


def _pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def _num(x, fmt="{:,.0f}") -> str:
    return "—" if x is None else fmt.format(x)


def _rows(tree: list[tuple]) -> pd.DataFrame:
    """tree: (depth, label, value, effect or None, note). Depth draws the connectors."""
    depths = [t[0] for t in tree]

    def more_siblings(i: int) -> bool:   # does a later row sit at the same depth before the branch closes?
        for d in depths[i + 1:]:
            if d <= depths[i]:
                return d == depths[i]
        return False

    out, last_at = [], {}
    for i, (depth, label, value, effect, note) in enumerate(tree):
        last_at[depth] = i
        bars = "".join("│  " if more_siblings(last_at[k]) else "   " for k in range(1, depth))
        prefix = "" if depth == 0 else bars + ("├─ " if more_siblings(i) else "└─ ")
        out.append({"Factor": prefix + label, "Value": value, "_pull": effect, "Why it matters": note})
    return pd.DataFrame(out)


CALL_SHADE = {"PROTECT": 1.0, "SHRINK": -1.0, "GROW": 1.0, "SKIP": -1.0}   # HOLD / WATCH: unshaded


def lounge_tree(f: dict) -> list[tuple]:
    """Shaded rows are what pulls the call; each pull is on one scale: a signal score s pulls 2s - 1
    (0.5 = neutral). The site's own rent row carries the cost pull: it is the cause, the median the yardstick."""
    c, sd, sc = f.get("composite"), f.get("score_demand"), f.get("score_cost")
    ref = f.get("demand_ref") or "its emirate's"
    site_rent, ratio = f.get("site_rent_m2"), f.get("rent_ratio")
    median = ratio * site_rent if ratio and site_rent else None
    pull_d = None if sd is None else 2 * sd - 1
    pull_c = None if sc is None else 2 * sc - 1
    action = f.get("action", "")
    return [
        (0, f"{action} · composite {_num(c, '{:.2f}')}", "", CALL_SHADE.get(action),
         (f"The average of the two signals below. SHRINK at {scorecard.SHRINK_AT} or less, PROTECT at "
          f"{scorecard.PROTECT_AT}+")),
        (1, f"Site demand: out-serves {_pct(f.get('demand_pct'))} of {ref} salon sites", f"score {_num(sd, '{:.2f}')}",
         pull_d, "Half the composite"),
        (2, "Women a typical lounge would serve here", _num(f.get("site_served")), pull_d,
         "The number that is ranked (Huff split, this lounge closed)"),
        (3, "Women 15+ within reach", _num(f.get("catchment_women")), None, "The market"),
        (3, "Premium salons competing for them", _num(f.get("premium_pool")), None, "Rivals that take a share"),
        (2, "UAE-wide percentile", _pct(f.get("demand_pct_uae")), None, "Context: against all UAE salon sites"),
        (1, f"Site rent: {_num(ratio, '{:.2f}x')} the median {ref} salon site", f"score {_num(sc, '{:.2f}')}",
         pull_c, "Half the composite. Above 1x = cheaper than typical"),
        (2, "Shop rent at this site (AED/m²/yr)", _num(site_rent), pull_c,
         "Our cost: an area rate that mixes mall and street shops, not this lounge's lease"),
        (2, "Median at its emirate's salon sites (AED/m²/yr)", _num(median), None, "The yardstick"),
        (0, "Context, not scored", "", None, ""),
        (1, "Women this lounge serves", _num(f.get("served_women")), None, "Its own customers (model estimate)"),
        (1, "Performance vs its site", _num(f.get("performance_vs_site"), "{:.1f}x"), None,
         "Its served women ÷ a typical lounge's at this site"),
        (1, "Share its siblings would absorb if it closed", _pct(f.get("absorbed_share")), None, "Cannibalisation what-if"),
    ]


def area_tree(f: dict) -> list[tuple]:
    net, pct, ratio = f.get("new_site_net"), f.get("demand_pct"), f.get("rent_ratio")
    fallback = bool(f.get("rent_fallback"))
    return [
        (0, f"{f.get('action', '')}", "", CALL_SHADE.get(f.get("action", "")), "GROW needs every test below to pass"),
        (1, f"Net new women (line {growth.NEW_SITE_MIN:,})", _num(net),
         None if net is None else _clip((net - growth.NEW_SITE_MIN) / growth.NEW_SITE_MIN), "Size test"),
        (2, "Women a typical new lounge would serve", _num(f.get("new_site_served")), None, "Huff split with our lounges and rivals"),
        (2, "…of which taken from our lounges", _num(f.get("new_site_taken")), None, "Cannibalisation, netted off"),
        (1, f"Out-serves its emirate's salon sites (line {growth.DEMAND_PCT_MIN:.0%})", _pct(pct),
         None if pct is None else _clip((pct - growth.DEMAND_PCT_MIN) / (1 - growth.DEMAND_PCT_MIN)), "Demand test"),
        (1, "Rent ratio (line 1x)", "median only" if fallback else _num(ratio, "{:.2f}x"),
         0.0 if fallback else (None if ratio is None else _clip((ratio - 1) / 0.5)),
         "Rent test; neutral (passes, low confidence) when only the emirate median is known"),
        (1, f"Worker housing (cap {growth.WORKER_CAP:.0%})", _pct(f.get("worker_share")),
         None if f.get("worker_share") is None else _clip((growth.WORKER_CAP - f["worker_share"]) / growth.WORKER_CAP),
         "Mostly worker housing caps the call at WATCH"),
        (1, f"Searched for competitors (needs {growth.MIN_COVERAGE:.0%})", _pct(f.get("data_coverage")),
         None if f.get("data_coverage") is None else _clip((f["data_coverage"] - growth.MIN_COVERAGE) / (1 - growth.MIN_COVERAGE)),
         "Less makes the call low confidence"),
        (0, "Context, not scored", "", None, ""),
        (1, "Women 15+ living here", _num(f.get("women")), None, "The place itself"),
        (1, "Nearest lounge (km, straight line)", _num(f.get("nearest_lounge_km"), "{:.1f}"), None, str(f.get("nearest_lounge_id", ""))),
    ]


def render(kind: str, facts: dict) -> None:
    df = _rows(lounge_tree(facts) if kind == "lounge" else area_tree(facts))
    pulls = df.pop("_pull")
    styled = df.style.apply(lambda row: [_colour(pulls[row.name]) if c in ("Factor", "Value") else ""
                                         for c in row.index], axis=1)
    st.dataframe(styled, hide_index=True, column_config={
        "Factor": st.column_config.TextColumn(width="large"),
        "Why it matters": st.column_config.TextColumn(width="large")})
    st.caption("Green pulls the call up (toward PROTECT, or passes a test), red pulls it down; deeper = "
               "stronger. Unshaded rows are context or yardsticks.")
