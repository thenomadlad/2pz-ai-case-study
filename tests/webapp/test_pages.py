import time

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


PAGES = [("overview", {}), ("overview", {"lounge": "al-barsha"}), ("overview", {"area": "sharjah-sharjah"}),
         ("lounge", {"lounge": "al-barsha"}), ("lounge", {"lounge": "zayed-international-airport"}),
         ("area", {"area": "sharjah-sharjah"}), ("area", {"area": "madinat-hind-4-dubai"}), ("how", {})]


def test_every_page_loads_at_baseline_and_with_two_lounges_closed():
    for page, query in PAGES:
        for what_if in (None, CLOSE_TWO):
            at = _page(page, what_if, **query)
            assert not at.exception, (page, query, what_if, at.exception)
            assert any("What-if view" in w.value for w in at.warning) == bool(what_if), (page, query)


def test_overview_full_app_leads_with_summary_then_limitations():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.subheader[0].value == "Executive summary"
    md = [m.value for m in at.markdown]
    box = md.index("#### ⚠️ Before you trust these calls")
    numbered = [m for m in md[:box] if m[:2] in {f"{i}." for i in range(1, 6)}]
    assert 2 <= len(numbered) <= 5                      # the pyramid comes first
    body = md[box + 1]
    assert "No money in the model" in body and "lifetime Google reviews" in body
    assert "**10 of 23**" in body and "Sharjah" in body    # live low-confidence count
    assert "Affluence is observed in Dubai only" in body and "27+ of the 81" in body


def test_overview_shows_cached_ai_summary():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert any(c.value.startswith("AI-written (cached)") for c in at.caption)


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
    at = _page("overview", lounge="al-barsha")
    start = time.perf_counter()
    at.selectbox(key="wi-travel").set_value("high").run()
    assert time.perf_counter() - start < 2
    assert not at.exception
    assert at.session_state["what_if"]["levels"] == Levels(travel="high")
    assert any("What-if view" in w.value and "20 min (high)" in w.value for w in at.warning)
    assert any("numbers changed by the what-if" in c.value for c in at.caption)
    assert any("What changed from the baseline" in m.value for m in at.markdown)
    at.button(key="wi-reset").click().run()
    assert not at.exception and not any("What-if view" in w.value for w in at.warning)


def test_closing_lounges_from_the_panel_shows_what_changed():
    at = _page("overview")
    at.multiselect(key="wi-closed").set_value(["al-barsha", "city-walk"]).run()
    assert not at.exception
    assert at.session_state["what_if"]["closed"] == frozenset({"al-barsha", "city-walk"})
    assert "**al-barsha**: HOLD → closed" in _text(at)


def test_level_selectors_show_actual_values():
    at = _page("overview")
    sb = at.selectbox(key="wi-travel")
    assert sb.options == ["10 min (low)", "15 min (medium)", "20 min (high)"]
    assert at.selectbox(key="wi-affluence").options == [
        "off (low)", "medium: rent^0.5 (medium)", "strong: rent^1 (high)"]
    assert at.number_input(key="wi-recall").value == 0.66


def test_lounge_page_shows_al_barshas_caveats_beside_the_call():
    at = _page("lounge", lounge="al-barsha")
    assert not at.exception
    caveats = next(w.value for w in at.warning if "Caveats for this lounge" in w.value)
    assert "Confidence: low" in caveats
    assert "within 0.05 of the SHRINK line" in caveats
    assert "changes in 27 of 81" in caveats
    assert "No revenue, rent or footfall data" in caveats
    assert "Threshold" in at.table[-1].value.columns
    assert "PROTECT ≥ 0.65" in " ".join(at.table[-1].value["Threshold"])


def test_lounge_specific_caveats():
    assert "lifetime Google reviews" in _text(_page("lounge", lounge="noya-plaza"))
    assert "Market overstated" in _text(_page("lounge", lounge="mirdif-35"))
    airport = _text(_page("lounge", lounge="zayed-international-airport"))
    assert "serves travellers" in airport and "Confidence: low" not in airport


def test_area_page_caveats():
    sharjah = _text(_page("area", area="sharjah-sharjah"))
    assert "only Sharjah lounges (al-jada, zawaya-walk)" in sharjah and "al-jada is nearest" in sharjah and "straight line" in sharjah
    assert "covers only 3%" in _text(_page("area", area="madinat-hind-4-dubai"))


def test_area_picker_leaves_out_areas_under_the_skip_floor():
    from src.baseline import run
    from src.model import growth
    r = run()
    thin = next(a.area_id for a in r.areas if a.women < growth.SKIP_UNDER_WOMEN)
    at = _page("area", area=thin)
    opts = at.selectbox(key="area-pick").options
    shown = {"Abu Dhabi", "Dubai"}       # the default emirates (a thin area's own emirate isn't ticked)
    assert len(opts) == sum(a.women >= growth.SKIP_UNDER_WOMEN and a.emirate in shown for a in r.areas)
    assert "isn't listed in this view" in _text(at)


def test_pickers_filter_by_emirate_abu_dhabi_and_dubai_by_default():
    from src.baseline import run
    r = run()
    emirate = {f"{f.name} · {d.action}": f.emirate for f, d in zip(r.features, r.decisions)}   # option labels
    at = _page("lounge")
    assert at.checkbox(key="lounge-em-Abu Dhabi").value and at.checkbox(key="lounge-em-Dubai").value
    assert not at.checkbox(key="lounge-em-Sharjah").value
    assert {emirate[b] for b in at.selectbox(key="lounge-pick").options} == {"Abu Dhabi", "Dubai"}
    # a deep link outside the defaults ticks its emirate and shows it, never something else
    at = _page("lounge", lounge="ras-al-khaimah")
    assert at.checkbox(key="lounge-em-Ras Al Khaimah").value
    assert at.selectbox(key="lounge-pick").value == "ras-al-khaimah"
    # unticking narrows the list
    at = _page("lounge")
    at.checkbox(key="lounge-em-Dubai").uncheck().run()
    assert {emirate[b] for b in at.selectbox(key="lounge-pick").options} == {"Abu Dhabi"}


def test_how_page_renders_limitations_market_model_and_every_assumption():
    at = _page("how")
    assert not at.exception
    text = _text(at)
    assert "No money in the model" in text and "Market model" not in at.title[0].value
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


def test_affluence_selector_switches_the_weighting_and_reports_what_changed():
    at = _page("overview")
    at.selectbox(key="wi-affluence").set_value("low").run()
    assert not at.exception
    assert at.session_state["what_if"]["levels"] == Levels(affluence="low")
    assert any("affluence weighting off (low)" in w.value for w in at.warning)
    assert "0 lounge call(s) changed, 2 more lounge(s) moved within their call" in _text(at)   # jumeirah-park, zawaya-walk


def test_lounge_and_area_pages_show_raw_and_addressable_women():
    at = _page("lounge", lounge="al-barsha")
    labels = {m.label: m.value for m in at.metric}
    assert labels["Women 15+ (raw)"] == "272,371" and labels["Addressable women"] == "320,731"
    assert labels["Affluence rent (median, AED/yr)"] == "115,000"
    assert "Affluence unknown here" not in _text(at)
    abu = _page("lounge", lounge="al-ain")
    assert "No observed rents outside Dubai: weighted neutral." in _text(abu)
    assert {m.label: m.value for m in abu.metric}["Affluence rent (median, AED/yr)"] == "no data"
    awir = _text(_page("area", area="al-awir-dubai"))
    assert "Affluence data covers only 38% of the women here" in awir and "Affluence unknown" not in awir
    assert "No observed rents outside Dubai: weighted neutral." in _text(_page("area", area="kalba-sharjah"))


def test_overview_affluence_toggle_adds_the_layer_and_its_legend():
    at = _page("overview")
    box = next(c for c in at.checkbox if c.label == "Affluence (Dubai rents)")
    assert not box.value
    box.check().run()
    assert not at.exception
    assert "uncoloured cells have no data" in _text(at)


def test_untrusted_url_ids_never_reach_markdown():
    evil = "[click](https://evil.example)"
    for page, key in (("overview", "lounge"), ("overview", "area"), ("area", "area"), ("lounge", "lounge")):
        at = _page(page, **{key: evil})
        assert not at.exception
        shown = [e.value for kind in ("markdown", "caption", "info") for e in getattr(at, kind)]
        assert not any("evil.example" in str(v) for v in shown), (page, key)


def test_overview_opens_on_the_question_and_whats_at_stake():
    from src.baseline import run
    from src.webapp.pages.overview import QUESTION, stake
    at = _page("overview")
    assert at.markdown[0].value == f"#### {QUESTION}"
    s, r = stake(run()), run()
    shrink = [f for f in r.features if next(d for d in r.decisions if d.branch_id == f.branch_id).action == "SHRINK"]
    assert 0 < s["SHRINK"][1] <= sum(f.shared_share * f.catchment_women for f in shrink) + 1  # each cell once
    assert s["GROW"][0] == 5     # run-2 fix D1 (saturation line 50 -> 150) added al-jerf-ajman
    labels = {m.label: m.value for m in at.metric}
    assert labels[f"Under pressure: {s['SHRINK'][0]} SHRINK lounges"] == f"{s['SHRINK'][1]:,.0f} women"


def test_overview_compares_lounges_and_ranks_growth_areas_with_filters():
    at = _page("overview")
    lounges, areas = at.dataframe[0].value, at.dataframe[1].value
    assert len(lounges) == 24 and {"Composite", "Demand", "Shared catchment", "Confidence",
                                   "Premium reviews per 1k women"} <= set(lounges.columns)
    assert "Confidence" in areas.columns
    assert list(areas.Call) == sorted(areas.Call) and set(areas.Call) == {"GROW", "WATCH"}   # GROW first
    grow = areas[areas.Call == "GROW"]["Addressable women"]
    assert list(grow) == sorted(grow, reverse=True) and areas.Why.str.len().min() > 0
    at.multiselect(key="cmp-call").set_value(["SHRINK"]).run()
    at.multiselect(key="cmp-area-emirate").set_value(["Sharjah"]).run()
    assert not at.exception
    assert set(at.dataframe[0].value.Call) == {"SHRINK"} and set(at.dataframe[1].value.Emirate) == {"Sharjah"}


def test_overview_panels_show_top_drivers_and_area_tests():
    assert "**Top drivers:** demand 1.00 (weight 1)" in _text(_page("overview", lounge="al-barsha"))
    assert "**The tests:** ✅ big enough" in _text(_page("overview", area="sharjah-sharjah"))


def test_lounge_page_shows_address_and_says_services_are_missing():
    text = _text(_page("lounge", lounge="al-barsha"))
    assert "Umm Suqeim St" in text and "Services offered and price tier" in text


def test_overview_overlap_toggle_adds_its_legend():
    at = _page("overview")
    next(c for c in at.checkbox if c.label == "All catchments (overlap)").check().run()
    assert not at.exception and "shared** by 2+ lounges" in _text(at)
