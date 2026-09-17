"""
Duplicate prevention + price-drop history.

Two JSON files persisted in data/ and committed back to the repo by the
GitHub Actions workflow after every run (see .github/workflows/deals_bot.yml):

  posted_deals.json  -> {dedup_key: iso_timestamp_last_posted}
                         Prevents reposting the exact same product again
                         within a cooldown window.

  price_history.json -> {dedup_key: last_known_discounted_price}
                         Lets us detect genuine NEW price drops rather than
                         just "this product happens to be cheap" every run.

No external database needed - this keeps the whole project at ₹0 and
dependency-free, at the cost of the state living in git history. That's a
deliberate, documented trade-off (see README "Limitations").
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("deals_bot.dedup")

# How long before the same product can be posted again even if it's still
# on the same discount (avoids spamming the channel with the same deal
# every single run).
REPOST_COOLDOWN_DAYS = 7


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read {path} ({e}); starting fresh.")
        return {}


def _save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)  # atomic write, avoids corruption mid-run


class DealStateStore:
    def __init__(self, posted_deals_file: str, price_history_file: str):
        self.posted_deals_file = posted_deals_file
        self.price_history_file = price_history_file
        self.posted_deals = _load_json(posted_deals_file)
        self.price_history = _load_json(price_history_file)

    def should_post(self, deal) -> bool:
        """
        A deal is worth posting if:
          - it's genuinely new, OR
          - its price dropped further since we last saw it, OR
          - the cooldown window has passed since we last posted it.
        """
        key = deal.dedup_key()
        last_posted = self.posted_deals.get(key)
        last_price = self.price_history.get(key)

        if last_posted is None:
            return True

        if last_price is not None and deal.discounted_price < last_price:
            logger.info(
                f"Price drop detected for {key}: {last_price} -> {deal.discounted_price}"
            )
            return True

        last_posted_dt = datetime.fromisoformat(last_posted)
        if datetime.now(timezone.utc) - last_posted_dt > timedelta(days=REPOST_COOLDOWN_DAYS):
            return True

        return False

    def mark_posted(self, deal):
        key = deal.dedup_key()
        self.posted_deals[key] = datetime.now(timezone.utc).isoformat()
        self.price_history[key] = deal.discounted_price

    def prune_old_entries(self, max_age_days: int = 60):
        """Keep the state files from growing forever."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        stale_keys = [
            k for k, ts in self.posted_deals.items()
            if datetime.fromisoformat(ts) < cutoff
        ]
        for k in stale_keys:
            self.posted_deals.pop(k, None)
            self.price_history.pop(k, None)
        if stale_keys:
            logger.info(f"Pruned {len(stale_keys)} stale entries older than {max_age_days} days.")

    def save(self):
        _save_json(self.posted_deals_file, self.posted_deals)
        _save_json(self.price_history_file, self.price_history)
