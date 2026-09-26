import csv
import json

from src.acquire.run import main
from src.config import Settings


def _write_branches(seed_dir):
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed"])
        w.writeheader()
        w.writerow({"id": "b1", "name": "B1", "lat": "25.1", "lng": "55.2", "area": "A",
                    "rating": "4.5", "review_count": "10", "avg_price_aed": "100"})
        w.writerow({"id": "b2", "name": "B2", "lat": "25.2", "lng": "55.3", "area": "B",
                    "rating": "", "review_count": "", "avg_price_aed": ""})


def _write_communities(seed_dir):
    with open(seed_dir / "communities.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name_en", "lat", "lng", "population_total", "population_female"])
        w.writeheader()
        w.writerow({"id": "c1", "name_en": "C1", "lat": "25.1", "lng": "55.2",
                    "population_total": "1000", "population_female": "480"})


def test_main_writes_raw_files(tmp_path):
    seed_dir = tmp_path / "seed"
    raw_dir = tmp_path / "raw"
    seed_dir.mkdir()
    raw_dir.mkdir()
    _write_branches(seed_dir)
    _write_communities(seed_dir)

    test_settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir)
    main(test_settings)

    branches_out = json.loads((raw_dir / "branches.json").read_text())
    price_flags = json.loads((raw_dir / "price_flags.json").read_text())
    communities_out = json.loads((raw_dir / "communities.json").read_text())

    assert len(branches_out) == 2
    assert price_flags == ["b2"]
    assert len(communities_out) == 1
