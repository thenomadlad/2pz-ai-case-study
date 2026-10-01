import yaml

from src.scenario.models import Scenario


def load_scenario(path) -> Scenario:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Scenario(**data)
