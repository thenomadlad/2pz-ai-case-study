from streamlit.testing.v1 import AppTest

APP = "../../streamlit_app.py"
# Any page as the landing page, so tests can open it with ?area=... / ?branch=... directly.
PAGE_APP = ("import streamlit as st\nfrom src.webapp import nav\n"
            "st.navigation(nav.pages(default='{page}')).run()")


def st_query(at: AppTest, key: str) -> str:
    value = at.query_params[key]
    return value[0] if isinstance(value, list) else value


def _page(page: str, **query) -> AppTest:
    at = AppTest.from_string(PAGE_APP.format(page=page), default_timeout=30)
    for k, v in query.items():
        at.query_params[k] = v
    return at.run()


def test_overview_leads_with_the_executive_summary():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.subheader[0].value == "Executive summary"
    # The answer, then 2-5 numbered arguments.
    numbered = [m.value for m in at.markdown if m.value[:2] in {f"{i}." for i in range(1, 6)}]
    assert 2 <= len(numbered) <= 5
    roic = next(e for e in at.expander if "return-on-invested-capital" in e.label)
    assert "Revenue per branch" in str(roic.table[0].value)


def test_overview_reopens_the_panel_for_a_branch_in_the_url():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["branch"] = "al-safa-2"
    at.run()
    assert not at.exception
    assert any("Al Safa" in s.value for s in at.subheader)


def test_area_page_summarises_what_is_left_and_links_its_branches():
    at = _page("area", area="al-barsha-second")
    assert not at.exception
    assert at.header[0].value == "Area: Al Barsha Second"
    metrics = {m.label: m.value for m in at.metric}
    assert {"Room for more salons", "Women not covered by Bedashing",
            "Bedashing fair share"} <= set(metrics)
    assert metrics["Bedashing fair share"] == "5%"  # 2 Bedashing branches among 38 salons


def test_area_page_follows_the_url_when_revisited_in_the_same_session():
    """Arriving again in the same session with a different ?area= shows that area. (The
    original bug, a stale selector value replayed by the browser, only reproduces in a real
    browser; it was verified there with Playwright.)"""
    at = _page("area", area="al-rifa")
    assert at.header[0].value == "Area: Al Rifa"
    at.query_params["area"] = "al-safa-first"
    at.run()
    assert not at.exception
    assert at.header[0].value == "Area: Al Safa First"
    assert st_query(at, "area") == "al-safa-first"


def test_branch_page_shows_its_catchment_and_scores():
    at = _page("branch", branch="al-safa-2")
    assert not at.exception
    assert at.header[0].value.startswith("Branch:") and "Al Safa" in at.header[0].value
    assert any("Catchment:" in m.value for m in at.markdown)
    assert any("SHRINK" in e.value for e in at.error)  # the verdict line


def test_branch_override_run_reset_flow():
    """A per-branch what-if runs a scenario, shows the scenario banner, and "Reset to
    baseline" clears both the override and the widget's remembered value."""
    at = _page("branch", branch="al-safa-2")
    assert not at.exception
    slider = at.slider(key="rating-al-safa-2-0")
    baseline_value = slider.value
    slider.set_value(1.0).run()
    at.button(key="apply-al-safa-2").click().run()
    assert at.session_state["branch_overrides"]["al-safa-2"]["rating"] == 1.0

    at.button(key="run-al-safa-2").click().run()
    assert not at.exception
    assert "scenario_run" in at.session_state
    assert any("Scenario view" in w.value for w in at.warning)

    at.button(key="reset-al-safa-2").click().run()
    assert not at.exception
    assert at.session_state["branch_overrides"] == {}
    assert "scenario_run" not in at.session_state
    # The nonce bumped, so the slider is a fresh component showing the baseline again.
    assert at.slider(key="rating-al-safa-2-1").value == baseline_value


def test_catchment_layers_appear_only_for_a_selected_branch():
    from src.config import settings
    from src.webapp.data import load_baseline
    from src.webapp.pages.overview import map_layers

    data = load_baseline(settings)
    ids = lambda layers: [layer.id for layer in layers]
    none = ids(map_layers(data, None, True, False))
    assert "communities" not in none and "assignment-lines" not in none
    assert none[-2:] == ["branches", "branch-flags"]  # flags on top, on every map
    picked = ids(map_layers(data, "al-safa-2", True, True))
    assert {"communities", "assignment-lines", "competitors"} <= set(picked)


def test_overview_side_panel_has_toggles_and_legend_with_thresholds():
    at = AppTest.from_file(APP, default_timeout=30).run()
    labels = [c.label for c in at.checkbox]
    assert labels == ["Opportunity areas", "Competitor salons"]  # catchment toggles removed
    legend = " ".join(m.value for m in at.markdown)
    assert "composite ≥ 0.65" in legend and "composite ≤ 0.35" in legend
    assert "nearest branch over 5 km" in legend


def test_factor_tables_have_a_threshold_column():
    area = _page("area", area="al-safa-first")
    branch = _page("branch", branch="al-safa-2")
    assert not area.exception and not branch.exception
    assert "Threshold" in area.table[0].value.columns
    assert "PROTECT ≥ 0.65" in " ".join(branch.table[1].value["Threshold"])  # after catchment
