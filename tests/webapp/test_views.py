from src.webapp import views
from src.webapp.data import baseline


def test_provenance_names_each_subjects_own_rent_source():
    src = {f.branch_id: views.rent_source("lounge", f.branch_id, {}) for f in baseline().features}
    assert (src["city-walk"], src["westyas"], src["al-jada"]) == ("dld", "adrec", "listings")
    assert "emirate_median" in src.values()          # two Abu Dhabi site cells have no rent of their own
    assert "DLD Ejari" in views.provenance("lounge", "dld")
    adrec = views.provenance("lounge", "adrec")
    assert "ADREC" in adrec and "DLD" not in adrec
    assert "Bayut" in views.provenance("area", views.rent_source("area", "x", {"rent_ratio": 1.2, "emirate": "Sharjah"}))
    fallback = views.rent_source("area", "x", {"rent_ratio": 1.0, "emirate": "Sharjah", "rent_fallback": True})
    assert "median shop rent stands in" in views.provenance("area", fallback)
    assert "shop rent" not in views.provenance("area", views.rent_source("area", "x", {"rent_ratio": None}))


def test_sharjah_caveat_says_beyond_reach_only_when_it_is():
    r = baseline()
    by_id = {a.area_id: (a, d) for a, d in zip(r.areas, r.area_decisions)}
    city = " ".join(views.area_caveats(*by_id["sharjah-sharjah"]))   # 2.5 km from al-jada
    assert "already reach 62% of this area's women" in city and "beyond the drive time" not in city
    dhaid = " ".join(views.area_caveats(*by_id["al-dhaid-sharjah"]))
    assert "beyond the drive time of both (al-jada is nearest)" in dhaid
