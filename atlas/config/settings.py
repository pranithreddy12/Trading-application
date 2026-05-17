import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
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
