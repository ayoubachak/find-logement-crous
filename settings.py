"""Shared settings store (settings.json) used by app.py (web UI), notifier.py (desktop helper) and the scraper loop."""
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
HEARTBEAT_FILE = os.path.join(BASE_DIR, "helper.heartbeat")  # touched by notifier.py while it runs

DEFAULTS = {
    "toast": True,        # Windows pop-up when new housing appears
    "autoopen": False,    # new Chrome window: listing | Google Maps | messervices
    "random_wait": False, # randomize the delay between checks
    "wait_min": 30,       # seconds, used when random_wait is on
    "wait_max": 90,
}
BOOL_KEYS = ("toast", "autoopen", "random_wait")
INT_KEYS = ("wait_min", "wait_max")
MIN_WAIT = 2
MAX_WAIT = 3600


def _clean(data):
    """Clamp the wait range: MIN_WAIT <= wait_min <= wait_max <= MAX_WAIT."""
    lo = max(MIN_WAIT, min(MAX_WAIT, int(data["wait_min"])))
    hi = max(lo, min(MAX_WAIT, int(data["wait_max"])))
    data["wait_min"], data["wait_max"] = lo, hi
    return data


def load():
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        for key in BOOL_KEYS:
            if key in saved:
                data[key] = bool(saved[key])
        for key in INT_KEYS:
            if key in saved:
                try:
                    data[key] = int(saved[key])
                except (TypeError, ValueError):
                    pass
    except Exception:
        pass  # missing or unreadable file: use defaults
    return _clean(data)


def update(changes):
    """Apply changes (unknown keys ignored, numbers clamped), save, and return the new settings."""
    changes = changes or {}
    data = load()
    for key in BOOL_KEYS:
        if key in changes:
            data[key] = bool(changes[key])
    for key in INT_KEYS:
        if key in changes:
            try:
                data[key] = int(changes[key])
            except (TypeError, ValueError):
                pass
    data = _clean(data)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, SETTINGS_FILE)
    return data


def helper_running():
    """True if notifier.py has written its heartbeat in the last few seconds."""
    try:
        return time.time() - os.path.getmtime(HEARTBEAT_FILE) < 15
    except OSError:
        return False
