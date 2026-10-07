import csv

from src.acquire import population
from src.config import Settings


def test_load_estimates_missing_female_population(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "communities.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "name_en", "lat", "lng", "population_total", "population_female",
        ])
        writer.writeheader()
        writer.writerow({"id": "c1", "name_en": "Deira", "lat": "25.27", "lng": "55.31",
                          "population_total": "1000", "population_female": "480"})
        writer.writerow({"id": "c2", "name_en": "Al Barsha", "lat": "25.11", "lng": "55.20",
                          "population_total": "1000", "population_female": ""})

    test_settings = Settings(_env_file=None, seed_dir=seed_dir)
    result = population.load(test_settings)

    by_id = {c.id: c for c in result}
    assert by_id["c1"].population_female == 480
    assert by_id["c1"].is_estimated is False
    assert by_id["c2"].population_female == 490
    assert by_id["c2"].is_estimated is True
