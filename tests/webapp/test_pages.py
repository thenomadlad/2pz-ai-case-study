from streamlit.testing.v1 import AppTest


def test_app_loads_without_exception():
    at = AppTest.from_file("../../streamlit_app.py")
    at.run()
    assert not at.exception


def test_app_product_page_shows_headline():
    at = AppTest.from_file("../../streamlit_app.py")
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "The recommendation" in headers


def test_app_model_page_lists_limitations():
    def run_model_page():
        from src.webapp.pages.model import render
        render()

    at = AppTest.from_function(run_model_page)
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "Known limitations" in headers


def test_app_story_page_explains_evolution():
    def run_story_page():
        from src.webapp.pages.story import render
        render()

    at = AppTest.from_function(run_story_page)
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "How this evolved" in headers


def test_product_page_override_run_reset_flow():
    """Regression test for the final-review findings: an override that only flips a
    branch's action (no other BranchFeatures field changed) must still show up in "What
    changed" (Finding 3), and "Reset to baseline" must clear both the override dict and the
    widget's own remembered value, not just the dict (Finding 2's clear_overrides fix)."""
    at = AppTest.from_file("../../streamlit_app.py")
    at.run()
    assert not at.exception

    rating_sliders = [s for s in at.slider if s.key and s.key.startswith("rating-")]
    assert rating_sliders, "expected at least one per-branch rating override slider"
    slider = rating_sliders[0]
    # Key format is rating-{branch_id}-{nonce} (the nonce suffix exists so a reset can force
    # a real widget remount -- see render_branch_override()'s docstring comment). This is the
    # first render, so the nonce is always "0".
    branch_id = slider.key.removeprefix("rating-").removesuffix("-0")
    baseline_value = slider.value

    # Pick a new rating distinct from baseline so the override actually does something.
    new_value = 1.0 if baseline_value != 1.0 else 5.0
    slider.set_value(new_value).run()
    assert not at.exception

    apply_button = next(b for b in at.button if b.key == f"apply-{branch_id}")
    apply_button.click().run()
    assert not at.exception
    assert at.session_state["branch_overrides"][branch_id]["rating"] == new_value

    run_button = next(b for b in at.button if b.label == "Run scenario")
    run_button.click().run()
    assert not at.exception

    scenario_run = at.session_state["scenario_run"]
    expected_changed = [b for b in scenario_run.diff.branches
                         if b.action_changed or b.changed_fields or b.old is None]
    # Without at least one action-only flip (action_changed but no changed_fields), this
    # test can't actually distinguish the fixed formula from the old buggy one -- pin that
    # the scenario produces one, so a future data/rubric change can't silently make this
    # test stop discriminating.
    assert any(b.action_changed and not b.changed_fields for b in scenario_run.diff.branches)
    markdown_texts = [m.value for m in at.markdown]
    count_line = next(t for t in markdown_texts if "branch(es) changed" in t)
    assert count_line.startswith(f"{len(expected_changed)} branch(es) changed")

    reset_button = next(b for b in at.button if b.label == "Reset to baseline")
    reset_button.click().run()
    assert not at.exception
    assert at.session_state["branch_overrides"] == {}

    # The reset must have bumped the widget-reset nonce, so the slider now rendered for this
    # branch has a different key (a fresh component) showing the real baseline value again --
    # not just session_state's branch_overrides dict being empty, which alone was proven
    # insufficient during browser verification (the old slider visually stayed stuck).
    fresh_sliders = [s for s in at.slider if s.key and s.key.startswith(f"rating-{branch_id}-")]
    assert fresh_sliders, "rating slider should still be rendered after reset"
    assert fresh_sliders[0].key != slider.key, "reset must assign the widget a new key"
    assert fresh_sliders[0].value == baseline_value
