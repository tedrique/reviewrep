"""Notification dispatcher for email, Slack, Telegram."""
import requests
from typing import Dict
from app.database import get_notification_prefs
from app.email_service import send_email
from app.config import APP_URL


def _build_text(event: str, payload: Dict) -> str:
    biz = payload.get("business_name", "your business")
    rating = payload.get("rating")
    author = payload.get("author", "Customer")
    if event == "new_review":
        return f"New review for {biz}: {rating}★ from {author}. Approve a reply at {APP_URL}/dashboard"
    if event == "draft_ready":
        return f"AI draft ready for {biz}: {rating}★ from {author}. Approve at {APP_URL}/dashboard"
    if event == "approved":
        return f"Response approved for {biz}. See history at {APP_URL}/dashboard"
    return f"Update for {biz} — {event}"


def send_notifications(account_id: int, event: str, payload: Dict):
    prefs = get_notification_prefs(account_id)
    text = _build_text(event, payload)
    for pref in prefs:
        events = pref.get("events", "")
        if events and event not in events.split(","):
            continue
        channel = pref["channel"]
        target = pref["target"]
        try:
            if channel == "email":
                send_email(target, text, f"<p>{text}</p>")
            elif channel == "slack":
                requests.post(target, json={"text": text}, timeout=5)
            elif channel == "telegram":
                if "|" in target:
                    token, chat_id = target.split("|", 1)
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=5)
        except Exception as e:
            print(f"[notify] {channel} failed: {e}")
