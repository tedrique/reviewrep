from app.celery_app import celery_app
from app.ai_responder import generate_response
from app.config import ANTHROPIC_API_KEY
from app.database import db_connection, save_response, approve_response, add_audit
from app.notifications import send_notifications


@celery_app.task(bind=True, max_retries=1, default_retry_delay=2)
def generate_bulk_task(self, account_id: int, review_ids: list[int], auto_approve: bool = True):
    with db_connection() as conn:
        rows = conn.execute(
            """SELECT r.*, b.name as business_name, b.type as business_type, b.location, b.tone,
                      b.owner_name, b.auto_approve_high, b.banned_phrases, b.signoff_library, b.brand_facts
               FROM reviews r JOIN businesses b ON r.business_id=b.id
               WHERE r.id IN ({seq}) AND b.user_id=?""".format(seq=",".join("?"*len(review_ids))),
            (*review_ids, account_id)
        ).fetchall()

    for rev in rows:
        ai_response = generate_response(
            review_text=rev["text"],
            rating=rev["rating"],
            author=rev["author"],
            business_name=rev["business_name"],
            business_type=rev["business_type"],
            location=rev["location"],
            tone=rev["tone"],
            api_key=ANTHROPIC_API_KEY,
            owner_name=rev["owner_name"] or "",
            banned_phrases=rev["banned_phrases"] or "",
            signoff_library=rev["signoff_library"] or "",
            brand_facts=rev["brand_facts"] or "",
        )
        resp_id = save_response(rev["id"], ai_response)
        add_audit(account_id, account_id, "bulk.generate", "review", rev["id"], "")
        should_auto = auto_approve and (rev["auto_approve_high"] or rev["rating"] >= 4)
        if should_auto:
            approve_response(resp_id, ai_response)
            send_notifications(account_id, "approved", {
                "business_name": rev["business_name"],
                "rating": rev["rating"],
                "author": rev["author"],
            })
        else:
            send_notifications(account_id, "draft_ready", {
                "business_name": rev["business_name"],
                "rating": rev["rating"],
                "author": rev["author"],
            })
