from app.google_reviews import post_reply, refresh_access_token
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.database import db_connection, add_audit


def _do_publish(account_id: int, actor_user_id: int, response_id: int, refresh_token: str, access_token: str):
    with db_connection() as conn:
        row = conn.execute("""
            SELECT resp.*, r.google_review_id, r.business_id, b.google_location_id
            FROM responses resp
            JOIN reviews r ON resp.review_id = r.id
            JOIN businesses b ON r.business_id = b.id
            WHERE resp.id = ? AND b.user_id = ?
        """, (response_id, account_id)).fetchone()
    if not row or not row["google_review_id"] or not row["google_location_id"]:
        return

    token = access_token
    if refresh_token:
        new_token = refresh_access_token(refresh_token, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
        if new_token:
            token = new_token

    reply_text = row["edited_response"] or row["ai_response"]
    review_name = f"{row['google_location_id']}/reviews/{row['google_review_id']}"
    success = post_reply(token, review_name, reply_text)
    if success:
        with db_connection() as conn:
            conn.execute("UPDATE responses SET status='published' WHERE id=?", (response_id,))
        add_audit(account_id, actor_user_id, "response.publish", "response", response_id, "")


def publish_response_task_sync(account_id: int, actor_user_id: int, response_id: int, refresh_token: str, access_token: str):
    _do_publish(account_id, actor_user_id, response_id, refresh_token, access_token)
