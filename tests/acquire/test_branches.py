import csv

from src.acquire import branches
from src.config import Settings


def test_load_from_seed(tmp_path, monkeypatch):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed",
        ])
        writer.writeheader()
        writer.writerow({"id": "b1", "name": "Branch One", "lat": "25.1", "lng": "55.2",
                          "area": "Area", "rating": "4.5", "review_count": "100",
                          "avg_price_aed": "150"})
        writer.writerow({"id": "b2", "name": "Branch Two", "lat": "25.2", "lng": "55.3",
                          "area": "Area2", "rating": "", "review_count": "", "avg_price_aed": ""})

    test_settings = Settings(_env_file=None, seed_dir=seed_dir)
    result = branches.load(test_settings)

    assert len(result) == 2
    assert result[0].source == "seed"
    assert result[0].rating == 4.5
    assert result[1].rating is None
    assert result[1].avg_price_aed is None
