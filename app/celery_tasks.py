from app.celery_app import celery_app
from app.notifications import send_notifications
from app.ai_responder import generate_response
from app.config import ANTHROPIC_API_KEY
from app.database import db_connection, save_response_with_flags, approve_response, add_audit, get_user, save_tags
from app.rules import parse_rule
from app.ai_responder import generate_response


@celery_app.task(bind=True, max_retries=2, default_retry_delay=2)
def send_notification(self, account_id: int, event: str, payload: dict):
    try:
        send_notifications(account_id, event, payload)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=1)
def generate_one(self, account_id: int, review_id: int):
    with db_connection() as conn:
        review = conn.execute("""
            SELECT r.*, b.name as business_name, b.type as business_type,
                   b.location, b.tone, b.owner_name, b.id as business_id,
                   b.auto_approve_high, b.banned_phrases, b.signoff_library, b.brand_facts,
                   b.brand_hours, b.brand_services, b.brand_geo, b.brand_usp, b.allowed_phrases,
                   b.auto_rule_1_2, b.auto_rule_3, b.auto_rule_4_5, b.quiet_hours
            FROM reviews r JOIN businesses b ON r.business_id = b.id
            WHERE r.id = ? AND b.user_id = ?
        """, (review_id, account_id)).fetchone()
    if not review:
        return

    user = get_user(account_id)
    plan = user.get("subscription_plan", "starter") if user else "starter"

    ai_response = generate_response(
        review_text=review["text"],
        rating=review["rating"],
        author=review["author"],
        business_name=review["business_name"],
        business_type=review["business_type"],
        location=review["location"],
        tone=review["tone"],
        api_key=ANTHROPIC_API_KEY,
        owner_name=review["owner_name"] or "",
        banned_phrases=review["banned_phrases"] or "",
        signoff_library=review["signoff_library"] or "",
        brand_facts=review["brand_facts"] or "",
        brand_hours=review["brand_hours"] or "",
        brand_services=review["brand_services"] or "",
        brand_geo=review["brand_geo"] or "",
        brand_usp=review["brand_usp"] or "",
        allowed_phrases=review["allowed_phrases"] or "",
    )
    # fact check
    missing_fact = 0
    lower_resp = ai_response.lower()
    if review["brand_usp"] and review["brand_usp"].lower() not in lower_resp:
        missing_fact = 1
    elif review["brand_facts"]:
        facts = [f.strip() for f in review["brand_facts"].splitlines() if f.strip()]
        if facts:
            present = any(f.lower() in lower_resp for f in facts)
            if not present:
                missing_fact = 1

    resp_id = save_response_with_flags(review_id, ai_response, missing_fact)

    # lightweight auto-tagging of root causes (for ROI/insights)
    tags = extract_tags(review["text"])
    save_tags(review_id, tags)

    add_audit(account_id, account_id, "response.generate.worker", "review", review_id, "")

    action = parse_rule(dict(review), review["rating"], plan)
    if action == "publish" or (review["auto_approve_high"] and review["rating"] >= 4):
        approve_response(resp_id, ai_response)
        send_notifications(account_id, "approved", {
            "business_name": review["business_name"],
            "rating": review["rating"],
            "author": review["author"],
        })
        add_audit(account_id, account_id, "response.auto_approve.worker", "response", resp_id, "")
    else:
        send_notifications(account_id, "draft_ready", {
            "business_name": review["business_name"],
            "rating": review["rating"],
            "author": review["author"],
        })


def extract_tags(text: str) -> list[str]:
    txt = (text or "").lower()
    buckets = {
        "service": ["service", "staff", "rude", "friendly", "attentive"],
        "speed": ["slow", "wait", "waiting", "delay", "delayed"],
        "price": ["price", "expensive", "cheap", "value", "overpriced"],
        "quality": ["quality", "cold", "stale", "burnt", "raw"],
        "cleanliness": ["clean", "dirty", "filthy"],
        "booking": ["booking", "reservation", "reserved"],
        "noise": ["noise", "noisy", "loud"],
        "ambience": ["ambience", "atmosphere"],
        "location": ["parking", "location"],
        "food": ["food", "meal", "dish", "pizza", "burger", "coffee"],
    }
    found = []
    for tag, kws in buckets.items():
        if any(k in txt for k in kws):
            found.append(tag)
    return list(dict.fromkeys(found))  # unique, keep order
