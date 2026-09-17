"""
Amazon India deals via the OFFICIAL Product Advertising API (PA-API 5.0).

REQUIREMENTS (see README for the full walkthrough):
  1. You must be an approved Amazon Associate (associates.amazon.in).
  2. You must generate 3 qualifying sales within your first 180 days,
     or Amazon can suspend your PA-API access (this is Amazon's rule,
     not something this code can work around).
  3. Uses the community-maintained `python-amazon-paapi` package, which
     wraps Amazon's official signed REST API - no scraping involved.

If AMAZON_ENABLED=false or credentials are missing, this source simply
returns an empty list rather than crashing the whole run.
"""
import logging
from .base import Deal, DealSource

logger = logging.getLogger("deals_bot.sources.amazon")


class AmazonSource(DealSource):
    name = "Amazon"

    def __init__(self, cfg):
        self.cfg = cfg

    def fetch_deals(self) -> list[Deal]:
        if not self.cfg.AMAZON_ENABLED:
            logger.info("Amazon source disabled (AMAZON_ENABLED=false). Skipping.")
            return []

        if not (self.cfg.AMAZON_ACCESS_KEY and self.cfg.AMAZON_SECRET_KEY and self.cfg.AMAZON_PARTNER_TAG):
            logger.warning("Amazon enabled but credentials incomplete. Skipping this run.")
            return []

        try:
            from amazon_paapi import AmazonApi
        except ImportError:
            logger.error(
                "python-amazon-paapi not installed. Run: pip install python-amazon-paapi"
            )
            return []

        deals: list[Deal] = []
        try:
            api = AmazonApi(
                self.cfg.AMAZON_ACCESS_KEY,
                self.cfg.AMAZON_SECRET_KEY,
                self.cfg.AMAZON_PARTNER_TAG,
                self.cfg.AMAZON_COUNTRY,
            )
        except Exception as e:
            logger.error(f"Failed to initialise Amazon PA-API client: {e}")
            return []

        keywords = self.cfg.AMAZON_SEARCH_KEYWORDS or ["deals"]
        for kw in keywords:
            try:
                # search_items is the official PA-API "SearchItems" operation
                results = api.search_items(keywords=kw, item_count=10)
                items = getattr(results, "items", None) or []
                for item in items:
                    deal = self._parse_item(item)
                    if deal:
                        deals.append(deal)
            except Exception as e:
                # A single bad keyword / transient API error should not kill
                # the whole run - log it and move on to the next keyword.
                logger.warning(f"Amazon search failed for keyword '{kw}': {e}")
                continue

        logger.info(f"Amazon: fetched {len(deals)} candidate deals.")
        return deals

    def _parse_item(self, item) -> Deal | None:
        try:
            asin = item.asin
            title = item.item_info.title.display_value
            url = item.detail_page_url

            image_url = None
            if item.images and item.images.primary and item.images.primary.large:
                image_url = item.images.primary.large.url

            offer = item.offers.listings[0] if item.offers and item.offers.listings else None
            if not offer:
                return None

            discounted_price = offer.price.amount
            original_price = None
            if offer.saving_basis:
                original_price = offer.saving_basis.amount

            return Deal(
                source=self.name,
                product_id=asin,
                title=title,
                product_url=url,
                image_url=image_url,
                original_price=original_price,
                discounted_price=discounted_price,
            )
        except AttributeError as e:
            logger.debug(f"Skipping malformed Amazon item (missing field {e}).")
            return None
