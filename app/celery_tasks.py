from app.celery_app import celery_app
from app.notifications import send_notifications
from app.ai_responder import generate_response
from app.config import ANTHROPIC_API_KEY
from app.database import db_connection, save_response, approve_response, add_audit


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
                   b.auto_approve_high, b.banned_phrases, b.signoff_library, b.brand_facts
            FROM reviews r JOIN businesses b ON r.business_id = b.id
            WHERE r.id = ? AND b.user_id = ?
        """, (review_id, account_id)).fetchone()
    if not review:
        return

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
    )
    resp_id = save_response(review_id, ai_response)
    add_audit(account_id, account_id, "response.generate.worker", "review", review_id, "")

    if review["auto_approve_high"] and review["rating"] >= 4:
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
