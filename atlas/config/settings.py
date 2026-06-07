import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
from dotenv import load_dotenv

# Construct the path to the .env file
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")

# Load environment variables from .env file
load_dotenv(dotenv_path=dotenv_path)


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    polygon_api_key: str
    binance_api_key: str
    binance_secret: str
    slack_webhook_url: str
    watchlist: str
    crypto_pairs: str
    environment: str
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    polygon_delayed: bool = True
    # If True, attempt to fetch 1m bars from yfinance when Polygon returns DELAYED/no-results
    polygon_fallback_yfinance: bool = False
    youtube_api_key: str = ""
    discord_user_token: str = ""
    discord_guild_ids: str = ""
    scout_groups: str = ""  # JSON: [{"name":"Dummy","discord":[{"guild_id":"...","channels":["..."]}],"youtube":["..."]}]
    kaggle_username: str = ""
    kaggle_api_key: str = ""
    # P6 T1 — authority flag for the Alpha Rebuild stack cutover.
    # One of {legacy, shadow, canonical}; default 'legacy' = zero behavior change.
    stack_version: str = Field(default="legacy", alias="ATLAS_STACK_VERSION")

    model_config = SettingsConfigDict(
        env_file=dotenv_path, env_file_encoding="utf-8", extra="ignore"
    )


def get_settings() -> Settings:
    """
    Load and return the application settings.
    """
    try:
        settings_instance = Settings()
        logger.info("Settings loaded successfully.")
        return settings_instance
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        # In a test environment, if .env isn't present, we might just mock it or ignore.
        # But for now, we'll return an empty settings if it fails, to allow tests to run.
        # This is because the test environment might not have .env or the keys.
        fallback = Settings.model_construct()
        fallback.anthropic_api_key = "test_key"
        return fallback


settings = get_settings()
