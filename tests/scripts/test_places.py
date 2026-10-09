from scripts.places import best_match, is_bedashing


def place(name, lat, lng):
    return {"id": name, "displayName": {"text": name},
            "location": {"latitude": lat, "longitude": lng}}


def test_is_bedashing_any_case():
    assert is_bedashing(place("BEDASHING Beauty Lounge Delma", 0, 0))
    assert not is_bedashing(place("Pink Madi Beauty Salon", 0, 0))


def test_best_match_picks_nearest_bedashing():
    near = place("Bedashing Beauty Lounge Al Barsha", 25.1131, 55.2156)
    far = place("Bedashing Beauty Lounge City Walk", 25.2020, 55.2638)
    rival = place("Leilani Beauty Lounge", 25.1137, 55.2146)
    assert best_match([rival, far, near], 25.1137, 55.2146) is near


def test_best_match_none_when_only_far_or_rivals():
    far = place("Bedashing Beauty Lounge City Walk", 25.2020, 55.2638)
    assert best_match([far, place("Some Salon", 25.1137, 55.2146)], 25.1137, 55.2146) is None


def test_best_match_prefers_title_over_distance():
    # Store-locator pins can be km off: the listing naming the lounge wins.
    named = place("Bedashing Beauty Lounge Al Ain", 24.30, 55.75)
    assert best_match([named], 24.2413, 55.7410, "Al Ain") is named


def test_best_match_title_in_address():
    mall = place("Bedashing Beauty Lounge", 24.55, 54.68)
    mall["formattedAddress"] = "Al Shahama Road Deerfields Mall, Abu Dhabi"
    assert best_match([mall], 24.4317, 54.5521, "Shahama") is mall
