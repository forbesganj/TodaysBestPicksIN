"""
Posts a Deal to a Telegram channel via the official Telegram Bot API
(https://core.telegram.org/bots/api). No third-party wrapper needed -
plain HTTPS requests, which keeps this dependency-light and easy to audit.

Your bot must already be added as an ADMIN of the target channel with
"Post Messages" permission, or these calls will fail with a 403.
"""
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("deals_bot.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_CAPTION_LENGTH = 1024  # Telegram's limit for photo captions


def _build_caption(deal) -> str:
    lines = [f"🔥 *{_escape_md(deal.title)}*", ""]

    if deal.original_price:
        lines.append(f"~₹{deal.original_price:,.0f}~  ➜  *₹{deal.discounted_price:,.0f}*")
    else:
        lines.append(f"*₹{deal.discounted_price:,.0f}*")

    if deal.discount_percent:
        lines.append(f"💸 *{deal.discount_percent:.0f}% OFF*")

    if deal.coupon_code:
        lines.append(f"🏷️ Coupon: `{deal.coupon_code}`")

    lines.append(f"🏬 {deal.source}")
    lines.append("")
    lines.append(f"[👉 Grab the Deal]({deal.product_url})")
    lines.append("")
    lines.append("📢 @DailyVaultIN")

    caption = "\n".join(lines)
    if len(caption) > MAX_CAPTION_LENGTH:
        caption = caption[: MAX_CAPTION_LENGTH - 1] + "…"
    return caption


def _escape_md(text: str) -> str:
    # Escape MarkdownV2-breaking chars for legacy Markdown mode; we use
    # plain "Markdown" parse mode below which only needs these escaped.
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


class TelegramPoster:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id

    def post_deal(self, deal) -> bool:
        caption = _build_caption(deal)
        try:
            if deal.image_url:
                return self._send_photo(deal.image_url, caption)
            else:
                return self._send_text(caption)
        except Exception as e:
            logger.error(f"Failed to post deal '{deal.title}' after retries: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
    )
    def _send_photo(self, image_url: str, caption: str) -> bool:
        url = TELEGRAM_API_BASE.format(token=self.bot_token, method="sendPhoto")
        resp = requests.post(
            url,
            data={
                "chat_id": self.channel_id,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "Markdown",
            },
            timeout=20,
        )
        return self._handle_response(resp, fallback_caption=caption)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
    )
    def _send_text(self, caption: str) -> bool:
        url = TELEGRAM_API_BASE.format(token=self.bot_token, method="sendMessage")
        resp = requests.post(
            url,
            data={
                "chat_id": self.channel_id,
                "text": caption,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        return self._handle_response(resp, fallback_caption=caption)

    def _handle_response(self, resp: requests.Response, fallback_caption: str) -> bool:
        if resp.status_code == 200 and resp.json().get("ok"):
            return True

        body = resp.text[:300]
        logger.warning(f"Telegram API error {resp.status_code}: {body}")

        # If sendPhoto failed because the image URL is broken/unreachable,
        # fall back to a text-only post so the deal isn't lost entirely.
        if resp.status_code == 400 and "photo" in body.lower():
            logger.info("Falling back to text-only message after photo failure.")
            return self._send_text(fallback_caption)

        resp.raise_for_status()
        return False
