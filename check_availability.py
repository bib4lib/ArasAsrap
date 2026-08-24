"""
Checks THE FIZZ Utrecht student housing page for availability changes
and sends a Telegram message when the "fully booked" status changes.

Runs on a schedule via GitHub Actions (see .github/workflows/check-availability.yml).
Only does actual checking work Tue-Fri, 06:00-19:00 Europe/Amsterdam time;
outside that window it exits immediately without checking or notifying.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://www.the-fizz.com/en/student-accommodation/utrecht/"
STATE_FILE = Path("state.json")
FULLY_BOOKED_PHRASE = "fully booked"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Allowed checking window
ALLOWED_DAYS = {1, 2, 3, 4}  # Monday=0 ... Tuesday-Friday = 1,2,3,4
ALLOWED_START_HOUR = 6
ALLOWED_END_HOUR = 19


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
    return {"fully_booked": True}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_page_text() -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AvailabilityChecker/1.0)"}
    resp = requests.get(URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator=" ", strip=True).lower()


def send_telegram_message(text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars.", file=sys.stderr)
        sys.exit(1)
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        api_url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": False},
        timeout=15,
    )
    resp.raise_for_status()


def main() -> None:
    if not within_allowed_window():
        print("Outside allowed checking window (Tue-Fri, 06:00-19:00 Amsterdam). Skipping.")
        return

    state = load_state()
    page_text = fetch_page_text()
    currently_fully_booked = FULLY_BOOKED_PHRASE in page_text

    print(f"Fully booked right now: {currently_fully_booked}")

    was_fully_booked = state.get("fully_booked", True)

    if was_fully_booked and not currently_fully_booked:
        # Status flipped from booked -> available: notify!
        message = (
            "🎉 New availability at THE FIZZ Utrecht!\n\n"
            "The 'fully booked' notice is gone from the page — "
            "there may be a studio open now.\n\n"
            f"Check here: {URL}"
        )
        send_telegram_message(message)
        print("Notification sent.")
    else:
        print("No change since last check. No notification sent.")

    state["fully_booked"] = currently_fully_booked
    save_state(state)


if __name__ == "__main__":
    main()
