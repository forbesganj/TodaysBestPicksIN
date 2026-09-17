"""
Central configuration loader.
Reads everything from environment variables so that the exact same code
works locally (via a .env file) and in GitHub Actions (via GitHub Secrets
injected as env vars in the workflow YAML). No secrets are ever hardcoded.
"""
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()  # no-op in GitHub Actions (no .env file there); loads locally

logger = logging.getLogger("deals_bot.config")


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default))
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: str = "") -> list:
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


class Config:
    # --- Telegram ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

    # --- Filtering ---
    MIN_DISCOUNT_PERCENT = float(os.getenv("MIN_DISCOUNT_PERCENT", "40"))
    MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "10"))

    # --- Amazon PA-API ---
    AMAZON_ENABLED = _env_bool("AMAZON_ENABLED", False)
    AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY", "")
    AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY", "")
    AMAZON_PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG", "")
    AMAZON_COUNTRY = os.getenv("AMAZON_COUNTRY", "IN")
    AMAZON_SEARCH_KEYWORDS = _env_list("AMAZON_SEARCH_KEYWORDS", "")

    # --- Flipkart Affiliate Feed ---
    FLIPKART_ENABLED = _env_bool("FLIPKART_ENABLED", False)
    FLIPKART_FEED_URLS = _env_list("FLIPKART_FEED_URLS", "")
    FLIPKART_AFFILIATE_ID = os.getenv("FLIPKART_AFFILIATE_ID", "")
    FLIPKART_AFFILIATE_TOKEN = os.getenv("FLIPKART_AFFILIATE_TOKEN", "")

    # --- Generic feeds (Myntra / Ajio / Meesho via affiliate networks) ---
    GENERIC_FEEDS_ENABLED = _env_bool("GENERIC_FEEDS_ENABLED", False)
    try:
        GENERIC_FEEDS_CONFIG = json.loads(os.getenv("GENERIC_FEEDS_CONFIG", "[]"))
    except json.JSONDecodeError:
        logger.warning("GENERIC_FEEDS_CONFIG is not valid JSON; defaulting to []")
        GENERIC_FEEDS_CONFIG = []

    # --- Paths ---
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    POSTED_DEALS_FILE = os.path.join(DATA_DIR, "posted_deals.json")
    PRICE_HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")
    LOG_FILE = os.path.join(DATA_DIR, "bot.log")

    @classmethod
    def validate(cls):
        """Fail loudly and early if required config is missing."""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.TELEGRAM_CHANNEL_ID:
            missing.append("TELEGRAM_CHANNEL_ID")
        if missing:
            raise RuntimeError(
                f"Missing required config: {', '.join(missing)}. "
                "Set these as GitHub Secrets (see README)."
            )
        if not (cls.AMAZON_ENABLED or cls.FLIPKART_ENABLED or cls.GENERIC_FEEDS_ENABLED):
            logger.warning(
                "No deal source is enabled (AMAZON_ENABLED / FLIPKART_ENABLED / "
                "GENERIC_FEEDS_ENABLED are all false). The bot will run and find "
                "zero deals. See README for how to enable a source."
            )
