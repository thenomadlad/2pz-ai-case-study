"""The what-if panel (What-if explorer): four assumption levels, search recall and closed lounges. Widgets
write into data.what_if() on change; everything recomputes through baseline.run()."""
import streamlit as st

from src.baseline import diff, run
from src.models import Levels
from src.webapp import data
from src.webapp.views import level_label, short

LEVELS = ("low", "medium", "high")
_AXES = (("travel", "Travel time to a lounge"), ("coverage", "Competitor coverage"),
         ("worker_share", "Women in worker housing"))     # affluence stays off (Levels default)


def _sync() -> None:
    s = st.session_state
    recall = s["wi-recall"]
    w = {"levels": Levels(**{axis: s[f"wi-{axis}"] for axis, _ in _AXES}),
         "closed": frozenset(s["wi-closed"]),
         "recall": None if abs(recall - data.assumptions().search_recall) < 1e-9 else recall}
    try:
        run(w["levels"], w["closed"], w["recall"])
    except ValueError as e:     # e.g. every scored lounge closed: keep the last valid what-if
        s["wi-error"] = str(e)
        return
    s.pop("wi-error", None)
    s["what_if"] = w


def _reset() -> None:
    st.session_state.pop("wi-error", None)
    st.session_state["what_if"] = {"levels": Levels(), "closed": frozenset(), "recall": None}


def render_panel() -> None:
    w = data.what_if()
    # Widgets mirror the stored what-if each run (they are dropped on pages that don't show them).
    for axis, _ in _AXES:
        st.session_state[f"wi-{axis}"] = getattr(w["levels"], axis)
    st.session_state["wi-recall"] = w["recall"] if w["recall"] is not None else data.assumptions().search_recall
    st.session_state["wi-closed"] = sorted(w["closed"])

    with st.expander("🧪 Change the assumptions, or test a SHRINK", expanded=True):
        if "wi-error" in st.session_state:
            st.error(f"Not applied: {st.session_state['wi-error']}")
        cols = st.columns(len(_AXES))
        for col, (axis, label) in zip(cols, _AXES):
            col.selectbox(label, LEVELS, key=f"wi-{axis}", on_change=_sync,
                          format_func=lambda lv, a=axis: level_label(a, lv))
        st.number_input("Search recall", min_value=0.3, max_value=1.0, step=0.01, key="wi-recall",
                        on_change=_sync, help="Share of premium reviews the search finds where Google's "
                        "20-result cap bites. Baseline 0.66, from one fully swept tile (an upper bound).")
        st.markdown("**Test a SHRINK**: close lounges and see where their customers go (to our other "
                    "lounges, to competitors, or nowhere) and whether any other call moves.")
        calls = {d.branch_id: d.action for d in data.baseline().decisions}
        order = {"SHRINK": 0, "HOLD": 1, "PROTECT": 2}
        names = {lo.branch_id: short(lo.title) for lo in data.v3().lounges}
        st.multiselect("Close lounges", sorted(names, key=lambda b: (order.get(calls.get(b), 3), names[b])),
                      key="wi-closed", on_change=_sync, format_func=lambda b: f"{names[b]} · {calls.get(b, '')}",
                      placeholder="SHRINK lounges first")
        st.caption("Opening is evaluated for every area on the Areas page, one area at a time. Opening several "
                   "together isn't modelled yet, which is why growth figures can't be added up (README: "
                   "Potential improvements).")
        st.button("Reset to baseline", on_click=_reset, disabled=not data.active(), key="wi-reset")
        if data.active():
            _render_diff()


def _render_diff() -> None:
    cur = data.current()
    d = diff(run(), cur)
    st.markdown("**What changed from the baseline**")
    if d.empty:
        st.caption("Nothing: every lounge's signals and every growth area's call are the same.")
        return
    calls = [c for c in d.lounges if c.old_action != c.new_action]
    lines = [f"- **{c.branch_id}**: {c.old_action or '—'} → {c.new_action or 'closed'}" for c in calls]
    moved = len(d.lounges) - len(calls)
    st.markdown(f"{len(calls)} lounge call(s) changed, {moved} more lounge(s) moved within their call.\n"
                + "\n".join(lines))
    act = {a.area_id: a.action for a in cur.area_decisions}
    grow = [f"**{c.area_id}**: {c.old_action} → {c.new_action}" for c in d.areas_changed
            if "GROW" in (c.old_action, c.new_action)]
    grow += [f"**{i}**: new area, GROW" for i in d.areas_appeared if act[i] == "GROW"]
    st.markdown(
        f"Growth areas: {len(d.areas_appeared)} appeared, {len(d.areas_disappeared)} disappeared, "
        f"{len(d.areas_changed)} changed call." + "".join(f"\n- {g}" for g in grow))
