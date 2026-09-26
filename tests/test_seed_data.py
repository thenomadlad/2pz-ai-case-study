# tests/test_seed_data.py
import csv

from src.config import settings

BRANCH_COLUMNS = {"id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed"}
COMMUNITY_COLUMNS = {"id", "name_en", "lat", "lng", "population_total", "population_female"}


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_branches_csv_schema_and_count():
    rows = _read(settings.seed_dir / "branches.csv")
    assert rows, "branches.csv must not be empty"
    assert set(rows[0].keys()) == BRANCH_COLUMNS
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "branch ids must be unique"
    for r in rows:
        float(r["lat"])
        float(r["lng"])


def test_communities_csv_schema_and_count():
    rows = _read(settings.seed_dir / "communities.csv")
    assert len(rows) >= 20, "expect roughly 30-60 communities, got too few"
    assert set(rows[0].keys()) == COMMUNITY_COLUMNS
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "community ids must be unique"
    for r in rows:
        float(r["lat"])
        float(r["lng"])
        int(r["population_total"])
