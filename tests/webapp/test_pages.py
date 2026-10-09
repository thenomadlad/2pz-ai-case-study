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
    assert at.number_input(key="wi-recall").value == 0.66


def test_lounge_page_shows_al_barshas_caveats_beside_the_call():
    at = _page("lounge", lounge="al-barsha")
    assert not at.exception
    caveats = next(w.value for w in at.warning if "Caveats for this lounge" in w.value)
    assert "Confidence: low" in caveats
    assert "within 0.05 of the SHRINK line" in caveats
    assert "changes in 9 of 27" in caveats
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


def test_how_page_renders_limitations_market_model_and_every_assumption():
    at = _page("how")
    assert not at.exception
    text = _text(at)
    assert "No money in the model" in text and "Market model" not in at.title[0].value
    assert "Capture** = lounge reviews" in text            # SOURCES.md "Market model"
    assumptions = at.table[0].value
    assert {"travel_time_minutes", "search_recall", "worker_housing_female_share"} <= set(assumptions.index)
    assert "low: 10 · medium: 15 · high: 20" in assumptions.loc["travel_time_minutes"].iloc[0]
    assert "autogenerated" not in assumptions.loc["travel_time_minutes"].iloc[0]
    assert any("UNSATURATED_PER_1K" in t.value.index for t in at.table)


def test_area_page_follows_the_url_when_revisited_in_the_same_session():
    at = _page("area", area="sharjah-sharjah")
    assert at.header[0].value == "Area: Sharjah, Sharjah"
    at.query_params["area"] = "kalba-sharjah"
    at.run()
    assert not at.exception and at.header[0].value == "Area: Kalba, Sharjah"
