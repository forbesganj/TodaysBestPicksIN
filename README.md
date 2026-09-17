# DailyVaultIN Deals Bot

Fully automated deal-posting bot for the **@DailyVaultIN** Telegram channel.
Runs entirely on GitHub Actions (free tier), costs ₹0, and requires no server,
no manual posting, and no daily maintenance once set up.

---

## ⚠️ Read this before you deploy

This project does **not** scrape Amazon, Flipkart, Myntra, Ajio, or Meesho.
Scraping violates every one of those platforms' Terms of Service and gets
GitHub Actions' shared IPs blocked within days — it would fail the "no
maintenance" requirement immediately. Instead, this bot only pulls data
from **official or approved affiliate sources**, which means:

| Platform | Source used | Status |
|---|---|---|
| Amazon | Product Advertising API 5.0 (official) | Works once you're an approved Amazon Associate |
| Flipkart | Affiliate Program product feeds (official) | Works once you're an approved Flipkart affiliate |
| Myntra / Ajio / Meesho | Affiliate network feed (EarnKaro / INRDeals / Cuelinks / Admitad — your choice) | Works once you're approved by one of these networks |

**None of these approvals are instant**, and none of them are guaranteed —
that's a real constraint of these platforms, not a limitation of this code.
The bot is built so each source is independently toggleable: turn on
whichever ones you're approved for, and it runs fully automated with just
those. See "Getting API access" below for how to apply to each.

The Telegram posting, deduplication, price-drop detection, scheduling, and
logging all work today with **zero approvals needed** — you can deploy the
whole pipeline immediately and switch sources on as approvals come through.

---

## How it works

```
GitHub Actions (cron, every 2 hours)
        │
        ▼
  main.py
        │
        ├─ AmazonSource        ─┐
        ├─ FlipkartSource       ├─► candidate deals
        ├─ GenericFeedSource   ─┘   (Myntra/Ajio/Meesho)
        │
        ▼
  filter: valid? min discount%? new or price-dropped? cap count
        │
        ▼
  TelegramPoster → sends photo + caption to @DailyVaultIN
        │
        ▼
  data/posted_deals.json, data/price_history.json
        │
        ▼
  workflow commits updated state back to the repo
```

---

## Project structure

```
telegram-deals-bot/
├── main.py                        # orchestrator / entry point
├── config.py                      # loads all settings from env vars
├── requirements.txt
├── .env.example                   # template for local testing
├── src/
│   ├── logger_setup.py
│   ├── dedup.py                   # duplicate + price-drop detection
│   ├── deal_filter.py
│   ├── telegram_poster.py
│   └── sources/
│       ├── base.py                # shared Deal data model
│       ├── amazon_paapi.py        # official Amazon PA-API 5.0
│       ├── flipkart_affiliate.py  # official Flipkart affiliate feeds
│       └── generic_feed.py        # Myntra/Ajio/Meesho via affiliate networks
├── data/
│   ├── posted_deals.json          # dedup state (auto-updated)
│   └── price_history.json         # price-drop state (auto-updated)
└── .github/workflows/deals_bot.yml
```

---

## Setup (one-time)

### 1. Create the Telegram bot

1. Open Telegram, message **@BotFather**, send `/newbot`, follow the prompts.
2. Copy the bot token it gives you (looks like `123456:ABC-...`).
3. Add the bot to **@DailyVaultIN** as an **administrator** with "Post
   Messages" permission.
4. Your channel ID is `@DailyVaultIN` if the channel is public. If it's
   private, get the numeric ID instead (message the bot in the channel once,
   then check `https://api.telegram.org/bot<TOKEN>/getUpdates`).

### 2. Fork/create this repository on GitHub

Push this project to a new GitHub repo (public or private — Actions free
tier covers both for personal accounts, within monthly minute limits).

### 3. Add GitHub Secrets

Go to **Repo → Settings → Secrets and variables → Actions → New repository
secret**, and add:

**Required:**
| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from BotFather |
| `TELEGRAM_CHANNEL_ID` | `@DailyVaultIN` or numeric ID |

**Optional (tune behaviour):**
| Secret name | Default | Meaning |
|---|---|---|
| `MIN_DISCOUNT_PERCENT` | `40` | Minimum discount % to post |
| `MAX_POSTS_PER_RUN` | `10` | Cap per run, prevents channel flooding |

**Optional (enable a source — leave blank/`false` to skip):**
See `.env.example` for the full list per source (`AMAZON_*`, `FLIPKART_*`,
`GENERIC_FEEDS_*`). Add each as its own GitHub Secret with the same name.

### 4. Enable the workflow

Go to the **Actions** tab of your repo → you should see "DailyVaultIN Deals
Bot" → click **Enable workflow** if prompted. It will now run automatically
every 2 hours (edit the cron line in `.github/workflows/deals_bot.yml` to
change frequency — GitHub Actions supports a minimum interval of 5 minutes,
but be mindful of your monthly Actions-minutes quota).

You can also trigger a manual run any time from **Actions → DailyVaultIN
Deals Bot → Run workflow**.

---

## Getting API access (do this in parallel, not before deploying)

### Amazon Associates + PA-API 5.0
1. Apply at [associates.amazon.in](https://affiliate-program.amazon.in/).
2. Approval is typically fast, but PA-API access requires **3 qualifying
   sales within 180 days** — Amazon can suspend API access without them.
3. Once approved, generate Access Key + Secret Key from the Associates
   dashboard, add them plus your Partner Tag as GitHub Secrets, set
   `AMAZON_ENABLED=true`.

### Flipkart Affiliate Program
1. Apply at [affiliate.flipkart.com](https://affiliate.flipkart.com/).
2. Once approved, their dashboard gives you category-wise **product feed
   URLs** (JSON) — this is not a generic search API, it's pre-built feeds
   per category. Copy the feed URLs you want into `FLIPKART_FEED_URLS`
   (comma-separated), set `FLIPKART_ENABLED=true`.
3. Flipkart's feed JSON schema can change; if `flipkart_affiliate.py`
   stops parsing correctly, check a sample feed response in your dashboard
   and adjust `_parse_item()` accordingly.

### Myntra / Ajio / Meesho (via an affiliate network)
These three don't offer a direct developer API. Pick **one** aggregator
network, apply, and use whatever feed export they give you:
- [EarnKaro](https://earnkaro.com) — publisher signup, free
- [INRDeals](https://inrdeals.com) — publisher signup, free
- [Cuelinks](https://cuelinks.com) — publisher signup, free
- [Admitad](https://www.admitad.com) — publisher signup, free

Once approved, they'll give you a deal feed (CSV or JSON export/API URL).
Configure it via `GENERIC_FEEDS_CONFIG` (see the JSON example in
`.env.example` and in `src/sources/generic_feed.py`) — map their field
names to `title`, `product_url`, `image_url`, `original_price`,
`discounted_price`, `product_id`. Set `GENERIC_FEEDS_ENABLED=true`.

---

## Local testing (optional)

```bash
git clone <your-repo-url>
cd telegram-deals-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with real values
python main.py
```

---

## Deploying and managing this from an Android phone

GitHub Actions runs entirely in GitHub's cloud — **your phone never runs
the bot**, it's only used to set up and manage the repo. You don't need
Termux or any local Python for the automation itself. Two ways to do the
one-time setup from Android:

**Option A — GitHub mobile app (easiest, no terminal)**
1. Install "GitHub" from the Play Store, sign in.
2. Create a new repo (or use the web version of GitHub in Chrome to upload
   this project's files the first time — the mobile app itself doesn't
   support file uploads well, so use `github.com` in your phone's browser,
   "Add file → Upload files", and drag in this whole project folder).
3. Go to Settings → Secrets and variables → Actions in the mobile browser
   (desktop-site mode helps) and add your secrets there.
4. Go to the Actions tab to confirm runs are succeeding.

**Option B — Termux (for git/CLI-comfortable users)**
```bash
pkg install git
git clone <your-repo-url>
cd telegram-deals-bot
# edit files with `nano` or Termux's file editor
git add . && git commit -m "update" && git push
```
Secrets still must be added via the GitHub website (mobile browser),
Termux/git has no access to Actions secrets management.

After the initial setup, everything runs unattended in GitHub's cloud —
no further phone/PC interaction needed.

---

## Limitations (please read)

- **Amazon/Flipkart require approval and ongoing qualifying activity** —
  this is Amazon's and Flipkart's policy, not something any code can bypass.
- **Myntra/Ajio/Meesho have no direct developer API** — coverage depends
  entirely on which affiliate network approves you and what merchants
  their feed actually includes.
- **GitHub Actions cron is best-effort**, not real-time — scheduled runs
  can be delayed by minutes during high load on GitHub's infrastructure.
- **State is stored in the git repo** (`data/*.json`), not a database —
  simple and free, but every bot run adds a commit, and very high deal
  volume would bloat repo history over time (mitigated by
  `prune_old_entries()`, which drops entries older than 60 days).
- **GitHub Actions free tier has monthly minute caps** (2,000 min/month for
  free personal accounts as of this writing) — verify current limits at
  [docs.github.com/actions](https://docs.github.com/actions), since GitHub
  can change these.
- **"Genuine" discount detection is only as good as the source data** — the
  bot trusts the MRP/price fields the API or feed reports; it doesn't
  independently verify a merchant's claimed MRP is real (no legitimate free
  data source lets you do that across platforms).
- Telegram's Bot API rate-limits messages; `MAX_POSTS_PER_RUN` and the
  2-second delay between posts in `main.py` keep the bot well under normal
  limits, but very high-frequency schedules could still hit them.

---

## Troubleshooting

- **Workflow fails at "Run deals bot" with "Missing required config"** →
  double check `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHANNEL_ID` secrets are set
  and spelled exactly as above.
- **Telegram posts fail with 403** → the bot isn't an admin of the channel,
  or lacks "Post Messages" permission.
- **No deals ever get posted** → check the Action's run log; if it says all
  sources are disabled, you haven't enabled/configured any source yet —
  that's expected until you've completed at least one affiliate approval.
- **Flipkart/generic feed parsing errors** → the feed's JSON/CSV schema
  from your affiliate dashboard may differ from what's assumed in
  `flipkart_affiliate.py` / `generic_feed.py`'s default field map — check a
  live sample from your dashboard and adjust `field_map` (for generic feeds)
  or `_parse_item()` (for Flipkart).

---

## License

Use and modify freely for your own channel.
