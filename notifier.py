"""
Desktop helper for the CROUS housing alert.

Runs in YOUR Windows session (a Windows service cannot show toasts or open windows),
watches latest_notification.json (written by scraper.py when new listings are found)
and, depending on the switches in settings.json (set from the web UI at /notify), does:

  * Windows toast          (setting "toast", on by default)
  * Auto-open in Chrome    (setting "autoopen", off by default)
      new Chrome window with tabs:  listing | Google Maps | messervices.etudiant.gouv.fr

The settings are re-read on every notification, so no restart is needed to change them.

Requires:  pip install winotify
"""
import json
import os
import shutil
import subprocess
import time
from urllib.parse import quote_plus

from winotify import Notification, audio

import settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTIFY_FILE = os.path.join(BASE_DIR, "latest_notification.json")

POLL_SECONDS = 3
MESSERVICES_URL = "https://messervices.etudiant.gouv.fr/"
DEFAULT_LINK = "https://trouverunlogement.lescrous.fr"
MAX_WINDOWS = 3  # at most this many new offers are opened automatically per notification


# ------------------------------------------------------------------- helpers
def read_notification():
    try:
        with open(NOTIFY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None  # file missing or being written


def maps_url(offer):
    """Google Maps search for the listing (title + the card's description, usually the address)."""
    query = " ".join(p for p in (offer.get("title", ""), offer.get("description", "")) if p).strip()
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)


def find_chrome():
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return shutil.which("chrome")


# ------------------------------------------------------------------- actions
def show_toast(data):
    offers = data.get("offers", [])
    first_link = offers[0]["link"] if offers else DEFAULT_LINK
    lines = [f'{o["title"]} - {o["price"]}' for o in offers[:3]]
    if len(offers) > 3:
        lines.append(f"... and {len(offers) - 3} more")

    toast = Notification(
        app_id="Logement CROUS",
        title=f'{data.get("new", len(offers))} new housing offer(s) ({data.get("total", "?")} available)',
        msg="\n".join(lines),
        duration="long",
        launch=first_link,
    )
    toast.set_audio(audio.Default, loop=False)
    toast.add_actions(label="Open listing", launch=first_link)
    toast.show()


def auto_open(data):
    """New Chrome window per new offer: listing | Google Maps (| messervices in the first one)."""
    chrome = find_chrome()
    if not chrome:
        return
    for i, offer in enumerate(data.get("offers", [])[:MAX_WINDOWS]):
        urls = [offer["link"], maps_url(offer)]
        if i == 0:
            urls.append(MESSERVICES_URL)
        subprocess.Popen([chrome, "--new-window", *urls])
        time.sleep(1.5)  # let each window appear before opening the next


def handle_notification(data):
    current = settings.load()
    if current["toast"]:
        try:
            show_toast(data)
        except Exception:
            pass  # never let one feature break the other
    if current["autoopen"]:
        try:
            auto_open(data)
        except Exception:
            pass


def beat():
    """Tell the web UI that the helper is alive."""
    try:
        with open(settings.HEARTBEAT_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def main():
    # Ignore whatever is already in the file at startup, so a reboot doesn't replay old alerts
    current = read_notification()
    last_id = current.get("id") if current else None

    while True:
        beat()
        data = read_notification()
        if data and data.get("id") != last_id:
            last_id = data.get("id")
            handle_notification(data)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
