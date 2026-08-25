"""
Checks THE FIZZ Utrecht student housing page for availability changes
and sends a Telegram message when the "fully booked" status changes.

Runs on a schedule via GitHub Actions (see .github/workflows/check-availability.yml).
Only does actual checking work Tue-Fri, 06:00-19:00 Europe/Amsterdam time;
outside that window it exits immediately without checking or notifying.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://www.the-fizz.com/en/student-accommodation/utrecht/"
STATE_FILE = Path("state.json")
FULLY_BOOKED_PHRASE = "fully booked"
# Strongest signal: confirmed from THE FIZZ Leiden (a page that currently HAS
# availability) — real listings show "from €1,111.11/month" style pricing
# directly in the apartment cards. Utrecht's static reference pricing table
# (present regardless of availability) never uses "from €" or "/month", so
# this pattern is specific to genuinely bookable listings, not background noise.
PRICE_PATTERN = re.compile(r"from\s*€\s*[\d,.]+\s*/\s*month")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Allowed checking window
ALLOWED_DAYS = {0, 1, 2, 3, 4}  # Monday=0 ... Monday-Friday = 0,1,2,3,4
ALLOWED_START_HOUR = 0   # full day — release timing isn't confined to business hours
ALLOWED_END_HOUR = 24


def within_allowed_window() -> bool:
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    if now.weekday() not in ALLOWED_DAYS:
        return False
    if not (ALLOWED_START_HOUR <= now.hour < ALLOWED_END_HOUR):
        return False
    return True


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"available": False, "fully_booked": True}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_page_text() -> str:
    """Fetch and return the page's visible text, lowercased.
    Retries once if the first attempt fails (network blips, timeouts)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AvailabilityChecker/1.0)"}
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.get(URL, headers=headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            return soup.get_text(separator=" ", strip=True).lower()
        except requests.RequestException as exc:
            last_error = exc
            print(f"Fetch attempt {attempt + 1} failed: {exc}", file=sys.stderr)
    raise RuntimeError(f"Could not fetch page after retry: {last_error}")


def page_looks_valid(page_text: str) -> bool:
    """Sanity check that we actually got the real page, not an error page,
    CAPTCHA, or a structurally-changed version we can no longer read
    correctly. If these baseline words are missing, something's wrong."""
    expected_markers = ["utrecht", "student accommodation", "apartment"]
    return all(marker in page_text for marker in expected_markers)


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars.", file=sys.stderr)
        return False
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            api_url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": False},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"Failed to send Telegram message: {exc}", file=sys.stderr)
        return False


def main() -> None:
    if not within_allowed_window():
        print("Outside allowed checking window (Tue-Fri, 06:00-19:00 Amsterdam). Skipping.")
        return

    state = load_state()

    try:
        page_text = fetch_page_text()
    except RuntimeError as exc:
        # Fetch failed twice in a row. Don't touch state (avoid recording a
        # false "available"/"booked" reading), and let the run fail loudly
        # so it shows up as a red X in the Actions tab.
        print(f"Giving up this run: {exc}", file=sys.stderr)
        sys.exit(1)

    if not page_looks_valid(page_text):
        # The page loaded, but doesn't contain the text we'd expect on a
        # normal page load. Could mean the site changed its layout, blocked
        # the request, or served an error page. Alert once (throttled to
        # avoid spam) rather than silently mis-reading the state.
        already_alerted_today = state.get("last_broken_alert_date") == datetime.now(
            ZoneInfo("Europe/Amsterdam")
        ).strftime("%Y-%m-%d")
        if not already_alerted_today:
            send_telegram_message(
                "⚠️ Heads up: the Fizz Utrecht availability checker fetched "
                "the page but couldn't recognize its content. The site may "
                "have changed, or the request may have been blocked. "
                "The bot will keep retrying automatically, but you may want "
                "to check it manually in the meantime.\n\n"
                f"{URL}"
            )
            state["last_broken_alert_date"] = datetime.now(
                ZoneInfo("Europe/Amsterdam")
            ).strftime("%Y-%m-%d")
            save_state(state)
        print("Page content didn't pass the sanity check. Skipping this run.")
        return

    currently_fully_booked = FULLY_BOOKED_PHRASE in page_text
    price_found = bool(PRICE_PATTERN.search(page_text))
    # Available if EITHER: the "fully booked" notice is gone, OR a real
    # listing price ("from €.../month") appeared.
    currently_available = (not currently_fully_booked) or price_found

    print(f"Fully booked right now: {currently_fully_booked}")
    print(f"Real listing price pattern found: {price_found}")

    was_available = state.get("available", False)

    if currently_available and not was_available:
        # Status flipped from booked -> available: notify!
        if price_found:
            reason = "a real listing price ('from €.../month') appeared on the page"
        else:
            reason = "the 'fully booked' notice is gone from the page"
        message = (
            "🎉 New availability at THE FIZZ Utrecht!\n\n"
            f"Detected because {reason} — there may be a studio open now.\n\n"
            f"Check here: {URL}"
        )
        send_telegram_message(message)
        print("Notification sent.")
    else:
        print("No change since last check. No notification sent.")

    state["available"] = currently_available
    state["fully_booked"] = currently_fully_booked  # kept for backward compatibility
    save_state(state)


if __name__ == "__main__":
    main()
