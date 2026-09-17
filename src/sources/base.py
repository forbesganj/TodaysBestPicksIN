"""
Shared Deal data model and base class for every source.
Every source module (Amazon, Flipkart, generic feed) must return a list
of Deal objects in this exact shape, so the rest of the pipeline
(filtering, dedup, posting) never needs to know which platform a deal
came from.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Deal:
    source: str              # "Amazon" | "Flipkart" | "Myntra" | "Ajio" | "Meesho" | ...
    product_id: str          # stable unique id (ASIN, SKU, feed item id, etc.)
    title: str
    product_url: str
    image_url: Optional[str]
    original_price: Optional[float]   # MRP / list price, in INR
    discounted_price: float           # current selling price, in INR
    currency: str = "INR"
    discount_percent: Optional[float] = None  # computed if not provided
    coupon_code: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        # Compute discount % if the source didn't supply it directly
        if self.discount_percent is None and self.original_price and self.original_price > 0:
            self.discount_percent = round(
                (1 - (self.discounted_price / self.original_price)) * 100, 1
            )

    def dedup_key(self) -> str:
        """Stable key used for duplicate detection across runs."""
        return f"{self.source}:{self.product_id}"

    def is_valid(self) -> bool:
        """Basic sanity check to reject garbage / malformed entries."""
        if not self.title or not self.product_url:
            return False
        if self.discounted_price is None or self.discounted_price <= 0:
            return False
        if self.original_price is not None and self.original_price < self.discounted_price:
            return False  # "discount" that isn't actually a discount
        return True


class DealSource:
    """Base interface every source must implement."""

    name = "base"

    def fetch_deals(self) -> list[Deal]:
        raise NotImplementedError
