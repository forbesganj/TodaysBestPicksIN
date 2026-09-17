"""
Generic affiliate-feed adapter - this is the realistic path for
Myntra, Ajio and Meesho.

Why this exists instead of a "MyntraSource" / "AjioSource" / "MeeshoSource":
None of these three publish a public, freely-available affiliate API for
developers to query directly. In practice, deal/coupon channels get
Myntra/Ajio/Meesho product links WITH live price & discount data through
affiliate aggregator networks such as:
  - EarnKaro     (https://earnkaro.com)
  - INRDeals     (https://inrdeals.com)
  - Cuelinks     (https://cuelinks.com)
  - Admitad      (https://www.admitad.com)
  - vCommission  (https://www.vcommission.com)

After you sign up and are APPROVED as a publisher on one of these (free),
they give you a deals feed - typically a CSV or JSON export/API URL - that
already covers Myntra, Ajio, Meesho and many more merchants at once, with
affiliate-tagged links.

Rather than guess a specific network's schema, this adapter accepts a
CONFIGURABLE list of feeds via GENERIC_FEEDS_CONFIG (JSON), each declaring
its own field mapping, so you plug in whichever network approves you
without touching code:

GENERIC_FEEDS_CONFIG example:
[
  {
    "name": "Myntra-EarnKaro",
    "url": "https://your-feed-url.example.com/feed.json",
    "format": "json",
    "field_map": {
      "title": "product_name",
      "product_url": "affiliate_url",
      "image_url": "image",
      "original_price": "mrp",
      "discounted_price": "price",
      "product_id": "id"
    }
  }
]

For CSV feeds, set "format": "csv" - the same field_map applies to column
headers.
"""
import csv
import io
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import Deal, DealSource

logger = logging.getLogger("deals_bot.sources.generic_feed")

DEFAULT_FIELD_MAP = {
    "title": "title",
    "product_url": "product_url",
    "image_url": "image_url",
    "original_price": "original_price",
    "discounted_price": "discounted_price",
    "product_id": "product_id",
}


class GenericFeedSource(DealSource):
    name = "GenericFeed"

    def __init__(self, cfg):
        self.cfg = cfg

    def fetch_deals(self) -> list[Deal]:
        if not self.cfg.GENERIC_FEEDS_ENABLED:
            logger.info("Generic feed source disabled (GENERIC_FEEDS_ENABLED=false). Skipping.")
            return []

        feeds = self.cfg.GENERIC_FEEDS_CONFIG
        if not feeds:
            logger.warning(
                "GENERIC_FEEDS_ENABLED=true but GENERIC_FEEDS_CONFIG is empty. "
                "This is where Myntra/Ajio/Meesho deals come from - see README."
            )
            return []

        all_deals: list[Deal] = []
        for feed in feeds:
            source_label = feed.get("name", "GenericFeed")
            try:
                rows = self._fetch(feed)
            except Exception as e:
                logger.warning(f"Failed to fetch feed '{source_label}': {e}")
                continue

            field_map = {**DEFAULT_FIELD_MAP, **feed.get("field_map", {})}
            for row in rows:
                deal = self._parse_row(row, field_map, source_label)
                if deal:
                    all_deals.append(deal)

        logger.info(f"Generic feeds: fetched {len(all_deals)} candidate deals.")
        return all_deals

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _fetch(self, feed: dict) -> list[dict]:
        resp = requests.get(feed["url"], timeout=30)
        resp.raise_for_status()

        fmt = feed.get("format", "json").lower()
        if fmt == "json":
            data = resp.json()
            return data if isinstance(data, list) else data.get("items", [])
        elif fmt == "csv":
            reader = csv.DictReader(io.StringIO(resp.text))
            return list(reader)
        else:
            raise ValueError(f"Unsupported feed format: {fmt}")

    def _parse_row(self, row: dict, field_map: dict, source_label: str) -> Deal | None:
        try:
            def g(key):
                return row.get(field_map[key])

            title = g("title")
            product_url = g("product_url")
            discounted_price = g("discounted_price")
            if not (title and product_url and discounted_price):
                return None

            original_price = g("original_price")
            return Deal(
                source=source_label,
                product_id=str(g("product_id") or product_url),
                title=str(title),
                product_url=str(product_url),
                image_url=g("image_url"),
                original_price=float(original_price) if original_price else None,
                discounted_price=float(discounted_price),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.debug(f"Skipping malformed row from '{source_label}': {e}")
            return None
