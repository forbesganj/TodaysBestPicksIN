#!/usr/bin/env python3
"""
Entry point for the DailyVaultIN Telegram Deals Bot.

Run manually:   python main.py
Run in CI:      triggered by .github/workflows/deals_bot.yml on a schedule.

Flow:
  1. Load + validate config from environment (GitHub Secrets).
  2. Fetch candidate deals from every enabled source.
  3. Filter: validity -> min discount % -> dedup/price-drop -> cap count.
  4. Post each surviving deal to the Telegram channel.
  5. Persist updated dedup/price-history state to data/*.json
     (the workflow commits these files back to the repo).

Exit code is non-zero on any unrecoverable error so GitHub Actions marks
the run as failed and you get notified.
"""
import sys
import time

from config import Config
from src.logger_setup import setup_logging
from src.dedup import DealStateStore
from src.deal_filter import filter_deals
from src.telegram_poster import TelegramPoster
from src.sources.amazon_paapi import AmazonSource
from src.sources.flipkart_affiliate import FlipkartSource
from src.sources.generic_feed import GenericFeedSource


def main() -> int:
    logger = setup_logging(Config.LOG_FILE)
    logger.info("=" * 60)
    logger.info("DailyVaultIN Deals Bot - run starting")

    try:
        Config.validate()
    except RuntimeError as e:
        logger.error(str(e))
        return 1

    state_store = DealStateStore(Config.POSTED_DEALS_FILE, Config.PRICE_HISTORY_FILE)
    state_store.prune_old_entries()

    sources = [
        AmazonSource(Config),
        FlipkartSource(Config),
        GenericFeedSource(Config),
    ]

    all_deals = []
    for source in sources:
        try:
            all_deals.extend(source.fetch_deals())
        except Exception as e:
            # One misbehaving source should never take down the whole run.
            logger.error(f"Source '{source.name}' raised an unexpected error: {e}", exc_info=True)

    if not all_deals:
        logger.info("No candidate deals fetched this run. Exiting cleanly.")
        state_store.save()
        return 0

    postable = filter_deals(
        all_deals,
        state_store,
        min_discount_percent=Config.MIN_DISCOUNT_PERCENT,
        max_posts=Config.MAX_POSTS_PER_RUN,
    )

    if not postable:
        logger.info("No deals passed filtering this run. Exiting cleanly.")
        state_store.save()
        return 0

    poster = TelegramPoster(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHANNEL_ID)
    posted_count = 0
    for deal in postable:
        success = poster.post_deal(deal)
        if success:
            state_store.mark_posted(deal)
            posted_count += 1
            logger.info(f"Posted: [{deal.source}] {deal.title} ({deal.discount_percent}% off)")
        else:
            logger.warning(f"Failed to post: [{deal.source}] {deal.title}")
        time.sleep(2)  # be gentle on Telegram's rate limits between posts

    state_store.save()
    logger.info(f"Run complete. Posted {posted_count}/{len(postable)} deals.")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
