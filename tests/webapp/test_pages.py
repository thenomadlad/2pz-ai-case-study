import time

import pytest
from streamlit.testing.v1 import AppTest

from src.models import Levels

APP = "../../streamlit_app.py"
# Any page as the landing page, so tests can open it with ?lounge=... / ?area=... directly.
PAGE_APP = ("import streamlit as st\nfrom src.webapp import nav\n"
            "st.navigation(nav.pages(default='{page}')).run()")
CLOSE_TWO = {"levels": Levels(), "closed": frozenset({"al-barsha", "city-walk"}), "recall": None}


def _page(page: str, what_if: dict | None = None, **query) -> AppTest:
    at = AppTest.from_string(PAGE_APP.format(page=page), default_timeout=30)
    for k, v in query.items():
        at.query_params[k] = v
    if what_if:
        at.session_state["what_if"] = what_if
    return at.run()


def _text(at: AppTest) -> str:
    return " ".join(e.value for kind in ("markdown", "warning", "info", "caption", "error")
                    for e in getattr(at, kind))


PAGES = [("overview", {}), ("predictions", {}), ("predictions", {"lounge": "al-barsha"}),
         ("predictions", {"area": "sharjah-sharjah"}),
         ("lounge", {"lounge": "al-barsha"}), ("lounge", {"lounge": "zayed-international-airport"}),
         ("area", {"area": "sharjah-sharjah"}), ("area", {"area": "madinat-hind-4-dubai"}), ("how", {})]


def test_every_page_loads_at_baseline_and_with_two_lounges_closed():
    for page, query in PAGES:
        for what_if in (None, CLOSE_TWO):
            at = _page(page, what_if, **query)
            assert not at.exception, (page, query, what_if, at.exception)
            # only the What-if explorer reads the what-if; every other page shows the baseline
            assert any("What-if view" in w.value for w in at.warning) == (bool(what_if) and page == "predictions"), (page, query)


def test_overview_full_app_leads_with_summary_then_limitations():
    from src.baseline import run as run_
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    from src.webapp.pages.overview import pyramid
    md = [m.value for m in at.markdown]
    assert md[1] == f"### {pyramid(run_()).get('thought')}"      # the governing thought comes first
    subs = [h.value for h in at.subheader]
    assert subs[:4] == [c[0].upper() + c[1:] for c in pyramid(run_())["claims"].values()][:3] + ["How sure we are"]
    box = md.index("#### ⚠️ Before you trust these calls")
    body = md[box + 1]
    assert "No revenue or lease data in the model" in body and "lifetime Google reviews" in body
    from src.baseline import run
    low = sum(d.confidence == "low" for d in run().decisions if d.action != "NOT SCORED")
    assert f"**{low} of 23**" in body and "Sharjah" in body    # live low-confidence count (7, 2026-10-11)
    assert "Shop rent comes from different sources per emirate" in body
    from src.model import scorecard
    assert f"{scorecard.FLIP_LOW}+ of the {scorecard.COMBOS}" in body


STALE = pytest.mark.xfail(reason="explanations regenerate in the thorough check (drive time and coverage wired "
                                 "into the Huff split: flips and the sensitivity field text changed)")


@STALE
def test_overview_shows_cached_ai_summary():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert any(c.value.startswith("AI-written (cached)") for c in at.caption)


@STALE
def test_baseline_explanations_are_all_ai_except_skip_and_not_scored():
    from src.baseline import run
    from src.webapp.views import explanation_for
    r = run()
    for kind, ids in (("uae", ["uae"]), ("lounge", [f.branch_id for f in r.features]),
                      ("area", [d.area_id for d in r.area_decisions if d.action != "SKIP"])):
        for sid in ids:
            exp, _ = explanation_for(r, kind, sid)
            assert exp.source == ("template" if sid == "zayed-international-airport" else "ai"), (kind, sid)


def test_level_switch_is_fast_and_marks_explanations_as_template():
    at = _page("predictions", lounge="al-barsha")
    start = time.perf_counter()
    at.selectbox(key="wi-worker_share").set_value("high").run()
    # 3 s: a new level re-runs the build plus level_flips' 3 lounge builds
    assert time.perf_counter() - start < 3
    assert not at.exception
    assert at.session_state["what_if"]["levels"] == Levels(worker_share="high")
    assert any("What-if view" in w.value and "women (high)" in w.value for w in at.warning)
    assert any("numbers changed by the what-if" in c.value for c in at.caption)
    assert any("What changed from the baseline" in m.value for m in at.markdown)
    at.button(key="wi-reset").click().run()
    assert not at.exception and not any("What-if view" in w.value for w in at.warning)


def test_what_if_never_leaks_into_the_other_pages():
    from src.baseline import run
    closed = {"levels": Levels(worker_share="high"), "closed": frozenset({"al-barsha"}), "recall": None}
    summary = _page("overview", what_if=closed)
    assert not summary.exception and not any("What-if view" in w.value for w in summary.warning)
    from src.webapp.pages.overview import pyramid
    assert summary.markdown[1].value == f"### {pyramid(run())['thought']}"         # baseline, not the what-if
    lounge = _page("lounge", what_if=closed, lounge="al-barsha")                     # closed in the what-if only
    assert not lounge.exception and lounge.header[0].value == "Lounge: Al Barsha"


def test_closing_lounges_from_the_panel_shows_what_changed():
    at = _page("predictions")
    at.multiselect(key="wi-closed").set_value(["al-barsha", "city-walk"]).run()
    assert not at.exception
    assert at.session_state["what_if"]["closed"] == frozenset({"al-barsha", "city-walk"})
    assert "**city-walk**: SHRINK → closed" in _text(at)    # SHRINK under the salon-site reference (2026-10-11)


def test_level_selectors_show_actual_values():
    at = _page("predictions")
    sb = at.selectbox(key="wi-worker_share")
    assert [o.split()[-1] for o in sb.options] == ["(low)", "(medium)", "(high)"] and "% women" in sb.options[0]
    assert at.selectbox(key="wi-travel").options == ["10 min (low)", "15 min (medium)", "20 min (high)"]
    assert at.selectbox(key="wi-coverage").options[1] == "60% of premium reviews (medium)"
    assert not any(sb.key == "wi-affluence" for sb in at.selectbox)       # affluence isn't offered in the app
    assert at.number_input(key="wi-recall").value == 0.66


def _tree(at):
    """The factor tree under the signals: the dataframe with Factor and Effect columns (shown via a Styler)."""
    for d in at.dataframe:
        v = getattr(d.value, "data", d.value)
        if {"Factor", "Effect"} <= set(v.columns):
            return v
    raise AssertionError("no factor tree on the page")


def test_lounge_page_shows_caveats_beside_the_call():
    # salon-site reference 2026-10-11: al-barsha is a HOLD within 0.05 of the SHRINK line
    at = _page("lounge", lounge="al-barsha")
    assert not at.exception
    caveats = next(w.value for w in at.warning if "Caveats for this lounge" in w.value)
    assert "Confidence: low" in caveats
    assert "within 0.05 of the SHRINK line" in caveats
    assert "No revenue, lease or footfall data" in caveats
    tree = _tree(at)                                      # 'What would change the call' as a tree
    assert list(tree.Factor[:2]) == ["Composite", "├─ Site demand score (weight 1)"]
    assert tree.Effect[0] < 0                             # near SHRINK: the composite row is shaded red


def test_lounge_page_says_performance_vs_site_is_context():
    from src.baseline import run
    f = next(f for f in run().features if f.branch_id == "khalifa-city-a")
    text = _text(_page("lounge", lounge="khalifa-city-a"))
    assert f"The model estimates this lounge is performing {f.performance_vs_site:.1f}x compared to its site" in text
    assert "Context, not scored" in text


def test_lounge_specific_caveats():
    assert "lifetime Google reviews" in _text(_page("lounge", lounge="noya-plaza"))
    assert "Market overstated" in _text(_page("lounge", lounge="mirdif-35"))
    airport = _text(_page("lounge", lounge="zayed-international-airport"))
    assert "serves travellers" in airport and "Confidence: low" not in airport


def test_area_page_caveats():
    sharjah = _text(_page("area", area="sharjah-sharjah"))
    assert "only Sharjah lounges (al-jada, zawaya-walk)" in sharjah and "al-jada is nearest" in sharjah and "straight line" in sharjah
    assert "Only 3% of its women were searched for competitors" in _text(_page("area", area="madinat-hind-4-dubai"))


def test_area_link_opens_an_area_the_table_leaves_out():
    # the table is the picker (SKIP left out); a ?area= link (the map's) still opens any area
    from src.baseline import run
    from src.model import growth
    r = run()
    thin = next(a for a in r.areas if a.women < growth.SKIP_UNDER_WOMEN)
    at = _page("area", area=thin.area_id)
    assert not at.exception and thin.area_id not in at.dataframe[0].value.index.tolist()
    assert at.header[0].value == f"Area: {thin.name}, {thin.emirate}"


def test_pages_default_to_the_top_row_and_ignore_unknown_links():
    from src.baseline import run
    r = run()
    top = max((d for d in r.decisions if d.composite is not None), key=lambda d: d.composite).branch_id
    for q in ({}, {"lounge": "no-such-lounge"}):
        at = _page("lounge", **q)
        assert not at.exception and at.query_params["lounge"] == top
    at = _page("lounge", lounge="al-jada")
    assert at.header[0].value == "Lounge: Al Jada"
    at = _page("area")
    first = at.dataframe[0].value
    assert first.Call.iloc[0] == "GROW" and at.query_params["area"] == first.index[0]


def test_how_page_renders_limitations_market_model_and_every_assumption():
    at = _page("how")
    assert not at.exception
    text = _text(at)
    assert "No revenue or lease data in the model" in text and "Market model" not in at.title[0].value
    assert "Capture** = lounge reviews" in text            # SOURCES.md "Market model"
    assumptions = at.table[0].value
    assert {"travel_time_minutes", "search_recall", "worker_housing_female_share"} <= set(assumptions.index)
    assert "low: 10 · medium: 15 · high: 20" in assumptions.loc["travel_time_minutes"].iloc[0]
    assert "Baseline assumptions" not in assumptions.loc["travel_time_minutes"].iloc[0]
    assert any("UNSATURATED_PER_1K" in t.value.index for t in at.table)


def test_area_page_follows_the_url_when_revisited_in_the_same_session():
    at = _page("area", area="sharjah-sharjah")
    assert at.header[0].value == "Area: Sharjah, Sharjah"
    at.query_params["area"] = "kalba-sharjah"
    at.run()
    assert not at.exception and at.header[0].value == "Area: Kalba, Sharjah"


def test_untrusted_url_ids_never_reach_markdown():
    evil = "[click](https://evil.example)"
    for page, key in (("predictions", "lounge"), ("predictions", "area"), ("area", "area"), ("lounge", "lounge")):
        at = _page(page, **{key: evil})
        assert not at.exception
        shown = [e.value for kind in ("markdown", "caption", "info") for e in getattr(at, kind)]
        assert not any("evil.example" in str(v) for v in shown), (page, key)


def test_overview_opens_on_the_question_and_its_pyramid():
    """Governing thought, then review / grow / protect, each backed by exactly its lounges or areas."""
    from src.baseline import run
    from src.webapp.pages.overview import QUESTION, pyramid
    at = _page("overview")
    assert at.markdown[0].value == f"#### {QUESTION}"
    r = run()
    p, calls = pyramid(r), {d.branch_id: d.action for d in r.decisions}
    assert {f.branch_id for f in p["shrink"]} == {b for b, a in calls.items() if a == "SHRINK"}
    assert {f.branch_id for f in p["protect"]} == {b for b, a in calls.items() if a == "PROTECT"}
    assert len(p["grow"]) == sum(d.action == "GROW" for d in r.area_decisions) > 0
    assert f"Review {len(p['shrink'])} weak" in p["thought"] and f"test {len(p['grow'])} areas" in p["thought"]
    net = [a.new_site_net for a in p["grow"]]
    assert net == sorted(net, reverse=True)                       # best area first
    evidence = [d.value for d in at.dataframe[:3]]               # review, grow, protect tables
    assert len(evidence[0]) == len(p["shrink"]) and len(evidence[1]) == len(p["grow"])
    assert len(evidence[2]) == len(p["protect"])
    assert p["base"] == sum(f.served_women or 0 for f in r.features) > 0     # % are of our served market
    assert "grow our served market by" in p["claims"]["grow"]
    assert evidence[1]["Est. growth"].iloc[0] == round(100 * p["grow"][0].new_site_net / p["base"])


def test_lounge_and_area_pages_open_on_their_full_tables_with_filters():
    at, ar = _page("lounge"), _page("area")
    lounges, areas = at.dataframe[0].value, ar.dataframe[0].value
    assert len(lounges) == 24 and {"Composite", "Demand", "Shared catchment", "Confidence",
                                   "Premium reviews per 1k women"} <= set(lounges.columns)
    assert "Confidence" in areas.columns
    assert not any(c.startswith("Call at") for c in [*lounges.columns, *areas.columns])   # owner: column dropped
    assert list(areas.Call) == sorted(areas.Call) and set(areas.Call) == {"GROW", "WATCH"}   # GROW first
    grow = areas[areas.Call == "GROW"]["Net new women"]
    assert list(grow) == sorted(grow, reverse=True) and areas.Why.str.len().min() > 0
    at.multiselect(key="cmp-call").set_value(["SHRINK"]).run()
    ar.multiselect(key="cmp-area-emirate").set_value(["Sharjah"]).run()
    assert not at.exception and not ar.exception
    assert set(at.dataframe[0].value.Call) == {"SHRINK"} and set(ar.dataframe[0].value.Emirate) == {"Sharjah"}


def test_overview_panels_show_top_drivers_and_area_tests():
    from src.baseline import run
    from src.explain import performance_sentence
    r = run()
    d = next(d for d in r.decisions if d.branch_id == "al-barsha")
    f = next(f for f in r.features if f.branch_id == "al-barsha")
    text = _text(_page("predictions", lounge="al-barsha"))
    assert "**Top drivers:** " + " · ".join(f"{n} {d.scores[n]:.2f} (weight 1)" for n in d.key_drivers) in text
    assert performance_sentence(f.performance_vs_site) in text and "Context, not scored" in text
    assert "**The tests:** ✅ big enough" in _text(_page("predictions", area="sharjah-sharjah"))


def test_lounge_page_shows_address_and_says_services_are_missing():
    text = _text(_page("lounge", lounge="al-barsha"))
    assert "Umm Suqeim St" in text and "Services offered and price tier" in text


def test_overview_overlap_toggle_adds_its_legend():
    at = _page("predictions")
    next(c for c in at.checkbox if c.label == "All catchments (overlap)").check().run()
    assert not at.exception and "shared** by 2+ lounges" in _text(at)


def test_shop_rent_shows_as_cost_with_the_unit_assumption():
    lounge = _tree(_page("lounge", lounge="al-barsha")).to_string()                          # factor tree
    assert "Shop rent at the site" in lounge and "AED/m²/yr" in lounge
    lounges, areas = _page("lounge"), _page("area")
    assert "Shop rent (AED/m²/yr)" in lounges.dataframe[0].value.columns
    assert "Shop rent is our cost; women per AED 1k assumes a 150 m² unit." in _text(lounges)
    # review I2: the area table carries the unit assumption too; I3: the mall/street caveat is shown
    assert "assumes a 150 m² unit" in _text(areas)
    assert "mixes mall and street shops" in lounge
