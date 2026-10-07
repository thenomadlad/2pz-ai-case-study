from src.model.opportunity import FAR_KM, MIN_POP, UNSATURATED_PER_10K, classify
from src.models import CommunityFeatures


def _c(km=FAR_KM + 1, per_10k=UNSATURATED_PER_10K - 1, pop=MIN_POP + 1, hosts=False,
       name="Al Rifa"):
    return CommunityFeatures(
        community_id="c", name=name, lat=25.0, lng=55.0, female_pop=pop, competitors=1,
        competitors_per_10k=per_10k, nearest_branch_id="b", nearest_branch_km=km,
        nearest_branch_pop_served=50_000, hosts_branch=hosts)


def test_two_by_two():
    assert classify(_c()).action == "GROW"
    assert classify(_c(km=1)).action == "WATCH"
    assert classify(_c(per_10k=UNSATURATED_PER_10K + 1)).action == "WATCH"
    assert classify(_c(km=1, per_10k=UNSATURATED_PER_10K + 1)).action == "SKIP"


def test_overrides_skip_small_and_hosting_areas():
    assert classify(_c(pop=MIN_POP - 1)).action == "SKIP"
    assert classify(_c(hosts=True)).action == "SKIP"


def test_worker_housing_capped_at_watch():
    o = classify(_c(name="Jebel Ali Industrial First"))
    assert o.action == "WATCH"
    assert "worker housing" in o.rationale
