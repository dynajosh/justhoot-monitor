#!/usr/bin/env python3
"""
Website change monitor -> Telegram alerts.

Checks a URL every 5 minutes and messages you on Telegram when the page's
content changes (visible text or referenced assets like scripts/images/CSS).

Env vars:
  TELEGRAM_BOT_TOKEN   token from @BotFather
  TELEGRAM_CHAT_ID     your chat id (see README steps)
  WATCH_URL            optional, default https://justhoot.fun/
  CHECK_INTERVAL       optional, seconds, default 300
  STATE_FILE           optional, default state.json

Usage:
  python monitor.py          # run forever, checking every CHECK_INTERVAL
  python monitor.py --once   # single check (for cron / GitHub Actions)
"""
import difflib
import hashlib
import html
import json
import os
import re
import sys
import time

import requests

URL = os.environ.get("WATCH_URL", "https://justhoot.fun/")
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
FAIL_ALERT_AFTER = 3  # consecutive failed checks before a "site down" alert

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SiteChangeMonitor/1.0)"}


def send(text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text[:4000],
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[telegram error] {e}", file=sys.stderr)


def normalize(raw: str) -> dict:
    """Reduce a page to visible text + asset references, ignoring noise."""
    assets = sorted(
        set(
            re.sub(r"\?.*$", "", m)
            for m in re.findall(
                r'(?:src|href)=["\']([^"\']+\.(?:js|css|png|jpe?g|gif|svg|webp|mp4)[^"\']*)["\']',
                raw,
                flags=re.I,
            )
        )
    )
    text = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    text = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return {"lines": lines, "assets": assets}


def fingerprint(page: dict) -> str:
    blob = json.dumps(page, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def describe_change(old: dict, new: dict) -> str:
    diff = list(
        difflib.unified_diff(
            old.get("lines", []), new["lines"], lineterm="", n=0
        )
    )
    changes = [d for d in diff if d[:1] in "+-" and not d.startswith(("+++", "---"))]
    parts = []
    if changes:
        parts.append("Text changes:\n" + "\n".join(changes[:25]))
    old_assets, new_assets = set(old.get("assets", [])), set(new["assets"])
    added, removed = new_assets - old_assets, old_assets - new_assets
    if added or removed:
        parts.append(f"Assets: +{len(added)} / -{len(removed)}")
    return "\n\n".join(parts) or "Page markup changed."


def check_once() -> None:
    state = load_state()
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        state["fails"] = state.get("fails", 0) + 1
        print(f"[fetch error] {e}", file=sys.stderr)
        if state["fails"] == FAIL_ALERT_AFTER:
            send(f"⚠️ {URL} has failed {FAIL_ALERT_AFTER} checks in a row.\n{e}")
        save_state(state)
        return

    if state.get("fails", 0) >= FAIL_ALERT_AFTER:
        send(f"✅ {URL} is reachable again.")
    state["fails"] = 0

    page = normalize(resp.text)
    fp = fingerprint(page)

    if "hash" not in state:
        send(f"👀 Now monitoring {URL}\nCurrently shows:\n" + "\n".join(page["lines"][:10]))
    elif fp != state["hash"]:
        send(f"🔔 {URL} changed!\n\n{describe_change(state.get('page', {}), page)}")

    state["hash"], state["page"] = fp, page
    save_state(state)
    print(f"[{time.strftime('%H:%M:%S')}] checked, hash={fp[:8]}")


if __name__ == "__main__":
    if "--once" in sys.argv:
        check_once()
    else:
        while True:
            check_once()
            time.sleep(INTERVAL)
