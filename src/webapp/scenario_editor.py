"""The What-if explorer's scenario: the summary against the baseline (always shown) and the panel that
sets it: model assumptions (drive time, competitor coverage, worker-housing share, search recall), the
portfolio team's decision rules, rent quotes and closed lounges. Widgets write into data.what_if() on
change; everything recomputes through baseline.run()."""
import pandas as pd
import streamlit as st

from src.baseline import Run, diff, run
from src.model import scorecard
from src.models import Levels, Rules
from src.webapp import data
from src.webapp.pages.overview import served_market
from src.webapp.views import level_label, quote_label, short, site_name

LEVELS = ("low", "medium", "high")
_AXES = (("travel", "Travel time to a lounge"), ("coverage", "Competitor coverage"),
         ("worker_share", "Women in worker housing"))     # scorecard.LIVE_AXES; affluence stays off (Levels default)
SIGNAL_WORDS = {"demand": "site demand", "cost": "site rent"}


# --- the summary ------------------------------------------------------------------------

def _measures(r: Run) -> dict[str, float]:
    calls = {d.branch_id: d for d in r.decisions}
    served = served_market(r)
    in_call = lambda a: sum(f.served_women or 0 for f in r.features if calls[f.branch_id].action == a)
    grow = [a for a, d in zip(r.areas, r.area_decisions) if d.action == "GROW"]
    acts = [d.action for d in r.area_decisions]
    return {**{f"{k} lounges": v for k, v in scorecard.counts(r.decisions).items()},
            "Low-confidence lounge calls": sum(d.confidence == "low" for d in r.decisions if d.action != "NOT SCORED"),
            **{f"{k} areas": acts.count(k) for k in ("GROW", "WATCH", "SKIP")},
            "Women our lounges serve (model est.)": served,
            "… of them in PROTECT lounges": in_call("PROTECT") / served,
            "… of them in SHRINK lounges": in_call("SHRINK") / served,
            "Best GROW area: est. growth": max((a.new_site_net or 0 for a in grow), default=0) / served}


def _fmt(label: str, v: float, change: bool = False) -> str:
    sign = "+" if change and v > 0 else ""
    if label.startswith(("…", "Best")):
        return f"{sign}{v * 100:.1f} pts" if change else f"{v:.1%}" if label.startswith("…") else f"+{v:.1%}"
    return f"{sign}{v:,.0f}"


def summary_table(base: Run, cur: Run) -> pd.DataFrame:
    """Baseline | This scenario | Change, one row per measure."""
    b, c = _measures(base), _measures(cur)
    return pd.DataFrame(
        {"Baseline": [_fmt(k, b[k]) for k in b], "This scenario": [_fmt(k, c[k]) for k in b],
         "Change": ["—" if abs(c[k] - b[k]) < 1e-9 else _fmt(k, c[k] - b[k], True) for k in b]}, index=list(b))


def diff_lines(base: Run, cur: Run) -> list[str]:
    """What changed, in markdown: every lounge call that changed (old struck, new bold) with the main
    reason, lounges that moved within their call, and growth areas that gained or lost GROW."""
    d = diff(base, cur)
    if d.empty:
        return []
    name = lambda sid: quote_label(sid, cur.quotes[sid]) if sid in cur.quotes else site_name(sid)
    out = []
    for c in (c for c in d.lounges if c.old_action != c.new_action):
        if c.new_action is None:
            out.append(f"- **{name(c.branch_id)}**: ~~{c.old_action}~~ → closed")
            continue
        s = c.main_signal
        why = (f"{SIGNAL_WORDS[s]} score {c.old_scores[s]:.2f} → {c.new_scores[s]:.2f}" if s
               else f"composite {c.old_composite:.2f} → {c.new_composite:.2f}" if c.old_composite != c.new_composite
               else f"composite {c.new_composite:.2f} against the new lines")
        out.append(f"- **{name(c.branch_id)}**: ~~{c.old_action}~~ → **{c.new_action}** ({why})")
    within = [c for c in d.lounges if c.old_action == c.new_action]
    if within:
        out.append(f"- Moved within their call ({len(within)}): " + ", ".join(
            f"{name(c.branch_id)} {c.old_composite:.2f} → {c.new_composite:.2f}" for c in within))
    act = {a.area_id: a.action for a in cur.area_decisions}
    net = {a.area_id: f"adds {a.new_site_net or 0:,.0f} net new women" for a in cur.areas}
    grow = [f"- **{name(c.area_id)}**: ~~{c.old_action}~~ → **{c.new_action}** ({net[c.area_id]})"
            for c in d.areas_changed if "GROW" in (c.old_action, c.new_action)]
    grow += [f"- **{name(i)}**: new area, **GROW** ({net[i]})" for i in d.areas_appeared if act[i] == "GROW"]
    return out + grow + [(f"- Growth areas: {len(d.areas_appeared)} appeared, {len(d.areas_disappeared)} "
                          f"disappeared, {len(d.areas_changed)} changed call.")]


def render_summary() -> None:
    base, cur = data.baseline(), data.current()
    st.markdown("##### This scenario against the baseline")
    st.table(summary_table(base, cur))
    st.markdown("**What changed**")
    lines = diff_lines(base, cur)
    st.markdown("\n".join(lines) if lines else "Nothing yet — change an assumption, a rule or a rent below.")


# --- the panel --------------------------------------------------------------------------

def _rules() -> Rules:
    s = st.session_state
    return Rules(demand_weight=s["wi-dw"] / 100, protect_at=round(s["wi-protect"], 2),
                 shrink_at=round(s["wi-shrink"], 2), grow_min=int(s["wi-growmin"]),
                 demand_pct_min=s["wi-growpct"] / 100)


def _apply(w: dict) -> None:
    """Store `w` if it runs; else keep the last valid what-if and say why."""
    try:
        run(w["levels"], w["closed"], w["recall"], w["rules"], w["quotes"])
    except ValueError as e:     # e.g. every scored lounge closed, or SHRINK above PROTECT
        st.session_state["wi-error"] = str(e)
        return
    st.session_state.pop("wi-error", None)
    st.session_state["what_if"] = w


def _sync() -> None:
    s = st.session_state
    recall = s["wi-recall"]
    _apply({"levels": Levels(**{axis: s[f"wi-{axis}"] for axis, _ in _AXES}),
            "closed": frozenset(s["wi-closed"]),
            "recall": None if abs(recall - data.assumptions().search_recall) < 1e-9 else recall,
            "rules": _rules(), "quotes": dict(data.what_if()["quotes"])})


def _add_quote() -> None:
    s, w = st.session_state, data.what_if()
    if s.get("wi-q-site"):
        _apply({**w, "quotes": {**w["quotes"], s["wi-q-site"]: float(s["wi-q-rent"])}})


def _remove_quote(sid: str) -> None:
    w = data.what_if()
    _apply({**w, "quotes": {k: v for k, v in w["quotes"].items() if k != sid}})


def _reset() -> None:
    st.session_state.pop("wi-error", None)
    st.session_state["what_if"] = data.empty_what_if()


def _mirror(w: dict) -> None:
    """Widgets mirror the stored what-if each run (they are dropped on pages that don't show them)."""
    s = st.session_state
    for axis, _ in _AXES:
        s[f"wi-{axis}"] = getattr(w["levels"], axis)
    s["wi-recall"] = w["recall"] if w["recall"] is not None else data.assumptions().search_recall
    s["wi-closed"] = sorted(w["closed"])
    r = w["rules"]
    s["wi-dw"], s["wi-protect"], s["wi-shrink"] = round(r.demand_weight * 100), r.protect_at, r.shrink_at
    s["wi-growmin"], s["wi-growpct"] = r.grow_min, round(r.demand_pct_min * 100)


def _site_rent(r: Run, sid: str) -> float | None:
    f = next((f for f in r.features if f.branch_id == sid), None)
    if f:
        return f.site_rent_m2
    return next((a.shop_rent_m2 for a in r.areas if a.area_id == sid), None)


def _prefill() -> None:
    """Start the rent box at the picked site's current rent."""
    sid = st.session_state.get("wi-q-site")
    now = _site_rent(data.current(), sid) if sid else None
    if now:
        st.session_state["wi-q-rent"] = min(20_000, max(100, int(round(now, -2))))


def _quote_box(w: dict) -> None:
    st.markdown("**Plug in a quote**: a landlord's rent for a lounge or a growth area re-scores that site "
                "(rent ratio against its emirate's median salon-site rent). A quote is an observation, so it "
                "clears the 'emirate-median fallback' low-confidence flag. Demand doesn't move.")
    r = data.current()
    calls = {d.branch_id: d.action for d in r.decisions}
    acts = {d.area_id: d.action for d in r.area_decisions}
    lounges = sorted((f.branch_id for f in r.features if not f.not_scored), key=site_name)
    areas = sorted((a.area_id for a in r.areas if acts[a.area_id] != "SKIP"), key=lambda i: (acts[i], site_name(i)))
    label = lambda i: f"{site_name(i)} · {calls.get(i) or acts.get(i)} · {'lounge' if i in calls else 'area'}"
    site, rent, add = st.columns([3, 2, 1], vertical_alignment="bottom")
    sid = site.selectbox("Lounge or growth area (GROW and WATCH)", lounges + areas, key="wi-q-site",
                         format_func=label, index=None, placeholder="Pick a site", on_change=_prefill)
    now = _site_rent(r, sid) if sid else None
    st.session_state.setdefault("wi-q-rent", 1500)
    rent.number_input("Quoted rent, AED/m²/yr", min_value=100, max_value=20_000, step=100, key="wi-q-rent",
                      help=f"The data's figure here: AED {now:,.0f}/m²." if now else None)
    add.button("Add quote", on_click=_add_quote, disabled=not sid, key="wi-q-add")
    for q_sid, q in sorted(w["quotes"].items()):
        text, rm = st.columns([5, 1], vertical_alignment="center")
        text.markdown(f"- {quote_label(q_sid, q)}")
        rm.button("Remove", key=f"wi-q-rm-{q_sid}", on_click=_remove_quote, args=(q_sid,))


def render_panel() -> None:
    w = data.what_if()
    _mirror(w)
    with st.expander("🧪 Change the assumptions, your decision rules or a rent, or test a SHRINK",
                     expanded=data.active()):
        if "wi-error" in st.session_state:
            st.error(f"Not applied: {st.session_state['wi-error']}")
        st.markdown("**The model's assumptions**")
        cols = st.columns(len(_AXES))
        for col, (axis, label) in zip(cols, _AXES):
            col.selectbox(label, LEVELS, key=f"wi-{axis}", on_change=_sync,
                          format_func=lambda lv, a=axis: level_label(a, lv))
        st.number_input("Search recall", min_value=0.3, max_value=1.0, step=0.01, key="wi-recall",
                        on_change=_sync, help="Share of premium reviews the search finds where Google's "
                        "20-result cap bites. Baseline 0.66, from one fully swept tile (an upper bound).")

        st.markdown("**Your decision rules** (risk appetite): how demand and rent trade off, where the lounge "
                    "lines sit, and what a new site must clear. The confidence check is unchanged.")
        a, b, c = st.columns(3)
        a.slider("Weight on site demand (rest: site rent)", 0, 100, step=5, key="wi-dw", format="%d%%",
                 on_change=_sync, help="Baseline 50%: the two signals count equally.")
        b.slider("PROTECT line (composite at or above)", 0.30, 0.95, step=0.01, key="wi-protect",
                 on_change=_sync, help="Baseline 0.65. Must stay above the SHRINK line.")
        c.slider("SHRINK line (composite at or below)", 0.05, 0.70, step=0.01, key="wi-shrink",
                 on_change=_sync, help="Baseline 0.35. Must stay below the PROTECT line.")
        a, b = st.columns(2)
        a.number_input("GROW: minimum net new women", min_value=1_000, max_value=30_000, step=500,
                       key="wi-growmin", on_change=_sync, help="Baseline 6,000: about what our median lounge serves.")
        b.slider("GROW: out-serve at least this share of its emirate's salon sites", 0, 100, step=5,
                 key="wi-growpct", format="%d%%", on_change=_sync, help="Baseline 50%: the median salon site.")

        _quote_box(w)

        st.markdown("**Test a SHRINK**: close lounges and see where their customers go (to our other "
                    "lounges, to competitors, or nowhere) and whether any other call moves.")
        calls = {d.branch_id: d.action for d in data.baseline().decisions}
        order = {"SHRINK": 0, "HOLD": 1, "PROTECT": 2}
        names = {lo.branch_id: short(lo.title, lo.branch_id) for lo in data.v3().lounges}
        st.multiselect("Close lounges", sorted(names, key=lambda b: (order.get(calls.get(b), 3), names[b])),
                      key="wi-closed", on_change=_sync, format_func=lambda b: f"{names[b]} · {calls.get(b, '')}",
                      placeholder="SHRINK lounges first")
        st.caption("Opening is evaluated for every area on the Areas page, one area at a time. Opening several "
                   "together isn't modelled yet, which is why growth figures can't be added up (How it works: "
                   "Potential improvements).")
        st.button("Reset to baseline", on_click=_reset, disabled=not data.active(), key="wi-reset")
