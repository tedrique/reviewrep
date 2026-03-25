"""Weekly ROI digest task (BETA)."""
from datetime import datetime, timedelta
from app.celery_app import celery_app
from app.database import db_connection
from app.notifications import send_notifications


@celery_app.task(name="app.roi.weekly_digest")
def weekly_digest():
    """Send a lightweight weekly ROI/email/Slack digest per account (BETA)."""
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    prev = (datetime.utcnow() - timedelta(days=14)).isoformat()
    with db_connection() as conn:
        users = conn.execute("SELECT id FROM users").fetchall()
        for u in users:
            account_id = u["id"]
            stats = _compute_stats(conn, account_id, since, prev)
            if stats["total_reviews"] == 0:
                continue
            send_notifications(account_id, "roi_digest", stats)


def _compute_stats(conn, account_id: int, since_iso: str, prev_iso: str) -> dict:
    total_reviews = conn.execute("""
        SELECT COUNT(*) as c FROM reviews r
        JOIN businesses b ON r.business_id=b.id
        WHERE b.user_id=? AND r.created_at>=?
    """, (account_id, since_iso)).fetchone()["c"]
    approved = conn.execute("""
        SELECT COUNT(*) as c FROM responses resp
        JOIN reviews r ON resp.review_id=r.id
        JOIN businesses b ON r.business_id=b.id
        WHERE b.user_id=? AND resp.status='approved' AND resp.created_at>=?
    """, (account_id, since_iso)).fetchone()["c"]
    negatives_handled = conn.execute("""
        SELECT COUNT(*) as c FROM responses resp
        JOIN reviews r ON resp.review_id=r.id
        JOIN businesses b ON r.business_id=b.id
        WHERE b.user_id=? AND resp.status='approved' AND r.rating<=2 AND resp.created_at>=?
    """, (account_id, since_iso)).fetchone()["c"]
    rating_recent = conn.execute("""
        SELECT AVG(rating) as a FROM reviews r
        JOIN businesses b ON r.business_id=b.id
        WHERE b.user_id=? AND r.created_at>=?
    """, (account_id, since_iso)).fetchone()["a"]
    rating_prev = conn.execute("""
        SELECT AVG(rating) as a FROM reviews r
        JOIN businesses b ON r.business_id=b.id
        WHERE b.user_id=? AND r.created_at BETWEEN ? AND ?
    """, (account_id, prev_iso, since_iso)).fetchone()["a"]
    rating_delta = round(rating_recent - rating_prev, 2) if rating_recent and rating_prev else None
    # crude time saved: 3 min per approved response
    minutes_saved = approved * 3
    return {
        "total_reviews": total_reviews,
        "approved": approved,
        "negatives_handled": negatives_handled,
        "rating_delta": rating_delta,
        "minutes_saved": minutes_saved,
    }
