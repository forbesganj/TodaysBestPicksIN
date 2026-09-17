"""
Flipkart deals via the OFFICIAL Flipkart Affiliate Program.

IMPORTANT - how this actually works, no invented endpoints:
Flipkart does NOT offer a generic "search any product" affiliate API to
the public. Once you are ACCEPTED as a Flipkart affiliate
(https://affiliate.flipkart.com), their dashboard issues you category-wise
PRODUCT FEED URLs (JSON) containing current price, MRP, discount % and
affiliate deep links for that category. You paste those feed URLs into
FLIPKART_FEED_URLS (comma-separated) as a GitHub Secret.

This module fetches those feed URLs and parses them. It does NOT guess a
search endpoint, because Flipkart does not publish one for this purpose.
If Flipkart changes their feed JSON schema, only the `_parse_item` method
below needs updating - check your affiliate dashboard for the current
schema/sample if parsing starts failing (see README "Troubleshooting").
"""
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import Deal, DealSource

logger = logging.getLogger("deals_bot.sources.flipkart")


class FlipkartSource(DealSource):
    name = "Flipkart"

    def __init__(self, cfg):
        self.cfg = cfg

    def fetch_deals(self) -> list[Deal]:
        if not self.cfg.FLIPKART_ENABLED:
            logger.info("Flipkart source disabled (FLIPKART_ENABLED=false). Skipping.")
            return []

        if not self.cfg.FLIPKART_FEED_URLS:
            logger.warning("Flipkart enabled but FLIPKART_FEED_URLS is empty. Skipping.")
            return []

        deals: list[Deal] = []
        for feed_url in self.cfg.FLIPKART_FEED_URLS:
            try:
                data = self._fetch_feed(feed_url)
            except Exception as e:
                logger.warning(f"Failed to fetch Flipkart feed {feed_url}: {e}")
                continue

            products = data.get("products", data) if isinstance(data, dict) else data
            if not isinstance(products, list):
                logger.warning(f"Unexpected Flipkart feed shape at {feed_url}; skipping.")
                continue

            for item in products:
                deal = self._parse_item(item)
                if deal:
                    deals.append(deal)

        logger.info(f"Flipkart: fetched {len(deals)} candidate deals.")
        return deals

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _fetch_feed(self, feed_url: str) -> dict:
        headers = {}
        if self.cfg.FLIPKART_AFFILIATE_ID:
            headers["Fk-Affiliate-Id"] = self.cfg.FLIPKART_AFFILIATE_ID
        if self.cfg.FLIPKART_AFFILIATE_TOKEN:
            headers["Fk-Affiliate-Token"] = self.cfg.FLIPKART_AFFILIATE_TOKEN

        resp = requests.get(feed_url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _parse_item(self, item: dict) -> Deal | None:
        try:
            product_info = item.get("productBaseInfoV1", item)
            title = product_info.get("title")
            product_url = product_info.get("productUrl")
            image_url = None
            images = product_info.get("imageUrls", {})
            if images:
                image_url = list(images.values())[0]

            price_info = product_info.get("flipkartSpecialPrice") or product_info.get("flipkartSellingPrice")
            mrp_info = product_info.get("maximumRetailPrice")

            discounted_price = float(price_info["amount"]) if price_info else None
            original_price = float(mrp_info["amount"]) if mrp_info else None
            product_id = product_info.get("productId") or product_url

            if not (title and product_url and discounted_price):
                return None

            return Deal(
                source=self.name,
                product_id=product_id,
                title=title,
                product_url=product_url,
                image_url=image_url,
                original_price=original_price,
                discounted_price=discounted_price,
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.debug(f"Skipping malformed Flipkart item: {e}")
            return None
