"""
Filters raw candidate deals down to the genuinely postable ones:
  1. Structural validity (Deal.is_valid()).
  2. Minimum discount percentage threshold.
  3. Deduplication / price-drop logic (via DealStateStore).
  4. Caps the number of posts per run so one run can't flood the channel.
"""
import logging

logger = logging.getLogger("deals_bot.filter")


def filter_deals(deals, state_store, min_discount_percent: float, max_posts: int):
    valid = [d for d in deals if d.is_valid()]
    logger.info(f"{len(valid)}/{len(deals)} deals passed structural validation.")

    discounted = [
        d for d in valid
        if d.discount_percent is not None and d.discount_percent >= min_discount_percent
    ]
    logger.info(
        f"{len(discounted)}/{len(valid)} deals meet the {min_discount_percent}% "
        "minimum discount threshold."
    )

    # Sort best discount first so if we hit MAX_POSTS_PER_RUN, we post the
    # genuinely best deals rather than whatever came first alphabetically.
    discounted.sort(key=lambda d: d.discount_percent, reverse=True)

    postable = [d for d in discounted if state_store.should_post(d)]
    logger.info(f"{len(postable)}/{len(discounted)} deals are new or dropped further in price.")

    return postable[:max_posts]
