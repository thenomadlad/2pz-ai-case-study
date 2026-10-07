from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    seed_dir: Path = REPO_ROOT / "data" / "seed"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    processed_dir: Path = REPO_ROOT / "data" / "processed" / "baseline"

    enable_scrape: bool = False
    dubai_pulse_enabled: bool = False
    contest_ratio: float = 1.25
    global_female_share: float = 0.49
    fallback_price_aed: float = 99.0
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"


settings = Settings()
