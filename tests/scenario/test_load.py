import pytest
import yaml
from pydantic import ValidationError

from src.scenario.load import load_scenario


def test_load_scenario_full(tmp_path):
    path = tmp_path / "test-scenario.yaml"
    path.write_text(yaml.dump({
        "name": "bigger-palm-jumeirah",
        "assumptions": {"contest_ratio": 1.1},
        "overrides": {
            "branches": {
                "palm-jumeirah": {"rating": 4.9},
                "hypothetical-marina": {
                    "name": "Hypothetical Marina", "lat": 25.08, "lng": 55.14, "area": "Marina",
                },
            },
            "communities": {
                "al-sufouh-second": {"population_female": 9000},
            },
        },
    }))

    scenario = load_scenario(path)

    assert scenario.name == "bigger-palm-jumeirah"
    assert scenario.assumptions.contest_ratio == 1.1
    assert scenario.overrides.branches["palm-jumeirah"]["rating"] == 4.9
    assert scenario.overrides.branches["hypothetical-marina"]["area"] == "Marina"
    assert scenario.overrides.communities["al-sufouh-second"]["population_female"] == 9000


def test_load_scenario_minimal(tmp_path):
    path = tmp_path / "minimal.yaml"
    path.write_text(yaml.dump({"name": "noop"}))

    scenario = load_scenario(path)

    assert scenario.name == "noop"
    assert scenario.overrides.branches == {}


def test_load_scenario_rejects_unknown_top_level_field(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.dump({"name": "bad", "asumptions": {"contest_ratio": 1.1}}))  # typo

    with pytest.raises(ValidationError):
        load_scenario(path)
