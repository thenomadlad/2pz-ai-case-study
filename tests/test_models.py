import pytest
from pydantic import ValidationError

from src.models import Decision


def test_decision_rejects_bad_action():
    with pytest.raises(ValidationError):
        Decision(branch_id="b1", action="EXPAND", confidence="low",
                  rationale="x", key_drivers=[], caveats=[])


def test_decision_valid_action():
    d = Decision(branch_id="b1", action="PROTECT", confidence="high",
                 rationale="Serves the most women with low contest.",
                 key_drivers=["female_pop_served", "contested_share"], caveats=["No revenue data."])
    assert d.action == "PROTECT"
