from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Absolute path: a relative ".env" is silently skipped when run from another directory.
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    seed_dir: Path = REPO_ROOT / "data" / "seed"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    processed_dir: Path = REPO_ROOT / "data" / "processed" / "baseline"

    contest_ratio: float = 1.25
    global_female_share: float = 0.49
    fallback_price_aed: float = 99.0
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    google_maps_api_key: str | None = None


settings = Settings()
